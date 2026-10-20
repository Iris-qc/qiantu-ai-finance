import { useCallback, useEffect, useState } from 'react'
import { downloadPdf } from '../api/client'
import { reportApi } from '../api/endpoints'
import type { ReportOut, ReportPeriodsOut } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import { Card, ConfirmDialog, Empty, ErrorBox, Field, Loading, Modal, Money } from '../components/ui'
import { formatDateTime } from '../utils/money'

const TYPE_LABEL: Record<string, string> = { monthly: '月报', semester: '学期报', annual: '年报' }

export default function Reports() {
  const { toast } = useToast()
  const [periods, setPeriods] = useState<ReportPeriodsOut | null>(null)
  const [reports, setReports] = useState<ReportOut[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [genOpen, setGenOpen] = useState(false)
  const [genType, setGenType] = useState<'monthly' | 'semester' | 'annual'>('monthly')
  const [genPeriod, setGenPeriod] = useState('')
  const [genBusy, setGenBusy] = useState(false)
  const [genErr, setGenErr] = useState('')

  const [current, setCurrent] = useState<ReportOut | null>(null)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [deleting, setDeleting] = useState<ReportOut | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    Promise.all([reportApi.periods(), reportApi.list()])
      .then(([p, r]) => {
        setPeriods(p)
        setReports(r.items)
      })
      .catch((e) => setError(e instanceof Error ? e.message : '加载报告失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function openGen() {
    setGenType('monthly')
    setGenPeriod(periods?.monthly[0] ?? '')
    setGenErr('')
    setGenOpen(true)
  }

  async function doGenerate() {
    setGenErr('')
    if (!genPeriod) {
      setGenErr('请选择报告周期')
      return
    }
    setGenBusy(true)
    try {
      let body: { report_type: 'monthly' | 'semester' | 'annual'; period_start?: string; period_end?: string }
      if (genType === 'monthly') body = { report_type: 'monthly', period_start: genPeriod }
      else if (genType === 'annual') body = { report_type: 'annual', period_start: genPeriod }
      else {
        const sem = periods?.semesters.find((s) => s.label === genPeriod)
        body = { report_type: 'semester', period_start: sem?.start, period_end: sem?.end }
      }
      const rep = await reportApi.generate(body)
      toast('报告已生成', 'success')
      setGenOpen(false)
      setCurrent(rep)
      load()
    } catch (err) {
      setGenErr(isApiError(err) ? err.message : '生成失败，请稍后重试')
    } finally {
      setGenBusy(false)
    }
  }

  async function doDownload(rep: ReportOut) {
    setPdfBusy(true)
    try {
      await downloadPdf(`/reports/${rep.id}/pdf`, `${rep.report_type}_${rep.period_start}_${rep.period_end}.pdf`)
      toast('PDF 已下载', 'success')
      load()
    } catch (err) {
      toast(isApiError(err) ? err.message : 'PDF 下载失败', 'error')
    } finally {
      setPdfBusy(false)
    }
  }

  async function doDelete() {
    if (!deleting) return
    try {
      await reportApi.remove(deleting.id)
      toast('报告已删除', 'success')
      if (current?.id === deleting.id) setCurrent(null)
      setDeleting(null)
      load()
    } catch (err) {
      toast(isApiError(err) ? err.message : '删除失败', 'error')
    }
  }

  const c = current?.content

  return (
    <div>
      <div className="flex-between mb16">
        <p className="muted">生成月度 / 学期 / 年度消费报告，可在网页查看并导出 PDF</p>
        <button className="btn btn-primary" onClick={openGen}>＋ 生成报告</button>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> : (
        <>
          {/* 当前查看的报告 */}
          {current && c && (
            <Card title={current.title} extra={
              <div className="flex gap8">
                <button className="btn btn-outline btn-sm" disabled={pdfBusy}
                        onClick={() => void doDownload(current)}>
                  {pdfBusy ? '导出中…' : '⬇ 导出 PDF'}
                </button>
                <button className="btn-inline danger" onClick={() => setCurrent(null)}>关闭</button>
              </div>
            }>
              <div className="report-preview">
                <p>
                  统计周期：<span className="strong">{c.summary.period_label}</span>
                  （{c.summary.period_start} ~ {c.summary.period_end}）· 生成时间 {formatDateTime(c.generated_at)}
                </p>
                <h3>一、消费总览</h3>
                <p>
                  总支出 <span className="strong money-out"><Money cents={c.summary.expense_cents} /></span>；
                  总收入 <span className="strong money-in"><Money cents={c.summary.income_cents} /></span>；
                  结余 <Money cents={c.summary.net_cents} />；账单 {c.summary.bill_count} 笔；
                  日均支出约 ¥{(c.summary.avg_daily_cents / 100).toFixed(2)}。
                </p>
                {c.summary.top_category && <p>最大支出类别：{c.summary.top_category}。</p>}
                {c.summary.max_day && (
                  <p>单日最高支出：{c.summary.max_day.day}，¥{(c.summary.max_day.amount_cents / 100).toFixed(2)}。</p>
                )}
                <p className="small muted">报告生成时当前资产：¥{(c.summary.current_assets_cents / 100).toFixed(2)}</p>

                <h3>二、分类消费</h3>
                {c.categories.length === 0 ? <p>该周期内没有支出记录。</p> : (
                  <table>
                    <thead><tr><th>分类</th><th>金额（元）</th><th>占比</th></tr></thead>
                    <tbody>
                      {c.categories.map((row) => (
                        <tr key={row.category_name}>
                          <td>{row.category_name}</td>
                          <td>{(row.amount_cents / 100).toFixed(2)}</td>
                          <td>{row.percent}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <h3>三、预算执行</h3>
                {c.budget ? (
                  <p>
                    区间总预算 ¥{(c.budget.total_cents / 100).toFixed(2)}，实际支出 ¥{(c.budget.spent_cents / 100).toFixed(2)}，
                    使用率 {c.budget.usage_percent}%
                    （{c.budget.status === 'exceeded' ? '已超支' : c.budget.status === 'approaching' ? '接近上限' : '正常'}）。
                  </p>
                ) : <p>该周期内未设置预算。</p>}

                <h3>四、异常消费</h3>
                {c.anomalies.length === 0 ? <p>该周期内未发现异常消费。</p> : (
                  <ul>
                    {c.anomalies.map((a) => (
                      <li key={a.bill_id}>
                        {a.occurred_at} {a.category_name} ¥{(a.amount_cents / 100).toFixed(2)}
                        {a.note ? `（${a.note}）` : ''}
                      </li>
                    ))}
                  </ul>
                )}

                <h3>五、储蓄目标</h3>
                {c.goals.length === 0 ? <p>未设置储蓄目标。</p> : (
                  <ul>
                    {c.goals.map((g) => (
                      <li key={g.name}>
                        {g.name}：¥{(g.current_cents / 100).toFixed(2)} / ¥{(g.target_cents / 100).toFixed(2)}
                        （{g.progress_percent}%），截止 {g.deadline}
                      </li>
                    ))}
                  </ul>
                )}

                <h3>六、建议</h3>
                {c.advice.split('\n').map((line, i) => <p key={i}>{line}</p>)}
                <p className="small muted">本报告由大学生智能财务管理平台生成，仅供个人理财参考。</p>
              </div>
            </Card>
          )}

          {/* 历史报告列表 */}
          <Card title="历史报告">
            {!reports || reports.length === 0 ? (
              <Empty text="还没有生成过报告，点击上方「生成报告」开始" />
            ) : (
              <div className="list">
                {reports.map((r) => (
                  <div key={r.id} className="bill-row">
                    <div className="bill-icon adj">📄</div>
                    <div className="bill-main">
                      <div className="bill-name">
                        {r.title}
                        <span className="badge badge-muted" style={{ marginLeft: 8 }}>{TYPE_LABEL[r.report_type] ?? r.report_type}</span>
                      </div>
                      <div className="bill-sub">{formatDateTime(r.created_at)}{r.has_pdf ? ' · PDF 已生成' : ''}</div>
                    </div>
                    <div className="bill-actions">
                      <button className="btn-inline" onClick={() => setCurrent(r)}>查看</button>
                      <button className="btn-inline" disabled={pdfBusy}
                              onClick={() => void doDownload(r)}>PDF</button>
                      <button className="btn-inline danger" onClick={() => setDeleting(r)}>删除</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {/* 生成弹窗 */}
      <Modal open={genOpen} title="生成消费报告" onClose={() => setGenOpen(false)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setGenOpen(false)} disabled={genBusy}>取消</button>
            <button className="btn btn-primary" onClick={() => void doGenerate()} disabled={genBusy}>
              {genBusy ? '生成中…' : '生成'}
            </button>
          </>
        }>
        <Field label="报告类型" required>
          <div className="flex gap8">
            {(['monthly', 'semester', 'annual'] as const).map((t) => (
              <button key={t} className={`chip ${genType === t ? 'active' : ''}`}
                      onClick={() => {
                        setGenType(t)
                        setGenPeriod(t === 'monthly' ? (periods?.monthly[0] ?? '')
                          : t === 'annual' ? (periods?.years[0] ?? '')
                          : (periods?.semesters[0]?.label ?? ''))
                      }}>
                {TYPE_LABEL[t]}
              </button>
            ))}
          </div>
        </Field>
        <Field label="报告周期" required>
          <select className="select" value={genPeriod} onChange={(e) => setGenPeriod(e.target.value)}>
            {genType === 'monthly' && (periods?.monthly ?? []).map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
            {genType === 'annual' && (periods?.years ?? []).map((y) => (
              <option key={y} value={y}>{y} 年</option>
            ))}
            {genType === 'semester' && (periods?.semesters ?? []).map((s) => (
              <option key={s.label} value={s.label}>{s.label}（{s.start} ~ {s.end}）</option>
            ))}
          </select>
        </Field>
        <p className="form-hint">
          周期规则：月报按自然月；学期报按可配置的学年学期（默认秋季 09-01~次年 01-20、春季 02-20~07-10）；年报按自然年。
        </p>
        {genErr && <div className="form-error">{genErr}</div>}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="删除报告"
        text={deleting ? `确定删除「${deleting.title}」吗？对应 PDF 文件将一并删除。` : ''}
        danger
        onConfirm={() => void doDelete()}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
