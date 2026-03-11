import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tokensApi, type TokenCreateResponse, type TokenRead, type TokenUpdate } from '@/api/tokensApi'
import { instancesApi, type InstanceRead } from '@/api/instancesApi'
import { usersApi, type UserRead } from '@/api/usersApi'
import { useAuthStore } from '@/store'
import { Plus, Trash2, Copy, Check, Pencil, ToggleLeft, ToggleRight, X, Save } from 'lucide-react'

// ─── Priority badge ───────────────────────────────────────────────────────────

const PRIORITY_LABELS: Record<string, string> = {
  high_priority: 'High Priority',
  medium_priority: 'Medium Priority',
  low_priority: 'Low Priority',
}

const PRIORITY_CLASSES: Record<string, string> = {
  high_priority: 'bg-green-950 border-green-700 text-green-300',
  medium_priority: 'bg-yellow-950 border-yellow-700 text-yellow-300',
  low_priority: 'bg-gray-800 border-gray-600 text-gray-400',
}

function PriorityBadge({ role }: { role: string | null }) {
  if (!role) return null
  return (
    <span className={`text-xs font-mono font-[500] border rounded px-1.5 py-0.5 ${PRIORITY_CLASSES[role] ?? PRIORITY_CLASSES['low_priority']}`}>
      {PRIORITY_LABELS[role] ?? role}
    </span>
  )
}

/**
 * Inline read-only field with an adjacent copy button.
 * Copies by selecting the real <input> element — works on HTTP and HTTPS,
 * all modern browsers, without hidden-element tricks.
 */
function CopyableField({ value, className = '' }: { value: string; className?: string }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  const copy = () => {
    const input = inputRef.current
    if (!input) return
    input.select()
    input.setSelectionRange(0, input.value.length) // iOS support
    let ok = false
    try { ok = document.execCommand('copy') } catch { /* ignore */ }
    // Best-effort modern API (HTTPS only).
    navigator.clipboard?.writeText(value).catch(() => {})
    setState(ok ? 'copied' : 'failed')
    setTimeout(() => setState('idle'), 2000)
  }

  return (
    <div className={`flex items-center gap-0 rounded overflow-hidden border border-gray-700 bg-gray-800 ${className}`}>
      <input
        ref={inputRef}
        readOnly
        value={value}
        onClick={(e) => (e.target as HTMLInputElement).select()}
        className="flex-1 bg-transparent px-3 py-2 font-mono text-sm text-white focus:outline-none cursor-text min-w-0"
      />
      <button
        onClick={copy}
        title={state === 'failed' ? 'Copy failed — select manually' : 'Copy to clipboard'}
        className={`px-3 py-2 shrink-0 border-l border-gray-700 transition-colors ${
          state === 'copied'
            ? 'text-green-400 bg-green-950'
            : state === 'failed'
            ? 'text-red-400 bg-red-950'
            : 'text-gray-400 hover:text-white hover:bg-gray-700'
        }`}
      >
        {state === 'copied' ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  )
}

/** Small inline copy-icon button for short strings. */
function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  const copy = () => {
    let ok = false
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      ok = document.execCommand('copy')
      document.body.removeChild(ta)
    } catch { /* ignore */ }
    navigator.clipboard?.writeText(text).catch(() => {})
    setState(ok ? 'copied' : 'failed')
    setTimeout(() => setState('idle'), 2000)
  }

  return (
    <button
      onClick={copy}
      title={state === 'failed' ? 'Copy failed' : 'Copy to clipboard'}
      className={`p-1 transition-colors ${
        state === 'failed' ? 'text-red-400' : 'text-gray-400 hover:text-white'
      }`}
    >
      {state === 'copied' ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
    </button>
  )
}

// ─── Multi-select chip helpers ────────────────────────────────────────────────

function InstanceChips({
  selected,
  instances,
  onChange,
}: {
  selected: number[]
  instances: InstanceRead[]
  onChange: (ids: number[]) => void
}) {
  const toggle = (id: number) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <div className="flex flex-wrap gap-2">
      {instances.map((inst) => {
        const active = selected.includes(inst.id)
        return (
          <button
            key={inst.id}
            type="button"
            onClick={() => toggle(inst.id)}
            className={`px-2 py-1 rounded text-xs font-mono font-[400] border transition-colors ${
              active
                ? 'bg-indigo-700 border-indigo-500 text-white'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-indigo-600'
            }`}
          >
            {inst.display_name}
            <span className="ml-1 text-gray-500">#{inst.id}</span>
          </button>
        )
      })}
      {instances.length === 0 && (
        <span className="text-gray-600 text-xs font-mono">No instances available</span>
      )}
    </div>
  )
}

