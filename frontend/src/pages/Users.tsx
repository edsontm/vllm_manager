import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  usersApi,
  type UserRead,
  type QueuePriorityRole,
  type AbacPolicyRead,
  type AbacPolicyCreate,
} from '@/api/usersApi'
import { useAuthStore } from '@/store'
import {
  UserX, UserCheck, Trash2, KeyRound, ShieldCheck, Plus, X, Globe,
} from 'lucide-react'

// ─── constants ────────────────────────────────────────────────────────────────

const ACTIONS_BY_RESOURCE: Record<string, string[]> = {
  instance: ['read', 'create', 'update', 'delete', 'start', 'stop', 'infer'],
  model:    ['read', 'create', 'delete'],
  token:    ['read', 'create', 'delete'],
  queue:    ['read'],
  user:     ['read', 'create', 'update', 'delete'],
}

const PRIORITY_OPTIONS: { value: QueuePriorityRole; label: string }[] = [
  { value: 'high_priority', label: 'High Priority' },
  { value: 'medium_priority', label: 'Medium Priority' },
  { value: 'low_priority', label: 'Low Priority' },
]

// ─── shared UI primitives ─────────────────────────────────────────────────────

function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`font-heading font-[800] text-[11px] uppercase px-2 py-0.5 rounded
      ${role === 'admin' ? 'bg-indigo-900/60 text-indigo-300' : 'bg-gray-800 text-gray-400'}`}>
      {role}
    </span>
  )
}

function PriorityBadge({ priority }: { priority: QueuePriorityRole }) {
  const cls =
    priority === 'high_priority'
      ? 'bg-red-900/50 text-red-300'
      : priority === 'medium_priority'
        ? 'bg-amber-900/50 text-amber-300'
        : 'bg-green-900/50 text-green-300'
  const label = PRIORITY_OPTIONS.find((p) => p.value === priority)?.label ?? priority
  return (
    <span className={`font-heading font-[800] text-[11px] uppercase px-2 py-0.5 rounded ${cls}`}>
      {label}
    </span>
  )
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={`font-mono font-[600] text-xs ${active ? 'text-green-400' : 'text-red-400'}`}>
      {active ? 'Active' : 'Inactive'}
    </span>
  )
}

