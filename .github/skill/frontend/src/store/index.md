# frontend/src/store/index.ts

## Purpose
Global client-side state management. Uses React Query for server state (caching, refetching, mutations) and Zustand for UI-only state (current user identity, sidebar open/close, notification list).

## React Query Setup
- `QueryClient` configured with:
  - `staleTime: 30_000` ms (metrics refetch frequently; other data is stable)
  - `retry: 1` for most queries; `retry: 0` for auth queries
- Per-query overrides defined in each page/component (not the global default).

## Zustand Store (`useAppStore`)

### State
| Field | Type | Description |
|---|---|---|
| `currentUser` | `UserRead \| null` | Logged-in user; hydrated from `/users/me` on load |
| `isAuthenticated` | `boolean` | Derived from `currentUser !== null` |
| `sidebarOpen` | `boolean` | Mobile sidebar state |
| `notifications` | `Notification[]` | Toast notifications queue |

### Actions
| Action | Description |
|---|---|
| `setCurrentUser(user)` | Set after successful login |
| `clearCurrentUser()` | Called on logout |
| `toggleSidebar()` | Toggle mobile nav |
| `addNotification(n)` | Push a toast (auto-dismissed after 5 s) |
| `dismissNotification(id)` | Remove a toast by ID |

## Contracts
- Server state (instances, metrics, tokens, etc.) lives exclusively in React Query cache.
- Zustand persists `currentUser` to `sessionStorage` so page refresh does not log the user out.
- No API calls are made directly from the store; only from React Query query functions.
