# backend/app/services/user_service.py

## Purpose
User lifecycle business logic: listing, creation, update, soft deletion, and password management. Keeps user account rules centralized outside routers.

## Internal Helper

### `_default_queue_priority_for_role(role: str) -> str`
Default queue role mapping:
- `admin` -> `high_priority`
- `user` -> `low_priority`
- any other role -> `medium_priority`

## Exported Functions

### `async list_users(db, page=1, size=20, search="") -> tuple[list[User], int]`
- Supports prefix search by username or email (`ILIKE {search}%`).
- Returns `(users, total_count)` for paginated UI responses.

### `async get_user(db, user_id: int) -> User`
- Fetches a user by ID.
- Raises `NotFoundError` if no row exists.

### `async create_user(db, data: UserCreate) -> User`
- Enforces unique username/email.
- Hashes password with `hash_password`.
- Assigns `queue_priority_role` from payload or role default.
- Persists and refreshes ORM object.

### `async update_user(db, user_id: int, data: UserUpdate) -> User`
- Partial update for `email`, `password`, `is_active`, `role`, `queue_priority_role`.
- Re-hashes password when provided.
- Returns refreshed user.

### `async delete_user(db, user_id: int) -> None`
- Soft delete only: sets `is_active = False`.
- Does not hard-delete DB rows.

### `async change_own_password(db, user, data: PasswordChange) -> None`
- Validates `current_password` before changing.
- Enforces minimum length (`>= 8`).
- Hashes and stores new password.

### `async admin_reset_password(db, user_id: int, data: AdminPasswordReset) -> None`
- Admin-only reset path without current password.
- Enforces minimum length (`>= 8`).
- Hashes and stores new password.

## Exceptions Raised
- `ConflictError` on duplicate username/email or invalid new password length.
- `NotFoundError` when target user does not exist.
- `ForbiddenError` when self-service current password validation fails.

## Contracts
- Passwords are always stored as hashes.
- User deletion is reversible at DB level because rows are retained (`is_active` toggle).
- Queue priority defaults stay role-driven unless explicitly overridden in payload.
