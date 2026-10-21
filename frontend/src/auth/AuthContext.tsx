import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { authApi } from '../api/endpoints'
import { getToken, setToken } from '../api/client'
import type { TokenOut, UserOut } from '../api/types'

interface AuthState {
  user: UserOut | null
  token: string | null
  /** 启动时是否还在恢复登录态 */
  booting: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, email: string) => Promise<void>
  logout: () => void
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [token, setTokenState] = useState<string | null>(getToken())
  const [booting, setBooting] = useState(true)

  useEffect(() => {
    let cancelled = false
    const onUnauthorized = () => {
      setUser(null)
      setTokenState(null)
    }
    window.addEventListener('csaifm:unauthorized', onUnauthorized)
    ;(async () => {
      if (getToken()) {
        try {
          const me = await authApi.me()
          if (!cancelled) setUser(me)
        } catch {
          // token 失效：client 已清除
          setTokenState(null)
        }
      }
      if (!cancelled) setBooting(false)
    })()
    return () => {
      cancelled = true
      window.removeEventListener('csaifm:unauthorized', onUnauthorized)
    }
  }, [])

  const applyToken = useCallback((t: TokenOut) => {
    setToken(t.access_token)
    setTokenState(t.access_token)
    setUser(t.user)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    applyToken(await authApi.login({ username, password }))
  }, [applyToken])

  const register = useCallback(async (username: string, password: string, email: string) => {
    applyToken(await authApi.register({ username, password, email }))
  }, [applyToken])

  const logout = useCallback(() => {
    setToken(null)
    setTokenState(null)
    setUser(null)
  }, [])

  const refreshMe = useCallback(async () => {
    const me = await authApi.me()
    setUser(me)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, booting, login, register, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}
