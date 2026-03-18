import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { instancesApi, type InstanceRead, type InstanceCreate } from '@/api/instancesApi'
import { metricsApi, type GpuInfo, type InstanceMetrics, type MetricPoint } from '@/api/metricsApi'
import { useAuthStore } from '@/store'
import CodeExample from '@/components/CodeExample'
import { Play, Square, RefreshCw, Trash2, Plus, ChevronDown, Pencil, Cpu, FileText } from 'lucide-react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

const toGb = (mb: number) => (mb / 1024).toFixed(1)

function ResourceBar({ used, total, label }: { used: number; total: number; label: string }) {
  const safeTotal = total > 0 ? total : used
  const pct = safeTotal > 0 ? Math.min(100, Math.round((used / safeTotal) * 100)) : 0
  const color = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-indigo-500'

  return (
    <div className="flex items-center gap-2 w-full">
      <span className="font-mono text-[10px] text-gray-500 whitespace-nowrap">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[10px] text-gray-400 whitespace-nowrap">
        {toGb(used)} / {toGb(safeTotal)} GB <span className="text-gray-600">({pct}%)</span>
      </span>
    </div>
  )
}

// ── GPU VRAM panel ────────────────────────────────────────────────────────────

function GpuBar({ gpu }: { gpu: GpuInfo }) {
  const pct = Math.round((gpu.memory_used_mb / gpu.memory_total_mb) * 100)
  const color = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="flex-1 min-w-[180px]">
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-[10px] text-gray-400 truncate max-w-[130px]" title={gpu.name}>
          GPU {gpu.index} <span className="text-gray-600">{gpu.name}</span>
        </span>
        <span className="font-mono text-[10px] text-gray-300 ml-2 whitespace-nowrap">
          {toGb(gpu.memory_used_mb)} / {toGb(gpu.memory_total_mb)} GB
        </span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between mt-0.5">
        <span className="font-mono text-[9px] text-gray-600">{pct}% used</span>
        {gpu.utilization_pct != null && (
          <span className="font-mono text-[9px] text-gray-600">GPU {gpu.utilization_pct}%</span>
        )}
      </div>
    </div>
  )
}

function GpuPanel({ gpus }: { gpus?: GpuInfo[] }) {
  if (!gpus || gpus.length === 0) return null

  const totalMb = gpus.reduce((s, g) => s + g.memory_total_mb, 0)
  const usedMb = gpus.reduce((s, g) => s + g.memory_used_mb, 0)
  const freeMb = totalMb - usedMb

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Cpu size={14} className="text-indigo-400" />
          <span className="font-heading font-[800] text-sm text-white">GPU VRAM</span>
        </div>
        <div className="flex gap-4 text-[11px] font-mono">
          <span className="text-gray-400">Total <span className="text-white">{toGb(totalMb)} GB</span></span>
          <span className="text-green-400">Free <span className="text-white">{toGb(freeMb)} GB</span></span>
          <span className="text-yellow-400">Used <span className="text-white">{toGb(usedMb)} GB</span></span>
        </div>
      </div>
      <div className="flex flex-wrap gap-4">
        {gpus.map((gpu) => <GpuBar key={gpu.index} gpu={gpu} />)}
      </div>
    </div>
  )
}

