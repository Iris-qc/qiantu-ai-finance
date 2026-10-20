import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi, categoryApi } from '../api/endpoints'
import type { AdviceOut, CategoryOut, DraftItem } from '../api/types'
import { isApiError } from '../api/client'
import { useToast } from '../components/Toast'
import { Card, Empty, Field, Loading } from '../components/ui'
import { centsToYuan, isoToLocalInput, localInputToIso, sanitizeYuanInput, yuanToCents } from '../utils/money'

type Tab = 'text' | 'voice' | 'image'

interface ChatMsg {
  role: 'user' | 'bot'
  text: string
  basis?: { label: string; value: string }[]
  warnings?: string[]
  disclaimer?: string
  mode?: string
}

export default function AiAssistant() {
  const { toast } = useToast()
  const [tab, setTab] = useState<Tab>('text')
  const [categories, setCategories] = useState<CategoryOut[]>([])

  // 自然语言
  const [nlText, setNlText] = useState('')
  const [nlBusy, setNlBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [drafts, setDrafts] = useState<DraftItem[]>([])
  const [confirmBusy, setConfirmBusy] = useState(false)

  // 语音
  const [recording, setRecording] = useState(false)
  const [speechBusy, setSpeechBusy] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  // 图片
  const [imageBusy, setImageBusy] = useState(false)
  const [ocrText, setOcrText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 建议对话
  const [question, setQuestion] = useState('')
  const [adviceBusy, setAdviceBusy] = useState(false)
  const [chat, setChat] = useState<ChatMsg[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    categoryApi.list().then(setCategories).catch(() => setCategories([]))
  }, [])
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat])

  const catsFor = useCallback((type: 'income' | 'expense') =>
    categories.filter((c) => c.kind === type), [categories])

  function applyDraftResult(items: DraftItem[], mode: string, modeNotice: string, extra?: string) {
    setDrafts(items)
    setNotice(`${extra ?? ''}${modeNotice}`)
  }

  function updateDraft(index: number, patch: Partial<DraftItem>) {
    setDrafts((prev) => prev.map((d, i) => (i === index ? { ...d, ...patch } : d)))
  }

  async function parseNl() {
    if (!nlText.trim()) return
    setNlBusy(true)
    setNotice('')
    setTranscript('')
    setOcrText('')
    try {
      const r = await aiApi.parseNl(nlText.trim())
      applyDraftResult(r.items, r.mode, r.notice)
      if (r.items.length === 0) toast('未识别出消费信息，请换个说法', 'error')
    } catch (err) {
      toast(isApiError(err) ? err.message : '解析失败', 'error')
    } finally {
      setNlBusy(false)
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      toast('当前浏览器不支持录音，请使用文字输入或图片识别', 'error')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
        if (blob.size === 0) { toast('没有录到声音，请重试', 'error'); return }
        const file = new File([blob], 'recording.webm', { type: blob.type })
        setSpeechBusy(true)
        setNotice('')
        setOcrText('')
        try {
          const r = await aiApi.parseSpeech(file)
          setTranscript(r.transcript)
          applyDraftResult(r.items, r.mode, r.notice)
        } catch (err) {
          toast(isApiError(err) ? err.message : '语音识别失败', 'error')
        } finally {
          setSpeechBusy(false)
        }
      }
      recorderRef.current = rec
      rec.start()
      setRecording(true)
    } catch {
      toast('无法访问麦克风，请检查浏览器权限', 'error')
    }
  }

  function stopRecording() {
    recorderRef.current?.stop()
  }

  async function onImagePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) { toast('请选择图片文件', 'error'); return }
    setImageBusy(true)
    setNotice('')
    setTranscript('')
    try {
      const r = await aiApi.parseImage(file)
      setOcrText(r.ocr_text)
      applyDraftResult(r.items, r.mode, r.notice)
      if (r.items.length === 0) toast('图片中未识别出消费信息', 'error')
    } catch (err) {
      toast(isApiError(err) ? err.message : '图片识别失败', 'error')
    } finally {
      setImageBusy(false)
    }
  }

  async function confirmDrafts(source: 'nlp' | 'voice' | 'ocr') {
    if (drafts.length === 0) return
    // 前端先做一次完整性校验，给出逐项提示
    for (let i = 0; i < drafts.length; i++) {
      const d = drafts[i]
      if (d.amount_cents <= 0) { toast(`第 ${i + 1} 条草稿金额无效`, 'error'); return }
      if (!d.category_id && !d.category_name) { toast(`第 ${i + 1} 条草稿缺少分类`, 'error'); return }
    }
    setConfirmBusy(true)
    try {
      const r = await aiApi.confirm({ source, items: drafts })
      toast(`已入账 ${r.created.length} 笔（草稿确认前不会写入任何账单）`, 'success')
      setDrafts([])
      setNotice('')
      setTranscript('')
      setOcrText('')
      window.dispatchEvent(new CustomEvent('csaifm:refresh-notifs'))
    } catch (err) {
      toast(isApiError(err) ? err.message : '确认失败，未写入任何账单', 'error')
    } finally {
      setConfirmBusy(false)
    }
  }

  async function askAdvice() {
    if (!question.trim()) return
    const q = question.trim()
    setQuestion('')
    setChat((prev) => [...prev, { role: 'user', text: q }])
    setAdviceBusy(true)
    try {
      const r: AdviceOut = await aiApi.advice(q)
      setChat((prev) => [...prev, {
        role: 'bot', text: r.answer, basis: r.basis, warnings: r.warnings,
        disclaimer: r.disclaimer, mode: r.mode,
      }])
    } catch (err) {
      setChat((prev) => [...prev, { role: 'bot', text: isApiError(err) ? err.message : '回答失败，请稍后重试' }])
    } finally {
      setAdviceBusy(false)
    }
  }

  const draftSource: 'nlp' | 'voice' | 'ocr' = tab === 'text' ? 'nlp' : tab === 'voice' ? 'voice' : 'ocr'

  return (
    <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr)' }}>
      {/* 草稿识别入口 */}
      <Card title="AI 智能记账">
        <div className="flex gap8 mb16">
          <button className={`chip ${tab === 'text' ? 'active' : ''}`} onClick={() => setTab('text')}>⌨️ 自然语言</button>
          <button className={`chip ${tab === 'voice' ? 'active' : ''}`} onClick={() => setTab('voice')}>🎤 语音</button>
          <button className={`chip ${tab === 'image' ? 'active' : ''}`} onClick={() => setTab('image')}>🖼️ 图片识别</button>
        </div>

        {tab === 'text' && (
          <div className="chat-input-row">
            <input className="input" value={nlText} maxLength={500}
                   placeholder='例如：今天奶茶18，打车25；昨天收到生活费2000'
                   onChange={(e) => setNlText(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter' && !nlBusy) void parseNl() }} />
            <button className="btn btn-primary" disabled={nlBusy || !nlText.trim()}
                    onClick={() => void parseNl()}>
              {nlBusy ? '解析中…' : '解析'}
            </button>
          </div>
        )}

        {tab === 'voice' && (
          <div className="flex gap8 wrap">
            {recording ? (
              <button className="btn btn-danger" onClick={stopRecording}>⏹ 停止录音</button>
            ) : (
              <button className="btn btn-primary" disabled={speechBusy}
                      onClick={() => void startRecording()}>
                {speechBusy ? '识别中…' : '🎤 开始录音'}
              </button>
            )}
            <span className="muted small" style={{ alignSelf: 'center' }}>
              录音后自动转写并生成草稿；需浏览器麦克风权限
            </span>
          </div>
        )}
        {transcript && (
          <div className="notice-info mt16">语音转写：{transcript}</div>
        )}

        {tab === 'image' && (
          <div className="flex gap8 wrap">
            <button className="btn btn-primary" disabled={imageBusy}
                    onClick={() => fileInputRef.current?.click()}>
              {imageBusy ? '识别中…' : '🖼️ 选择图片'}
            </button>
            <input ref={fileInputRef} type="file" accept="image/*" hidden
                   onChange={(e) => void onImagePicked(e)} />
            <span className="muted small" style={{ alignSelf: 'center' }}>
              上传小票/账单截图，识别结果生成可编辑草稿
            </span>
          </div>
        )}
        {ocrText && (
          <div className="notice-info mt16">图片识别文本：{ocrText}</div>
        )}

        {notice && <div className="notice-demo mt16">{notice}</div>}

        {/* 草稿区 */}
        {drafts.length > 0 && (
          <div className="mt16">
            <h3 className="card-title mb16">待确认草稿（{drafts.length} 条）</h3>
            {drafts.map((d, i) => (
              <div key={i} className="draft-item">
                <select className="select" style={{ width: 90 }}
                        value={d.bill_type}
                        onChange={(e) => {
                          const t = e.target.value as 'income' | 'expense'
                          const first = catsFor(t)[0]
                          updateDraft(i, {
                            bill_type: t,
                            category_id: first?.id ?? null,
                            category_name: first?.name ?? '',
                          })
                        }}>
                  <option value="expense">支出</option>
                  <option value="income">收入</option>
                </select>
                <span className="draft-amount">
                  <input className="input" inputMode="decimal"
                         value={centsToYuan(d.amount_cents)}
                         onChange={(e) => {
                           const cents = yuanToCents(sanitizeYuanInput(e.target.value))
                           if (cents !== null) updateDraft(i, { amount_cents: cents })
                         }} />
                </span>
                <select className="select" style={{ width: 120 }}
                        value={d.category_id ?? ''}
                        onChange={(e) => {
                          const cat = categories.find((c) => c.id === Number(e.target.value))
                          updateDraft(i, { category_id: cat?.id ?? null, category_name: cat?.name ?? '' })
                        }}>
                  {catsFor(d.bill_type).map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <input className="input" type="datetime-local" style={{ width: 190 }}
                       value={d.occurred_at ? isoToLocalInput(d.occurred_at) : ''}
                       onChange={(e) => updateDraft(i, { occurred_at: e.target.value ? localInputToIso(e.target.value) : null })} />
                <input className="input" style={{ flex: 1, minWidth: 120 }} maxLength={200}
                       value={d.note ?? ''} placeholder="备注"
                       onChange={(e) => updateDraft(i, { note: e.target.value })} />
                <button className="btn-inline danger draft-remove"
                        onClick={() => setDrafts((prev) => prev.filter((_, x) => x !== i))}>
                  移除
                </button>
              </div>
            ))}
            <div className="flex gap8 mt16">
              <button className="btn btn-primary" disabled={confirmBusy}
                      onClick={() => void confirmDrafts(draftSource)}>
                {confirmBusy ? '入账中…' : `确认全部入账（${drafts.length} 笔）`}
              </button>
              <button className="btn btn-outline" disabled={confirmBusy}
                      onClick={() => { setDrafts([]); setNotice(''); setTranscript(''); setOcrText('') }}>
                放弃草稿
              </button>
            </div>
            <p className="small muted mt8">确认前不会写入任何账单；取消/失败均不影响已有数据。</p>
          </div>
        )}
      </Card>

      {/* 消费建议对话 */}
      <Card title="AI 消费建议">
        <div className="chat mb16" style={{ maxHeight: 420, overflowY: 'auto' }}>
          {chat.length === 0 && (
            <Empty text="问点关于消费的问题吧，例如：「这个月还能买500元的鞋吗」" />
          )}
          {chat.map((m, i) => (
            <div key={i} className={`chat-msg ${m.role === 'user' ? 'chat-user' : 'chat-bot'}`}>
              {m.mode && (
                <span className={`badge ${m.mode === 'demo' ? 'badge-warning' : 'badge-success'}`} style={{ marginBottom: 6 }}>
                  {m.mode === 'demo' ? '演示模式' : '外部服务'}
                </span>
              )}
              <div>{m.text}</div>
              {m.basis && m.basis.length > 0 && (
                <div className="mt8 small" style={{ opacity: 0.9 }}>
                  <div className="strong">依据（均来自系统实际数据）：</div>
                  {m.basis.map((b, x) => (
                    <div key={x}>· {b.label}：{b.value}</div>
                  ))}
                </div>
              )}
              {m.warnings && m.warnings.length > 0 && m.warnings.map((w, x) => (
                <div key={x} className="small mt8" style={{ opacity: 0.9 }}>⚠️ {w}</div>
              ))}
              {m.disclaimer && <div className="small mt8" style={{ opacity: 0.7 }}>{m.disclaimer}</div>}
            </div>
          ))}
          {adviceBusy && (
            <div className="chat-msg chat-bot"><Loading text="思考中…" /></div>
          )}
          <div ref={chatEndRef} />
        </div>
        <div className="chat-input-row">
          <input className="input" value={question} maxLength={500}
                 placeholder="输入你的财务问题…"
                 onChange={(e) => setQuestion(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter' && !adviceBusy) void askAdvice() }} />
          <button className="btn btn-primary" disabled={adviceBusy || !question.trim()}
                  onClick={() => void askAdvice()}>提问</button>
        </div>
      </Card>
    </div>
  )
}
