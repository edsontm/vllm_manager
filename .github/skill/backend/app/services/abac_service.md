# backend/app/services/abac_service.py

## Purpose
Service layer for ABAC policy persistence (CRUD) and evaluation. Used by both `routers/policies.py` (CRUD) and `core/abac.py` (the authorize helper). Keeps DB queries and cache logic in one place.

## Exported Functions

### `async get_policies(db, *, user_id=None, role=None, resource_type=None, action=None, page, size) -> tuple[list[AbacPolicy], int]`
Paginated query with optional filters. Used by `GET /policies`.

### `async get_policies_for_user(user: User, db: AsyncSession) -> list[AbacPolicy]`
Returns all policies that could match `user`: rows where `subject_user_id = user.id` **or** `subject_role = user.role AND subject_user_id IS NULL`. Used during authorization evaluation and by `GET /users/{id}/policies`.

### `async create_policy(data: AbacPolicyCreate, created_by: User, db: AsyncSession) -> AbacPolicy`
Inserts a new policy row. Flushes the ABAC Redis cache for the affected user after insert.

### `async update_policy(policy_id: int, data: AbacPolicyUpdate, db: AsyncSession) -> AbacPolicy`
Partial update (effect, resource_id). Invalidates Redis cache.

### `async delete_policy(policy_id: int, db: AsyncSession) -> None`
Hard-deletes the row. Invalidates Redis cache for the policy's `subject_user_id`.

### `async delete_all_for_user(user_id: int, db: AsyncSession) -> int`
Bulk-deletes all rows where `subject_user_id = user_id`. Returns the count of deleted rows. Invalidates Redis cache.

### `async evaluate(user: User, action: str, resource_type: str, resource_id: int | None, db: AsyncSession) -> Literal["allow", "deny"]`
Core evaluation function called by `core.abac.authorize()`. Implements the deny-wins algorithm:
1. Return `"allow"` immediately for admin role.
2. Fetch (or read from Redis cache) all matching policies for `user`.
3. Filter to matching `(action, resource_type, resource_id-or-wildcard)`.
4. If any `effect == "deny"` → return `"deny"`.
5. If any `effect == "allow"` → return `"allow"`.
6. Default → return `"deny"`.

## Redis Cache Schema

| Key | Value | TTL |
|---|---|---|
| `abac:{user_id}` | JSON-serialised `list[AbacPolicy]` (all policies for this user) | 60 s |

Cache is populated lazily on first `evaluate()` call and invalidated synchronously on any write operation.

## Contracts
- `evaluate()` never raises; it returns `"allow"` or `"deny"`. The HTTP 403 is raised by the caller (`core.abac.authorize()`).
- All write functions must flush `abac:{user_id}` from Redis before returning to ensure the next request sees the updated policies.
- The service never checks `user.role == "admin"` outside `evaluate()` — callers should not assume short-circuit behaviour in other functions.
