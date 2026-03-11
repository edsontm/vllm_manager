# backend/app/models/user.py

## Purpose
SQLAlchemy ORM model for the `users` table.

## Table: `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | Internal user ID |
| `username` | `String(64)` | UNIQUE, NOT NULL | Login name |
| `email` | `String(256)` | UNIQUE, NOT NULL | Email address |
| `hashed_password` | `String(256)` | NOT NULL | bcrypt hash |
| `role` | `Enum('admin','user')` | NOT NULL, default `'user'` | Access role |
| `queue_priority_role` | `Enum('high_priority','medium_priority','low_priority')` | NOT NULL, default `'medium_priority'` | Determines position in per-instance priority queues |
| `is_active` | `Boolean` | NOT NULL, default `True` | Soft-disable without deleting |
| `created_at` | `DateTime(tz=True)` | server_default `now()` | Creation timestamp |
| `updated_at` | `DateTime(tz=True)` | onupdate `now()` | Last update timestamp |

## Relationships
- `access_tokens`: one-to-many → `AccessToken` (cascade delete)
- `request_logs`: one-to-many → `RequestLog`
- `abac_policies`: one-to-many → `AbacPolicy` (subject user, cascade delete)

## Contracts
- `hashed_password` is set via `core.security.hash_password()`, never plain text.
- Deleting a user cascades to their tokens via DB cascade.
- `queue_priority_role` is assigned automatically based on `role` when not explicitly provided (`admin` → `high_priority`, `user` → `low_priority`); see `services.user_service._default_queue_priority_for_role()`.
- `delete_user()` performs a **soft delete** (`is_active = False`) — the row is kept for audit/FK purposes.
