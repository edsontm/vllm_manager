import { useState, useRef, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { instancesApi } from '@/api/instancesApi'
import { queueApi } from '@/api/queueApi'
import { Play, Square, AlertTriangle, KeyRound } from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface RequestResult {
  queueWait: number | null    // ms in queue (from result payload)
  processingTime: number | null // e2el - queueWait
  e2el: number                 // ms total
  outputTokens: number
  error: string | null
  sampleError?: string
}

interface AggStats {
  mean: number
  p50: number
  p95: number
  p99: number
  min: number
  max: number
}

const REQUEST_TIMEOUT_MS = 120_000
const RUN_TIMEOUT_MS = 10 * 60_000
const PREFLIGHT_TIMEOUT_MS = 60_000
const QUEUE_POLL_INTERVAL_MS = 1_000

// ── Math helpers ──────────────────────────────────────────────────────────────

function pct(sorted: number[], p: number): number {
  if (!sorted.length) return 0
  const idx = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.max(0, idx)]
}

function aggStats(values: number[]): AggStats {
  if (!values.length) return { mean: 0, p50: 0, p95: 0, p99: 0, min: 0, max: 0 }
  const s = [...values].sort((a, b) => a - b)
  const mean = s.reduce((a, b) => a + b, 0) / s.length
  return { mean, p50: pct(s, 50), p95: pct(s, 95), p99: pct(s, 99), min: s[0], max: s[s.length - 1] }
}

function fmt(ms: number): string {
  if (ms >= 1000) return (ms / 1000).toFixed(2) + ' s'
  return ms.toFixed(1) + ' ms'
}

function fmtN(n: number, dec = 2): string {
  return n.toFixed(dec)
}

function normalizeTokenInput(input: string): string {
  return input
    .replace(/^Bearer\s+/i, '')
    .replace(/\s+/g, '')
    .replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200D\uFEFF]/g, '')
    .replace(/[^\x20-\x7E]/g, '')
    .trim()
}

// ── Single non-streaming request ─────────────────────────────────────────────

async function runRequest(
  slug: string,
  modelId: string,
  token: string,
  messages: { role: string; content: string }[],
  maxTokens: number,
  signal: AbortSignal,
): Promise<RequestResult> {
  const start = performance.now()

  const timeoutCtrl = new AbortController()
  const timeoutId = window.setTimeout(() => timeoutCtrl.abort(), REQUEST_TIMEOUT_MS)
  const onExternalAbort = () => timeoutCtrl.abort()
  signal.addEventListener('abort', onExternalAbort, { once: true })

  try {
    const endpointPath = `/v1/${slug}/chat/completions`

    const res = await fetch(endpointPath, {
      method: 'POST',
      signal: timeoutCtrl.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ model: modelId, messages, max_tokens: maxTokens, stream: false }),
    })

    const e2el = performance.now() - start

    if (!res.ok) {
      const errText = await res.text().catch(() => `HTTP ${res.status}`)
      let detail = errText
      try { const j = JSON.parse(errText); detail = j?.detail ?? j?.message ?? j?.error ?? errText } catch {}
      return { queueWait: null, processingTime: null, e2el, outputTokens: 0, error: `HTTP ${res.status}: ${detail}`, sampleError: `HTTP ${res.status}: ${detail}` }
    }

    const body = await res.json()

    // Extract queue_wait_ms injected by the proxy
    const queueWait: number | null = typeof body?.queue_wait_ms === 'number' ? body.queue_wait_ms : null
    const processingTime: number | null = queueWait !== null ? Math.max(0, e2el - queueWait) : null

    // Extract token count from usage
    let outputTokens = 0
    const completionTokens = body?.usage?.completion_tokens
    if (typeof completionTokens === 'number' && completionTokens > 0) {
      outputTokens = completionTokens
    } else {
      const messageContent = body?.choices?.[0]?.message?.content
      const text = typeof messageContent === 'string' ? messageContent.trim() : ''
      outputTokens = text ? Math.max(1, text.split(/\s+/).length) : 0
    }

    // Check for error in body
    if (body?.error || body?.detail) {
      const errMsg = body?.detail ?? body?.message ?? body?.error
      return { queueWait, processingTime, e2el, outputTokens, error: String(errMsg), sampleError: String(errMsg) }
    }

    return { queueWait, processingTime, e2el, outputTokens, error: null }
  } catch (err: unknown) {
    if ((err as any)?.name === 'AbortError') {
      if (signal.aborted) return { queueWait: null, processingTime: null, e2el: 0, outputTokens: 0, error: 'aborted' }
      return { queueWait: null, processingTime: null, e2el: performance.now() - start, outputTokens: 0, error: 'timeout', sampleError: `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s` }
    }
    const msg = String(err)
    console.error('[StressTest] runRequest threw:', err)
    return { queueWait: null, processingTime: null, e2el: performance.now() - start, outputTokens: 0, error: msg, sampleError: msg }
  } finally {
    window.clearTimeout(timeoutId)
    signal.removeEventListener('abort', onExternalAbort)
  }
}

