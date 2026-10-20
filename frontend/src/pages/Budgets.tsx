import { useCallback, useEffect, useMemo, useState } from 'react'
import { budgetApi, categoryApi } from '../api/endpoints'
import type { BudgetOverviewOut, CategoryOut } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import { Card, ConfirmDialog, Empty, ErrorBox, Field, Loading, Modal, Money, ProgressBar } from '../components/ui'
import { thisMonth } from '../utils/money'
import { monthLabel, shiftMonth } from '../utils/date'

interface SetForm {
  scope: 'total' | 'category'
  category_id: number | null
  category_name: string
  amount: string
  threshold: string
}

const RISK_TONE: Record<string, string> = {
  none: 'badge-success', potential: 'badge-warning', high: 'badge-danger', no_budget: 'badge-muted',
}

export default function Budgets() {
  const { toast } = useToast()
  const [month, setMonth] = useState(thisMonth())
  const [overview, setOverview] = useState<BudgetOverviewOut | null>(null)
  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState<SetForm>({ scope: 'total', category_id: null, category_name: '', amount: '', threshold: '80' })
  const [formErr, setFormErr] = useState('')
  const [formBusy, setFormBusy] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [deleteName, setDeleteName] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    budgetApi.overview(month)
      .then(setOverview)
      .catch((e) => setError(e instanceof Error ? e.message : '加载预算失败'))
      .finally(() => setLoading(false))
  }, [month])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    categoryApi.list().then(setCategories).catch(() => setCategories([]))
  }, [])

  const expCats = useMemo(() => categories.filter((c) => c.kind === 'expense'), [categories])
  const totalBudget = overview?.items.find((b) => b.scope === 'total')
  const catBudgets = overview?.items.filter((b) => b.scope === 'category') ?? []

  function openSet(scope: 'total' | 'category', cat?: CategoryOut) {
    setForm({
      scope,
      category_id: cat?.id ?? null,
      category_name: cat?.name ?? '',
      amount: '',
      threshold: '80',
    })
    setFormErr('')
    setFormOpen(true)
  }

  async function submitSet() {
    setFormErr('')
    const amount = Number(form.amount)
    if (!/^\d+(\.\d{1,2})?$/.test(form.amount) || !Number.isFinite(amount) || amount <= 0) {
      setFormErr('请输入正确的预算金额（元，大于 0）')
      return
    }
    const threshold = parseInt(form.threshold, 10)
    if (Number.isNaN(threshold) || threshold < 50 || threshold > 100) {
      setFormErr('预警阈值需在 50-100 之间')
      return
    }
    setFormBusy(true)
    try {
      await budgetApi.upsert({
        month,
        scope: form.scope,
        category_id: form.scope === 'category' ? form.category_id : null,
        amount_cents: Math.round(amount * 100),
        threshold_percent: threshold,
      })
      toast('预算已保存', 'success')
      setFormOpen(false)
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
      load()
    } catch (err) {
      setFormErr(isApiError(err) ? err.message : '保存失败，请稍后重试')
    } finally {
      setFormBusy(false)
    }
  }

  async function doDelete() {
    if (deleting === null) return
    try {
      await budgetApi.remove(deleting)
      toast('预算已删除', 'success')
      setDeleting(null)
      load()
    } catch (err) {
      toast(isApiError(err) ? err.message : '删除失败', 'error')
    }
  }

  const f = overview?.forecast

  return (
    <div>
      <div className="flex-between mb16">
        <h2 className="card-title" style={{ fontSize: 16 }}>{monthLabel(month)}预算</h2>
        <div className="flex gap8">
          <button className="btn btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, -1))}>◀ 上月</button>
          {month !== thisMonth() && (
            <button className="btn btn-outline btn-sm" onClick={() => setMonth(thisMonth())}>本月</button>
          )}
          <button className="btn btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, 1))}>下月 ▶</button>
        </div>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> : (
        <>
          {/* 总预算 */}
          <Card title="月度总预算" extra={totalBudget ? (
            <button className="btn-inline" onClick={() => openSet('total')}>修改</button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={() => openSet('total')}>设置总预算</button>
          )}>
            {totalBudget ? (
              <>
                <div className="flex-between mb8">
                  <span className="muted">已用 <Money cents={totalBudget.spent_cents} /> / <Money cents={totalBudget.amount_cents} /></span>
                  <span className={`badge ${totalBudget.status === 'exceeded' ? 'badge-danger' : totalBudget.status === 'approaching' ? 'badge-warning' : 'badge-success'}`}>
                    {totalBudget.usage_percent}%（预警线 {totalBudget.threshold_percent}%）
                  </span>
                </div>
                <ProgressBar percent={totalBudget.usage_percent} status={totalBudget.status} height={10} />
              </>
            ) : (
              <Empty text="本月未设置总预算">
                <button className="btn btn-primary btn-sm" onClick={() => openSet('total')}>立即设置</button>
              </Empty>
            )}
          </Card>

          {/* 月底预测 */}
          {f && (
            <Card title="月底超支预测">
              <div className="grid grid-2">
                <div>
                  <div className="muted small">已过 {f.days_elapsed} / {f.days_total} 天，日均支出 ¥{(f.avg_daily_cents / 100).toFixed(2)}</div>
                  <div className="muted small mt8">预计月底总支出 <span className="strong">¥{(f.predicted_cents / 100).toFixed(2)}</span></div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className={`badge ${RISK_TONE[f.risk] ?? 'badge-muted'}`}>{f.risk_label}</span>
                  <div className="small muted mt8">
                    {f.budget_cents !== null
                      ? `预算 ¥${(f.budget_cents / 100).toFixed(2)}`
                      : '未设置总预算，无法对比'}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* 分类预算 */}
          <Card title="分类预算">
            {expCats.length === 0 ? (
              <Empty text="暂无支出分类" />
            ) : (
              <div className="list">
                {expCats.map((c) => {
                  const b = catBudgets.find((x) => x.category_id === c.id)
                  return (
                    <div key={c.id} className="bill-row">
                      <div className="bill-icon out">{c.name.slice(0, 1)}</div>
                      <div className="bill-main">
                        <div className="flex-between">
                          <span className="strong">{c.name}</span>
                          {b && (
                            <span className={`badge ${b.status === 'exceeded' ? 'badge-danger' : b.status === 'approaching' ? 'badge-warning' : 'badge-success'}`}>
                              {b.usage_percent}%
                            </span>
                          )}
                        </div>
                        {b ? (
                          <>
                            <div className="mt8"><ProgressBar percent={b.usage_percent} status={b.status} height={6} /></div>
                            <div className="small muted mt8">已用 ¥{(b.spent_cents / 100).toFixed(2)} / ¥{(b.amount_cents / 100).toFixed(2)}</div>
                          </>
                        ) : (
                          <div className="small muted mt8">未设置预算</div>
                        )}
                      </div>
                      <div className="bill-actions">
                        <button className="btn-inline" onClick={() => openSet('category', c)}>{b ? '修改' : '设置'}</button>
                        {b && (
                          <button className="btn-inline danger" onClick={() => { setDeleting(b.id); setDeleteName(c.name) }}>删除</button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </>
      )}

      {/* 设置预算弹窗 */}
      <Modal open={formOpen}
             title={`${form.scope === 'total' ? '月度总预算' : `「${form.category_name}」分类预算`}（${monthLabel(month)}）`}
             onClose={() => setFormOpen(false)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setFormOpen(false)} disabled={formBusy}>取消</button>
            <button className="btn btn-primary" onClick={() => void submitSet()} disabled={formBusy}>
              {formBusy ? '保存中…' : '保存'}
            </button>
          </>
        }>
        <Field label="预算金额（元）" required>
          <input className="input" inputMode="decimal" value={form.amount}
                 onChange={(e) => setForm({ ...form, amount: e.target.value.replace(/[^\d.]/g, '') })}
                 placeholder="例如 1800" />
        </Field>
        <Field label="预警阈值（%）" hint="使用率达到该比例时发送预算提醒，可在 50-100 之间调整">
          <input className="input" type="number" min={50} max={100} value={form.threshold}
                 onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
        </Field>
        {formErr && <div className="form-error">{formErr}</div>}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="删除预算"
        text={`确定删除「${deleteName}」的预算吗？对应的预算提醒将同步清除。`}
        danger
        onConfirm={() => void doDelete()}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
