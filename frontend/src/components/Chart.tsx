// ECharts 封装：图表墨色来自全局 CSS 变量（dataviz 校验过的明暗两套），
// 主题切换时用新墨色重建 option 并整体重绘。
import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { THEME_EVENT } from '../utils/theme'

export interface VizInk {
  ink: string
  ink2: string
  muted: string
  grid: string
  baseline: string
  income: string
  expense: string
  bar: string
}

export function vizColors(): VizInk {
  const cs = getComputedStyle(document.documentElement)
  const pick = (name: string, fallback: string) => {
    const v = cs.getPropertyValue(name).trim()
    return v || fallback
  }
  return {
    ink: pick('--viz-ink', '#0b0b0b'),
    ink2: pick('--viz-ink2', '#52514e'),
    muted: pick('--viz-muted', '#898781'),
    grid: pick('--viz-grid', '#e1e0d9'),
    baseline: pick('--viz-baseline', '#c3c2b7'),
    income: pick('--viz-income', '#2a78d6'),
    expense: pick('--viz-expense', '#e34948'),
    bar: pick('--viz-bar', '#2a78d6'),
  }
}

export default function Chart({ build, height = 300 }: {
  /** 用当前墨色构建 option；主题切换时会重新调用并整体重绘 */
  build: (c: VizInk) => echarts.EChartsOption
  height?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const buildRef = useRef(build)
  buildRef.current = build

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = echarts.init(el)
    chartRef.current = chart
    chart.setOption(buildRef.current(vizColors()), true)

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onThemeChange = () => {
      chartRef.current?.setOption(buildRef.current(vizColors()), true)
    }
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    window.addEventListener(THEME_EVENT, onThemeChange)
    mq.addEventListener('change', onThemeChange)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener(THEME_EVENT, onThemeChange)
      mq.removeEventListener('change', onThemeChange)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(buildRef.current(vizColors()), true)
  }, [build])

  return <div ref={ref} style={{ width: '100%', height }} />
}
