import { useQuery } from '@tanstack/react-query'
import { metricsApi } from '@/api/metricsApi'
import { instancesApi } from '@/api/instancesApi'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs font-mono font-[600] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="font-heading font-[800] text-3xl text-white">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const { data: summary } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: metricsApi.summary,
    refetchInterval: 15_000,
  })
  const { data: instances } = useQuery({
    queryKey: ['instances'],
    queryFn: instancesApi.list,
    refetchInterval: 15_000,
  })

  const running = instances?.filter((i) => i.status === 'running').length ?? 0
  const total = instances?.length ?? 0
  const totalRequests = summary?.total_requests_1h ?? 0

  const chartData =
    summary?.instances.map((m) => ({
      slug: m.slug,
      requests: m.requests_total_1h,
      latency: m.avg_latency_ms,
    })) ?? []

  return (
    <div className="p-8">
      <h1 className="font-heading font-[800] text-2xl text-white mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard label="Instances Running" value={`${running} / ${total}`} />
        <StatCard label="Requests (1h)" value={totalRequests} />
        <StatCard label="Active Queues" value={summary?.instances.filter((m) => m.queue_depth > 0).length ?? 0} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
        <h2 className="font-heading font-[800] text-base text-gray-300 mb-4">Requests per Instance (1h)</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="slug" tick={{ fontFamily: 'JetBrains Mono', fontSize: 11, fill: '#9ca3af' }} />
              <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 11, fill: '#9ca3af' }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', fontFamily: 'JetBrains Mono', fontSize: 12 }}
              />
              <Bar dataKey="requests" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm font-sans font-[200] text-gray-500">No data yet — start an instance!</p>
        )}
      </div>
    </div>
  )
}