function ResourceSummaryPanel({
  gpus,
  totalInstanceGpuUsedMb,
  totalInstanceRamUsedMb,
  systemMemoryTotalMb,
  systemMemoryUsedMb,
  systemMemoryFreeMb,
}: {
  gpus?: GpuInfo[]
  totalInstanceGpuUsedMb: number
  totalInstanceRamUsedMb: number
  systemMemoryTotalMb: number | null
  systemMemoryUsedMb: number | null
  systemMemoryFreeMb: number | null
}) {
  const totalGpuMb = (gpus ?? []).reduce((sum, gpu) => sum + gpu.memory_total_mb, 0)
  const usedGpuMb = (gpus ?? []).reduce((sum, gpu) => sum + gpu.memory_used_mb, 0)
  const freeGpuMb = Math.max(totalGpuMb - usedGpuMb, 0)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading font-[800] text-sm text-white">System Memory Overview</h2>
          <p className="font-sans font-[200] text-xs text-gray-500">Live host availability and aggregate instance consumption.</p>
        </div>
        <div className="flex flex-wrap gap-4 text-[11px] font-mono">
          <span className="text-indigo-300">Models VRAM <span className="text-white">{toGb(totalInstanceGpuUsedMb)} GB</span></span>
          <span className="text-cyan-300">Models RAM <span className="text-white">{toGb(totalInstanceRamUsedMb)} GB</span></span>
          <span className="text-green-400">Free VRAM <span className="text-white">{toGb(freeGpuMb)} GB</span></span>
          {systemMemoryFreeMb != null && <span className="text-green-400">Free RAM <span className="text-white">{toGb(systemMemoryFreeMb)} GB</span></span>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-950/60 border border-gray-800 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase text-gray-500">Host VRAM</span>
            <span className="font-mono text-[10px] text-gray-600">{toGb(usedGpuMb)} used · {toGb(freeGpuMb)} free</span>
          </div>
          {totalGpuMb > 0 ? <ResourceBar used={usedGpuMb} total={totalGpuMb} label="VRAM" /> : <p className="text-xs text-gray-600">No GPU data available.</p>}
        </div>

        <div className="bg-gray-950/60 border border-gray-800 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase text-gray-500">Host RAM</span>
            {systemMemoryTotalMb != null && systemMemoryUsedMb != null ? (
              <span className="font-mono text-[10px] text-gray-600">{toGb(systemMemoryUsedMb)} used · {toGb(systemMemoryFreeMb ?? 0)} free</span>
            ) : (
              <span className="font-mono text-[10px] text-gray-600">Unavailable</span>
            )}
          </div>
          {systemMemoryTotalMb != null && systemMemoryUsedMb != null ? (
            <ResourceBar used={systemMemoryUsedMb} total={systemMemoryTotalMb} label="RAM" />
          ) : (
            <p className="text-xs text-gray-600">System RAM metrics unavailable.</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Instance VRAM bar ─────────────────────────────────────────────────────────

function MachineGpuUsage({ gpus }: { gpus: GpuInfo[] }) {
  if (gpus.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] text-gray-500 uppercase">Machine GPU VRAM</span>
        <span className="font-mono text-[10px] text-gray-600">
          {gpus.length} GPU{gpus.length === 1 ? '' : 's'} available
        </span>
      </div>
      <div className="flex flex-wrap gap-3">
        {gpus.map((gpu) => <GpuBar key={gpu.index} gpu={gpu} />)}
      </div>
    </div>
  )
}

// ── Log panel ─────────────────────────────────────────────────────────────────

function LogPanel({ instanceId, trigger }: { instanceId: number; trigger: number }) {
  const [lines, setLines] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLines([])
    const cancel = instancesApi.streamLogs(instanceId, (line) => {
      setLines((prev) => [...prev, line])
    })
    return cancel
  }, [instanceId, trigger])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'instant' })
  }, [lines])

  return (
    <div className="bg-black rounded-lg font-mono text-xs text-green-300 p-3 h-64 overflow-y-auto whitespace-pre-wrap break-all">
      {lines.length === 0 && <span className="text-gray-600">Waiting for logs…</span>}
      {lines.map((line, i) => (
        <div key={i}>{line}</div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

// ── Shared create / edit form ─────────────────────────────────────────────────

type FormState = {
  slug: string
  display_name: string
  model_id: string
  description: string
  gpu_ids: string
  gpu_memory_utilization: string
  max_model_len: string
  tensor_parallel_size: string
  dtype: string
  quantization: string
  extra_args: string  // JSON text
}

const DTYPE_OPTIONS = ['auto', 'float16', 'bfloat16', 'float32']
const QUANT_OPTIONS = ['', 'awq', 'gptq', 'squeezellm', 'fp8']
const DEFAULT_CREATE_EXTRA_ARGS: Record<string, string> = {
  '--enable-prefix-caching': 'true',
}

function toFormState(instance?: InstanceRead | null, prefill?: { model_id: string; slug: string; display_name: string }): FormState {
  if (instance) {
    return {
      slug: instance.slug,
      display_name: instance.display_name,
      model_id: instance.model_id,
      description: instance.description ?? '',
      gpu_ids: (instance.gpu_ids ?? [0]).join(', '),
      gpu_memory_utilization: String(instance.gpu_memory_utilization),
      max_model_len: instance.max_model_len != null ? String(instance.max_model_len) : '',
      tensor_parallel_size: String(instance.tensor_parallel_size),
      dtype: instance.dtype,
      quantization: instance.quantization ?? '',
      extra_args: instance.extra_args ? JSON.stringify(instance.extra_args, null, 2) : '',
    }
  }
  return {
    slug: prefill?.slug ?? '',
    display_name: prefill?.display_name ?? '',
    model_id: prefill?.model_id ?? '',
    description: '',
    gpu_ids: '0',
    gpu_memory_utilization: '0.9',
    max_model_len: '',
    tensor_parallel_size: '1',
    dtype: 'auto',
    quantization: '',
    extra_args: JSON.stringify(DEFAULT_CREATE_EXTRA_ARGS, null, 2),
  }
}

function toApiBody(form: FormState): Partial<InstanceCreate> {
  let parsedExtra: Record<string, string> | undefined
  const trimmedExtra = form.extra_args.trim()
  if (trimmedExtra) {
    try { parsedExtra = JSON.parse(trimmedExtra) } catch { parsedExtra = undefined }
  }
  return {
    slug: form.slug,
    display_name: form.display_name,
    model_id: form.model_id,
    description: form.description || undefined,
    gpu_ids: form.gpu_ids.split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n)),
    gpu_memory_utilization: parseFloat(form.gpu_memory_utilization) || 0.9,
    max_model_len: form.max_model_len ? parseInt(form.max_model_len, 10) : undefined,
    tensor_parallel_size: parseInt(form.tensor_parallel_size, 10) || 1,
    dtype: form.dtype || 'auto',
    quantization: form.quantization || undefined,
    extra_args: parsedExtra,
  }
}

interface InstanceFormProps {
  instance?: InstanceRead       // undefined = create mode
  prefill?: { model_id: string; slug: string; display_name: string }
  onClose: () => void
  onSaved?: (saved: InstanceRead) => void
}

function InstanceForm({ instance, prefill, onClose, onSaved }: InstanceFormProps) {
  const qc = useQueryClient()
  const isEdit = !!instance
  const [form, setForm] = useState<FormState>(() => toFormState(instance, prefill))
  const [extraArgsError, setExtraArgsError] = useState('')
  const [andRestart, setAndRestart] = useState(false)

  const set = <K extends keyof FormState>(k: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }))

  const invalidate = () => qc.invalidateQueries({ queryKey: ['instances'] })

  const { mutate: createMut, isPending: creating } = useMutation({
    mutationFn: () => instancesApi.create(toApiBody(form) as InstanceCreate),
    onSuccess: (saved) => { invalidate(); onSaved?.(saved); onClose() },
  })

  const { mutate: updateMut, isPending: updating } = useMutation({
    mutationFn: () => instancesApi.update(instance!.id, toApiBody(form)),
    onSuccess: (saved) => {
      invalidate()
      onSaved?.(saved)
      if (andRestart) {
        instancesApi.restart(instance!.id).then(invalidate).catch(() => invalidate())
      }
      onClose()
    },
  })

  const isPending = creating || updating

  const handleSubmit = () => {
    if (form.extra_args.trim()) {
      try { JSON.parse(form.extra_args) }
      catch { setExtraArgsError('Invalid JSON'); return }
    }
    setExtraArgsError('')
    isEdit ? updateMut() : createMut()
  }

  const inputCls = 'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono font-[300] text-sm focus:outline-none focus:border-indigo-500'
  const labelCls = 'block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase'
  const hintCls = 'text-[10px] text-gray-600 mt-0.5'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
      <h2 className="font-heading font-[800] text-white mb-5">{isEdit ? `Edit — ${instance!.display_name}` : 'New Instance'}</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Slug */}
        <div>
          <label className={labelCls}>Slug</label>
          <input value={form.slug} onChange={set('slug')} disabled={isEdit} className={inputCls + (isEdit ? ' opacity-50 cursor-not-allowed' : '')} placeholder="my-model" />
          <p className={hintCls}>URL-safe identifier (lowercase a-z, 0-9, hyphens). Cannot change after creation.</p>
        </div>

        {/* Display name */}
        <div>
          <label className={labelCls}>Display Name</label>
          <input value={form.display_name} onChange={set('display_name')} className={inputCls} placeholder="My Model" />
        </div>

        {/* Model ID */}
        <div className="md:col-span-2">
          <label className={labelCls}>Model ID</label>
          <input value={form.model_id} onChange={set('model_id')} className={inputCls} placeholder="Qwen/Qwen3-8B" />
          <p className={hintCls}>HuggingFace model repo (e.g. Qwen/Qwen3-8B, mistralai/Mistral-7B-v0.1)</p>
        </div>

        {/* Description */}
        <div className="md:col-span-2">
          <label className={labelCls}>Description <span className="normal-case text-gray-600">(optional)</span></label>
          <input value={form.description} onChange={set('description')} className={inputCls} placeholder="Short description shown to users" />
        </div>

        {/* GPU IDs */}
        <div>
          <label className={labelCls}>GPU IDs</label>
          <input value={form.gpu_ids} onChange={set('gpu_ids')} className={inputCls} placeholder="0" />
          <p className={hintCls}>Comma-separated GPU indices (e.g. 0 or 0,1 for multi-GPU)</p>
        </div>

        {/* GPU memory utilization */}
        <div>
          <label className={labelCls}>GPU Memory Utilization</label>
          <input type="number" min="0.01" max="1" step="0.01" value={form.gpu_memory_utilization} onChange={set('gpu_memory_utilization')} className={inputCls} />
          <p className={hintCls}>Fraction of GPU VRAM for KV cache (0.01–1.0). Lower when sharing a GPU.</p>
        </div>

        {/* Max model len */}
        <div>
          <label className={labelCls}>Max Model Len <span className="normal-case text-gray-600">(optional)</span></label>
          <input type="number" min="1" value={form.max_model_len} onChange={set('max_model_len')} className={inputCls} placeholder="Use model default" />
          <p className={hintCls}>Override the model's max context length in tokens.</p>
        </div>

        {/* Tensor parallel size */}
        <div>
          <label className={labelCls}>Tensor Parallel Size</label>
          <input type="number" min="1" max="8" value={form.tensor_parallel_size} onChange={set('tensor_parallel_size')} className={inputCls} />
          <p className={hintCls}>Number of GPUs to shard the model across (must match number of GPU IDs).</p>
        </div>

        {/* dtype */}
        <div>
          <label className={labelCls}>dtype</label>
          <select value={form.dtype} onChange={set('dtype')} className={inputCls}>
            {DTYPE_OPTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <p className={hintCls}>Weight dtype. "auto" uses the model's native dtype.</p>
        </div>

        {/* Quantization */}
        <div>
          <label className={labelCls}>Quantization <span className="normal-case text-gray-600">(optional)</span></label>
          <select value={form.quantization} onChange={set('quantization')} className={inputCls}>
            {QUANT_OPTIONS.map((q) => <option key={q} value={q}>{q || '— none —'}</option>)}
          </select>
          <p className={hintCls}>Quantization method already applied to the model weights.</p>
        </div>

        {/* Extra args */}
        <div className="md:col-span-2">
          <label className={labelCls}>Extra vLLM Args <span className="normal-case text-gray-600">(optional JSON)</span></label>
          <textarea
            rows={4}
            value={form.extra_args}
            onChange={set('extra_args')}
            className={inputCls + ' resize-y font-mono' + (extraArgsError ? ' border-red-600' : '')}
            placeholder={'{\n  "--enable-prefix-caching": "true"\n}'}
          />
          {extraArgsError
            ? <p className="text-[10px] text-red-400 mt-0.5">{extraArgsError}</p>
            : <p className={hintCls}>JSON object of extra flags passed to vllm serve. Boolean flags use "true" as value.</p>
          }
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mt-6">
        {isEdit && (
          <label className="flex items-center gap-2 text-xs text-gray-400 font-mono cursor-pointer select-none">
            <input
              type="checkbox"
              checked={andRestart}
              onChange={(e) => setAndRestart(e.target.checked)}
              className="accent-indigo-500"
            />
            Restart after save
            {instance!.status === 'running' && <span className="text-yellow-500">(instance is running)</span>}
          </label>
        )}
        <button
          onClick={handleSubmit}
          disabled={isPending}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-sans font-[700] transition-colors"
        >
          {isPending ? (isEdit ? 'Saving…' : 'Creating…') : (isEdit ? 'Save Changes' : 'Create Instance')}
        </button>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-sm font-sans font-[200] transition-colors">Cancel</button>
      </div>
    </div>
  )
}

