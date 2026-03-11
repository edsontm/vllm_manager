# backend/app/core/abac.py

## Purpose
Attribute-Based Access Control (ABAC) policy engine. Evaluates whether a subject (user) is authorised to perform an action on a resource, based on policy rows stored in the `abac_policies` table.

## Why ABAC instead of pure RBAC
The existing `role` column (`admin` / `user`) provides coarse-grained access. ABAC extends this by allowing fine-grained, row-level grants:

- A `user`-role account can be granted `infer` on `instance:42` only.
- A department lead can be granted `read` on all instances (`resource_id = *`) without admin privileges.
- Explicit `deny` rules take precedence over `allow` rules, enabling blacklisting.

Admins bypass ABAC entirely — admin role always grants full access to every resource.

## Policy Evaluation Algorithm

```
1. If subject.role == "admin"  →  ALLOW (short-circuit)
2. Collect matching policies:
     WHERE (subject_user_id = user.id  OR  subject_user_id IS NULL)
       AND (subject_role     = user.role OR  subject_role     IS NULL)
       AND  resource_type    = requested_resource_type
       AND (resource_id      = requested_resource_id
            OR resource_id IS NULL)   -- NULL = wildcard
       AND  action           = requested_action
3. If any matching policy has effect = "deny"  →  DENY  (deny wins)
4. If any matching policy has effect = "allow" →  ALLOW
5. Default  →  DENY
```

Specificity tiebreaking: a policy matching `resource_id = 42` is more specific than one with `resource_id = NULL`, but **deny always wins** regardless of specificity.

## Exported Function

### `async authorize(user: User, action: str, resource_type: str, resource_id: int | None, db: AsyncSession) -> None`
- Runs the evaluation algorithm above.
- Raises `HTTPException(status_code=403, detail="Permission denied")` when DENY.
- Returns `None` on ALLOW — callers need not check the return value.

```python
# Usage in a router:
@router.get("/instances/{id}")
async def get_instance(id: int, user=Depends(get_current_active_user), db=Depends(get_db)):
    await authorize(user, "read", "instance", id, db)
    ...
```

## Resource Types

| `resource_type` | Covers |
|---|---|
| `instance` | `VllmInstance` rows — start, stop, infer, read, update, delete |
| `model` | HF model list/download operations |
| `token` | API access tokens (own tokens only by default) |
| `queue` | Request queue visibility and management |
| `user` | User records (admin CRUD) |

## Actions

| Action | Meaning |
|---|---|
| `read` | GET (list or detail) |
| `create` | POST |
| `update` | PATCH |
| `delete` | DELETE |
| `start` | POST `/{id}/start` on instances |
| `stop` | POST `/{id}/stop` on instances |
| `infer` | Proxy inference requests through `/v1/{slug}/` |

## Caching
Policy lookups are cached in Redis under `abac:{user_id}` with a 60-second TTL. The cache is invalidated immediately when any policy for that user is created, updated, or deleted.

## Contracts
- `admin` role bypasses all policy checks; no `abac_policies` rows are needed for admins.
- A user with no matching policies is denied by default (default-deny posture).
- `resource_id = NULL` in a policy row means "all resources of that type" (wildcard).
- Callers must not skip `authorize()` for non-admin users; omission is treated as a security bug.
