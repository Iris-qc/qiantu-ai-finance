// 主题偏好：system 跟随系统，light / dark 手动指定。
// 通过 <html data-theme> 驱动 CSS 变量；图表监听 csaifm:theme 事件重绘。
export type ThemeMode = 'system' | 'light' | 'dark'

export const THEME_STORAGE_KEY = 'csaifm-theme'
export const THEME_EVENT = 'csaifm:theme'

export function getStoredTheme(): ThemeMode {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') return saved
  } catch {
    /* 隐私模式下 localStorage 可能不可用 */
  }
  return 'system'
}

export function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  if (mode === 'light' || mode === 'dark') {
    root.dataset.theme = mode
  } else {
    delete root.dataset.theme
  }
  try {
    if (mode === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
    else localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    /* 存不下就只在本次会话生效 */
  }
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: mode }))
}

/** 在 React 挂载前执行，避免首屏闪烁 */
export function initTheme() {
  const mode = getStoredTheme()
  if (mode === 'light' || mode === 'dark') {
    document.documentElement.dataset.theme = mode
  }
}