function EffectBadge({ effect }: { effect: string }) {
  return (
    <span className={`font-mono font-[600] text-[11px] uppercase px-2 py-0.5 rounded
      ${effect === 'allow' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
      {effect}
    </span>
  )
}

function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-gray-950 border-l border-gray-800 flex flex-col shadow-2xl overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-heading font-[800] text-[22px] text-white">{title}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors"><X size={18} /></button>
        </div>
        <div className="flex-1 px-6 py-5 space-y-5">{children}</div>
      </div>
    </div>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="block font-sans font-[200] text-[11px] uppercase tracking-widest text-gray-500 mb-1">{children}</label>
}

function TextInput({ ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 font-sans font-[700] text-[15px] text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
    />
  )
}

function StyledSelect({ ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 font-sans font-[700] text-[15px] text-white focus:outline-none focus:border-indigo-500"
    />
  )
}

function ActionBtn({ children, title, onClick, className }: {
  children: React.ReactNode; title: string; onClick: () => void; className: string
}) {
  return (
    <button title={title} onClick={onClick} className={`p-1.5 rounded transition-colors ${className}`}>
      {children}
    </button>
  )
}

// ─── Delete dialog ────────────────────────────────────────────────────────────

function DeleteDialog({ username, onConfirm, onCancel }: {
  username: string; onConfirm: () => void; onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onCancel} />
      <div className="relative bg-gray-950 border border-gray-800 rounded-xl p-6 w-full max-w-sm shadow-2xl">
        <h3 className="font-heading font-[800] text-lg text-white mb-2">Delete user</h3>
        <p className="font-sans font-[200] text-sm text-gray-400 mb-5">
          Deactivate <span className="font-[700] text-white">{username}</span>? All their tokens will be revoked.
        </p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 text-sm font-sans font-[700] text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button onClick={onConfirm} className="px-4 py-2 text-sm font-sans font-[700] bg-red-700 hover:bg-red-600 text-white rounded-lg transition-colors">Delete</button>
        </div>
      </div>
    </div>
  )
}

// ─── Create / Edit drawer ─────────────────────────────────────────────────────

function UserDrawer({ user, onClose }: { user: UserRead | null; onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    username: user?.username ?? '',
    email: user?.email ?? '',
    password: '',
    role: (user?.role ?? 'user') as 'admin' | 'user',
    queue_priority_role: (user?.queue_priority_role ?? 'medium_priority') as QueuePriorityRole,
    is_active: user?.is_active ?? true,
  })
  const [error, setError] = useState('')
  const isCreate = !user

  const { mutate: save, isPending } = useMutation({
    mutationFn: () =>
      isCreate
        ? usersApi.create({
            username: form.username,
            email: form.email,
            password: form.password,
            role: form.role,
            queue_priority_role: form.queue_priority_role,
          })
        : usersApi.update(user!.id, {
            email: form.email,
            role: form.role,
            queue_priority_role: form.queue_priority_role,
            is_active: form.is_active,
            ...(form.password ? { password: form.password } : {}),
          }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); onClose() },
    onError: (e: any) => setError(e?.response?.data?.message ?? String(e)),
  })

  return (
    <Drawer title={isCreate ? 'Add User' : `Edit ${user!.username}`} onClose={onClose}>
      {error && <p className="text-red-400 font-sans font-[200] text-sm">{error}</p>}

      {isCreate && (
        <div>
          <FieldLabel>Username</FieldLabel>
          <TextInput value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="jdoe" />
        </div>
      )}
      <div>
        <FieldLabel>Email</FieldLabel>
        <TextInput type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="user@example.com" />
      </div>
      <div>
        <FieldLabel>{isCreate ? 'Password' : 'New Password'}</FieldLabel>
        <TextInput
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          placeholder={isCreate ? 'Min. 8 characters' : 'Leave blank to keep current'}
        />
      </div>
      <div>
        <FieldLabel>Role</FieldLabel>
        <StyledSelect value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as 'admin' | 'user' })}>
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </StyledSelect>
      </div>
      <div>
        <FieldLabel>Queue Priority</FieldLabel>
        <StyledSelect
          value={form.queue_priority_role}
          onChange={(e) => setForm({ ...form, queue_priority_role: e.target.value as QueuePriorityRole })}
        >
          {PRIORITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </StyledSelect>
      </div>
      {!isCreate && (
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            className="rounded border-gray-600 bg-gray-900 text-indigo-500"
          />
          <span className="font-sans font-[200] text-[13px] text-gray-300">Active account</span>
        </label>
      )}
      <button
        onClick={() => save()}
        disabled={isPending}
        className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-sans font-[700] text-sm py-2 rounded-lg transition-colors"
      >
        {isPending ? 'Saving…' : isCreate ? 'Create User' : 'Save Changes'}
      </button>
    </Drawer>
  )
}

// ─── Admin password reset drawer ──────────────────────────────────────────────

function PasswordResetDrawer({ user, onClose }: { user: UserRead; onClose: () => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const { mutate: reset, isPending } = useMutation({
    mutationFn: () => {
      if (password.length < 8) throw new Error('Password must be at least 8 characters')
      if (password !== confirm) throw new Error('Passwords do not match')
      return usersApi.adminResetPassword(user.id, password)
    },
    onSuccess: () => setDone(true),
    onError: (e: any) => setError(e?.response?.data?.message ?? e?.message ?? String(e)),
  })

  return (
    <Drawer title={`Reset Password — ${user.username}`} onClose={onClose}>
      {done ? (
        <div className="space-y-4">
          <p className="text-green-400 font-sans font-[200] text-sm">
            Password reset. All tokens for <strong>{user.username}</strong> were revoked.
          </p>
          <button onClick={onClose} className="w-full bg-gray-800 hover:bg-gray-700 text-white font-sans font-[700] text-sm py-2 rounded-lg transition-colors">Close</button>
        </div>
      ) : (
        <>
          {error && <p className="text-red-400 font-sans font-[200] text-sm">{error}</p>}
          <div>
            <FieldLabel>New Password</FieldLabel>
            <TextInput type="password" value={password} onChange={(e) => { setPassword(e.target.value); setError('') }} placeholder="Min. 8 characters" />
          </div>
          <div>
            <FieldLabel>Confirm New Password</FieldLabel>
            <TextInput type="password" value={confirm} onChange={(e) => { setConfirm(e.target.value); setError('') }} placeholder="Repeat password" />
          </div>
          <button
            onClick={() => reset()}
            disabled={isPending}
            className="w-full bg-amber-700 hover:bg-amber-600 disabled:opacity-50 text-white font-sans font-[700] text-sm py-2 rounded-lg transition-colors"
          >
            {isPending ? 'Resetting…' : 'Reset Password'}
          </button>
        </>
      )}
    </Drawer>
  )
}

// ─── ABAC permissions drawer ──────────────────────────────────────────────────

function PolicyRow({ policy, isRole, onDelete }: {
  policy: AbacPolicyRead; isRole: boolean; onDelete: (id: number) => void
}) {
  const resourceLabel = policy.resource_id != null
    ? `${policy.resource_type} #${policy.resource_id}`
    : `All ${policy.resource_type}s`

  return (
    <tr className="border-b border-gray-800/50 hover:bg-gray-800/20">
      <td className="px-2 py-2">
        <span className="font-mono font-[300] text-gray-300">{resourceLabel}</span>
        {isRole && <span title="Role-level policy"><Globe size={10} className="inline ml-1 text-gray-500" /></span>}
      </td>
      <td className="px-2 py-2 font-mono font-[300] text-gray-400">{policy.action}</td>
      <td className="px-2 py-2"><EffectBadge effect={policy.effect} /></td>
      <td className="px-2 py-2">
        <button onClick={() => onDelete(policy.id)} title="Remove policy" className="text-gray-600 hover:text-red-400 transition-colors">
          <X size={14} />
        </button>
      </td>
    </tr>
  )
}

function PermissionsDrawer({ user, onClose }: { user: UserRead; onClose: () => void }) {
  const qc = useQueryClient()

  const { data: policyList, isLoading } = useQuery({
    queryKey: ['user-policies', user.id],
    queryFn: () => usersApi.listPolicies(user.id),
  })

  const [newPolicy, setNewPolicy] = useState<AbacPolicyCreate>({
    subject_user_id: user.id,
    resource_type: 'instance',
    action: 'infer',
    effect: 'allow',
    resource_id: null,
  })
  const [addError, setAddError] = useState('')

  const { mutate: addPolicy, isPending: adding } = useMutation({
    mutationFn: () => usersApi.createPolicy(newPolicy),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['user-policies', user.id] }); setAddError('') },
    onError: (e: any) => setAddError(e?.response?.data?.message ?? String(e)),
  })

  const { mutate: removePolicy } = useMutation({
    mutationFn: (id: number) => usersApi.deletePolicy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user-policies', user.id] }),
  })

  const { mutate: clearAll, isPending: clearing } = useMutation({
    mutationFn: () => usersApi.clearPolicies(user.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user-policies', user.id] }),
  })

  const handleResourceChange = (rt: string) => {
    const actions = ACTIONS_BY_RESOURCE[rt] ?? []
    setNewPolicy((p) => ({ ...p, resource_type: rt as any, action: actions[0] as any }))
  }

  const policies = policyList?.items ?? []
  const userPolicies = policies.filter((p) => p.subject_user_id === user.id)
  const rolePolicies = policies.filter((p) => p.subject_user_id === null)
  const availableActions = ACTIONS_BY_RESOURCE[newPolicy.resource_type] ?? []

  return (
    <Drawer title={`Permissions — ${user.username}`} onClose={onClose}>
      {isLoading ? (
        <p className="font-sans font-[200] text-sm text-gray-500">Loading…</p>
      ) : policies.length === 0 ? (
        <p className="font-sans font-[200] text-sm text-gray-500 italic">No policies yet — default deny.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800">
                {['Resource', 'Action', 'Effect', ''].map((h) => (
                  <th key={h} className="text-left px-2 py-2 font-mono font-[600] text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rolePolicies.map((p) => <PolicyRow key={p.id} policy={p} isRole onDelete={(id) => removePolicy(id)} />)}
              {userPolicies.map((p) => <PolicyRow key={p.id} policy={p} isRole={false} onDelete={(id) => removePolicy(id)} />)}
            </tbody>
          </table>
        </div>
      )}

      {/* Add policy */}
      <div className="border-t border-gray-800 pt-4 space-y-3">
        <p className="font-sans font-[200] text-[11px] uppercase tracking-widest text-gray-500">Add Policy</p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <FieldLabel>Resource Type</FieldLabel>
            <StyledSelect value={newPolicy.resource_type} onChange={(e) => handleResourceChange(e.target.value)}>
              {Object.keys(ACTIONS_BY_RESOURCE).map((rt) => <option key={rt} value={rt}>{rt}</option>)}
            </StyledSelect>
          </div>
          <div>
            <FieldLabel>Resource ID (blank = all)</FieldLabel>
            <TextInput
              type="number"
              min="1"
              value={newPolicy.resource_id ?? ''}
              onChange={(e) => setNewPolicy((p) => ({ ...p, resource_id: e.target.value ? Number(e.target.value) : null }))}
              placeholder="all"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <FieldLabel>Action</FieldLabel>
            <StyledSelect value={newPolicy.action} onChange={(e) => setNewPolicy((p) => ({ ...p, action: e.target.value as any }))}>
              {availableActions.map((a) => <option key={a} value={a}>{a}</option>)}
            </StyledSelect>
          </div>
          <div>
            <FieldLabel>Effect</FieldLabel>
            <StyledSelect value={newPolicy.effect} onChange={(e) => setNewPolicy((p) => ({ ...p, effect: e.target.value as any }))}>
              <option value="allow">Allow</option>
              <option value="deny">Deny</option>
            </StyledSelect>
          </div>
        </div>
        {addError && <p className="text-red-400 font-sans font-[200] text-xs">{addError}</p>}
        <button
          onClick={() => addPolicy()}
          disabled={adding}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-sans font-[700] text-sm py-2 rounded-lg transition-colors"
        >
          <Plus size={13} /> {adding ? 'Adding…' : 'Add Policy'}
        </button>
      </div>

      {policies.length > 0 && (
        <div className="border-t border-gray-800 pt-4">
          <button
            onClick={() => { if (window.confirm(`Remove ALL policies for ${user.username}?`)) clearAll() }}
            disabled={clearing}
            className="text-xs font-sans font-[200] text-red-500 hover:text-red-400 transition-colors disabled:opacity-50"
          >
            {clearing ? 'Removing…' : 'Clear All Policies'}
          </button>
        </div>
      )}
    </Drawer>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Users() {
  const qc = useQueryClient()
  const currentUser = useAuthStore((s) => s.currentUser)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  type DrawerMode = 'create' | UserRead
  const [editTarget, setEditTarget] = useState<DrawerMode | null>(null)
  const [resetTarget, setResetTarget] = useState<UserRead | null>(null)
  const [permTarget, setPermTarget] = useState<UserRead | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<UserRead | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['users', page, search],
    queryFn: () => usersApi.list(page, 20, search),
  })

  const { mutate: toggleActive } = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      usersApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  const { mutate: deleteUser } = useMutation({
    mutationFn: (id: number) => usersApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); setDeleteTarget(null) },
  })

  return (
    <div className="p-8">
      <h1 className="font-heading font-[900] text-[48px] leading-none text-white mb-2">Users</h1>

      <div className="flex items-center gap-3 mb-6 mt-4">
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search by username or email…"
          className="w-full max-w-sm bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white font-sans font-[700] text-sm focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={() => setEditTarget('create')}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-sans font-[700] transition-colors shrink-0"
        >
          <Plus size={14} /> Add User
        </button>
      </div>

      {isLoading ? (
        <p className="text-gray-500 font-sans font-[200]">Loading…</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {['Username', 'Email', 'Role', 'Priority', 'Status', 'Created', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-3 py-2 font-mono font-[600] text-xs text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.items.map((user) => {
                  const isSelf = user.id === currentUser?.id
                  return (
                    <tr key={user.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
                      <td className="px-3 py-3 font-sans font-[700] text-[15px] text-white">{user.username}</td>
                      <td className="px-3 py-3 font-sans font-[200] text-[14px] text-gray-400">{user.email}</td>
                      <td className="px-3 py-3"><RoleBadge role={user.role} /></td>
                      <td className="px-3 py-3"><PriorityBadge priority={user.queue_priority_role} /></td>
                      <td className="px-3 py-3"><StatusBadge active={user.is_active} /></td>
                      <td className="px-3 py-3 font-mono font-[300] text-xs text-gray-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          <ActionBtn title="Edit user" onClick={() => setEditTarget(user)} className="text-gray-400 hover:text-white hover:bg-gray-800">
                            <span className="text-xs font-mono px-1">Edit</span>
                          </ActionBtn>
                          <ActionBtn title="Reset password" onClick={() => setResetTarget(user)} className="text-amber-500 hover:text-amber-300 hover:bg-amber-950">
                            <KeyRound size={14} />
                          </ActionBtn>
                          <ActionBtn title="Manage permissions" onClick={() => setPermTarget(user)} className="text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950">
                            <ShieldCheck size={14} />
                          </ActionBtn>
                          {!isSelf && (
                            <ActionBtn
                              title={user.is_active ? 'Deactivate' : 'Activate'}
                              onClick={() => toggleActive({ id: user.id, is_active: !user.is_active })}
                              className={user.is_active ? 'text-red-400 hover:text-red-300 hover:bg-red-950' : 'text-green-400 hover:text-green-300 hover:bg-green-950'}
                            >
                              {user.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                            </ActionBtn>
                          )}
                          {!isSelf && (
                            <ActionBtn title="Delete user" onClick={() => setDeleteTarget(user)} className="text-red-500 hover:text-red-400 hover:bg-red-950">
                              <Trash2 size={14} />
                            </ActionBtn>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {data && data.total > 20 && (
            <div className="flex gap-3 mt-4 items-center">
              <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="text-sm font-sans font-[200] text-gray-400 hover:text-white disabled:opacity-40">← Prev</button>
              <span className="font-mono font-[300] text-xs text-gray-500">Page {page}</span>
              <button disabled={page * 20 >= data.total} onClick={() => setPage((p) => p + 1)} className="text-sm font-sans font-[200] text-gray-400 hover:text-white disabled:opacity-40">Next →</button>
            </div>
          )}
        </>
      )}

      {/* Drawers & modals */}
      {editTarget !== null && (
        <UserDrawer user={editTarget === 'create' ? null : editTarget} onClose={() => setEditTarget(null)} />
      )}
      {resetTarget && <PasswordResetDrawer user={resetTarget} onClose={() => setResetTarget(null)} />}
      {permTarget && <PermissionsDrawer user={permTarget} onClose={() => setPermTarget(null)} />}
      {deleteTarget && (
        <DeleteDialog
          username={deleteTarget.username}
          onConfirm={() => deleteUser(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
