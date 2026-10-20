// 通用 UI 小组件：金额文本、进度条、加载/空/错误状态、弹窗、卡片
import type { ReactNode } from 'react'
import { centsToYuan } from '../utils/money'

export function Money({ cents, className = '' }: { cents: number; className?: string }) {
  const neg = cents < 0
  return (
    <span className={`money ${neg ? 'money-neg' : ''} ${className}`}>
      {neg ? '-' : ''}¥{centsToYuan(Math.abs(cents))}
    </span>
  )
}

/** 收支着色金额：收入绿、支出红（与金额本身正负无关，只看方向） */
export function DirectionMoney({ cents, type, className = '' }: {
  cents: number
  type: 'income' | 'expense' | 'adjustment'
  className?: string
}) {
  const cls = type === 'income' ? 'money-in' : type === 'expense' ? 'money-out' : 'money-adj'
  const prefix = type === 'expense' ? '-' : type === 'income' ? '+' : '±'
  return (
    <span className={`money ${cls} ${className}`}>{prefix}¥{centsToYuan(cents)}</span>
  )
}

export function ProgressBar({ percent, status = 'normal', height = 8 }: {
  percent: number
  status?: 'normal' | 'approaching' | 'exceeded' | 'warning' | 'danger'
  height?: number
}) {
  const clamped = Math.min(Math.max(percent, 0), 100)
  return (
    <div className="progress" style={{ height }}>
      <div
        className={`progress-fill progress-${status}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="state-box">
      <span className="spinner" aria-hidden="true" />
      <p>{text}</p>
    </div>
  )
}

export function Empty({ text = '暂无数据', children }: { text?: string; children?: ReactNode }) {
  return (
    <div className="state-box">
      <div className="empty-icon" aria-hidden="true">🗒️</div>
      <p>{text}</p>
      {children}
    </div>
  )
}

export function ErrorBox({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div className="state-box state-error">
      <div className="empty-icon" aria-hidden="true">⚠️</div>
      <p>{text}</p>
      {onRetry && (
        <button type="button" className="btn btn-outline btn-sm" onClick={onRetry}>重试</button>
      )}
    </div>
  )
}

export function Card({ title, extra, children, className = '' }: {
  title?: ReactNode
  extra?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {(title || extra) && (
        <header className="card-head">
          <h2 className="card-title">{title}</h2>
          {extra}
        </header>
      )}
      {children}
    </section>
  )
}

export function Modal({ open, title, onClose, children, footer }: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  if (!open) return null
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}
           onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭">✕</button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ open, title, text, confirmText = '确认', danger = false,
                                busy = false, onConfirm, onCancel }: {
  open: boolean
  title: string
  text: string
  confirmText?: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel}
      footer={
        <>
          <button type="button" className="btn btn-outline" onClick={onCancel} disabled={busy}>取消</button>
          <button type="button" className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
                  onClick={onConfirm} disabled={busy}>
            {busy ? '处理中…' : confirmText}
          </button>
        </>
      }>
      <p className="confirm-text">{text}</p>
    </Modal>
  )
}

export function Stat({ label, value, sub, tone }: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'in' | 'out' | 'plain'
}) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

/** 表单行：标签 + 输入 */
export function Field({ label, required = false, children, hint }: {
  label: string
  required?: boolean
  children: ReactNode
  hint?: string
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required && <span className="required">*</span>}
      </span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}
