// 登录 / 注册 / 找回密码 / 初始化共用的品牌化外壳
import type { ReactNode } from 'react'
import { BrandMark, Icon } from './Icon'
import type { IconName } from './Icon'

export default function AuthShell({
  icon,
  title,
  subtitle,
  children,
  wide = false,
}: {
  icon: IconName
  title: string
  subtitle: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className="auth-shell">
      <aside className="auth-aside" aria-hidden="true">
        <div className="auth-aside-brand">
          <BrandMark size={42} />
          <span>钱途</span>
        </div>

        <div className="auth-aside-copy">
          <span className="auth-kicker">大学生智能财务管理平台</span>
          <h2>
            把每一笔钱，
            <br />
            都花在计划里。
          </h2>
          <p>记账、预算、储蓄目标与消费分析，一个平台管好你的校园财务。</p>
        </div>

        <ul className="auth-features">
          <li>
            <span className="auth-feature-icon"><Icon name="sparkles" size={17} /></span>
            AI 智能记账，一句话生成账单
          </li>
          <li>
            <span className="auth-feature-icon"><Icon name="chart" size={17} /></span>
            消费分析，看清钱花在哪里
          </li>
          <li>
            <span className="auth-feature-icon"><Icon name="target" size={17} /></span>
            储蓄目标，按剩余天数给出建议
          </li>
        </ul>

        <div className="auth-aside-foot">
          <Icon name="shield" size={15} />
          每位用户的数据独立存储，仅本人可见
        </div>
      </aside>

      <main className="auth-main">
        <div className={`auth-card ${wide ? 'auth-card-wide' : ''}`}>
          <div className="auth-brand">
            <span className="auth-icon"><Icon name={icon} size={24} /></span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          {children}
        </div>
      </main>
    </div>
  )
}
