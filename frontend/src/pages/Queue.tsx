import { useQuery } from '@tanstack/react-query'
import { queueApi } from '@/api/queueApi'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

export default function Queue() {
  const { data: depths = [], isLoading } = useQuery({
    queryKey: ['queue-depths'],
    queryFn: queueApi.allDepths,
    refetchInterval: 5_000,
  })

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
              <div key={d.instance_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between">
                <span className="font-heading font-[800] text-white">{d.slug}</span>
                <span className={`font-mono font-[900] text-lg ${d.depth > 10 ? 'text-red-400' : d.depth > 3 ? 'text-yellow-400' : 'text-green-400'}`}>
                  {d.depth}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
