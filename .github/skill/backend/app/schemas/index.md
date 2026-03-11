# backend/app/schemas/

## Purpose
Pydantic v2 schemas for request validation and response serialisation. Each schema file corresponds to a router domain. Schemas are the only layer that crosses the HTTP boundary — ORM models are never returned directly.

## Files

| File | Contains |
|---|---|
| `user.py` | `UserCreate`, `UserUpdate`, `UserRead`, `UserList`, `PasswordChange`, `AdminPasswordReset` |
| `policy.py` | `AbacPolicyCreate`, `AbacPolicyUpdate`, `AbacPolicyRead`, `AbacPolicyList` |
| `token.py` | `TokenCreate`, `TokenRead`, `TokenRevoke`, `LoginRequest`, `LoginResponse` (JWT) |
| `instance.py` | `InstanceCreate`, `InstanceUpdate`, `InstanceRead`, `InstanceStatusRead` |
| `metrics.py` | `InstanceMetrics`, `MetricsSummary`, `ContextLengthSuggestion` |
| `model.py` | `HFModelInfo`, `LocalModelInfo`, `DeployModelRequest`, `SwitchModelRequest`, `ModelPrefill` |
| `queue.py` | `QueueStatus`, `QueueConfig` |

## Naming Conventions
- `*Create` — input for POST (no `id`, no `created_at`)
- `*Update` — input for PATCH (all fields optional)
- `*Read` — output (includes `id`, timestamps; inherits `model_config = ConfigDict(from_attributes=True)`)
- `*List` — paginated wrapper: `{"items": [...], "total": int, "page": int, "size": int}`

## Model Schemas (`model.py`)

```python
class HFModelInfo(BaseModel):
    id: str
    downloads: int | None = None
    likes: int | None = None
    tags: list[str] = []
    pipeline_tag: str | None = None
    private: bool = False
    num_parameters: int | None = None     # from config.json when available
    license: str | None = None
    vram_required_gb: float | None = None  # estimated from safetensors sizes × 1.2

class LocalModelInfo(BaseModel):
    id: str
    local_path: str
    disk_size_gb: float
    last_modified: datetime
    vram_required_gb: float | None = None  # estimated from local .safetensors sizes × 1.2

class ModelPrefill(BaseModel):
    """Lightweight shape returned by GET /models/prefill/{model_id:path}.
    Used by the frontend to populate the Create Instance drawer."""
    model_id: str
    suggested_slug: str          # lowercased model name tail, hyphens, max 48 chars
    suggested_display_name: str  # human-readable tail (spaces, title-case)
    vram_required_gb: float | None = None
```

`vram_required_gb` is `None` when the model has no `.safetensors` files in its metadata. The frontend renders `—` or `Unknown` in that case.

---

## ABAC Policy Schemas (`policy.py`)

```python
ResourceType = Literal['instance', 'model', 'token', 'queue', 'user']
Action       = Literal['read', 'create', 'update', 'delete', 'start', 'stop', 'infer']
Effect       = Literal['allow', 'deny']

class AbacPolicyCreate(BaseModel):
    subject_user_id: int | None = None   # NULL = match any user in subject_role
    subject_role: Literal['admin','user'] | None = None  # NULL = match any role
    resource_type: ResourceType
    resource_id: int | None = None       # NULL = wildcard (all resources of this type)
    action: Action
    effect: Effect = 'allow'

class AbacPolicyUpdate(BaseModel):
    effect: Effect | None = None
    resource_id: int | None = None       # can widen/narrow the resource scope

class AbacPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_user_id: int | None
    subject_role: str | None
    resource_type: str
    resource_id: int | None
    action: str
    effect: str
    created_at: datetime
    created_by_id: int | None

AbacPolicyList = PaginatedList[AbacPolicyRead]  # items, total, page, size
```

At least one of `subject_user_id` or `subject_role` must be non-`None` — enforced by a `@model_validator` in `AbacPolicyCreate`.

---

## Password Change Schemas (`user.py`)

```python
class PasswordChange(BaseModel):
    current_password: str          # verified against stored hash
    new_password: str = Field(..., min_length=8)

class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8)
```

`PasswordChange` is used by `PATCH /users/me/password` (self-service).
`AdminPasswordReset` is used by `PATCH /users/{id}/password` (admin resets any account).
Neither schema appears in any `*Read` response.

## Contracts
- No ORM imports in schema files (keep Pydantic and SQLAlchemy layers separate — SOLID's Dependency Inversion).
- All `*Read` schemas use `model_config = ConfigDict(from_attributes=True)` for `.model_validate(orm_obj)`.
- Sensitive fields (`hashed_password`, `hashed_token`) are excluded from all `*Read` schemas via `exclude` or by omission.
