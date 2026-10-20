import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { analyticsApi, billApi, budgetApi, notificationApi } from '../api/endpoints'
import type { BudgetOverviewOut, ProfileOut, SummaryOut } from '../api/types'
import { useProfile } from '../auth/ProfileContext'
import { Card, DirectionMoney, Empty, ErrorBox, Loading, Money, ProgressBar, Stat } from '../components/ui'
import { formatDateTime, thisMonth, todayStr } from '../utils/money'
import { monthLabel } from '../utils/date'

export default function Dashboard() {
  const { profile, loading, error, refresh } = useProfile()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<SummaryOut | null>(null)
  const [budget, setBudget] = useState<BudgetOverviewOut | null>(null)
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof billApi.list>> | null>(null)
  const [unread, setUnread] = useState(0)
  const [listErr, setListErr] = useState('')

  useEffect(() => {
    const month = thisMonth()
    const start = `${month}-01`
    let cancelled = false
    Promise.all([
      analyticsApi.summary(start, todayStr()),
      budgetApi.overview(month),
      billApi.list({ page: 1, page_size: 5 }),
      notificationApi.list(),
    ])
      .then(([s, b, r, n]) => {
        if (cancelled) return
        setSummary(s)
        setBudget(b)
        setRecent(r)
        setUnread(n.unread_count)
      })
      .catch((e) => { if (!cancelled) setListErr(e instanceof Error ? e.message : '加载失败') })
    return () => { cancelled = true }
  }, [])

  if (loading) return <Loading />
  if (error) return <ErrorBox text={error} onRetry={() => void refresh()} />
  const p = profile as ProfileOut

  const totalBudget = budget?.items.find((b) => b.scope === 'total')
  const f = budget?.forecast

  return (
    <div>
      {/* 资产横幅 */}
      <section className="hero">
        <div className="hero-label">当前总资产（自动重算）</div>
        <div className="hero-value">¥{(p.current_assets_cents / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
        <div className="hero-grid">
          <div className="hero-item">
            <div className="l">距离下次生活费</div>
            <div className="v">{p.days_to_next_allowance} 天</div>
          </div>
          <div className="hero-item">
            <div className="l">发放日（每月 {p.allowance_day} 日）</div>
            <div className="v">{p.next_allowance_date}</div>
          </div>
          <div className="hero-item">
            <div className="l">建议每日支出</div>
            <div className="v">≤ ¥{(p.suggested_daily_cents / 100).toFixed(2)}</div>
          </div>
        </div>
      </section>

      {/* 快捷操作 */}
      <div className="flex gap8 wrap mb16">
        <button className="btn btn-primary" onClick={() => navigate('/bills?new=1')}>＋ 记一笔</button>
        <button className="btn btn-outline" onClick={() => navigate('/ai')}>🤖 AI 智能记账</button>
        <button className="btn btn-outline" onClick={() => navigate('/budgets')}>💰 预算管理</button>
        <button className="btn btn-outline" onClick={() => navigate('/reports')}>📄 生成报告</button>
        {unread > 0 && (
          <button className="btn btn-outline" onClick={() => navigate('/notifications')}>
            🔔 {unread} 条未读提醒
          </button>
        )}
      </div>

      {/* 本月收支 */}
      <div className="grid grid-2 mb16">
        <Stat label={`本月收入（${monthLabel(thisMonth())}）`} tone="in"
              value={summary ? <Money cents={summary.income_cents} /> : '—'}
              sub={summary && summary.prev_income_cents !== null && summary.prev_income_cents !== undefined
                ? `上期 ¥${(summary.prev_income_cents / 100).toFixed(2)}` : '上月数据不足或暂无'} />
        <Stat label="本月支出" tone="out"
              value={summary ? <Money cents={summary.expense_cents} /> : '—'}
              sub={summary && summary.prev_expense_cents !== null && summary.prev_expense_cents !== undefined
                ? `上期 ¥${(summary.prev_expense_cents / 100).toFixed(2)}` : '上月数据不足或暂无'} />
      </div>

      {/* 预算进度 */}
      <Card title="本月总预算" extra={<Link to="/budgets" className="small">预算管理 →</Link>}>
        {budget === null ? (
          <p className="muted small">加载中…</p>
        ) : totalBudget ? (
          <>
            <div className="flex-between mb8">
              <span className="muted">已用 <Money cents={totalBudget.spent_cents} /> / <Money cents={totalBudget.amount_cents} /></span>
              <span className={`badge ${totalBudget.status === 'exceeded' ? 'badge-danger' : totalBudget.status === 'approaching' ? 'badge-warning' : 'badge-success'}`}>
                {totalBudget.usage_percent}%
              </span>
            </div>
            <ProgressBar percent={totalBudget.usage_percent} status={totalBudget.status} height={10} />
            {f && (
              <p className="small muted mt8">
                月底预测：约 <span className="strong">¥{(f.predicted_cents / 100).toFixed(2)}</span>
                {' '}· 风险：<span className="strong">{f.risk_label}</span>
              </p>
            )}
          </>
        ) : (
          <div className="flex-between">
            <p className="muted small">本月还未设置总预算</p>
            <Link to="/budgets" className="btn btn-outline btn-sm">去设置</Link>
          </div>
        )}
      </Card>

      {/* 最近账单 */}
      <Card title="最近账单" extra={<Link to="/bills" className="small">全部账单 →</Link>}>
        {listErr ? (
          <ErrorBox text={listErr} onRetry={() => window.location.reload()} />
        ) : recent === null ? (
          <Loading />
        ) : recent.items.length === 0 ? (
          <Empty text="还没有账单，点击上方「记一笔」开始记账">
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/bills?new=1')}>记第一笔</button>
          </Empty>
        ) : (
          <div className="list">
            {recent.items.map((b) => (
              <div key={b.id} className="bill-row">
                <div className={`bill-icon ${b.bill_type}`}>
                  {b.bill_type === 'income' ? '💰' : b.bill_type === 'expense' ? '🛒' : '⚖️'}
                </div>
                <div className="bill-main">
                  <div className="bill-name">{b.category_name}</div>
                  <div className="bill-sub">{formatDateTime(b.occurred_at)}{b.note ? ` · ${b.note}` : ''}</div>
                </div>
                <DirectionMoney cents={b.amount_cents} type={b.bill_type} className="bill-amount" />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
