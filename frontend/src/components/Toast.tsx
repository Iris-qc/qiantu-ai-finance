import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Icon } from './Icon'
import type { IconName } from './Icon'

interface ToastItem {
  id: number
  text: string
  kind: 'success' | 'error' | 'info'
}

const TOAST_ICON: Record<ToastItem['kind'], IconName> = {
  success: 'check-circle',
  error: 'alert-circle',
  info: 'info',
}

interface ToastState {
  toast: (text: string, kind?: ToastItem['kind']) => void
}

const ToastContext = createContext<ToastState | null>(null)

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const timers = useRef<Map<number, number>>(new Map())

  const toast = useCallback((text: string, kind: ToastItem['kind'] = 'info') => {
    const id = nextId++
    setItems((prev) => [...prev.slice(-3), { id, text, kind }])
    const timer = window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id))
      timers.current.delete(id)
    }, 3500)
    timers.current.set(id, timer)
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <Icon name={TOAST_ICON[t.kind]} size={17} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastState {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast 必须在 ToastProvider 内使用')
  return ctx
}
