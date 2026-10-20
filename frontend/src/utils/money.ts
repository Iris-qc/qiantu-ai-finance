// 金额工具：与后端约定一致——传输/存储一律整数分，展示层才转为"元"。
// 禁止使用浮点参与金额计算。

/** 分 → "元" 字符串（如 1234 → "12.34"，-5 → "-0.05"） */
export function centsToYuan(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(Math.round(cents))
  const yuan = Math.floor(abs / 100)
  const fen = abs % 100
  return `${sign}${yuan}.${fen.toString().padStart(2, '0')}`
}

const YUAN_RE = /^(\d{1,12})(?:\.(\d{1,2}))?$/

/** "元"字符串 → 分（整数）。非法输入返回 null，绝不返回浮点结果。 */
export function yuanToCents(s: string): number | null {
  const t = s.trim()
  const m = YUAN_RE.exec(t)
  if (!m) return null
  const yuan = parseInt(m[1], 10)
  const fen = m[2] ? parseInt(m[2].padEnd(2, '0'), 10) : 0
  return yuan * 100 + fen
}

/** 金额输入框的合法化：过滤到数字与一个小数点、最多两位小数 */
export function sanitizeYuanInput(s: string): string {
  let t = s.replace(/[^\d.]/g, '')
  const firstDot = t.indexOf('.')
  if (firstDot !== -1) {
    t = t.slice(0, firstDot + 1) + t.slice(firstDot + 1).replace(/\./g, '')
    t = t.slice(0, firstDot + 3)
  }
  return t
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function todayStr(): string {
  const d = new Date()
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function thisMonth(): string {
  return todayStr().slice(0, 7)
}

/** 本地 datetime-local 输入值 → ISO8601（后端按业务时区解析） */
export function localInputToIso(v: string): string {
  return new Date(v).toISOString()
}

/** ISO8601 → datetime-local 输入值 */
export function isoToLocalInput(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
