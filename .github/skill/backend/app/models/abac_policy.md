# backend/app/models/abac_policy.py

## Purpose
SQLAlchemy ORM model for the `abac_policies` table. Each row represents a single access-control grant or denial for a subject (user or role) acting on a resource type (and optionally a specific resource ID).

## Table: `abac_policies`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | Internal policy ID |
| `subject_user_id` | `Integer` | FK → `users.id` SET NULL, nullable | Specific user this policy applies to. `NULL` = any user matching `subject_role`. |
| `subject_role` | `Enum('admin','user')` | nullable | Role this policy applies to. `NULL` = any role. Used together with `subject_user_id` for per-user + per-role intersection. |
| `resource_type` | `Enum('instance','model','token','queue','user')` | NOT NULL | Resource domain |
| `resource_id` | `Integer` | nullable | Specific resource row ID. `NULL` = wildcard (all resources of this type). |
| `action` | `Enum('read','create','update','delete','start','stop','infer')` | NOT NULL | The operation being governed |
| `effect` | `Enum('allow','deny')` | NOT NULL, default `'allow'` | Whether to grant or block the action |
| `created_at` | `DateTime(tz=True)` | server_default `now()` | When the policy was created |
| `created_by_id` | `Integer` | FK → `users.id` SET NULL, nullable | Admin who created this policy (audit trail) |

## Relationships
- `subject_user` → `User` (via `subject_user_id`)
- `created_by` → `User` (via `created_by_id`)

## Indexes
- `(subject_user_id, resource_type, action)` — covering index for the most common lookup pattern
- `(subject_role, resource_type, action)` — covering index for role-level lookups

## Contracts
- At least one of `subject_user_id` or `subject_role` must be non-NULL (enforced at the schema/service layer, not DB constraint, for flexibility).
- When both `subject_user_id` and `subject_role` are set, the policy applies only when the user matches **both** — used to create a role-scoped user-specific grant.
- `resource_id = NULL` is the wildcard meaning "all resources of this type". Explicit `resource_id` values take no precedence over wildcards — `deny` always wins.
- Policies with `subject_user_id` referencing a deleted user are kept (`SET NULL`) for audit purposes but become permanently inactive (no user will match `subject_user_id = NULL AND subject_role = NULL`).
