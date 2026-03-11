# backend/app/models/access_token.py

## Purpose
SQLAlchemy ORM model for the `access_tokens` table. Stores per-user API tokens used to authenticate against the vLLM proxy endpoints.

## Table: `access_tokens`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `user_id` | `Integer` | FK `users.id` CASCADE, NOT NULL | Owning user |
| `name` | `String(128)` | NOT NULL | Human-readable label (e.g., "prod key") |
| `hashed_token` | `String(255)` | UNIQUE, NOT NULL | bcrypt hash of the raw token |
| `raw_token` | `String(255)` | nullable | Raw token stored temporarily for "show again" UX; should be treated as sensitive |
| `token_prefix` | `String(16)` | NOT NULL, default `""` | First 8 chars of raw token for display purposes |
| `is_enabled` | `Boolean` | NOT NULL, default `True` | Enable/disable without deleting |
| `scoped_instance_ids` | `ARRAY(Integer)` | NOT NULL, default `[]` | If non-empty, token only valid for these `VllmInstance` IDs |
| `scoped_model_ids` | `ARRAY(String)` | NOT NULL, default `[]` | If non-empty, token only valid for these model IDs (e.g. `"meta-llama/Llama-3-8B"`) |
| `created_at` | `DateTime(tz=True)` | server_default `now()` | |
| `last_used_at` | `DateTime(tz=True)` | nullable | Updated on each successful proxy use |
| `expires_at` | `DateTime(tz=True)` | nullable | Optional expiry; NULL = never expires |

## Relationships
- `user`: many-to-one → `User`

## Contracts
- Only the `hashed_token` (bcrypt) is used for validation via `core.security.verify_api_token()`.
- Empty `scoped_instance_ids` = all instances allowed. Empty `scoped_model_ids` = all models allowed.
- Token scope is enforced by `services.token_service.validate_token_scope()` and `validate_model_scope()`.
- Revoking a token deletes the row entirely (hard delete) — not a soft-disable.
