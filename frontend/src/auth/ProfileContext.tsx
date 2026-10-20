import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { profileApi } from '../api/endpoints'
import type { ProfileOut } from '../api/types'
import { useAuth } from './AuthContext'

interface ProfileState {
  profile: ProfileOut | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const ProfileContext = createContext<ProfileState | null>(null)

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const [profile, setProfile] = useState<ProfileOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      setProfile(await profileApi.get())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载档案失败')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (token) void refresh()
    else {
      setProfile(null)
      setLoading(false)
    }
  }, [token, refresh])

  return (
    <ProfileContext.Provider value={{ profile, loading, error, refresh }}>
      {children}
    </ProfileContext.Provider>
  )
}

export function useProfile(): ProfileState {
  const ctx = useContext(ProfileContext)
  if (!ctx) throw new Error('useProfile 必须在 ProfileProvider 内使用')
  return ctx
}
