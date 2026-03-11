import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

type Tab = 'curl' | 'python' | 'javascript'

interface Props {
  slug: string
  curl: string
  python: string
  javascript: string
}

const TAB_LABELS: { key: Tab; label: string }[] = [
  { key: 'curl', label: 'cURL' },
  { key: 'python', label: 'Python' },
  { key: 'javascript', label: 'JavaScript' },
]

export default function CodeExample({ slug, curl, python, javascript }: Props) {
  const [active, setActive] = useState<Tab>('python')
  const [copied, setCopied] = useState(false)
  const baseUrl = (import.meta.env.VITE_BASE_URL as string | undefined)?.replace(/\/$/, '') || window.location.origin

  const code = { curl, python, javascript }[active]

  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-xl border border-gray-700 overflow-hidden">
      {/* Tab bar */}
      <div className="flex bg-gray-800 border-b border-gray-700">
        {TAB_LABELS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`px-4 py-2 text-xs font-mono font-[600] transition-colors ${
              active === key
                ? 'text-white bg-gray-900 border-b-2 border-indigo-500'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={copy}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-mono font-[300] text-gray-400 hover:text-white transition-colors"
        >
          {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* Code area */}
      <pre className="bg-gray-900 p-4 text-xs font-mono font-[300] text-gray-200 overflow-x-auto leading-relaxed whitespace-pre-wrap">
        {code}
      </pre>

      {/* Endpoint URL note */}
      <div className="bg-gray-800/50 px-4 py-2 border-t border-gray-700">
        <p className="text-xs font-mono font-[300] text-gray-500">
          Endpoint:{' '}
          <span className="text-indigo-400">
            {baseUrl}/v1/{slug}/
          </span>
        </p>
      </div>
    </div>
  )
}