// ── Concurrency pool ──────────────────────────────────────────────────────────

async function runPool(
  concurrency: number,
  total: number,
  task: (idx: number) => Promise<RequestResult>,
  onResult: (r: RequestResult, done: number) => void,
  signal: AbortSignal,
  taskTimeoutMs = REQUEST_TIMEOUT_MS + 5_000,
): Promise<void> {
  let started = 0
  let completed = 0

  async function worker() {
    while (started < total && !signal.aborted) {
      const idx = started++
      const result = await new Promise<RequestResult>((resolve) => {
        const timer = window.setTimeout(() => {
          resolve({
            queueWait: null,
            processingTime: null,
            e2el: taskTimeoutMs,
            outputTokens: 0,
            error: 'timeout',
            sampleError: `Request timed out after ${Math.round(taskTimeoutMs / 1000)}s`,
          })
        }, taskTimeoutMs)

        task(idx)
          .then((r) => resolve(r))
          .catch((err: unknown) => {
            resolve({
              queueWait: null,
              processingTime: null,
              e2el: 0,
              outputTokens: 0,
              error: String(err),
              sampleError: String(err),
            })
          })
          .finally(() => window.clearTimeout(timer))
      })
      if (signal.aborted && result.error === 'aborted') return
      completed++
      onResult(result, completed)
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, total) }, worker))
}

// ── Live aggregate ────────────────────────────────────────────────────────────

interface LiveStats {
  done: number
  errors: number
  queueWaits: number[]
  processingTimes: number[]
  e2els: number[]
  totalOutputTokens: number
  wallStart: number
  wallEnd: number | null
  sampleError: string | null
}

function computeMetrics(s: LiveStats) {
  const elapsed = ((s.wallEnd ?? performance.now()) - s.wallStart) / 1000  // seconds
  return {
    queueWait: aggStats(s.queueWaits),
    processingTime: aggStats(s.processingTimes),
    e2el: aggStats(s.e2els),
    rps: s.done / (elapsed || 1),
    tps: s.totalOutputTokens / (elapsed || 1),
    errorRate: s.done > 0 ? (s.errors / s.done) * 100 : 0,
    elapsed,
  }
}

// ── UI components ─────────────────────────────────────────────────────────────

