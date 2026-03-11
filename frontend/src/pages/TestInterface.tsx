import { useState, useMemo, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { instancesApi } from '@/api/instancesApi'
import axios, { AxiosError } from 'axios'
import { Send, Settings2, Trash2, Bot, User, ChevronDown, ChevronUp } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
}

function normalizeTokenInput(input: string): string {
  return input
    .replace(/^Bearer\s+/i, '')
    .replace(/\s+/g, '')
    .replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200D\uFEFF]/g, '')
    .replace(/[^\x20-\x7E]/g, '')
    .trim()
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'

  if (isError) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] bg-red-950/60 border border-red-800/60 rounded-2xl rounded-tl-sm px-4 py-3">
          <p className="font-mono text-xs text-red-400 whitespace-pre-wrap break-words">{msg.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex items-end gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mb-0.5
        ${isUser ? 'bg-indigo-600' : 'bg-gray-700'}`}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-gray-300" />}
      </div>
      <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm font-sans font-[400] leading-relaxed whitespace-pre-wrap break-words
        ${isUser
          ? 'bg-indigo-600 text-white rounded-br-sm'
          : 'bg-gray-800 text-gray-100 rounded-bl-sm border border-gray-700/50'}`}>
        {msg.content}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center">
        <Bot size={14} className="text-gray-300" />
      </div>
      <div className="bg-gray-800 border border-gray-700/50 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center">
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  )
}

