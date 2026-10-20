import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProfile } from '../auth/ProfileContext'
import { profileApi } from '../api/endpoints'
import { isApiError } from '../api/client'
import { centsToYuan, sanitizeYuanInput, yuanToCents } from '../utils/money'

export default function Onboarding() {
  const navigate = useNavigate()
  const { refresh } = useProfile()
  const [assets, setAssets] = useState('')
  const [allowance, setAllowance] = useState('')
  const [day, setDay] = useState('1')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const assetsCents = yuanToCents(assets)
    const allowanceCents = yuanToCents(allowance)
    if (assetsCents === null || assetsCents < 0) {
      setError('请输入正确的可支配资产金额（元，最多两位小数）')
      return
    }
    if (allowanceCents === null || allowanceCents < 0) {
      setError('请输入正确的每月生活费金额（元，最多两位小数）')
      return
    }
    setBusy(true)
    try {
      await profileApi.init({
        initial_assets_cents: assetsCents,
        allowance_cents: allowanceCents,
        allowance_day: parseInt(day, 10),
      })
      await refresh()
      navigate('/', { replace: true })
    } catch (err) {
      setError(isApiError(err) ? err.message : '初始化失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ maxWidth: 440 }}>
        <div className="auth-brand">
          <div className="big">👋</div>
          <h1>财务资料初始化</h1>
          <p>完成初始化后即可开始记账</p>
        </div>
        <form onSubmit={onSubmit}>
          <label className="field">
            <span className="field-label">当前可支配资产（元）<span className="required">*</span></span>
            <input className="input" inputMode="decimal" value={assets}
                   onChange={(e) => setAssets(sanitizeYuanInput(e.target.value))}
                   placeholder="例如 5000" />
            <span className="field-hint">作为资产基数，之后不可重复设置；如有偏差请使用「资产校准」</span>
          </label>
          <label className="field">
            <span className="field-label">每月生活费（元）<span className="required">*</span></span>
            <input className="input" inputMode="decimal" value={allowance}
                   onChange={(e) => setAllowance(sanitizeYuanInput(e.target.value))}
                   placeholder="例如 2000" />
          </label>
          <label className="field">
            <span className="field-label">生活费发放日<span className="required">*</span></span>
            <select className="select" value={day} onChange={(e) => setDay(e.target.value)}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>每月 {d} 日</option>
              ))}
            </select>
            <span className="field-hint">
              发放日只用于周期计算（倒计时/每日建议支出），不会自动增加资产；实际到账请记一笔收入账单
            </span>
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? '保存中…' : '完成初始化'}
          </button>
        </form>
        {assets && yuanToCents(assets) !== null && (
          <div className="notice-info mt16">
            你的资产基数将记为 <span className="strong">¥{centsToYuan(yuanToCents(assets)!)}</span>
          </div>
        )}
      </div>
    </div>
  )
}