// ── Status ────────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  running: 'text-green-400',
  stopped: 'text-gray-400',
  starting: 'text-yellow-400',
  error: 'text-red-400',
  pulling: 'text-blue-400',
}

// ── Requests chart ────────────────────────────────────────────────────────────

function RequestsChart({ instanceId }: { instanceId: number }) {
  const { data: history = [] } = useQuery<MetricPoint[]>({
    queryKey: ['metrics-history', instanceId],
    queryFn: () => metricsApi.history(instanceId),
    refetchInterval: 60_000,
    retry: false,
  })

  const chartData = history.map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    count: p.count,
  }))

  if (chartData.length === 0) {
    return (
      <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 h-[120px] flex items-center justify-center">
        <span className="text-[11px] font-mono text-gray-600">No request data (last 6h)</span>
      </div>
    )
  }

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-lg p-3">
      <span className="text-[10px] font-mono text-gray-500 uppercase mb-1 block">Requests (15 min buckets, last 6h)</span>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: '#6b7280' }}
            tickLine={false}
            axisLine={{ stroke: '#374151' }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: '#6b7280' }}
            tickLine={false}
            axisLine={{ stroke: '#374151' }}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: '#9ca3af' }}
            itemStyle={{ color: '#818cf8' }}
          />
          <Area
            type="monotone"
            dataKey="count"
            name="Requests"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Instance row ──────────────────────────────────────────────────────────────

