# backend/app/dependencies.py

## Purpose
FastAPI dependency injection functions shared across routers. Centralises DB session, Redis client, and current-user resolution so routers stay thin.

## Exported Dependencies

### `get_db() -> AsyncSession`
Yields an async SQLAlchemy session. Commits on clean exit, rolls back on exception.

### `get_redis() -> Redis`
Yields a `redis.asyncio.Redis` client from the shared connection pool.

### `get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) -> User`
Decodes the JWT, looks up the user, raises `401` if invalid or expired.

### `get_current_active_user(user = Depends(get_current_user)) -> User`
Extends `get_current_user` — raises `403` if `user.is_active` is `False`.

### `get_admin_user(user = Depends(get_current_active_user)) -> User`
Raises `403` if `user.role != "admin"`.

### `require_permission(action: str, resource_type: str) -> Depends`
Factory that returns a FastAPI dependency checking ABAC policy. Usage:

```python
# In a router — resource_id comes from the path parameter
@router.get("/instances/{id}")
async def get_instance(
    id: int,
    user = Depends(get_current_active_user),
    db  = Depends(get_db),
):
    await authorize(user, "read", "instance", id, db)  # core.abac.authorize()
    ...
```

`require_permission` is a **convenience shortcut** for the common case where the resource ID can be extracted directly from the path under the name `id`:

```python
@router.get("/instances/{id}", dependencies=[require_permission("read", "instance")])
async def get_instance(id: int, db = Depends(get_db)): ...
```

For paths where the resource ID has a different name (e.g. `instance_id`), call `core.abac.authorize()` explicitly inside the handler.

- Admins bypass all checks (short-circuit in `core.abac.authorize`).
- Raises `HTTPException(403)` when the ABAC policy evaluation returns `"deny"` or no matching `"allow"` exists.

### `get_vllm_token(authorization: str = Header(...), db = Depends(get_db)) -> tuple[AccessToken, VllmInstance]`
Used exclusively by `routers.proxy`. Validates a static Bearer token against `access_tokens` table, checks scope, raises `401`/`403` as appropriate.

## Contracts
- All DB sessions are async (`asyncpg` driver).
- Redis client is reused from a module-level pool (not re-created per request).
- No business logic lives here — only wiring.
- `require_permission` depends on `get_current_active_user` internally; do not stack both in the same route to avoid double auth resolution.
