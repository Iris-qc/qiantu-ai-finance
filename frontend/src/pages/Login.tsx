import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { isApiError } from '../api/client'
import AuthShell from '../components/AuthShell'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const from = (location.state as { from?: string } | null)?.from || '/'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('请输入用户名和密码')
      return
    }
    setBusy(true)
    setError('')
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(isApiError(err) ? err.message : '登录失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      icon="wallet"
      title="欢迎回来"
      subtitle="登录后继续管理你的校园财务"
    >
      <form onSubmit={onSubmit}>
        <label className="field">
          <span className="field-label">用户名</span>
          <input className="input" value={username} autoComplete="username"
                 onChange={(e) => setUsername(e.target.value)} placeholder="4-12 位字母/数字/下划线" />
        </label>
        <label className="field">
          <span className="field-label">密码</span>
          <input className="input" type="password" value={password} autoComplete="current-password"
                 onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
      <div className="auth-foot">
        <Link to="/register">没有账号？立即注册</Link>
        <span className="muted"> · </span>
        <Link to="/forgot-password">忘记密码</Link>
      </div>
      <div className="notice-info mt16 small">
        演示账号：<span className="strong">demo</span> / <span className="strong">Demo123456</span>（已含约 60 天示例账单）
      </div>
    </AuthShell>
  )
}
