import { useCallback, useEffect, useMemo, useState } from 'react'
import type { EChartsOption } from 'echarts'
import { analyticsApi } from '../api/endpoints'
import type { CategoryStatsOut, SummaryOut, TrendOut } from '../api/types'
import Chart from '../components/Chart'
import type { VizInk } from '../components/Chart'
import { Card, Empty, ErrorBox, Loading, Money, Stat } from '../components/ui'
import { thisMonth, todayStr } from '../utils/money'
import { monthLabel } from '../utils/date'

type Granularity = 'day' | 'week' | 'month'

function lastDayOfMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m, 0).getDate().toString().padStart(2, '0')
}

function fmtYuanShort(v: number): string {
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`
  return `${v}`
}

/** 不同粒度的统计窗口 */
function computeWindow(g: Granularity, month: string): { start: string; end: string } {
  const today = todayStr()
  if (g === 'day') return { start: `${month}-01`, end: `${month}-${lastDayOfMonth(month)}` }
  if (g === 'week') {
    const d = new Date(today)
    d.setDate(d.getDate() - 83) // 最近 12 周
    return { start: d.toISOString().slice(0, 10), end: today }
  }
  const y = Number(today.slice(0, 4))
  const m = Number(today.slice(5, 7))
  const d = new Date(y, m - 12, 1) // 最近 12 个月
  const p = (n: number) => n.toString().padStart(2, '0')
  return { start: `${d.getFullYear()}-${p(d.getMonth() + 1)}-01`, end: today }
}

const GRAN_LABEL: Record<Granularity, string> = { day: '日', week: '周', month: '月' }

export default function Analytics() {
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [month, setMonth] = useState(thisMonth())
  const [trend, setTrend] = useState<TrendOut | null>(null)
  const [cats, setCats] = useState<CategoryStatsOut | null>(null)
  const [summary, setSummary] = useState<SummaryOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [trendView, setTrendView] = useState<'chart' | 'table'>('chart')
  const [catView, setCatView] = useState<'chart' | 'table'>('chart')

  const window = useMemo(() => computeWindow(granularity, month), [granularity, month])

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    Promise.all([
      analyticsApi.trend(granularity, window.start, window.end),
      analyticsApi.categories(window.start, window.end),
      analyticsApi.summary(window.start, window.end),
    ])
      .then(([t, c, s]) => {
        setTrend(t)
        setCats(c)
        setSummary(s)
      })
      .catch((e) => setError(e instanceof Error ? e.message : '加载分析数据失败'))
      .finally(() => setLoading(false))
  }, [granularity, window.start, window.end])

  useEffect(() => { load() }, [load])

  function trendOption(c: VizInk): EChartsOption {
    const points = trend?.points ?? []
    const sparse = granularity === 'day' // 点多时不显示符号，避免拥挤
    const yuan = (cents: number) => Number((cents / 100).toFixed(2))
    const incomeData = points.map((p) => yuan(p.income_cents))
    const expenseData = points.map((p) => yuan(p.expense_cents))
    return {
      backgroundColor: 'transparent',
      legend: {
        top: 0, right: 0, itemWidth: 12, itemHeight: 4, icon: 'roundRect',
        textStyle: { color: c.ink2, fontSize: 12 },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: c.baseline }, crossStyle: { color: c.baseline } },
        backgroundColor: '#1f2937',
        borderWidth: 0,
        textStyle: { color: '#fff', fontSize: 12 },
        valueFormatter: (v: unknown) => `¥${Number(v ?? 0).toFixed(2)}`,
      },
      grid: { left: 8, right: 16, top: 36, bottom: 4, containLabel: true },
      xAxis: {
        type: 'category', data: points.map((p) => p.label), boundaryGap: false,
        axisLine: { lineStyle: { color: c.baseline } }, axisTick: { show: false },
        axisLabel: { color: c.muted, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: c.muted, fontSize: 11, formatter: (v: number) => fmtYuanShort(v) },
        splitLine: { lineStyle: { color: c.grid } },
      },
      series: [
        {
          name: '收入', type: 'line', data: incomeData,
          lineStyle: { width: 2, color: c.income }, itemStyle: { color: c.income },
          showSymbol: !sparse, symbol: 'circle', symbolSize: sparse ? 0 : 8,
          emphasis: { focus: 'series' },
          markPoint: sparse && points.length > 0 ? {
            data: [{ name: '最高', type: 'max', label: { color: c.ink, fontSize: 11, formatter: (p: any) => `¥${Number(p.value ?? 0).toFixed(0)}` } }],
            symbolSize: 8, itemStyle: { color: c.income },
          } : undefined,
        },
        {
          name: '支出', type: 'line', data: expenseData,
          lineStyle: { width: 2, color: c.expense }, itemStyle: { color: c.expense },
          showSymbol: !sparse, symbol: 'circle', symbolSize: sparse ? 0 : 8,
          emphasis: { focus: 'series' },
          markPoint: sparse && points.length > 0 ? {
            data: [{ name: '最高', type: 'max', label: { color: c.ink, fontSize: 11, formatter: (p: any) => `¥${Number(p.value ?? 0).toFixed(0)}` } }],
            symbolSize: 8, itemStyle: { color: c.expense },
          } : undefined,
        },
      ],
    }
  }

  function barsOption(c: VizInk): EChartsOption {
    // 水平条形图：按金额升序（自上而下递增），单色蓝，末端直接标注数值
    const items = cats?.items ?? []
    const sorted = [...items].sort((a, b) => a.amount_cents - b.amount_cents)
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1f2937',
        borderWidth: 0,
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: (p: any) =>
          `${p.name}：¥${Number(p.value).toFixed(2)}（${sorted[p.dataIndex]?.percent ?? 0}%）`,
      },
      grid: { left: 8, right: 64, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: c.muted, fontSize: 11, formatter: (v: number) => fmtYuanShort(v) },
        splitLine: { lineStyle: { color: c.grid } },
      },
      yAxis: {
        type: 'category',
        data: sorted.map((i) => i.category_name),
        axisLine: { lineStyle: { color: c.baseline } }, axisTick: { show: false },
        axisLabel: { color: c.ink2, fontSize: 12 },
      },
      series: [{
        type: 'bar',
        data: sorted.map((i) => Number((i.amount_cents / 100).toFixed(2))),
        barWidth: 14,
        itemStyle: { color: c.bar, borderRadius: [0, 4, 4, 0] },
        label: {
          show: true, position: 'right', color: c.ink2, fontSize: 11,
          formatter: (p: any) => `¥${Number(p.value).toFixed(2)}`,
        },
      }],
    }
  }

  const windowLabel = granularity === 'day'
    ? monthLabel(month)
    : granularity === 'week' ? '最近 12 周' : '最近 12 个月'

  return (
    <div>
      {/* 控件：粒度 + 月份（仅日粒度可选月份） */}
      <Card>
        <div className="flex gap8 wrap flex-between">
          <div className="flex gap8">
            {(['day', 'week', 'month'] as const).map((g) => (
              <button key={g} className={`chip ${granularity === g ? 'active' : ''}`}
                      onClick={() => setGranularity(g)}>
                按{GRAN_LABEL[g]}
              </button>
            ))}
          </div>
          {granularity === 'day' && (
            <input className="input" type="month" style={{ width: 150 }} value={month}
                   onChange={(e) => setMonth(e.target.value)} aria-label="选择月份" />
          )}
        </div>
      </Card>

      {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> : (
        <>
          {/* 周期汇总（KPI 行，非图表） */}
          <div className="grid grid-4 mb16">
            <Stat label={`${windowLabel}收入`} tone="in"
                  value={summary ? <Money cents={summary.income_cents} /> : '—'}
                  sub={summary && (summary.prev_income_cents ?? 0) > 0
                    ? `上期 ¥${((summary.prev_income_cents ?? 0) / 100).toFixed(2)}` : undefined} />
            <Stat label="支出" tone="out"
                  value={summary ? <Money cents={summary.expense_cents} /> : '—'}
                  sub={summary && (summary.prev_expense_cents ?? 0) > 0
                    ? `上期 ¥${((summary.prev_expense_cents ?? 0) / 100).toFixed(2)}` : undefined} />
            <Stat label="结余"
                  value={summary ? <Money cents={summary.income_cents - summary.expense_cents} /> : '—'}
                  sub={summary ? `共 ${summary.bill_count} 笔` : undefined} />
            <Stat label="支出 Top 分类" value={summary?.top_category ?? '—'} />
          </div>

          {/* 收支趋势 */}
          <Card title={`收支趋势（${windowLabel}）`} extra={
            <div className="flex gap8">
              <button className={`chip ${trendView === 'chart' ? 'active' : ''}`} onClick={() => setTrendView('chart')}>图表</button>
              <button className={`chip ${trendView === 'table' ? 'active' : ''}`} onClick={() => setTrendView('table')}>数据表</button>
            </div>
          }>
            {!trend || trend.points.length === 0 ? (
              <Empty text="该时间段内还没有收支记录" />
            ) : trendView === 'chart' ? (
              <Chart build={trendOption} height={300} />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>时间</th><th className="num">收入</th><th className="num">支出</th></tr>
                  </thead>
                  <tbody>
                    {trend.points.map((p, i) => (
                      <tr key={i}>
                        <td>{p.label}</td>
                        <td className="num"><Money cents={p.income_cents} /></td>
                        <td className="num"><Money cents={p.expense_cents} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* 分类占比 */}
          <Card title={`支出分类排行（${windowLabel}）`} extra={
            <div className="flex gap8">
              <button className={`chip ${catView === 'chart' ? 'active' : ''}`} onClick={() => setCatView('chart')}>图表</button>
              <button className={`chip ${catView === 'table' ? 'active' : ''}`} onClick={() => setCatView('table')}>数据表</button>
            </div>
          }>
            {!cats || cats.items.length === 0 ? (
              <Empty text="该时间段内还没有支出记录" />
            ) : catView === 'chart' ? (
              <Chart build={barsOption} height={Math.max(220, cats.items.length * 38)} />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>分类</th><th className="num">金额</th><th className="num">占比</th></tr>
                  </thead>
                  <tbody>
                    {[...cats.items].sort((a, b) => b.amount_cents - a.amount_cents).map((i) => (
                      <tr key={i.category_name}>
                        <td>{i.category_name}</td>
                        <td className="num"><Money cents={i.amount_cents} /></td>
                        <td className="num">{i.percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
