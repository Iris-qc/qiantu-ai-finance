"""演示模式 NL 解析器与金额工具单元测试。"""
import pytest

from app.core.money import cents_to_yuan, yuan_to_cents
from app.services.parsing import ParseFailure, parse_nl_demo


def test_money_roundtrip():
    assert yuan_to_cents("12.34") == 1234
    assert yuan_to_cents("0.01") == 1
    assert yuan_to_cents("100") == 10000
    assert yuan_to_cents(5) == 500
    with pytest.raises(ValueError):
        yuan_to_cents("1.234")
    with pytest.raises(ValueError):
        yuan_to_cents("abc")
    assert cents_to_yuan(1234) == "12.34"
    assert cents_to_yuan(-5) == "-0.05"


def test_parse_simple():
    items, unparsed = parse_nl_demo("今天奶茶18，打车25")
    assert len(items) == 2
    assert items[0]["amount_cents"] == 1800 and items[0]["category_name"] == "餐饮"
    assert items[1]["amount_cents"] == 2500 and items[1]["category_name"] == "交通"
    assert items[0]["occurred_at"].hour == 12  # "今天" 默认中午
    assert not unparsed


def test_parse_income():
    items, _ = parse_nl_demo("收到生活费2000元")
    assert len(items) == 1
    assert items[0]["bill_type"] == "income"
    assert items[0]["amount_cents"] == 200000
    assert items[0]["category_name"] == "生活费"


def test_parse_with_unit_and_decimal():
    items, _ = parse_nl_demo("昨天买书45.5元")
    assert items[0]["amount_cents"] == 4550
    assert items[0]["category_name"] == "学习"


def test_parse_garbage_raises():
    with pytest.raises(ParseFailure):
        parse_nl_demo("今天天气不错")
    with pytest.raises(ParseFailure):
        parse_nl_demo("买了牛奶，还买了个包")  # 没有金额，同样视为解析失败
