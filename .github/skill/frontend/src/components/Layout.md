# frontend/src/components/Layout.tsx

## Purpose
Shell component for authenticated application routes. Provides sidebar navigation, role-aware menu visibility, and logout behavior around page content rendered via `Outlet`.

## Navigation Model
`navItems` defines route metadata:
- Dashboard
- Instances
- Models
- Tokens
- Queue
- Test
- Stress Test
- Users (admin-only)

Admin gating rule:
- Items marked `adminOnly: true` are visible only when `currentUser.role === "admin"`.

## State and Interactions
- Reads `currentUser` and `logout` from `useAuthStore`.
- Reads `sidebarOpen` and `toggleSidebar` from `useUIStore`.
- Sidebar width toggles between compact and expanded states.
- Active route highlighting is handled by `NavLink` state.

## Logout Flow
`handleLogout`:
1. Attempts `authApi.logout()` best-effort.
2. Calls local `logout()` store action regardless of API outcome.
3. Redirects to `/login` by setting `window.location.href`.

## Contracts
- Route content is rendered inside `Outlet` and must remain independent of shell internals.
- Failed server-side logout must not block local session teardown.
- Admin-only navigation entries are filtered client-side for usability (server-side auth remains authoritative).
- Layout is responsive through collapsible sidebar behavior.
