import { useQuery, useQueryClient } from '@tanstack/react-query'
import { queueApi, QueueJob } from '@/api/queueApi'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { useState } from 'react'

const priorityBadge = (priority: string) => {
  if (priority.startsWith('high'))
    return <span className="px-1.5 py-0.5 text-[10px] font-mono font-[700] rounded bg-red-900/50 text-red-400 border border-red-800">HIGH</span>
  if (priority.startsWith('low'))
    return <span className="px-1.5 py-0.5 text-[10px] font-mono font-[700] rounded bg-gray-700/50 text-gray-400 border border-gray-600">LOW</span>
  return <span className="px-1.5 py-0.5 text-[10px] font-mono font-[700] rounded bg-yellow-900/50 text-yellow-400 border border-yellow-800">MED</span>
}

function formatWait(enqueuedAt: number) {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - enqueuedAt))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs}s`
}

function JobsTable({ instanceId }: { instanceId: number }) {
  const { data: jobs = [] } = useQuery({
    queryKey: ['queue-jobs', instanceId],
    queryFn: () => queueApi.listJobs(instanceId),
    refetchInterval: 5_000,
  })

  if (jobs.length === 0) {
    return <p className="text-gray-600 font-sans font-[200] text-sm py-2 pl-2">Queue is empty.</p>
  }

  return (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            <th className="text-left py-1 px-2 font-[600]">Priority</th>
            <th className="text-left py-1 px-2 font-[600]">Model</th>
            <th className="text-left py-1 px-2 font-[600]">Prompt</th>
            <th className="text-right py-1 px-2 font-[600]">Max Tokens</th>
            <th className="text-right py-1 px-2 font-[600]">Wait</th>
            <th className="text-left py-1 px-2 font-[600]">Method / Path</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job: QueueJob) => (
            <tr key={job.job_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
              <td className="py-1.5 px-2">{priorityBadge(job.priority)}</td>
              <td className="py-1.5 px-2 text-gray-300">{job.model ?? '—'}</td>
              <td className="py-1.5 px-2 text-gray-400 max-w-[260px] truncate" title={job.prompt_preview ?? ''}>
                {job.prompt_preview ?? '—'}
              </td>
              <td className="py-1.5 px-2 text-gray-300 text-right">{job.max_tokens ?? '—'}</td>
              <td className="py-1.5 px-2 text-amber-400 text-right">{formatWait(job.enqueue_time)}</td>
              <td className="py-1.5 px-2 text-gray-500">{job.method} {job.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Queue() {
  const queryClient = useQueryClient()
  const [clearing, setClearing] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const { data: depths = [], isLoading } = useQuery({
    queryKey: ['queue-depths'],
    queryFn: queueApi.allDepths,
    refetchInterval: 5_000,
  })

  const handleClear = async (instanceId: number) => {
    setClearing(instanceId)
    try {
      await queueApi.clear(instanceId)
      queryClient.invalidateQueries({ queryKey: ['queue-depths'] })
      queryClient.invalidateQueries({ queryKey: ['queue-jobs', instanceId] })
    } finally {
      setClearing(null)
    }
  }

  const toggleExpand = (instanceId: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(instanceId)) next.delete(instanceId)
      else next.add(instanceId)
      return next
    })
  }

  return (
    <div className="p-8">
      <h1 className="font-heading font-[800] text-2xl text-white mb-6">Queue Status</h1>

      {isLoading ? (
        <p className="text-gray-500 font-sans font-[200]">Loading…</p>
      ) : depths.length === 0 ? (
        <p className="text-gray-500 font-sans font-[200]">No instances to monitor.</p>
      ) : (
        <>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
            <h2 className="font-heading font-[800] text-base text-gray-300 mb-4">Queue Depths</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={depths}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="slug" tick={{ fontFamily: 'JetBrains Mono', fontSize: 11, fill: '#9ca3af' }} />
                <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 11, fill: '#9ca3af' }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', fontFamily: 'JetBrains Mono', fontSize: 12 }} />
                <Bar dataKey="depth" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-3">
            {depths.map((d) => (
              <div key={d.instance_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => toggleExpand(d.instance_id)}
                      className="text-gray-500 hover:text-gray-300 transition-colors text-sm font-mono"
                      title={expanded.has(d.instance_id) ? 'Collapse' : 'Expand'}
                    >
                      {expanded.has(d.instance_id) ? '▼' : '▶'}
                    </button>
                    <span className="font-heading font-[800] text-white">{d.slug}</span>
                    <button
                      onClick={() => handleClear(d.instance_id)}
                      disabled={clearing === d.instance_id || d.depth === 0}
                      className="px-2 py-0.5 text-xs font-mono font-[600] rounded bg-red-900/50 text-red-400 border border-red-800 hover:bg-red-800/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {clearing === d.instance_id ? 'Clearing...' : 'Clear'}
                    </button>
                  </div>
                  <span className={`font-mono font-[900] text-lg ${d.depth > 10 ? 'text-red-400' : d.depth > 3 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {d.depth}
                  </span>
                </div>
                {expanded.has(d.instance_id) && <JobsTable instanceId={d.instance_id} />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
