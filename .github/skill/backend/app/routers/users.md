# backend/app/routers/users.py

## Purpose
CRUD endpoints for user management. Admin-only for create, update-role, and delete. Regular users may only read and update their own profile.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/users` | admin | Paginated list of all users |
| `POST` | `/users` | admin | Create new user |
| `GET` | `/users/me` | any authenticated | Own profile |
| `PATCH` | `/users/me/password` | any authenticated | Change own password |
| `GET` | `/users/{id}` | admin | Get user by ID |
| `PATCH` | `/users/{id}` | admin or self (no role change) | Update user fields |
| `PATCH` | `/users/{id}/password` | admin | Admin resets any user's password (no current-password check) |
| `GET` | `/users/{id}/policies` | admin | List all ABAC policies applying to this user (user-specific + role-level) |
| `DELETE` | `/users/{id}/policies` | admin | Bulk-remove all ABAC policies for this user |
| `DELETE` | `/users/{id}` | admin | Soft-delete (sets `is_active=False`; row is preserved for audit/FK) |

## Dependencies
- `get_current_active_user`, `get_admin_user`
- `services.user_service`
- `services.abac_service` (for policy sub-resource endpoints)
- See [`backend/app/routers/policies.md`](policies.md) for the full ABAC policy CRUD router (`/policies`).

## Contracts
- A user cannot change their own `role`.
- `PATCH /users/me/password` requires `PasswordChange` body with `current_password` and `new_password`; returns `400` if `current_password` is wrong.
- `PATCH /users/{id}/password` (admin) uses `AdminPasswordReset` body with only `new_password`; no `current_password` required.
- After any password change, all existing API tokens for that user are revoked (force re-authenticate).
- Deleting a user cascades token revocation (DB cascade + Redis key cleanup).
- `GET /users` supports `?page=`, `?size=`, `?search=` (username/email prefix filter).
