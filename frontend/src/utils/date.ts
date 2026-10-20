// 日期辅助

export function monthLabel(month: string): string {
  const [y, m] = month.split('-')
  return `${y}年${parseInt(m, 10)}月`
}

export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}`
}
