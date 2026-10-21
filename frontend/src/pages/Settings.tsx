import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useProfile } from '../auth/ProfileContext'
import { categoryApi, profileApi } from '../api/endpoints'
import type { CategoryOut } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import { Icon } from '../components/Icon'
import { Card, ConfirmDialog, ErrorBox, Field, Loading, Modal, Money } from '../components/ui'
import { sanitizeYuanInput, yuanToCents } from '../utils/money'
import { applyTheme, getStoredTheme } from '../utils/theme'
import type { ThemeMode } from '../utils/theme'

export default function Settings() {
  const { user, logout } = useAuth()
  const { profile, loading, error, refresh } = useProfile()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [categories, setCategories] = useState<CategoryOut[]>([])
  const [catBusy, setCatBusy] = useState(false)

  const [allowance, setAllowance] = useState('')
  const [allowanceDay, setAllowanceDay] = useState('1')
  const [allowanceBusy, setAllowanceBusy] = useState(false)

  const [email, setEmail] = useState('')
  const [emailBusy, setEmailBusy] = useState(false)

  const [calibOpen, setCalibOpen] = useState(false)
  const [calibValue, setCalibValue] = useState('')
  const [calibBusy, setCalibBusy] = useState(false)
  const [calibErr, setCalibErr] = useState('')

  // 分类弹窗
  const [catModal, setCatModal] = useState<null | { mode: 'create' | 'rename'; cat?: CategoryOut }>(null)
  const [catName, setCatName] = useState('')
  const [catKind, setCatKind] = useState<'income' | 'expense'>('expense')
  const [catErr, setCatErr] = useState('')
  const [deletingCat, setDeletingCat] = useState<CategoryOut | null>(null)

  const [theme, setTheme] = useState<ThemeMode>(getStoredTheme)

  function chooseTheme(mode: ThemeMode) {
    applyTheme(mode)
    setTheme(mode)
  }

  const loadCats = useCallback(() => {
    categoryApi.list().then(setCategories).catch(() => setCategories([]))
  }, [])

  useEffect(() => {
    loadCats()
  }, [loadCats])
  useEffect(() => {
    if (profile) {
      setAllowance((profile.allowance_cents / 100).toString())
      setAllowanceDay(String(profile.allowance_day))
    }
  }, [profile])
  useEffect(() => {
    if (user) setEmail(user.email ?? '')
  }, [user])

  const expCats = useMemo(() => categories.filter((c) => c.kind === 'expense'), [categories])
  const incCats = useMemo(() => categories.filter((c) => c.kind === 'income'), [categories])

  async function saveAllowance() {
    const cents = yuanToCents(allowance)
    if (cents === null || cents < 0) { toast('请输入正确的生活费金额', 'error'); return }
    const day = parseInt(allowanceDay, 10)
    if (Number.isNaN(day) || day < 1 || day > 31) { toast('发放日需在 1-31 之间', 'error'); return }
    setAllowanceBusy(true)
    try {
      await profileApi.update({ allowance_cents: cents, allowance_day: day })
      toast('生活费设置已保存（发放日不会自动增加资产）', 'success')
      await refresh()
    } catch (err) {
      toast(isApiError(err) ? err.message : '保存失败', 'error')
    } finally {
      setAllowanceBusy(false)
    }
  }

  async function saveEmail() {
    const e = email.trim()
    if (!e) { toast('邮箱不能为空', 'error'); return }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) { toast('邮箱格式不正确', 'error'); return }
    setEmailBusy(true)
    try {
      const r = await profileApi.bindEmail(e)
      toast(r.message, 'success')
      await refresh()
    } catch (err) {
      toast(isApiError(err) ? err.message : '保存失败', 'error')
    } finally {
      setEmailBusy(false)
    }
  }

  function openCatModal(mode: 'create' | 'rename', cat?: CategoryOut) {
    setCatModal({ mode, cat })
    setCatName(cat?.name ?? '')
    setCatKind(cat?.kind ?? 'expense')
    setCatErr('')
  }

  async function submitCat() {
    setCatErr('')
    const name = catName.trim()
    if (!name) { setCatErr('请输入分类名称'); return }
    if (name.length > 12) { setCatErr('分类名称最多 12 个字'); return }
    setCatBusy(true)
    try {
      if (catModal?.mode === 'rename' && catModal.cat) {
        await categoryApi.rename(catModal.cat.id, { name, kind: catKind })
        toast('分类已更新（历史账单保留原分类名称）', 'success')
      } else {
        await categoryApi.create({ name, kind: catKind })
        toast('分类已创建', 'success')
      }
      setCatModal(null)
      loadCats()
    } catch (err) {
      setCatErr(isApiError(err) ? err.message : '保存失败')
    } finally {
      setCatBusy(false)
    }
  }

  async function deleteCat() {
    if (!deletingCat) return
    try {
      await categoryApi.remove(deletingCat.id)
      toast('分类已删除（历史账单仍显示该分类名称）', 'success')
      setDeletingCat(null)
      loadCats()
    } catch (err) {
      toast(isApiError(err) ? err.message : '删除失败', 'error')
    }
  }

  async function doCalibrate() {
    setCalibErr('')
    const cents = yuanToCents(calibValue)
    if (cents === null || cents < 0) { setCalibErr('请输入正确的资产金额（元）'); return }
    setCalibBusy(true)
    try {
      await profileApi.calibrate({ actual_assets_cents: cents })
      toast('已按实际资产校准（生成一条可追溯的校准账单）', 'success')
      setCalibOpen(false)
      setCalibValue('')
      await refresh()
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
    } catch (err) {
      setCalibErr(isApiError(err) ? err.message : '校准失败')
    } finally {
      setCalibBusy(false)
    }
  }

  if (loading) return <Loading />
  if (error) return <ErrorBox text={error} onRetry={() => void refresh()} />

  return (
    <div>
      {/* 账户信息 */}
      <Card title="账户信息" icon="user">
        <div className="grid grid-2">
          <Field label="用户名（注册后不可修改）">
            <input className="input" value={user?.username ?? ''} disabled />
          </Field>
          <Field label="邮箱（用于找回密码）">
            <div className="flex gap8">
              <input className="input" type="email" value={email}
                     onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" />
              <button className="btn btn-outline" disabled={emailBusy} onClick={() => void saveEmail()}>
                <Icon name="check" size={15} />
                {emailBusy ? '保存中…' : '保存'}
              </button>
            </div>
          </Field>
        </div>
        <div className="flex mt16">
          <button className="btn btn-danger-outline"
                  onClick={() => { logout(); navigate('/login') }}>
            <Icon name="logout" size={16} />
            退出登录
          </button>
        </div>
      </Card>

      {/* 外观 */}
      <Card title="外观" icon="sun">
        <div className="theme-options" role="group" aria-label="主题外观">
          {([
            { mode: 'system', label: '跟随系统', icon: 'monitor' },
            { mode: 'light', label: '浅色', icon: 'sun' },
            { mode: 'dark', label: '深色', icon: 'moon' },
          ] as const).map((opt) => (
            <button
              key={opt.mode}
              type="button"
              className={`theme-option ${theme === opt.mode ? 'active' : ''}`}
              aria-pressed={theme === opt.mode}
              onClick={() => chooseTheme(opt.mode)}
            >
              <Icon name={opt.icon} size={20} />
              {opt.label}
            </button>
          ))}
        </div>
        <p className="small muted mt16">跟随系统时，会随操作系统的浅色 / 深色设置自动切换。</p>
      </Card>

      {/* 生活费设置 */}
      <Card title="生活费设置" icon="wallet">
        <div className="grid grid-2">
          <Field label="每月生活费（元）" hint="仅用于周期计算与建议，实际到账请记收入账单">
            <input className="input" inputMode="decimal" value={allowance}
                   onChange={(e) => setAllowance(sanitizeYuanInput(e.target.value))} />
          </Field>
          <Field label="发放日" hint="发放日不会自动增加资产">
            <select className="select" value={allowanceDay}
                    onChange={(e) => setAllowanceDay(e.target.value)}>
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>每月 {d} 日</option>
              ))}
            </select>
          </Field>
        </div>
        <button className="btn btn-primary" disabled={allowanceBusy} onClick={() => void saveAllowance()}>
          <Icon name="check" size={15} />
          {allowanceBusy ? '保存中…' : '保存生活费设置'}
        </button>
      </Card>

      {/* 资产校准 */}
      <Card title="资产校准" icon="scale">
        <p className="muted mb16">
          系统资产 = 资产基数 + 收入 − 支出 ± 校准。当前计算值：
          <span className="strong"> <Money cents={profile?.current_assets_cents ?? 0} /></span>
        </p>
        <p className="small muted mb16">
          如果实际手持金额与系统计算不一致（如遗漏补记、现金丢失等），输入实际金额进行校准；
          系统会生成一条「资产校准」记录，差额可追溯。校准记录不可编辑，再次校准即可修正。
        </p>
        <button className="btn btn-outline" onClick={() => { setCalibValue(''); setCalibErr(''); setCalibOpen(true) }}>
          <Icon name="scale" size={16} />
          校准资产
        </button>
      </Card>

      {/* 分类管理 */}
      <Card title="分类管理" icon="receipt" extra={
        <button className="btn btn-primary btn-sm" onClick={() => openCatModal('create')}>
          <Icon name="plus" size={14} />
          新建分类
        </button>
      }>
        <h3 className="muted small mb8">支出分类</h3>
        <div className="chips mb16">
          {expCats.map((c) => (
            <span key={c.id} className="chip" style={{ cursor: 'default' }}>
              {c.name}
              {c.is_builtin
                ? <span className="small muted">（内置）</span>
                : <>
                    <button className="btn-inline" style={{ marginLeft: 6 }} onClick={() => openCatModal('rename', c)}>改</button>
                    <button className="btn-inline danger" style={{ marginLeft: 4 }} onClick={() => setDeletingCat(c)}>删</button>
                  </>}
            </span>
          ))}
        </div>
        <h3 className="muted small mb8">收入分类</h3>
        <div className="chips">
          {incCats.map((c) => (
            <span key={c.id} className="chip" style={{ cursor: 'default' }}>
              {c.name}
              {c.is_builtin
                ? <span className="small muted">（内置）</span>
                : <>
                    <button className="btn-inline" style={{ marginLeft: 6 }} onClick={() => openCatModal('rename', c)}>改</button>
                    <button className="btn-inline danger" style={{ marginLeft: 4 }} onClick={() => setDeletingCat(c)}>删</button>
                  </>}
            </span>
          ))}
        </div>
        <p className="small muted mt16">内置分类不可修改；删除自定义分类后，历史账单仍显示原分类名称。</p>
      </Card>

      {/* 更多功能（移动端入口） */}
      <Card title="更多功能" icon="menu" className="mobile-links-card">
        <div className="grid grid-2">
          <Link className="btn btn-outline" to="/goals"><Icon name="target" size={16} />储蓄目标</Link>
          <Link className="btn btn-outline" to="/notifications"><Icon name="bell" size={16} />提醒</Link>
          <Link className="btn btn-outline" to="/reports"><Icon name="file-text" size={16} />报告</Link>
          <Link className="btn btn-outline" to="/ai"><Icon name="sparkles" size={16} />AI 助手</Link>
        </div>
      </Card>

      {/* 校准弹窗 */}
      <Modal open={calibOpen} title="资产校准" onClose={() => setCalibOpen(false)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setCalibOpen(false)} disabled={calibBusy}>取消</button>
            <button className="btn btn-primary" onClick={() => void doCalibrate()} disabled={calibBusy}>
              {calibBusy ? '校准中…' : '确认校准'}
            </button>
          </>
        }>
        <Field label="实际手持资产（元）" required>
          <input className="input" inputMode="decimal" value={calibValue}
                 onChange={(e) => setCalibValue(sanitizeYuanInput(e.target.value))} placeholder="请输入当前实际金额" />
        </Field>
        {calibErr && <div className="form-error">{calibErr}</div>}
      </Modal>

      {/* 分类弹窗 */}
      <Modal open={!!catModal}
             title={catModal?.mode === 'rename' ? `修改分类「${catModal.cat?.name}」` : '新建分类'}
             onClose={() => setCatModal(null)}
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setCatModal(null)} disabled={catBusy}>取消</button>
            <button className="btn btn-primary" onClick={() => void submitCat()} disabled={catBusy}>
              {catBusy ? '保存中…' : '保存'}
            </button>
          </>
        }>
        <Field label="分类名称" required>
          <input className="input" value={catName} maxLength={12}
                 onChange={(e) => setCatName(e.target.value)} placeholder="最多 12 个字" />
        </Field>
        <Field label="收支类型" required>
          <div className="flex gap8">
            {(['expense', 'income'] as const).map((k) => (
              <button key={k} className={`chip ${catKind === k ? 'active' : ''}`}
                      onClick={() => setCatKind(k)}>
                {k === 'expense' ? '支出' : '收入'}
              </button>
            ))}
          </div>
        </Field>
        {catErr && <div className="form-error">{catErr}</div>}
      </Modal>

      {/* 删除分类确认 */}
      <ConfirmDialog
        open={!!deletingCat}
        title="删除分类"
        text={deletingCat ? `确定删除分类「${deletingCat.name}」吗？历史账单仍会显示该分类名称，但不能再用于新账单。` : ''}
        danger
        onConfirm={() => void deleteCat()}
        onCancel={() => setDeletingCat(null)}
      />
    </div>
  )
}
