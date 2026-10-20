import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { isApiError } from '../api/client'

export default function ForgotPassword() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [step, setStep] = useState<1 | 2>(1)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function requestCode(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const r = await authApi.requestReset(email.trim())
      setNotice(r.message)
      setStep(2)
    } catch (err) {
      // SMTP 未配置时后端返回 503，message 中已明确说明演示模式
      if (isApiError(err) && err.code === 'SERVICE_NOT_CONFIGURED') {
        setNotice(err.message)
        setStep(2) // 本地演示：验证码在服务端日志中，仍可进入下一步
      } else {
        setError(isApiError(err) ? err.message : '发送失败，请稍后重试')
      }
    } finally {
      setBusy(false)
    }
  }

  async function confirmReset(e: FormEvent) {
    e.preventDefault()
    if (!/^\d{6}$/.test(code)) {
      setError('验证码为 6 位数字')
      return
    }
    if (newPassword.length < 8 || newPassword.length > 20 ||
        !/[A-Za-z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setError('新密码需为 8-20 位，且同时包含字母和数字')
      return
    }
    setBusy(true)
    setError('')
    try {
      const r = await authApi.confirmReset({ email: email.trim(), code, new_password: newPassword })
      setNotice(r.message)
      window.setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      setError(isApiError(err) ? err.message : '重置失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="big">🔐</div>
          <h1>找回密码</h1>
          <p>通过绑定邮箱的验证码重置密码</p>
        </div>
        {step === 1 ? (
          <form onSubmit={requestCode}>
            <label className="field">
              <span className="field-label">注册邮箱<span className="required">*</span></span>
              <input className="input" type="email" value={email}
                     onChange={(e) => setEmail(e.target.value)} placeholder="请输入注册时绑定的邮箱" />
            </label>
            {error && <div className="form-error">{error}</div>}
            <button className="btn btn-primary btn-block" type="submit" disabled={busy || !email.trim()}>
              {busy ? '发送中…' : '获取验证码'}
            </button>
          </form>
        ) : (
          <form onSubmit={confirmReset}>
            {notice && <div className="notice-info">{notice}</div>}
            <label className="field">
              <span className="field-label">6 位验证码<span className="required">*</span></span>
              <input className="input" value={code} inputMode="numeric" maxLength={6}
                     onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                     placeholder="请输入邮箱收到的验证码" />
            </label>
            <label className="field">
              <span className="field-label">新密码<span className="required">*</span></span>
              <input className="input" type="password" value={newPassword} autoComplete="new-password"
                     onChange={(e) => setNewPassword(e.target.value)} placeholder="8-20 位，需包含字母和数字" />
            </label>
            {error && <div className="form-error">{error}</div>}
            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
              {busy ? '重置中…' : '重置密码'}
            </button>
          </form>
        )}
        <div className="auth-foot">
          <Link to="/login">返回登录</Link>
        </div>
      </div>
    </div>
  )
}
