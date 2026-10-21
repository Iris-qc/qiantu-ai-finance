import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { isApiError } from '../api/client'
import AuthShell from '../components/AuthShell'

const USERNAME_RE = /^[A-Za-z0-9_-]{4,12}$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setFieldErrors({})
    const fe: Record<string, string> = {}
    if (!USERNAME_RE.test(username.trim())) {
      fe.username = '用户名需为 4-12 位字母、数字、下划线或连字符'
    }
    if (password.length < 8 || password.length > 20) {
      fe.password = '密码需为 8-20 位'
    } else if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      fe.password = '密码需同时包含字母和数字'
    }
    if (password !== confirm) fe.confirm = '两次输入的密码不一致'
    if (email.trim() && !EMAIL_RE.test(email.trim())) fe.email = '邮箱格式不正确'
    if (Object.keys(fe).length) {
      setFieldErrors(fe)
      setError('请修正表单中的错误')
      return
    }
    setBusy(true)
    setError('')
    try {
      await register(username.trim(), password, email.trim() || undefined)
      navigate('/onboarding', { replace: true })
    } catch (err) {
      setError(isApiError(err) ? err.message : '注册失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      icon="user-plus"
      title="创建账号"
      subtitle="注册后请先完成财务资料初始化"
      wide
    >
      <form onSubmit={onSubmit}>
        <label className="field">
          <span className="field-label">用户名<span className="required">*</span></span>
          <input className={`input ${fieldErrors.username ? 'invalid' : ''}`} value={username}
                 autoComplete="username"
                 onChange={(e) => setUsername(e.target.value)} placeholder="4-12 位字母/数字/下划线" />
          {fieldErrors.username && <span className="field-hint" style={{ color: 'var(--expense)' }}>{fieldErrors.username}</span>}
          <span className="field-hint">用户名唯一，注册后不可修改</span>
        </label>
        <label className="field">
          <span className="field-label">密码<span className="required">*</span></span>
          <input className={`input ${fieldErrors.password ? 'invalid' : ''}`} type="password"
                 value={password} autoComplete="new-password"
                 onChange={(e) => setPassword(e.target.value)} placeholder="8-20 位，需包含字母和数字" />
          {fieldErrors.password && <span className="field-hint" style={{ color: 'var(--expense)' }}>{fieldErrors.password}</span>}
        </label>
        <label className="field">
          <span className="field-label">确认密码<span className="required">*</span></span>
          <input className={`input ${fieldErrors.confirm ? 'invalid' : ''}`} type="password"
                 value={confirm} autoComplete="new-password"
                 onChange={(e) => setConfirm(e.target.value)} placeholder="再次输入密码" />
          {fieldErrors.confirm && <span className="field-hint" style={{ color: 'var(--expense)' }}>{fieldErrors.confirm}</span>}
        </label>
        <label className="field">
          <span className="field-label">邮箱（选填）</span>
          <input className={`input ${fieldErrors.email ? 'invalid' : ''}`} value={email}
                 type="email" autoComplete="email"
                 onChange={(e) => setEmail(e.target.value)} placeholder="用于找回密码，可稍后在设置中绑定" />
          {fieldErrors.email && <span className="field-hint" style={{ color: 'var(--expense)' }}>{fieldErrors.email}</span>}
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? '注册中…' : '注册并登录'}
        </button>
      </form>
      <div className="auth-foot">
        已有账号？<Link to="/login">直接登录</Link>
      </div>
    </AuthShell>
  )
}