export default function TestInterface() {
  const { data: instances = [] } = useQuery({ queryKey: ['instances'], queryFn: instancesApi.list })
  const REQUEST_TIMEOUT_MS = 120_000

  const [selectedSlug, setSelectedSlug] = useState('')
  const [rawToken, setRawToken] = useState('')
  const [systemMsg, setSystemMsg] = useState('You are a helpful assistant.')
  const [maxTokens, setMaxTokens] = useState('512')
  const [settingsOpen, setSettingsOpen] = useState(true)

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const selectedInstance = useMemo(
    () => instances.find((i) => i.slug === selectedSlug),
    [instances, selectedSlug],
  )

  const runningInstances = instances.filter((i) => i.status === 'running')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [input])

  const canSend = !!selectedSlug && !!rawToken && !!input.trim() && !loading

  const handleSend = async () => {
    if (!canSend) return
    const normalizedToken = normalizeTokenInput(rawToken)
    if (!normalizedToken) {
      setMessages((prev) => [...prev, { role: 'error', content: 'Invalid token: remove hidden/special characters and try again.' }])
      return
    }
    const userContent = input.trim()
    setInput('')

    const newUserMsg: Message = { role: 'user', content: userContent }
    const updatedMessages = [...messages, newUserMsg]
    setMessages(updatedMessages)
    setLoading(true)

    try {
      const endpointPath = `/v1/${selectedSlug}/chat/completions`
      const apiMessages: { role: string; content: string }[] = []
      if (systemMsg.trim()) apiMessages.push({ role: 'system', content: systemMsg.trim() })
      // include full history
      updatedMessages.filter((m) => m.role !== 'error').forEach((m) =>
        apiMessages.push({ role: m.role, content: m.content })
      )

      const requestBody = {
        model: selectedInstance?.model_id ?? '',
        messages: apiMessages,
        max_tokens: parseInt(maxTokens, 10) || 512,
        stream: false,
      }

      const requestConfig = {
        timeout: REQUEST_TIMEOUT_MS,
        headers: {
          Authorization: `Bearer ${normalizedToken}`,
          'Content-Type': 'application/json',
        },
      }

      const response = await axios.post(endpointPath, requestBody, requestConfig)
      const data = response.data

      const assistantContent = data.choices?.[0]?.message?.content ?? JSON.stringify(data, null, 2)
      setMessages((prev) => [...prev, { role: 'assistant', content: assistantContent }])
    } catch (err: unknown) {
      let detail = String(err)
      if (err instanceof AxiosError) {
        if (err.code === 'ECONNABORTED') {
          detail = `Request timed out after ${Math.round(REQUEST_TIMEOUT_MS / 1000)}s`
        }
        const d =
          err.response?.data?.detail ??
          err.response?.data?.message ??
          err.response?.data?.error ??
          err.message
        detail = typeof d === 'string' ? d : JSON.stringify(d, null, 2)
      }
      setMessages((prev) => [...prev, { role: 'error', content: detail }])
    } finally {
      setLoading(false)
      textareaRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => setMessages([])

  return (
    <div className="flex flex-col h-full">
      {/* ── Header / Settings ─────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-gray-800 bg-gray-950/80 backdrop-blur">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <h1 className="font-heading font-[800] text-lg text-white">Chat Interface</h1>
            {selectedInstance && (
              <span className="font-mono text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                {selectedInstance.display_name} · {selectedInstance.model_id}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                title="Clear conversation"
                className="p-2 text-gray-500 hover:text-red-400 rounded-lg transition-colors"
              >
                <Trash2 size={15} />
              </button>
            )}
            <button
              onClick={() => setSettingsOpen((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-sans font-[700] text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <Settings2 size={13} />
              Settings
              {settingsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>
        </div>

        {settingsOpen && (
          <div className="px-6 pb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 border-t border-gray-800/60 pt-3">
            {/* Instance */}
            <div>
              <label className="block text-[10px] font-mono font-[600] text-gray-500 uppercase mb-1">Instance</label>
              <select
                value={selectedSlug}
                onChange={(e) => { setSelectedSlug(e.target.value); clearChat() }}
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-white font-mono font-[300] text-xs focus:outline-none focus:border-indigo-500"
              >
                <option value="">Select instance…</option>
                {runningInstances.map((i) => (
                  <option key={i.id} value={i.slug}>{i.display_name}</option>
                ))}
              </select>
              {runningInstances.length === 0 && (
                <p className="text-[10px] text-yellow-500 mt-1">No running instances.</p>
              )}
            </div>

            {/* Token */}
            <div>
              <label className="block text-[10px] font-mono font-[600] text-gray-500 uppercase mb-1">API Token</label>
              <input
                type="password"
                value={rawToken}
                onChange={(e) => setRawToken(e.target.value)}
                placeholder="Paste raw token…"
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-white font-mono font-[300] text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* System message */}
            <div>
              <label className="block text-[10px] font-mono font-[600] text-gray-500 uppercase mb-1">System Message</label>
              <input
                type="text"
                value={systemMsg}
                onChange={(e) => setSystemMsg(e.target.value)}
                placeholder="You are a helpful assistant."
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-white font-mono font-[300] text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Max tokens */}
            <div>
              <label className="block text-[10px] font-mono font-[600] text-gray-500 uppercase mb-1">Max Tokens</label>
              <input
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)}
                min={1}
                max={8192}
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-white font-mono font-[300] text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Messages area ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 opacity-40">
            <Bot size={40} className="text-gray-500" />
            <p className="font-sans font-[300] text-sm text-gray-400">
              {!selectedSlug || !rawToken
                ? 'Configure an instance and API token above to start chatting.'
                : 'Send a message to start the conversation.'}
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ─────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-gray-800 bg-gray-950/80 backdrop-blur px-4 py-3">
        <div className="flex items-end gap-2 max-w-4xl mx-auto">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              !selectedSlug || !rawToken
                ? 'Set instance and token first…'
                : 'Message… (Enter to send, Shift+Enter for newline)'
            }
            disabled={!selectedSlug || !rawToken || loading}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white font-sans font-[400] text-sm resize-none focus:outline-none focus:border-indigo-500 disabled:opacity-40 leading-relaxed"
            style={{ minHeight: '48px', maxHeight: '160px' }}
          />
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="flex-shrink-0 w-11 h-11 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors"
          >
            <Send size={16} className="text-white" />
          </button>
        </div>
        <p className="text-center text-[10px] text-gray-600 mt-1.5 font-sans">
          Conversation history is included in every request.
        </p>
      </div>
    </div>
  )
}