function ModelChips({
  selected,
  models,
  onChange,
}: {
  selected: string[]
  models: string[]
  onChange: (ids: string[]) => void
}) {
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <div className="flex flex-wrap gap-2">
      {models.map((m) => {
        const active = selected.includes(m)
        return (
          <button
            key={m}
            type="button"
            onClick={() => toggle(m)}
            className={`px-2 py-1 rounded text-xs font-mono font-[400] border transition-colors ${
              active
                ? 'bg-purple-700 border-purple-500 text-white'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-purple-600'
            }`}
          >
            {m}
          </button>
        )
      })}
      {models.length === 0 && (
        <span className="text-gray-600 text-xs font-mono">No models deployed yet</span>
      )}
    </div>
  )
}

// ─── Token card ───────────────────────────────────────────────────────────────

function TokenCard({
  token,
  currentUserId,
  isAdmin,
  instances,
  availableModels,
}: {
  token: TokenRead
  currentUserId: number
  isAdmin: boolean
  instances: InstanceRead[]
  availableModels: string[]
}) {
  const qc = useQueryClient()
  const isOwner = token.user_id === currentUserId || isAdmin
  const [editing, setEditing] = useState(false)

  // Edit state mirrors the token fields
  const [editName, setEditName] = useState(token.name)
  const [editInstances, setEditInstances] = useState<number[]>(token.scoped_instance_ids)
  const [editModels, setEditModels] = useState<string[]>(token.scoped_model_ids)

  const { mutate: toggleEnabled, isPending: toggling } = useMutation({
    mutationFn: (enabled: boolean) => tokensApi.update(token.id, { is_enabled: enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  })

  const { mutate: saveEdit, isPending: saving } = useMutation({
    mutationFn: (body: TokenUpdate) => tokensApi.update(token.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      setEditing(false)
    },
  })

  const { mutate: revoke } = useMutation({
    mutationFn: () => tokensApi.revoke(token.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  })

  const scopedInstanceNames = token.scoped_instance_ids
    .map((id) => instances.find((i) => i.id === id)?.display_name ?? `#${id}`)
    .join(', ')

  return (
    <div
      className={`bg-gray-900 border rounded-xl p-4 transition-colors ${
        token.is_enabled ? 'border-gray-800' : 'border-red-900/60 opacity-70'
      }`}
    >
      {/* ── Header row ── */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white font-mono font-[400] text-sm focus:outline-none focus:border-indigo-500 mb-1"
            />
          ) : (
            <p className="font-heading font-[800] text-white text-sm">{token.name}</p>
          )}

          {/* Token value */}
          <div className="flex items-center gap-1 mt-1">
            <span className="font-mono font-[300] text-xs text-gray-500">
              token:
            </span>
            {token.token ? (
              <>
                <span className="font-mono font-[400] text-xs text-yellow-400 bg-yellow-950 border border-yellow-800 rounded px-2 py-0.5 break-all">
                  {token.token}
                </span>
                <CopyButton text={token.token} />
              </>
            ) : (
              <span className="font-mono font-[400] text-xs text-gray-500 bg-gray-800 border border-gray-700 rounded px-2 py-0.5">
                unavailable for old tokens
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="font-mono font-[300] text-xs text-gray-500">
              {token.owner_username ? (
                <>
                  <span className="text-gray-300">{token.owner_username}</span>
                  <span className="text-gray-600"> #{token.user_id}</span>
                </>
              ) : (
                `user #${token.user_id}`
              )}
            </span>
            <PriorityBadge role={token.owner_queue_priority_role} />
          </div>
          <p className="font-mono font-[300] text-xs text-gray-500 mt-0.5">
            Created: {new Date(token.created_at).toLocaleDateString()}
            {token.expires_at && ` · Expires: ${new Date(token.expires_at).toLocaleDateString()}`}
            {token.last_used_at && ` · Last used: ${new Date(token.last_used_at).toLocaleDateString()}`}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Enable / disable toggle — owner only */}
          {isOwner && (
            <button
              onClick={() => toggleEnabled(!token.is_enabled)}
              disabled={toggling}
              className={`p-1.5 rounded transition-colors ${
                token.is_enabled
                  ? 'text-green-400 hover:text-green-300 hover:bg-green-950'
                  : 'text-red-400 hover:text-red-300 hover:bg-red-950'
              }`}
              title={token.is_enabled ? 'Disable token' : 'Enable token'}
            >
              {token.is_enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
            </button>
          )}

          {/* Edit — owner only */}
          {isOwner && !editing && (
            <button
              onClick={() => {
                setEditName(token.name)
                setEditInstances(token.scoped_instance_ids)
                setEditModels(token.scoped_model_ids)
                setEditing(true)
              }}
              className="p-1.5 text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950 rounded transition-colors"
              title="Edit token"
            >
              <Pencil size={14} />
            </button>
          )}

          {/* Cancel edit */}
          {editing && (
            <button
              onClick={() => setEditing(false)}
              className="p-1.5 text-gray-400 hover:text-white rounded transition-colors"
            >
              <X size={14} />
            </button>
          )}

          {/* Save edit */}
          {editing && (
            <button
              onClick={() =>
                saveEdit({
                  name: editName,
                  scoped_instance_ids: editInstances,
                  scoped_model_ids: editModels,
                })
              }
              disabled={saving || !editName}
              className="p-1.5 text-green-400 hover:text-green-300 hover:bg-green-950 rounded transition-colors disabled:opacity-40"
            >
              <Save size={14} />
            </button>
          )}

          {/* Revoke — owner only */}
          {isOwner && (
            <button
              onClick={() => { if (confirm('Revoke this token? This cannot be undone.')) revoke() }}
              className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-950 rounded transition-colors"
              title="Revoke token"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* ── Scope badges / editing area ── */}
      <div className="mt-3 space-y-2">
        {editing ? (
          <>
            <div>
              <p className="text-xs font-mono font-[600] text-gray-400 uppercase mb-1">Instance scope</p>
              <InstanceChips selected={editInstances} instances={instances} onChange={setEditInstances} />
              {editInstances.length === 0 && (
                <p className="text-gray-600 text-xs font-mono mt-1">All instances allowed</p>
              )}
            </div>
            <div>
              <p className="text-xs font-mono font-[600] text-gray-400 uppercase mb-1">Model scope</p>
              <ModelChips selected={editModels} models={availableModels} onChange={setEditModels} />
              {editModels.length === 0 && (
                <p className="text-gray-600 text-xs font-mono mt-1">All models allowed</p>
              )}
            </div>
          </>
        ) : (
          <>
            {token.scoped_instance_ids.length > 0 && (
              <p className="font-mono font-[300] text-xs text-indigo-300">
                Instances: {scopedInstanceNames}
              </p>
            )}
            {token.scoped_model_ids.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {token.scoped_model_ids.map((m) => (
                  <span key={m} className="px-1.5 py-0.5 bg-purple-950 border border-purple-800 rounded text-purple-300 font-mono font-[300] text-xs">
                    {m}
                  </span>
                ))}
              </div>
            )}
            {token.scoped_instance_ids.length === 0 && token.scoped_model_ids.length === 0 && (
              <p className="font-mono font-[300] text-xs text-gray-600">No scope restrictions</p>
            )}
          </>
        )}
      </div>

      {/* Disabled badge */}
      {!token.is_enabled && (
        <div className="mt-2">
          <span className="text-xs font-mono font-[600] text-red-400 bg-red-950 border border-red-800 rounded px-2 py-0.5">
            DISABLED
          </span>
        </div>
      )}
    </div>
  )
}

// ─── Create form ──────────────────────────────────────────────────────────────

function CreateTokenForm({
  onClose,
  onCreate,
  instances,
  availableModels,
  isAdmin,
  users,
}: {
  onClose: () => void
  onCreate: (t: TokenCreateResponse) => void
  instances: InstanceRead[]
  availableModels: string[]
  isAdmin: boolean
  users: UserRead[]
}) {
  const [name, setName] = useState('')
  const [expiresInDays, setExpiresInDays] = useState('')
  const [selectedInstances, setSelectedInstances] = useState<number[]>([])
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | undefined>(undefined)

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      tokensApi.create({
        name,
        user_id: isAdmin && selectedUserId !== undefined ? selectedUserId : undefined,
        expires_in_days: expiresInDays ? parseInt(expiresInDays, 10) : undefined,
        scoped_instance_ids: selectedInstances.length > 0 ? selectedInstances : undefined,
        scoped_model_ids: selectedModels.length > 0 ? selectedModels : undefined,
      }),
    onSuccess: onCreate,
  })

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 space-y-5">
      <h2 className="font-heading font-[800] text-white">New API Token</h2>

      <div>
        <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono font-[300] text-sm focus:outline-none focus:border-indigo-500"
          placeholder="my-api-key"
        />
      </div>

      {isAdmin && users.length > 0 && (
        <div>
          <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">
            Owner user <span className="normal-case text-gray-500">(default: yourself)</span>
          </label>
          <select
            value={selectedUserId ?? ''}
            onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono font-[300] text-sm focus:outline-none focus:border-indigo-500"
          >
            <option value="">— assign to myself —</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} ({u.queue_priority_role.replace(/_/g, ' ')}) #{u.id}
              </option>
            ))}
          </select>
        </div>
      )}

      <div>
        <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">Expires in days (blank = never)</label>
        <input
          value={expiresInDays}
          onChange={(e) => setExpiresInDays(e.target.value)}
          type="number"
          min="1"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-mono font-[300] text-sm focus:outline-none focus:border-indigo-500"
        />
      </div>

      <div>
        <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">
          Instance scope <span className="normal-case text-gray-500">(empty = all instances)</span>
        </label>
        <InstanceChips selected={selectedInstances} instances={instances} onChange={setSelectedInstances} />
      </div>

      <div>
        <label className="block text-xs font-mono font-[600] text-gray-400 mb-1 uppercase">
          Model scope <span className="normal-case text-gray-500">(empty = all models)</span>
        </label>
        <ModelChips selected={selectedModels} models={availableModels} onChange={setSelectedModels} />
      </div>

      <div className="flex gap-3 pt-1">
        <button
          onClick={() => mutate()}
          disabled={isPending || !name}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2 rounded text-sm font-sans font-[700] transition-colors"
        >
          {isPending ? 'Creating…' : 'Create'}
        </button>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-sm font-sans font-[200] transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Tokens() {
  const qc = useQueryClient()
  const currentUser = useAuthStore((s) => s.currentUser)
  const isAdmin = currentUser?.role === 'admin'
  const [showCreate, setShowCreate] = useState(false)
  const [newToken, setNewToken] = useState<TokenCreateResponse | null>(null)

  const { data: tokens = [], isLoading } = useQuery({ queryKey: ['tokens'], queryFn: tokensApi.list })
  const { data: instances = [] } = useQuery({ queryKey: ['instances'], queryFn: instancesApi.list })
  const { data: usersData } = useQuery({
    queryKey: ['users-all'],
    queryFn: () => usersApi.list(1, 200),
    enabled: isAdmin,
  })
  const users: UserRead[] = usersData?.items ?? []

  // Unique model IDs from all known instances ordered alphabetically
  const availableModels = [...new Set(instances.map((i) => i.model_id))].sort()

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-heading font-[800] text-2xl text-white">API Tokens</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-sans font-[700] transition-colors"
        >
          <Plus size={14} /> New Token
        </button>
      </div>

      {/* ── Newly created token banner ── */}
      {newToken && (
        <div className="bg-yellow-950 border border-yellow-700 rounded-xl p-5 mb-6">
          <p className="font-heading font-[800] text-yellow-300 mb-2">
            Full token value
          </p>
          <CopyableField value={newToken.token} className="mt-1" />
          <p className="mt-2 text-xs font-mono text-yellow-600">
            Prefix for quick identification: {newToken.token_prefix}…
          </p>
          <button
            onClick={() => setNewToken(null)}
            className="mt-3 text-xs font-sans font-[200] text-yellow-400 hover:text-yellow-300"
          >
            I've saved it
          </button>
        </div>
      )}

      {/* ── Create form ── */}
      {showCreate && (
        <CreateTokenForm
          onClose={() => setShowCreate(false)}
          onCreate={(t) => {
            setNewToken(t)
            setShowCreate(false)
            qc.invalidateQueries({ queryKey: ['tokens'] })
          }}
          instances={instances}
          availableModels={availableModels}
          isAdmin={isAdmin}
          users={users}
        />
      )}

      {/* ── Token list ── */}
      {isLoading ? (
        <p className="text-gray-500 font-sans font-[200]">Loading…</p>
      ) : tokens.length === 0 ? (
        <p className="text-gray-500 font-sans font-[200]">No tokens yet.</p>
      ) : (
        <div className="space-y-3">
          {tokens.map((t) => (
            <TokenCard
              key={t.id}
              token={t}
              currentUserId={currentUser?.id ?? -1}
              isAdmin={isAdmin}
              instances={instances}
              availableModels={availableModels}
            />
          ))}
        </div>
      )}
    </div>
  )
}

