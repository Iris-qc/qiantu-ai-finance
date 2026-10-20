// 后端接口的一一映射（见 backend/app/api/）
import { api } from './client'
import type {
  AdviceOut, BillListOut, BillOut, BudgetOverviewOut, CategoryOut, CategoryStatsOut,
  DraftConfirmOut, GoalListOut, GoalOut, NlParseOut, NotificationListOut, NotificationOut,
  OcrParseOut, ProfileOut, ReportListOut, ReportOut, ReportPeriodsOut, SpeechParseOut,
  SummaryOut, TokenOut, TrendOut, UserOut,
} from './types'

// —— 认证 ——
export const authApi = {
  register: (body: { username: string; password: string; email?: string }) =>
    api.post<TokenOut>('/auth/register', body),
  login: (body: { username: string; password: string }) =>
    api.post<TokenOut>('/auth/login', body),
  me: () => api.get<UserOut>('/auth/me'),
  requestReset: (email: string) =>
    api.post<{ message: string }>('/auth/password-reset/request', { email }),
  confirmReset: (body: { email: string; code: string; new_password: string }) =>
    api.post<{ message: string }>('/auth/password-reset/confirm', body),
}

// —— 档案 ——
export const profileApi = {
  get: () => api.get<ProfileOut>('/profile'),
  init: (body: { initial_assets_cents: number; allowance_cents: number; allowance_day: number }) =>
    api.put<ProfileOut>('/profile/init', body),
  update: (body: { allowance_cents: number; allowance_day: number }) =>
    api.put<ProfileOut>('/profile', body),
  calibrate: (body: { actual_assets_cents: number }) =>
    api.post<ProfileOut>('/profile/calibrate', body),
  bindEmail: (email: string) => api.put<{ message: string }>('/profile/email', { email }),
}

// —— 分类 ——
export const categoryApi = {
  list: () => api.get<CategoryOut[]>('/categories'),
  create: (body: { name: string; kind: 'income' | 'expense' }) =>
    api.post<CategoryOut>('/categories', body),
  rename: (id: number, body: { name: string; kind: 'income' | 'expense' }) =>
    api.patch<CategoryOut>(`/categories/${id}`, body),
  remove: (id: number) => api.delete<void>(`/categories/${id}`),
}

// —— 账单 ——
export interface BillQuery {
  bill_type?: string
  category_id?: number
  start?: string
  end?: string
  keyword?: string
  page?: number
  page_size?: number
  sort?: 'asc' | 'desc'
}

export const billApi = {
  list: (q?: BillQuery) => api.get<BillListOut>('/bills', q as Record<string, string | number | undefined>),
  get: (id: number) => api.get<BillOut>(`/bills/${id}`),
  create: (body: {
    bill_type: 'income' | 'expense'; amount_cents: number; category_id: number
    occurred_at?: string | null; note?: string | null
  }) => api.post<BillOut>('/bills', body),
  update: (id: number, body: {
    bill_type?: string; amount_cents?: number; category_id?: number
    occurred_at?: string | null; note?: string | null
  }) => api.patch<BillOut>(`/bills/${id}`, body),
  remove: (id: number) => api.delete<void>(`/bills/${id}`),
}

// —— 预算 ——
export const budgetApi = {
  overview: (month?: string) => api.get<BudgetOverviewOut>('/budgets', { month }),
  upsert: (body: {
    month: string; scope: 'total' | 'category'; category_id?: number | null
    amount_cents: number; threshold_percent?: number
  }) => api.put<BudgetOverviewOut>('/budgets', body),
  remove: (id: number) => api.delete<void>(`/budgets/${id}`),
}

// —— 分析 ——
export const analyticsApi = {
  trend: (granularity: 'day' | 'week' | 'month', start?: string, end?: string) =>
    api.get<TrendOut>('/analytics/trend', { granularity, start, end }),
  categories: (start?: string, end?: string) =>
    api.get<CategoryStatsOut>('/analytics/categories', { start, end }),
  summary: (start?: string, end?: string) =>
    api.get<SummaryOut>('/analytics/summary', { start, end }),
}

// —— 目标 ——
export const goalApi = {
  list: () => api.get<GoalListOut>('/goals'),
  create: (body: {
    name: string; target_cents: number; current_cents?: number; deadline: string; note?: string
  }) => api.post<GoalOut>('/goals', body),
  update: (id: number, body: {
    name?: string; target_cents?: number; current_cents?: number; deadline?: string; note?: string | null
  }) => api.patch<GoalOut>(`/goals/${id}`, body),
  remove: (id: number) => api.delete<void>(`/goals/${id}`),
}

// —— 提醒 ——
export const notificationApi = {
  list: (unread_only?: boolean, kind?: string) =>
    api.get<NotificationListOut>('/notifications', { unread_only, kind }),
  markRead: (id: number) => api.post<NotificationOut>(`/notifications/${id}/read`),
  markAllRead: () => api.post<{ message: string }>('/notifications/read-all'),
}

// —— 报告 ——
export const reportApi = {
  periods: () => api.get<ReportPeriodsOut>('/reports/periods'),
  generate: (body: { report_type: 'monthly' | 'semester' | 'annual'; period_start?: string; period_end?: string }) =>
    api.post<ReportOut>('/reports/generate', body),
  list: () => api.get<ReportListOut>('/reports'),
  get: (id: number) => api.get<ReportOut>(`/reports/${id}`),
  remove: (id: number) => api.delete<void>(`/reports/${id}`),
}

// —— AI ——
export const aiApi = {
  parseNl: (text: string) => api.post<NlParseOut>('/ai/drafts/nl', { text }),
  parseSpeech: (file: File) => api.upload<SpeechParseOut>('/ai/drafts/speech', file),
  parseImage: (file: File) => api.upload<OcrParseOut>('/ai/drafts/image', file),
  confirm: (body: { source: 'nlp' | 'voice' | 'ocr'; items: unknown[] }) =>
    api.post<DraftConfirmOut>('/ai/drafts/confirm', body),
  advice: (question: string) => api.post<AdviceOut>('/ai/advice', { question }),
}
