import { useCallback, useEffect, useState } from 'react'
import { goalApi } from '../api/endpoints'
import type { GoalOut } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import { Icon } from '../components/Icon'
import { Card, ConfirmDialog, Empty, ErrorBox, Field, Loading, Modal, ProgressBar } from '../components/ui'
import { centsToYuan, formatDate, sanitizeYuanInput, todayStr, yuanToCents } from '../utils/money'

const RISK_LABEL: Record<string, string> = {
  on_track: '按计划进行', tight: '进度偏紧', overdue: '已逾期', done: '已达成',
}
const RISK_BADGE: Record<string, string> = {
  on_track: 'badge-success', tight: 'badge-warning', overdue: 'badge-danger', done: 'badge-info',
}

interface GoalForm {
  name: string
  target: string
  current: string
  deadline: string
  note: string
}

const EMPTY_FORM: GoalForm = { name: '', target: '', current: '', deadline: todayStr(), note: '' }

export default function Goals() {
  const { toast } = useToast()
  const [goals, setGoals] = useState<GoalOut[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<GoalOut | null>(null)
  const [form, setForm] = useState<GoalForm>(EMPTY_FORM)
  const [formErr, setFormErr] = useState('')
  const [formBusy, setFormBusy] = useState(false)
  const [deleting, setDeleting] = useState<GoalOut | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    goalApi.list()
      .then((r) => setGoals(r.items))
      .catch((e) => setError(e instanceof Error ? e.message : '加载目标失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormErr('')
    setFormOpen(true)
  }

  function openEdit(g: GoalOut) {
    setEditing(g)
    setForm({
      name: g.name,
      target: (g.target_cents / 100).toString(),
      current: (g.current_cents / 100).toString(),
      deadline: g.deadline,
      note: g.note ?? '',
    })
    setFormErr('')
    setFormOpen(true)
  }

  async function submitForm() {
    setFormErr('')
    const target = yuanToCents(form.target)
    const current = yuanToCents(form.current)
    if (!form.name.trim()) { setFormErr('请输入目标名称'); return }
    if (target === null || target <= 0) { setFormErr('请输入正确的目标金额（元，大于 0）'); return }
    if (current === null || current < 0) { setFormErr('请输入正确的已存金额（元）'); return }
    if (!form.deadline) { setFormErr('请选择目标日期'); return }
    setFormBusy(true)
    try {
      const body = {
        name: form.name.trim(),
        target_cents: target,
        current_cents: current,
        deadline: form.deadline,
        note: form.note.trim() || undefined,
      }
      if (editing) await goalApi.update(editing.id, body)
      else await goalApi.create(body)
      toast(editing ? '目标已更新' : '目标已创建', 'success')
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
      await goalApi.remove(deleting.id)
      toast('目标已删除', 'success')
      setDeleting(null)
      load()
    } catch (err) {
      toast(isApiError(err) ? err.message : '删除失败', 'error')
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div>
      <div className="flex-between mb16">
        <p className="muted">设定储蓄目标，系统按剩余天数给出每日 / 每月建议储蓄额</p>
        <button className="btn btn-primary" onClick={openCreate}>
          <Icon name="plus" size={16} />
          新建目标
        </button>
      </div>

      {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> :
        !goals || goals.length === 0 ? (
          <Empty text="还没有储蓄目标">
            <button className="btn btn-primary btn-sm" onClick={openCreate}>创建第一个目标</button>
          </Empty>
        ) : (
          <div className="grid grid-2">
            {goals.map((g) => (
              <Card key={g.id} className="goal-card">
                <div className="flex-between">
                  <h2 className="card-title">
                    <span className="card-title-icon"><Icon name="target" size={16} /></span>
                    {g.name}
                  </h2>
                  <span className={`badge ${RISK_BADGE[g.risk] ?? 'badge-muted'}`}>
                    {RISK_LABEL[g.risk] ?? g.risk}
                  </span>
                </div>
                <div className="mb8 small muted">
                  目标 <span className="strong">¥{centsToYuan(g.target_cents)}</span>
                  {' · '}截止 {formatDate(g.deadline)}
                  {g.days_left >= 0 ? `（剩 ${g.days_left} 天）` : `（已超期 ${-g.days_left} 天）`}
                </div>
                <ProgressBar percent={g.progress_percent}
                             status={g.risk === 'overdue' ? 'exceeded' : g.risk === 'tight' ? 'approaching' : 'normal'}
                             height={10} />
                <div className="flex-between mt8">
                  <span className="muted small">已存 ¥{centsToYuan(g.current_cents)} / ¥{centsToYuan(g.target_cents)}（{g.progress_percent}%）</span>
                </div>
                <div className="grid grid-2 mt16">
                  <div className="small muted">还差 <span className="strong">¥{centsToYuan(g.remaining_cents)}</span></div>
                  <div className="small muted" style={{ textAlign: 'right' }}>
                    {g.risk === 'done'
                      ? <span className="badge badge-success"><Icon name="check-circle" size={13} />已达成</span>
                      : <>建议每日存 <span className="strong">¥{centsToYuan(g.suggested_daily_cents)}</span></>}
                  </div>
                </div>
                {g.note && <p className="small muted mt8">备注：{g.note}</p>}
                <div className="flex gap8 mt16" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn-inline" onClick={() => openEdit(g)}>
                    <Icon name="edit" size={13} />编辑
                  </button>
                  <button className="btn-inline danger" onClick={() => setDeleting(g)}>
                    <Icon name="trash" size={13} />删除
                  </button>
                </div>
              </Card>
            ))}
          </div>
        )}

      <Modal open={formOpen} title={editing ? '编辑储蓄目标' : '新建储蓄目标'} onClose={() => setFormOpen(false)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setFormOpen(false)} disabled={formBusy}>取消</button>
            <button className="btn btn-primary" onClick={() => void submitForm()} disabled={formBusy}>
              {formBusy ? '保存中…' : '保存'}
            </button>
          </>
        }>
        <Field label="目标名称" required>
          <input className="input" value={form.name} maxLength={50}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如 买电脑" />
        </Field>
        <Field label="目标金额（元）" required>
          <input className="input" inputMode="decimal" value={form.target}
                 onChange={(e) => setForm({ ...form, target: sanitizeYuanInput(e.target.value) })} placeholder="例如 5000" />
        </Field>
        <Field label="已存金额（元）">
          <input className="input" inputMode="decimal" value={form.current}
                 onChange={(e) => setForm({ ...form, current: sanitizeYuanInput(e.target.value) })} placeholder="例如 800" />
        </Field>
        <Field label="目标日期" required>
          <input className="input" type="date" value={form.deadline}
                 onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
        </Field>
        <Field label="备注（选填）">
          <input className="input" value={form.note} maxLength={200}
                 onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </Field>
        {formErr && <div className="form-error">{formErr}</div>}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="删除目标"
        text={deleting ? `确定删除储蓄目标「${deleting.name}」吗？` : ''}
        danger
        busy={deleteBusy}
        onConfirm={() => void doDelete()}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
