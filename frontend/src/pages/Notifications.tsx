import { useCallback, useEffect, useState } from 'react'
import { notificationApi } from '../api/endpoints'
import type { NotificationListOut } from '../api/types'
import { useToast } from '../components/Toast'
import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { Card, Empty, ErrorBox, Loading } from '../components/ui'
import { formatDateTime } from '../utils/money'

const KIND_LABEL: Record<string, string> = { budget: '预算', anomaly: '异常消费', goal: '储蓄目标' }
const KIND_ICON: Record<string, IconName> = { budget: 'wallet', anomaly: 'alert-triangle', goal: 'target' }
const LEVEL_BADGE: Record<string, string> = {
  info: 'badge-info', warning: 'badge-warning', danger: 'badge-danger',
}

export default function Notifications() {
  const { toast } = useToast()
  const [data, setData] = useState<NotificationListOut | null>(null)
  const [kindFilter, setKindFilter] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    notificationApi.list(unreadOnly || undefined, kindFilter || undefined)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : '加载提醒失败'))
      .finally(() => setLoading(false))
  }, [unreadOnly, kindFilter])

  useEffect(() => { load() }, [load])

  async function markRead(id: number) {
    try {
      await notificationApi.markRead(id)
      load()
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
    } catch (err) {
      toast(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  async function markAll() {
    try {
      await notificationApi.markAllRead()
      toast('已全部标记为已读', 'success')
      load()
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
    } catch (err) {
      toast(err instanceof Error ? err.message : '操作失败', 'error')
    }
  }

  return (
    <div>
      <Card>
        <div className="flex gap8 wrap flex-between">
          <div className="flex gap8 wrap">
            <button className={`chip ${unreadOnly ? 'active' : ''}`} onClick={() => setUnreadOnly(!unreadOnly)}>
              <Icon name="bell" size={13} />
              只看未读
            </button>
            {(['', 'budget', 'anomaly', 'goal'] as const).map((k) => (
              <button key={k} className={`chip ${kindFilter === k ? 'active' : ''}`}
                      onClick={() => setKindFilter(k)}>
                {k === '' ? '全部' : KIND_LABEL[k]}
              </button>
            ))}
          </div>
          {!!data && data.unread_count > 0 && (
            <button className="btn btn-outline btn-sm" onClick={() => void markAll()}>
              <Icon name="check" size={14} />
              全部标为已读
            </button>
          )}
        </div>
      </Card>

      {loading ? <Loading /> : error ? <ErrorBox text={error} onRetry={load} /> :
        !data || data.items.length === 0 ? (
          <Empty text={unreadOnly ? '没有未读提醒' : '暂无提醒'} />
        ) : (
          <Card title={`提醒列表（${data.unread_count} 条未读）`} icon="bell">
            <div className="list">
              {data.items.map((n) => {
                const unread = !n.read_at
                return (
                  <div key={n.id} className={`bill-row notification-row ${unread ? 'is-unread' : 'is-read'}`}>
                    <div className={`bill-icon ${n.kind === 'anomaly' ? 'out' : 'adj'}`}>
                      <Icon name={KIND_ICON[n.kind] ?? 'bell'} size={18} />
                    </div>
                    <div className="bill-main">
                      <div className="bill-name">
                        {n.title}
                        <span className={`badge ${LEVEL_BADGE[n.level] ?? 'badge-muted'}`}>
                          {KIND_LABEL[n.kind] ?? n.kind}
                        </span>
                      </div>
                      <div className="bill-sub">{n.content}</div>
                      <div className="bill-sub">{formatDateTime(n.created_at)}</div>
                    </div>
                    <div className="bill-actions">
                      {unread ? (
                        <button className="btn-inline" onClick={() => void markRead(n.id)}>
                          <Icon name="check" size={13} />标为已读
                        </button>
                      ) : (
                        <span className="small muted">已读</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>
        )}
    </div>
  )
}
