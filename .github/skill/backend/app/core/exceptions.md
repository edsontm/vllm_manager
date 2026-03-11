# backend/app/core/exceptions.py

## Purpose
Defines custom exception classes and the global FastAPI exception handlers registered in `main.py`. Ensures consistent JSON error responses across the entire API.

## Custom Exception Classes

| Class | HTTP Status | When used |
|---|---|---|
| `NotFoundError` | 404 | Resource not found in DB |
| `UnauthorizedError` | 401 | Invalid/expired token |
| `ForbiddenError` | 403 | Insufficient role or token scope |
| `ConflictError` | 409 | Unique constraint violation (e.g., duplicate username) |
| `VllmError` | 502 | vLLM container returned an error or is unreachable |
| `QueueFullError` | 503 | Redis queue has exceeded the configured depth limit |
| `HuggingFaceError` | 502 | HuggingFace API call failed |

## Error Response Format
```json
{
  "error": "not_found",
  "message": "VllmInstance with id=5 not found",
  "request_id": "uuid"
}
```

## Handlers
- `sqlalchemy.exc.IntegrityError` → `ConflictError`
- `pydantic.ValidationError` → 422 with field-level detail
- Catch-all `Exception` → 500 with sanitised message (no stack trace in response)

## Contracts
- Stack traces are never returned in HTTP responses, only logged server-side.
- All error bodies include `request_id` for correlation with logs.
