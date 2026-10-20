// 与后端 schemas 一一对应的类型定义（金额字段均为整数分）

export interface UserOut {
  id: number
  username: string
  email: string | null
  created_at: string
}

export interface TokenOut {
  access_token: string
  token_type: string
  user: UserOut
}

export interface ProfileOut {
  initialized: boolean
  initial_assets_cents: number
  allowance_cents: number
  allowance_day: number
  current_assets_cents: number
  total_income_cents: number
  total_expense_cents: number
  adjustment_cents: number
  days_to_next_allowance: number
  next_allowance_date: string
  suggested_daily_cents: number
}

export type BillType = 'income' | 'expense' | 'adjustment'

export interface CategoryOut {
  id: number
  name: string
  kind: 'income' | 'expense'
  is_builtin: boolean
}

export interface BillOut {
  id: number
  bill_type: BillType
  amount_cents: number
  category_id: number | null
  category_name: string
  occurred_at: string
  note: string | null
  source: string
  created_at: string
  updated_at: string
}

export interface BillListOut {
  items: BillOut[]
  total: number
  page: number
  page_size: number
}

export interface BudgetItemOut {
  id: number
  scope: 'total' | 'category'
  category_id: number | null
  category_name: string | null
  amount_cents: number
  spent_cents: number
  usage_percent: number
  threshold_percent: number
  status: 'normal' | 'approaching' | 'exceeded'
}

export interface BudgetForecastOut {
  days_total: number
  days_elapsed: number
  days_remaining: number
  avg_daily_cents: number
  spent_cents: number
  predicted_cents: number
  budget_cents: number | null
  risk: 'none' | 'potential' | 'high' | 'no_budget'
  risk_label: string
}

export interface BudgetOverviewOut {
  month: string
  items: BudgetItemOut[]
  forecast: BudgetForecastOut
}

export interface TrendPoint {
  label: string
  expense_cents: number
  income_cents: number
}

export interface TrendOut {
  granularity: 'day' | 'week' | 'month'
  points: TrendPoint[]
}

export interface CategoryShare {
  category_name: string
  amount_cents: number
  percent: number
}

export interface CategoryStatsOut {
  items: CategoryShare[]
  total_cents: number
}

export interface SummaryOut {
  period_start: string
  period_end: string
  expense_cents: number
  income_cents: number
  bill_count: number
  top_category: string | null
  prev_expense_cents: number | null
  prev_income_cents: number | null
}

export interface GoalOut {
  id: number
  name: string
  target_cents: number
  current_cents: number
  deadline: string
  note: string | null
  created_at: string
  progress_percent: number
  remaining_cents: number
  days_left: number
  suggested_daily_cents: number
  suggested_monthly_cents: number
  risk: 'on_track' | 'tight' | 'overdue' | 'done'
}

export interface GoalListOut {
  items: GoalOut[]
}

export interface NotificationOut {
  id: number
  kind: 'budget' | 'anomaly' | 'goal' | string
  level: 'info' | 'warning' | 'danger' | string
  title: string
  content: string
  bill_id: number | null
  read_at: string | null
  created_at: string
}

export interface NotificationListOut {
  items: NotificationOut[]
  unread_count: number
}

export interface ReportOut {
  id: number
  report_type: 'monthly' | 'semester' | 'annual'
  period_start: string
  period_end: string
  title: string
  content: ReportContent
  has_pdf: boolean
  created_at: string
}

export interface ReportListOut {
  items: ReportOut[]
}

export interface ReportPeriodsOut {
  monthly: string[]
  semesters: { label: string; start: string; end: string }[]
  years: string[]
}

export interface ReportContent {
  summary: {
    period_label: string
    period_start: string
    period_end: string
    expense_cents: number
    income_cents: number
    net_cents: number
    bill_count: number
    avg_daily_cents: number
    top_category: string | null
    max_day: { day: string; amount_cents: number } | null
    current_assets_cents: number
  }
  categories: { category_name: string; amount_cents: number; percent: number }[]
  budget: {
    total_cents: number
    spent_cents: number
    usage_percent: number
    status: string
  } | null
  anomalies: { bill_id: number; category_name: string; amount_cents: number; occurred_at: string; note: string | null }[]
  goals: { name: string; target_cents: number; current_cents: number; progress_percent: number; deadline: string }[]
  advice: string
  generated_at: string
}

export interface DraftItem {
  bill_type: 'income' | 'expense'
  amount_cents: number
  category_id: number | null
  category_name: string
  occurred_at: string | null
  note: string | null
  merchant?: string | null
}

export interface NlParseOut {
  mode: 'demo' | 'external'
  notice: string
  items: DraftItem[]
}

export interface SpeechParseOut {
  mode: string
  transcript: string
  items: DraftItem[]
  notice: string
}

export interface OcrParseOut {
  mode: string
  ocr_text: string
  items: DraftItem[]
  notice: string
}

export interface DraftConfirmOut {
  created: number[]
}

export interface AdviceBasis {
  label: string
  value: string
}

export interface AdviceOut {
  mode: 'demo' | 'external'
  answer: string
  basis: AdviceBasis[]
  warnings: string[]
  disclaimer: string
}

export interface ApiErrorBody {
  detail: {
    code: string
    message: string
    fields?: Record<string, unknown>
  }
}
