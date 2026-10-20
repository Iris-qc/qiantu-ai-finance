"""初始化种子数据（幂等，可重复执行）。

- 内置分类（缺失时补齐）
- 演示账号 demo / Demo123456（邮箱 demo@csaifm.local），含：
  财务档案（初始资产 1200 元、生活费 2000 元/月、每月 1 日发放）
  近两个月的学生消费账单（收入：生活费；支出：餐饮/交通/学习/娱乐/网购/生活用品）
  当月总预算与分类预算、储蓄目标
- 通过正常业务路径触发预算提醒与异常消费提醒，便于演示提醒模块。

运行：python -m app.seed
"""
import random
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .core.security import hash_password
from .core.timeutil import app_tz, now
from .db.session import get_sessionmaker
from .models import Bill, Budget, Category, Goal, Notification, Profile, User
from .services import anomalies, budgets
from .services.parsing import BUILTIN_EXPENSE, BUILTIN_INCOME

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo123456"
DEMO_EMAIL = "demo@csaifm.local"


def ensure_builtins(db: Session) -> dict[str, Category]:
    cats: dict[str, Category] = {}
    for name in BUILTIN_EXPENSE + BUILTIN_INCOME:
        kind = "expense" if name in BUILTIN_EXPENSE else "income"
        c = db.execute(
            select(Category).where(Category.is_builtin.is_(True), Category.name == name)
        ).scalar_one_or_none()
        if c is None:
            c = Category(user_id=None, name=name, kind=kind, is_builtin=True)
            db.add(c)
            db.flush()
        cats[name] = c
    return cats


def seed_bills(db: Session, user: User, cats: dict[str, Category]) -> None:
    rng = random.Random(20261018)
    today = now().date()
    # 收入：近两个月每月 1 日发放生活费 2000 元（实际到账由收入账单记录）
    for back in (1, 0):
        d = (today.replace(day=1) - timedelta(days=back * 32)).replace(day=1)
        if d > today:
            continue
        occ = datetime(d.year, d.month, d.day, 9, 0, tzinfo=app_tz())
        db.add(Bill(user_id=user.id, bill_type="income", amount_cents=200000,
                    category_id=cats["生活费"].id, category_name="生活费",
                    occurred_at=occ, note="家里转的生活费", source="manual"))

    expense_pool = [
        ("餐饮", 800, 2500, ["食堂午饭", "食堂晚饭", "奶茶", "外卖", "早餐"]),
        ("交通", 200, 1500, ["地铁", "公交", "打车", "共享单车"]),
        ("学习", 500, 6000, ["打印资料", "买书", "文具", "网课"]),
        ("娱乐", 800, 8000, ["电影", "游戏", "和朋友唱歌"]),
        ("网购", 1200, 15000, ["淘宝买衣服", "拼多多日用品", "京东数码配件"]),
        ("生活用品", 500, 4000, ["洗发水", "纸巾", "洗衣液"]),
    ]
    for cat_name, low, high, notes in expense_pool:
        # 近 60 天每类 6-12 笔
        for _ in range(rng.randint(6, 12)):
            days_ago = rng.randint(0, 59)
            d = today - timedelta(days=days_ago)
            occ = datetime(d.year, d.month, d.day, rng.randint(8, 21), rng.randint(0, 59),
                           tzinfo=app_tz())
            db.add(Bill(user_id=user.id, bill_type="expense",
                        amount_cents=rng.randint(low, high),
                        category_id=cats[cat_name].id, category_name=cat_name,
                        occurred_at=occ, note=rng.choice(notes), source="manual"))

    # 一笔"明显的异常消费"：今天一笔大额网购，触发异常提醒演示
    db.add(Bill(user_id=user.id, bill_type="expense", amount_cents=49900,
                category_id=cats["网购"].id, category_name="网购",
                occurred_at=now(), note="耳机（较贵的一笔，触发异常提醒）", source="manual"))
    db.flush()

    # 按正常业务路径评估异常并同步预算提醒
    for b in db.execute(select(Bill).where(Bill.user_id == user.id)).scalars():
        anomalies.evaluate_bill(db, b)
    for back in range(3):
        m = (today.replace(day=1) - timedelta(days=back * 32)).replace(day=1)
        budgets.sync_budget_for_month(db, user.id, m)


def seed() -> None:
    db: Session = get_sessionmaker()()
    try:
        cats = ensure_builtins(db)
        db.commit()

        user = db.execute(select(User).where(User.username == DEMO_USERNAME)).scalar_one_or_none()
        if user is None:
            user = User(username=DEMO_USERNAME, password_hash=hash_password(DEMO_PASSWORD),
                        email=DEMO_EMAIL)
            db.add(user)
            db.flush()

        p = db.execute(select(Profile).where(Profile.user_id == user.id)).scalar_one_or_none()
        if p is None:
            p = Profile(user_id=user.id, initialized=True, initial_assets_cents=120000,
                        allowance_cents=200000, allowance_day=1)
            db.add(p)
            db.flush()

        if db.execute(select(func.count(Bill.id)).where(Bill.user_id == user.id)).scalar_one() == 0:
            seed_bills(db, user, cats)

        # 本月预算
        ms = now().date().replace(day=1)
        for scope, cat_name, amount, threshold in [
            ("total", None, 180000, 80),
            ("category", "餐饮", 90000, 80),
            ("category", "网购", 30000, 80),
            ("category", "娱乐", 20000, 80),
        ]:
            exists = db.execute(select(Budget).where(
                Budget.user_id == user.id, Budget.month_start == ms, Budget.scope == scope,
                Budget.category_id == (cats[cat_name].id if cat_name else None),
            )).scalar_one_or_none()
            if exists is None:
                db.add(Budget(user_id=user.id, month_start=ms, scope=scope,
                              category_id=cats[cat_name].id if cat_name else None,
                              category_name=cat_name, amount_cents=amount,
                              threshold_percent=threshold))
        db.flush()
        budgets.sync_budget_for_month(db, user.id, ms)

        if db.execute(select(func.count(Goal.id)).where(Goal.user_id == user.id)).scalar_one() == 0:
            db.add(Goal(user_id=user.id, name="攒钱买新电脑", target_cents=400000,
                        current_cents=150000, deadline=today_plus(150), note="想换一台 4000 元左右的笔记本"))
            db.add(Goal(user_id=user.id, name="暑假旅游基金", target_cents=200000,
                        current_cents=60000, deadline=today_plus(90), note="和室友去重庆"))

        db.commit()
        print(f"[seed] OK  演示账号：{DEMO_USERNAME} / {DEMO_PASSWORD}（邮箱 {DEMO_EMAIL}）")
    finally:
        db.close()


def today_plus(n: int):
    return now().date() + timedelta(days=n)


if __name__ == "__main__":
    seed()
