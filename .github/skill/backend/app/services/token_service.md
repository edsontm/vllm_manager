# backend/app/services/token_service.py

## Purpose
Business logic for API token creation, validation, scope checking, and revocation. Keeps all token semantics out of the routers. All functions are module-level.

## Exported Functions

### `async create_token(db, user_id, data: TokenCreate) -> tuple[AccessToken, str]`
- Calls `core.security.generate_api_token()` to get `(raw, hashed)`.
- Persists `AccessToken` row with `hashed_token`, `raw_token`, `token_prefix` (first 8 chars), `scoped_instance_ids`, `scoped_model_ids`, `expires_at`.
- Returns `(AccessToken ORM object, raw_token_string)`.

### `async list_tokens(db, user_id, is_admin) -> list[AccessToken]`
- Eagerly loads the owner `User` (via `joinedload`) so the router can populate `owner_username` and `owner_queue_priority_role`.
- Admins receive all tokens system-wide; non-admins see only their own.

### `async get_token(db, token_id) -> AccessToken`
Raises `NotFoundError` if missing.

### `async update_token(db, token_id, data: TokenUpdate, requesting_user) -> AccessToken`
- Partial update: name, `is_enabled`, `scoped_instance_ids`, `scoped_model_ids`.
- Only token owner or admin may update.

### `async validate_token(db, raw) -> AccessToken`
- Iterates all tokens and checks bcrypt hash via `core.security.verify_api_token()`.
- Checks `is_enabled` and `expires_at`.
- Raises `UnauthorizedError` on failure.

### `async validate_token_scope(token, instance_id) -> None`
- If `token.scoped_instance_ids` is empty → all instances allowed.
- Otherwise checks `instance_id in token.scoped_instance_ids`.
- Raises `ForbiddenError` if out of scope.

### `async validate_model_scope(token, model_id) -> None`
- If `token.scoped_model_ids` is empty → all models allowed.
- Otherwise checks `model_id in token.scoped_model_ids`.
- Raises `ForbiddenError` if out of scope.

### `async revoke_token(db, token_id, requesting_user) -> None`
- Verifies ownership (owner or admin).
- Nullifies `token_id` in all `RequestLog` rows referencing this token (for audit preservation).
- **Hard-deletes** the `AccessToken` row (no soft-disable).

### `async revoke_all_user_tokens(db, user_id) -> int`
Bulk hard-deletes all tokens for a user (called on password change). Returns count deleted.

## Contracts
- Token validation never logs the raw token value.
- `validate_token` is used by `dependencies.get_vllm_token`.
- Revocation is permanent — once deleted, the token is gone.
