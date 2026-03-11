# frontend/src/pages/Users.tsx

## Purpose
Admin-only CRUD interface for user accounts. Not visible to non-admin users (the route is protected; attempting to navigate redirects to Dashboard).

## Access Guard
```tsx
// Route definition
<Route path="/users" element={<AdminRoute><Users /></AdminRoute>} />
```
`AdminRoute` checks `currentUser.role === "admin"` from the Zustand store; otherwise renders `<Navigate to="/" />`.

## Layout
- **Toolbar**: search input (username/email) + "Add User" button
- **Table**: Username, Email, Role badge, Status (Active/Inactive), Created, Actions (Edit, Deactivate/Reactivate, Delete)
- **Create/Edit Drawer**: form with Username, Email, Password (create only), Role selector, Active toggle
- **Permissions Drawer**: slide-in panel listing ABAC policies for the selected user; opened via the "Permissions" row action

## ABAC Permissions Management
Accessed from the Users table via the row action "Permissions". Opens a side drawer showing the user's current policies and controls to add new ones.

### Permissions Drawer layout
- **Header**: `Permissions — {username}` in `Bricolage Grotesque` 800, `22px`
- **Policy table**: columns Resource Type, Resource, Action, Effect (Allow/Deny badge), Created, Delete
  - Resource column: shows resource type + ID (e.g. `instance #3`) or `All instances` when `resource_id` is null
  - Effect badge: green chip for `allow`, red chip for `deny`
- **Add Policy form** (inline below the table):
  - `Resource type` — select: Instance / Model / Token / Queue / User
  - `Resource` — searchable dropdown scoped to the selected type; "All" option maps to `resource_id = null`
  - `Action` — select scoped to the resource type (e.g. Instance shows: read, create, update, delete, start, stop, infer)
  - `Effect` — radio: Allow / Deny
  - "Add" button → calls `POST /api/policies`
- Deleting a policy row calls `DELETE /api/policies/{id}` and removes the row optimistically.
- "Clear All" button at the bottom calls `DELETE /api/users/{id}/policies` and empties the table.

### Action scoping by resource type
| Resource type | Available actions |
|---|---|
| `instance` | read, create, update, delete, start, stop, infer |
| `model` | read, create, delete |
| `token` | read, create, delete |
| `queue` | read |
| `user` | read, create, update, delete |

### Subject scope note
- Policies created from this drawer always have `subject_user_id` = the user being edited.
- Role-level policies (`subject_user_id = null, subject_role = "user"`) are **displayed** in the drawer (marked with a globe icon to indicate they apply to the whole role) but can only be deleted, not created, from here. To create role-level policies, use the dedicated `GET /policies` admin interface (future enhancement).

## Behaviour
- Search is debounced (300 ms) and passed to `usersApi.listUsers()` as `?search=`.
- "Deactivate" performs PATCH `is_active=false` (soft disable — token access immediately blocked).
- "Delete" shows a confirmation dialog; if confirmed, calls DELETE which cascades token revocation.
- An admin cannot deactivate or delete themselves.

## Password Management
Two distinct flows exist for changing passwords:

| Actor | Where | Endpoint | Requires current password? |
|---|---|---|---|
| Any authenticated user | Account Settings (avatar menu → "Change Password") | `PATCH /users/me/password` | Yes |
| Admin | Users page → row action "Reset Password" | `PATCH /users/{id}/password` | No |

- **Self-service (any user)**: A "Change Password" dialog is accessible from the top-right avatar/account menu. It presents three fields: `Current password`, `New password`, `Confirm new password`. On submit it calls `PATCH /users/me/password` with `{ current_password, new_password }`. A wrong `current_password` returns `400` and displays an inline error. On success, the user is logged out and redirected to `/login` (all API tokens are revoked server-side).
- **Admin reset**: Inside the Users table, the row action menu includes "Reset Password". This opens a simple dialog with only `New password` + `Confirm`, then calls `PATCH /users/{id}/password`. No knowledge of the current password is needed. Token revocation also happens server-side.

## Contracts
- Password field only shown on create (Users page admin form); edit uses the "Reset Password" row action.
- Role selector is hidden when editing own profile (cannot escalate/deescalate self).
- After a successful admin password reset, the target user's active sessions are invalidated (tokens revoked).

## Typography
- **Page title "Users"**: `Bricolage Grotesque` 900, `48px`
- **Username in table**: `IBM Plex Sans` 700, `15px`
- **Email in table**: `IBM Plex Sans` 200, `14px` — secondary, lighter than username
- **Role badge** (admin / user): `Bricolage Grotesque` 800, `11px` uppercase — same badge style as status badges across the app
- **Drawer form labels**: `IBM Plex Sans` 200, `11px` uppercase tracked
- **Drawer form values / inputs**: `IBM Plex Sans` 700, `15px`