function StatCard({ label, stats, unit = 'ms' }: { label: string; stats: AggStats; unit?: string }) {
  const rows: [string, number][] = [
    ['Mean', stats.mean],
    ['P50', stats.p50],
    ['P95', stats.p95],
    ['P99', stats.p99],
    ['Min', stats.min],
    ['Max', stats.max],
  ]
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs font-mono font-[600] text-gray-500 uppercase mb-3">{label}</p>
      <div className="space-y-1">
        {rows.map(([name, val]) => (
          <div key={name} className="flex justify-between items-baseline">
            <span className="text-xs text-gray-500 font-mono">{name}</span>
            <span className={`text-sm font-mono font-[600] ${name === 'P95' || name === 'P99' ? 'text-yellow-400' : 'text-white'}`}>
              {unit === 'ms' ? fmt(val) : fmtN(val)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScalarCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
      <p className="text-xs font-mono font-[600] text-gray-500 uppercase mb-2">{label}</p>
      <p className="text-2xl font-mono font-[800] text-white">{value}</p>
      {sub && <p className="text-xs text-gray-600 font-mono mt-1">{sub}</p>}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const DEFAULT_PROMPT = 'Write a short poem about the ocean.'
const DEFAULT_SYSTEM = 'You are a helpful assistant.'

export default function StressTest() {
  const { data: instances = [] } = useQuery({ queryKey: ['instances'], queryFn: instancesApi.list })
  const navigate = useNavigate()

  // Config
  const [selectedSlug, setSelectedSlug] = useState('')
  const [rawToken, setRawToken] = useState('')
  const [systemMsg, setSystemMsg] = useState(DEFAULT_SYSTEM)
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [concurrency, setConcurrency] = useState('10')
  const [totalRequests, setTotalRequests] = useState('50')
  const [maxTokens, setMaxTokens] = useState('128')

  // State
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [liveStats, setLiveStats] = useState<LiveStats | null>(null)
  const [preflight, setPreflight] = useState<{ ok: boolean; msg: string } | null>(null)
  const [queueDepth, setQueueDepth] = useState<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const selectedInstance = instances.find((i) => i.slug === selectedSlug)
  const runningInstances = instances.filter((i) => i.status === 'running')
  const total = parseInt(totalRequests, 10) || 50
  const conc = Math.min(parseInt(concurrency, 10) || 10, total)
  const maxTok = parseInt(maxTokens, 10) || 128
  const tokenMissing = !rawToken.trim()

  // Poll queue depth while running
  useEffect(() => {
    if (!running || !selectedInstance) {
      setQueueDepth(null)
      return
    }
    let cancelled = false
    const poll = async () => {
      try {
        const data = await queueApi.allDepths()
        if (!cancelled) {
          const entry = data.find((d) => d.instance_id === selectedInstance.id)
          setQueueDepth(entry?.depth ?? null)
        }
      } catch {}
    }
    poll()
    const interval = window.setInterval(poll, QUEUE_POLL_INTERVAL_MS)
    return () => { cancelled = true; window.clearInterval(interval) }
  }, [running, selectedInstance])

  const handleRun = useCallback(async () => {
    if (!selectedSlug || !selectedInstance || !rawToken.trim()) return
    const token = normalizeTokenInput(rawToken)
    if (!token) {
      setPreflight({ ok: false, msg: 'Invalid token: remove hidden/special characters and try again.' })
      return
    }

    const messages: { role: string; content: string }[] = []
    if (systemMsg.trim()) messages.push({ role: 'system', content: systemMsg.trim() })
    messages.push({ role: 'user', content: prompt })

    // Pre-flight: one non-streaming request to verify auth + model before the pool
    setPreflight(null)
    try {
      const endpointPath = `/v1/${selectedInstance.slug}/chat/completions`
      const requestInit: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ model: selectedInstance.model_id, messages, max_tokens: 8, stream: false }),
      }

      const preflightCtrl = new AbortController()
      const preflightTimeoutId = window.setTimeout(() => preflightCtrl.abort(), PREFLIGHT_TIMEOUT_MS)

      const pf = await fetch(endpointPath, { ...requestInit, signal: preflightCtrl.signal })
      window.clearTimeout(preflightTimeoutId)

      const pfText = await pf.text()
      if (!pf.ok) {
        let detail = pfText
        try { const j = JSON.parse(pfText); detail = j?.detail ?? j?.message ?? j?.error ?? pfText } catch {}
        setPreflight({ ok: false, msg: `HTTP ${pf.status}: ${detail}` })
        return
      }
      setPreflight({ ok: true, msg: 'Connection OK' })
    } catch (e) {
      if ((e as any)?.name === 'AbortError') {
        setPreflight({ ok: false, msg: `Pre-flight timed out after ${PREFLIGHT_TIMEOUT_MS / 1000}s` })
        return
      }
      setPreflight({ ok: false, msg: `Network error: ${String(e)}` })
      return
    }

    const ctrl = new AbortController()
    abortRef.current = ctrl
    setRunning(true)
    setProgress(0)

    const wallStart = performance.now()
    const stats: LiveStats = {
      done: 0, errors: 0,
      queueWaits: [], processingTimes: [], e2els: [],
      totalOutputTokens: 0,
      wallStart, wallEnd: null,
      sampleError: null,
    }
    setLiveStats({ ...stats })

    const runTimeoutId = window.setTimeout(() => {
      if (!ctrl.signal.aborted) ctrl.abort()
    }, RUN_TIMEOUT_MS)

    try {
      await runPool(
        conc,
        total,
        (_idx) => runRequest(selectedInstance.slug, selectedInstance.model_id, token, messages, maxTok, ctrl.signal),
        (result, done) => {
          if (result.error !== 'aborted' && result.e2el > 0) {
            stats.e2els.push(result.e2el)
          }
          if (result.error && result.error !== 'aborted') {
            stats.errors++
            if (!stats.sampleError && result.sampleError) stats.sampleError = result.sampleError
          } else if (!result.error) {
            if (result.queueWait !== null) stats.queueWaits.push(result.queueWait)
            if (result.processingTime !== null) stats.processingTimes.push(result.processingTime)
            stats.totalOutputTokens += result.outputTokens
          }
          stats.done = done
          setProgress(Math.round((done / total) * 100))
          setLiveStats({ ...stats })
        },
        ctrl.signal,
      )
    } catch (err: unknown) {
      const msg = String(err)
      stats.errors++
      if (!stats.sampleError) stats.sampleError = msg
      setLiveStats({ ...stats })
    } finally {
      window.clearTimeout(runTimeoutId)
      stats.wallEnd = performance.now()
      setLiveStats({ ...stats })
      setRunning(false)
      abortRef.current = null
    }
  }, [selectedSlug, selectedInstance, rawToken, systemMsg, prompt, conc, total, maxTok])

  const handleStop = () => {
    abortRef.current?.abort()
    setRunning(false)
  }

  const metrics = liveStats ? computeMetrics(liveStats) : null

  return (
    <div className="p-8 max-w-5xl">
      <h1 className="font-heading font-[800] text-2xl text-white mb-1">Stress Test</h1>
      <p className="text-sm text-gray-500 font-sans font-[200] mb-8">
        Measure queue wait, processing time, E2E latency, RPS, TPS and error rate under load.
      </p>

      {/* Config */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 space-y-4">
        <h2 className="font-heading font-[700] text-white text-sm uppercase tracking-wide">Configuration</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Instance</label>
            <select
              value={selectedSlug}
              onChange={(e) => setSelectedSlug(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500"
            >
              <option value="">Select running instance…</option>
              {runningInstances.map((i) => (
                <option key={i.id} value={i.slug}>{i.display_name} — {i.model_id}</option>
              ))}
            </select>
            {runningInstances.length === 0 && (
              <p className="text-[10px] text-yellow-500 mt-1">No running instances.</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">
              API Token <span className="normal-case text-red-500">required</span>
            </label>
            <input
              type="password"
              value={rawToken}
              onChange={(e) => setRawToken(e.target.value)}
              placeholder="Paste a token from the Tokens page…"
              className={`w-full bg-gray-800 border rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500 ${tokenMissing ? 'border-red-700' : 'border-gray-700'}`}
            />
            {tokenMissing && (
              <button
                onClick={() => navigate('/tokens')}
                className="flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 transition-colors"
              >
                <KeyRound size={10} /> Create a token on the Tokens page
              </button>
            )}
          </div>

          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Concurrent Users</label>
            <input type="number" min="1" max="200" value={concurrency} onChange={(e) => setConcurrency(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500" />
            <p className="text-[10px] text-gray-600 mt-0.5">Number of parallel in-flight requests</p>
          </div>

          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Total Requests</label>
            <input type="number" min="1" max="2000" value={totalRequests} onChange={(e) => setTotalRequests(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500" />
            <p className="text-[10px] text-gray-600 mt-0.5">Total requests to send across all workers</p>
          </div>

          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Max Output Tokens</label>
            <input type="number" min="1" max="4096" value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500" />
          </div>

          <div>
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">System Message</label>
            <input value={systemMsg} onChange={(e) => setSystemMsg(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500" />
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Prompt</label>
            <textarea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-indigo-500 resize-y" />
            <p className="text-[10px] text-gray-600 mt-0.5">Same prompt is sent for every request. Keep it consistent for fair comparison.</p>
          </div>
        </div>

        <div className="flex flex-col gap-2 pt-2">
          <div className="flex items-center gap-4">
            {running ? (
              <button onClick={handleStop} className="flex items-center gap-2 bg-red-700 hover:bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-sans font-[700] transition-colors">
                <Square size={14} /> Stop
              </button>
            ) : (
              <button
                onClick={handleRun}
                disabled={!selectedSlug || tokenMissing}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-sans font-[700] transition-colors"
              >
                <Play size={14} /> Run Test ({conc} concurrent × {total} requests)
              </button>
            )}
          </div>
          {preflight && (
            <p className={`text-xs font-mono ${preflight.ok ? 'text-green-400' : 'text-red-400'}`}>
              {preflight.ok ? '✓' : '✗'} Pre-flight: {preflight.msg}
            </p>
          )}
        </div>
      </div>

      {/* Progress */}
      {(running || liveStats) && (
        <div className="mb-6">
          <div className="flex justify-between text-xs font-mono text-gray-500 mb-1">
            <span>{liveStats?.done ?? 0} / {total} requests</span>
            <span className="flex items-center gap-3">
              {running && queueDepth !== null && (
                <span className="text-indigo-400">Queue depth: {queueDepth}</span>
              )}
              <span>{progress}%</span>
            </span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${running ? 'bg-indigo-500' : 'bg-green-500'}`}
              style={{ width: `${progress}%` }}
            />
          </div>
          {running && (
            <p className="text-[10px] text-gray-600 font-mono mt-1 animate-pulse">Running… metrics update live.</p>
          )}
        </div>
      )}

      {/* Results */}
      {metrics && liveStats && liveStats.done > 0 && (
        <>
          {/* Scalar cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <ScalarCard
              label="Requests / sec"
              value={fmtN(metrics.rps)}
              sub={`${liveStats.done} completed in ${fmtN(metrics.elapsed)}s`}
            />
            <ScalarCard
              label="Output Tokens / sec"
              value={fmtN(metrics.tps)}
              sub={`${liveStats.totalOutputTokens} tokens total`}
            />
            <ScalarCard
              label="Error Rate"
              value={fmtN(metrics.errorRate) + '%'}
              sub={`${liveStats.errors} / ${liveStats.done} failed`}
            />
            <ScalarCard
              label="Max Concurrency"
              value={String(conc)}
              sub={`${total} total requests`}
            />
          </div>

          {/* Error warning */}
          {liveStats.errors > 0 && (
            <div className="flex flex-col gap-1 bg-red-950/40 border border-red-800 rounded-xl p-4 mb-6 font-mono">
              <div className="flex items-start gap-2 text-sm text-red-300">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <span>
                  {liveStats.errors} request{liveStats.errors > 1 ? 's' : ''} failed.
                  {metrics.errorRate >= 5 && ' High error rate — model may be overloaded or rate-limited.'}
                </span>
              </div>
              {liveStats.sampleError && (
                <p className="text-xs text-red-400 mt-1 pl-5 break-all">Sample error: {liveStats.sampleError}</p>
              )}
            </div>
          )}

          {/* Latency cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <StatCard
              label="Queue Wait Time"
              stats={metrics.queueWait}
            />
            <StatCard
              label="Processing Time"
              stats={metrics.processingTime}
            />
            <StatCard
              label="End-to-End Latency (E2EL)"
              stats={metrics.e2el}
            />
          </div>

          {/* Tail latency summary table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
            <p className="text-xs font-mono font-[600] text-gray-500 uppercase mb-3">Tail Latency Summary</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-gray-600 border-b border-gray-800">
                    <th className="text-left py-1 pr-6">Metric</th>
                    <th className="text-right py-1 pr-6">P50</th>
                    <th className="text-right py-1 pr-6">P95</th>
                    <th className="text-right py-1 pr-6">P99</th>
                    <th className="text-right py-1 pr-6">Max</th>
                    <th className="text-right py-1">Mean</th>
                  </tr>
                </thead>
                <tbody>
                  {([
                    ['Queue Wait', metrics.queueWait],
                    ['Processing', metrics.processingTime],
                    ['E2EL', metrics.e2el],
                  ] as [string, AggStats][]).map(([name, s]) => (
                    <tr key={name} className="border-b border-gray-800/50">
                      <td className="py-1.5 pr-6 text-gray-400">{name}</td>
                      <td className="text-right pr-6 text-white">{fmt(s.p50)}</td>
                      <td className="text-right pr-6 text-yellow-400">{fmt(s.p95)}</td>
                      <td className="text-right pr-6 text-orange-400">{fmt(s.p99)}</td>
                      <td className="text-right pr-6 text-red-400">{fmt(s.max)}</td>
                      <td className="text-right text-gray-300">{fmt(s.mean)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap gap-x-6 gap-y-1 text-[10px] font-mono text-gray-600">
              <span>Queue Wait — time spent in Redis queue before worker picks up the job</span>
              <span>Processing — actual vLLM inference time (E2EL minus queue wait)</span>
              <span>E2EL — End-to-End Latency: total request time including queue</span>
              <span className="text-yellow-700">P95 / P99 = tail latency (slowest 5% / 1%)</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
