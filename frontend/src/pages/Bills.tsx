import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { billApi, categoryApi } from '../api/endpoints'
import type { BillListOut, BillOut, BillType, CategoryOut } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import {
  Card, ConfirmDialog, DirectionMoney, Empty, ErrorBox, Field, Loading, Modal,
} from '../components/ui'
import {
  formatDateTime, isoToLocalInput, localInputToIso, sanitizeYuanInput, yuanToCents,
} from '../utils/money'

interface FormState {
  bill_type: 'income' | 'expense'
  amount: string
  category_id: string
  occurred_at: string
  note: string
}

const EMPTY_FORM: FormState = { bill_type: 'expense', amount: '', category_id: '', occurred_at: '', note: '' }

function lastDayOfMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m, 0).getDate().toString().padStart(2, '0')
}

export default function Bills() {
  const [params, setParams] = useSearchParams()
  const { toast } = useToast()

  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [data, setData] = useState<BillListOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [typeFilter, setTypeFilter] = useState<string>(params.get('type') || '')
  const [monthFilter, setMonthFilter] = useState<string>('')
  const [catFilter, setCatFilter] = useState<string>('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<BillOut | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formErr, setFormErr] = useState('')
  const [formBusy, setFormBusy] = useState(false)
  const [deleting, setDeleting] = useState<BillOut | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)

  const loadCategories = useCallback(() => {
    categoryApi.list().then(setCategories).catch(() => setCategories([]))
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const q: Record<string, string | number> = { page, page_size: 10 }
    if (typeFilter) q.bill_type = typeFilter
    if (monthFilter) {
      q.start = `${monthFilter}-01`
      q.end = `${monthFilter}-${lastDayOfMonth(monthFilter)}`
    }
    if (catFilter) q.category_id = Number(catFilter)
    if (keyword.trim()) q.keyword = keyword.trim()
    billApi.list(q)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : '加载账单失败'))
      .finally(() => setLoading(false))
  }, [page, typeFilter, monthFilter, catFilter, keyword])

  useEffect(() => { loadCategories() }, [loadCategories])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    // 首页/快捷入口 ?new=1 直接打开记账弹窗
    if (params.get('new')) {
      openCreate()
      setParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  const expCats = useMemo(() => categories.filter((c) => c.kind === 'expense'), [categories])
  const incCats = useMemo(() => categories.filter((c) => c.kind === 'income'), [categories])
  const totalPages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormErr('')
    setFormOpen(true)
  }

  function openEdit(b: BillOut) {
    setEditing(b)
    setForm({
      bill_type: b.bill_type === 'adjustment' ? 'expense' : b.bill_type,
      amount: (b.amount_cents / 100).toString(),
      category_id: b.category_id ? String(b.category_id) : '',
      occurred_at: isoToLocalInput(b.occurred_at),
      note: b.note ?? '',
    })
    setFormErr('')
    setFormOpen(true)
  }

  async function submitForm(e: FormEvent) {
    e.preventDefault()
    setFormErr('')
    const cents = yuanToCents(form.amount)
    if (cents === null || cents <= 0) {
      setFormErr('请输入正确的金额（元，最多两位小数，大于 0）')
      return
    }
    const catId = Number(form.category_id)
    if (!catId) {
      setFormErr('请选择分类')
      return
    }
    const payload = {
      bill_type: form.bill_type,
      amount_cents: cents,
      category_id: catId,
      occurred_at: form.occurred_at ? localInputToIso(form.occurred_at) : null,
      note: form.note.trim() || null,
    }
    setFormBusy(true)
    try {
      if (editing) {
        await billApi.update(editing.id, payload)
        toast('账单已更新', 'success')
      } else {
        await billApi.create(payload)
        toast('记账成功', 'success')
      }
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
    if (!deleting) return
    setDeleteBusy(true)
    try {
      await billApi.remove(deleting.id)
      toast('账单已删除（资产与预算已联动重算）', 'success')
      setDeleting(null)
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
      load()
    } catch (err) {
      toast(isApiError(err) ? err.message : '删除失败', 'error')
    } finally {
      setDeleteBusy(false)
    }
  }

  function resetFilters() {
    setTypeFilter('')
    setMonthFilter('')
    setCatFilter('')
    setKeyword('')
    setPage(1)
  }

  const catOptions = typeFilter === 'income' ? incCats : typeFilter === 'expense' ? expCats : categories
  const formCatOptions = form.bill_type === 'income' ? incCats : expCats

  return (
    <div>
      {/* 筛选区 */}
      <Card>
        <div className="flex gap8 wrap mb8">
          <button className="btn btn-primary" onClick={openCreate}>＋ 记一笔</button>
          {(['', 'expense', 'income', 'adjustment'] as const).map((t) => (
            <button key={t} className={`chip ${typeFilter === t ? 'active' : ''}`}
                    onClick={() => { setTypeFilter(t); setPage(1) }}>
              {t === '' ? '全部' : t === 'expense' ? '支出' : t === 'income' ? '收入' : '校准'}
            </button>
          ))}
        </div>
        <div className="flex gap8 wrap">
          <input className="input" type="month" style={{ width: 150 }} value={monthFilter}
                 onChange={(e) => { setMonthFilter(e.target.value); setPage(1) }} aria-label="按月份筛选" />
          <select className="select" style={{ width: 140 }} value={catFilter}
                  onChange={(e) => { setCatFilter(e.target.value); setPage(1) }} aria-label="按分类筛选">
            <option value="">全部分类</option>
            {catOptions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input className="input" style={{ flex: 1, minWidth: 140 }} value={keyword}
                 placeholder="搜索分类或备注…"
                 onChange={(e) => { setKeyword(e.target.value); setPage(1) }} aria-label="搜索" />
        </div>
      </Card>

      {/* 列表 */}
      <Card title={`账单列表${data ? `（共 ${data.total} 笔）` : ''}`}>
        {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> :
          !data || data.items.length === 0 ? (
            <Empty text={typeFilter || monthFilter || catFilter || keyword ? '没有符合筛选条件的账单' : '还没有账单，点击「记一笔」开始记账'}>
              {(typeFilter || monthFilter || catFilter || keyword) && (
                <button className="btn btn-outline btn-sm" onClick={resetFilters}>清除筛选</button>
              )}
            </Empty>
          ) : (
            <>
              <div className="table-wrap desktop-only">
                <table className="table">
                  <thead>
                    <tr>
                      <th>时间</th><th>类型</th><th>分类</th><th>备注</th>
                      <th className="num">金额</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((b) => (
                      <tr key={b.id}>
                        <td className="small">{formatDateTime(b.occurred_at)}</td>
                        <td>
                          <span className={`badge ${b.bill_type === 'income' ? 'badge-success' : b.bill_type === 'expense' ? 'badge-danger' : 'badge-warning'}`}>
                            {b.bill_type === 'income' ? '收入' : b.bill_type === 'expense' ? '支出' : '校准'}
                          </span>
                        </td>
                        <td>{b.category_name}</td>
                        <td className="muted ellipsis" style={{ maxWidth: 180 }}>{b.note || '—'}</td>
                        <td className="num"><DirectionMoney cents={b.amount_cents} type={b.bill_type} /></td>
                        <td className="bill-actions">
                          {b.bill_type !== 'adjustment' && (
                            <button className="btn-inline" onClick={() => openEdit(b)}>编辑</button>
                          )}
                          <button className="btn-inline danger" onClick={() => setDeleting(b)}>删除</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* 移动端卡片式列表 */}
              <div className="list mobile-bills">
                {data.items.map((b) => (
                  <div key={b.id} className="bill-row">
                    <div className={`bill-icon ${b.bill_type}`}>
                      {b.bill_type === 'income' ? '💰' : b.bill_type === 'expense' ? '🛒' : '⚖️'}
                    </div>
                    <div className="bill-main">
                      <div className="bill-name">
                        {b.category_name}
                        {b.bill_type === 'adjustment' && <span className="badge badge-warning small" style={{ marginLeft: 6 }}>校准</span>}
                      </div>
                      <div className="bill-sub">{formatDateTime(b.occurred_at)}{b.note ? ` · ${b.note}` : ''}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <DirectionMoney cents={b.amount_cents} type={b.bill_type} className="bill-amount" />
                      <div className="flex gap8 mt8" style={{ justifyContent: 'flex-end' }}>
                        {b.bill_type !== 'adjustment' && (
                          <button className="btn-inline" onClick={() => openEdit(b)}>编辑</button>
                        )}
                        <button className="btn-inline danger" onClick={() => setDeleting(b)}>删除</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {/* 分页 */}
              <div className="flex-between mt16">
                <button className="btn btn-outline btn-sm" disabled={page <= 1}
                        onClick={() => setPage(page - 1)}>上一页</button>
                <span className="muted small">第 {data.page} / {totalPages} 页</span>
                <button className="btn btn-outline btn-sm" disabled={page >= totalPages}
                        onClick={() => setPage(page + 1)}>下一页</button>
              </div>
            </>
          )}
      </Card>

      {/* 记账/编辑弹窗 */}
      <Modal open={formOpen} title={editing ? '编辑账单' : '记一笔'} onClose={() => setFormOpen(false)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setFormOpen(false)} disabled={formBusy}>取消</button>
            <button className="btn btn-primary" onClick={submitForm} disabled={formBusy}>
              {formBusy ? '保存中…' : '保存'}
            </button>
          </>
        }>
        <div className="flex gap8 mb16">
          {(['expense', 'income'] as const).map((t) => (
            <button key={t} className={`chip ${form.bill_type === t ? 'active' : ''}`}
                    onClick={() => setForm({ ...form, bill_type: t, category_id: '' })}>
              {t === 'expense' ? '支出' : '收入'}
            </button>
          ))}
        </div>
        <Field label="金额（元）" required>
          <input className="input" inputMode="decimal" value={form.amount}
                 onChange={(e) => setForm({ ...form, amount: sanitizeYuanInput(e.target.value) })}
                 placeholder="例如 25.5" />
        </Field>
        <Field label="分类" required>
          <select className="select" value={form.category_id}
                  onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">请选择分类</option>
            {formCatOptions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="发生时间（留空为当前时间）">
          <input className="input" type="datetime-local" value={form.occurred_at}
                 onChange={(e) => setForm({ ...form, occurred_at: e.target.value })} />
        </Field>
        <Field label="备注（选填）">
          <input className="input" value={form.note} maxLength={200}
                 onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="最多 200 字" />
        </Field>
        {formErr && <div className="form-error">{formErr}</div>}
      </Modal>

      {/* 删除确认 */}
      <ConfirmDialog
        open={!!deleting}
        title="删除账单"
        text={deleting ? `确定删除「${deleting.category_name}」¥${(deleting.amount_cents / 100).toFixed(2)} 这笔账单吗？删除后资产与预算将自动重算。` : ''}
        danger
        busy={deleteBusy}
        onConfirm={() => void doDelete()}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