function InstanceRow({ instance, metrics, machineGpus = [] }: { instance: InstanceRead; metrics?: InstanceMetrics; machineGpus?: GpuInfo[] }) {
  const qc = useQueryClient()
  const isAdmin = useAuthStore((s) => s.currentUser?.role === 'admin')
  const [showExamples, setShowExamples] = useState(false)
  const [examples, setExamples] = useState<{ curl: string; python: string; javascript: string } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showLogs, setShowLogs] = useState(false)
  const [logTrigger, setLogTrigger] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [showEdit, setShowEdit] = useState(false)

  const openLogs = () => {
    setShowLogs(true)
    setLogTrigger((t) => t + 1)
  }

  const invalidate = () => qc.invalidateQueries({ queryKey: ['instances'] })
  const onError = (err: unknown) => {
    const msg = (err as any)?.response?.data?.detail ?? (err as any)?.message ?? 'Unknown error'
    setActionError(String(msg))
  }

  const { mutate: start, isPending: starting } = useMutation({ mutationFn: () => instancesApi.start(instance.id), onSuccess: invalidate, onError })
  const { mutate: stop, isPending: stopping } = useMutation({ mutationFn: () => instancesApi.stop(instance.id), onSuccess: invalidate, onError })
  const { mutate: restart, isPending: restarting } = useMutation({
    mutationFn: () => instancesApi.restart(instance.id),
    onSuccess: () => {
      invalidate()
      openLogs()
    },
    onError,
  })
  const { mutate: deleteInst, isPending: deleting } = useMutation({ mutationFn: () => instancesApi.delete(instance.id), onSuccess: invalidate, onError })

  const loadExamples = async () => {
    if (!examples) {
      const ex = await instancesApi.connectionExamples(instance.id)
      setExamples(ex)
    }
    setShowExamples((v) => !v)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-heading font-[800] text-white">{instance.display_name}</h3>
          <p className="font-mono font-[300] text-xs text-gray-500">{instance.slug}</p>
          <p className="font-sans font-[200] text-sm text-gray-400 mt-1">{instance.model_id}</p>
          {instance.description && (
            <p className="font-sans font-[200] text-xs text-gray-600 mt-0.5">{instance.description}</p>
          )}
        </div>
        {instance.status === 'error' ? (
          <button
            type="button"
            onClick={openLogs}
            className={`font-mono font-[600] text-xs uppercase ${STATUS_COLOR[instance.status] ?? 'text-gray-400'} hover:text-red-300 underline decoration-dotted underline-offset-2 transition-colors`}
          >
            {instance.status}
          </button>
        ) : (
          <span className={`font-mono font-[600] text-xs uppercase ${STATUS_COLOR[instance.status] ?? 'text-gray-400'}`}>
            {instance.status}
          </span>
        )}
      </div>

      {/* Config summary */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-gray-600">
        <span>GPU {(instance.gpu_ids ?? []).join(',') || '0'}</span>
        <span>mem {Math.round(instance.gpu_memory_utilization * 100)}%</span>
        <span>tp {instance.tensor_parallel_size}</span>
        <span>dtype {instance.dtype}</span>
        {instance.quantization && <span>quant {instance.quantization}</span>}
        {instance.max_model_len && <span>ctx {instance.max_model_len}</span>}
        {instance.extra_args && Object.keys(instance.extra_args).length > 0 && (
          <span>{Object.entries(instance.extra_args).map(([k, v]) => `${k}${v && v !== 'true' ? ' ' + v : ''}`).join(' ')}</span>
        )}
      </div>

      {/* VRAM bar (running instances with live data) */}
      {instance.status === 'running' && metrics?.gpu_memory_used_mb != null && metrics?.gpu_memory_total_mb != null && (
        <ResourceBar used={metrics.gpu_memory_used_mb} total={metrics.gpu_memory_total_mb} label="Observed VRAM" />
      )}

      {instance.status === 'running' && metrics?.system_memory_used_mb != null && metrics?.system_memory_total_mb != null && (
        <ResourceBar used={metrics.system_memory_used_mb} total={metrics.system_memory_total_mb} label="Container RAM" />
      )}

      {instance.status === 'running' && machineGpus.length > 0 && (
        <MachineGpuUsage gpus={machineGpus} />
      )}

      {instance.status === 'running' && (
        <RequestsChart instanceId={instance.id} />
      )}

      {/* Error message from crashed container */}
      {instance.status === 'error' && instance.error_message && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={openLogs}
            className="w-full text-left cursor-pointer text-[11px] font-mono text-red-400 hover:text-red-300 transition-colors flex items-center gap-1"
          >
            <span>⚠</span>
            Container error — click to view logs
          </button>
          <pre className="bg-black/60 border border-red-900/40 rounded-lg p-3 font-mono text-[11px] text-red-300 whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
            {instance.error_message.trim()}
          </pre>
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center">
        {isAdmin && (
          <>
            <button onClick={() => { setActionError(null); openLogs(); start() }} disabled={starting} className="flex items-center gap-1 text-xs bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white px-3 py-1 rounded transition-colors">
              <Play size={12} /> {starting ? 'Starting…' : 'Start'}
            </button>
            <button onClick={() => { setActionError(null); openLogs(); stop() }} disabled={stopping} className="flex items-center gap-1 text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white px-3 py-1 rounded transition-colors">
              <Square size={12} /> {stopping ? 'Stopping…' : 'Stop'}
            </button>
            <button onClick={() => { setActionError(null); openLogs(); restart() }} disabled={restarting} className="flex items-center gap-1 text-xs bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 text-white px-3 py-1 rounded transition-colors">
              <RefreshCw size={12} /> {restarting ? 'Restarting…' : 'Restart'}
            </button>
            <button onClick={() => { setActionError(null); setShowEdit((v) => !v) }} className="flex items-center gap-1 text-xs bg-indigo-800 hover:bg-indigo-700 text-white px-3 py-1 rounded transition-colors">
              <Pencil size={12} /> Edit
            </button>
            <button onClick={() => { setActionError(null); openLogs() }} className="flex items-center gap-1 text-xs bg-slate-800 hover:bg-slate-700 text-white px-3 py-1 rounded transition-colors">
              <FileText size={12} /> Logs
            </button>
            {confirmDelete ? (
              <span className="flex items-center gap-2 ml-auto">
                <span className="text-xs text-red-400 font-mono">Delete?</span>
                <button onClick={() => { setConfirmDelete(false); deleteInst() }} disabled={deleting} className="text-xs bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white px-2 py-1 rounded transition-colors">
                  {deleting ? 'Deleting…' : 'Yes'}
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-xs text-gray-400 hover:text-white transition-colors">No</button>
              </span>
            ) : (
              <button onClick={() => { setActionError(null); setConfirmDelete(true) }} className="flex items-center gap-1 text-xs bg-red-800 hover:bg-red-700 text-white px-3 py-1 rounded transition-colors ml-auto">
                <Trash2 size={12} /> Delete
              </button>
            )}
          </>
        )}
        <button onClick={loadExamples} className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 ml-auto transition-colors">
          <ChevronDown size={12} className={showExamples ? 'rotate-180' : ''} /> Examples
        </button>
      </div>

      {actionError && (
        <div className="text-xs text-red-400 bg-red-950/40 border border-red-800 rounded px-3 py-2 font-mono break-all">
          {actionError}
        </div>
      )}

      {showEdit && isAdmin && (
        <InstanceForm
          instance={instance}
          onClose={() => setShowEdit(false)}
        />
      )}

      {showLogs && (
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-[600] text-gray-500 uppercase">Container logs</span>
            <button onClick={() => setShowLogs(false)} className="text-gray-600 hover:text-gray-300 text-xs font-mono transition-colors">✕ close</button>
          </div>
          <LogPanel instanceId={instance.id} trigger={logTrigger} />
        </div>
      )}

      {showExamples && examples && (
        <CodeExample
          slug={instance.slug}
          curl={examples.curl}
          python={examples.python}
          javascript={examples.javascript}
        />
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Instances() {
  const location = useLocation()
  const prefill = (location.state as any)?.prefill as { model_id: string; slug: string; display_name: string } | undefined

  const {
    data: instances = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['instances'],
    queryFn: instancesApi.list,
    refetchInterval: 10_000,
    retry: false,
    refetchOnWindowFocus: false,
  })
  const { data: metricsSummary } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: metricsApi.summary,
    refetchInterval: 5_000,
    retry: false,
  })
  const { data: gpuSummary } = useQuery({
    queryKey: ['metrics-gpus'],
    queryFn: metricsApi.gpus,
    refetchInterval: 3_000,
    retry: false,
  })
  const isAdmin = useAuthStore((s) => s.currentUser?.role === 'admin')
  const [showCreate, setShowCreate] = useState(false)

  const metricsById = Object.fromEntries(
    (metricsSummary?.instances ?? []).map((m) => [m.instance_id, m])
  )

  useEffect(() => {
    if (prefill && isAdmin) setShowCreate(true)
  }, [prefill, isAdmin])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-heading font-[800] text-2xl text-white">Instances</h1>
        {isAdmin && (
          <button onClick={() => setShowCreate((v) => !v)} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-sans font-[700] transition-colors">
            <Plus size={14} /> New Instance
          </button>
        )}
      </div>

      <ResourceSummaryPanel
        gpus={gpuSummary?.gpus}
        totalInstanceGpuUsedMb={metricsSummary?.total_instance_gpu_memory_used_mb ?? 0}
        totalInstanceRamUsedMb={metricsSummary?.total_instance_system_memory_used_mb ?? 0}
        systemMemoryTotalMb={gpuSummary?.system_memory_total_mb ?? null}
        systemMemoryUsedMb={gpuSummary?.system_memory_used_mb ?? null}
        systemMemoryFreeMb={gpuSummary?.system_memory_free_mb ?? null}
      />

      <GpuPanel gpus={gpuSummary?.gpus} />

      {showCreate && isAdmin && (
        <InstanceForm prefill={prefill} onClose={() => setShowCreate(false)} />
      )}

      {isLoading ? (
        <p className="text-gray-500 font-sans font-[200]">Loading…</p>
      ) : isError ? (
        <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-4 space-y-2">
          <p className="text-red-300 font-mono text-xs break-all">
            Failed to load instances: {(error as any)?.message ?? 'Unknown error'}
          </p>
          <button
            onClick={() => refetch()}
            className="text-xs bg-red-800 hover:bg-red-700 text-white px-3 py-1 rounded transition-colors"
          >
            Retry
          </button>
        </div>
      ) : instances.length === 0 ? (
        <p className="text-gray-500 font-sans font-[200]">No instances yet.</p>
      ) : (
        <div className="space-y-4">
          {instances.map((inst) => (
            <InstanceRow
              key={inst.id}
              instance={inst}
              metrics={metricsById[inst.id]}
              machineGpus={gpuSummary?.gpus ?? []}
            />
          ))}
        </div>
      )}
    </div>
  )
}
