# backend/app/routers/policies.py

## Purpose
CRUD endpoints for ABAC policy management. Admin-only. Allows admins to grant or deny fine-grained permissions to users (or to whole roles) on any resource type.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/policies` | admin | Paginated list of all policies; filterable by `?user_id=`, `?role=`, `?resource_type=`, `?action=` |
| `POST` | `/policies` | admin | Create a new policy (grant or deny) |
| `GET` | `/policies/{id}` | admin | Get a single policy by ID |
| `PATCH` | `/policies/{id}` | admin | Update effect (`allow`/`deny`) or swap resource |
| `DELETE` | `/policies/{id}` | admin | Remove the policy |
| `GET` | `/users/{id}/policies` | admin | All policies applying to a specific user (user-specific + role-level) |
| `DELETE` | `/users/{id}/policies` | admin | Remove all policies for a specific user (bulk revoke) |

## Dependencies
- `get_admin_user`
- `services.abac_service`

## Request / Response Shapes
All endpoints consume / produce `AbacPolicyCreate`, `AbacPolicyUpdate`, `AbacPolicyRead` (see schemas).

Example `POST /policies` body:
```json
{
  "subject_user_id": 7,
  "subject_role": null,
  "resource_type": "instance",
  "resource_id": 3,
  "action": "infer",
  "effect": "allow"
}
```

Example `GET /policies?user_id=7` response:
```json
{
  "items": [
    {
      "id": 12,
      "subject_user_id": 7,
      "subject_role": null,
      "resource_type": "instance",
      "resource_id": 3,
      "action": "infer",
      "effect": "allow",
      "created_at": "2026-03-03T10:00:00Z",
      "created_by_id": 1
    }
  ],
  "total": 1,
  "page": 1,
  "size": 50
}
```

## Contracts
- Only admins can call any endpoint in this router.
- Creating a policy for an admin-role user is a no-op in practice (admins bypass all checks), but is not rejected — it is stored for documentation purposes.
- Deleting a policy invalidates the affected user's ABAC Redis cache immediately (`abac:{user_id}` key deleted).
- `GET /users/{id}/policies` returns **all** matching policies: those with `subject_user_id = id` plus those with `subject_role = user.role` and `subject_user_id = NULL`.
- The router is mounted at `/api/policies` and `/api/users/{id}/policies` (shared with users router for the per-user sub-resource endpoints).
