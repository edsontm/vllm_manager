# backend/app/routers/tokens.py

## Purpose
Endpoints for generating, listing, updating, and permanently revoking per-user API tokens used to authenticate against the vLLM proxy.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/tokens` | any authenticated | List tokens — admins see all tokens system-wide; users see only their own |
| `POST` | `/tokens` | any authenticated | Create a new API token (admins may set `user_id` to create for another user) |
| `PATCH` | `/tokens/{id}` | owner or admin | Update token name, enabled state, instance scope, or model scope |
| `DELETE` | `/tokens/{id}` | owner or admin | Permanently delete (hard delete) the token |

## Request Body for `POST /tokens`
```json
{
  "name": "my-prod-key",
  "user_id": null,
  "scoped_instance_ids": [1, 3],
  "scoped_model_ids": ["meta-llama/Llama-3-8B"],
  "expires_in_days": 365
}
```
- `user_id`: admin-only; if set, assigns the token to a different user.
- `scoped_instance_ids`: optional. Empty = all instances allowed.
- `scoped_model_ids`: optional. Empty = all models allowed.
- `expires_in_days`: optional. If omitted, token never expires.

## Request Body for `PATCH /tokens/{id}`
```json
{
  "name": "renamed-key",
  "is_enabled": false,
  "scoped_instance_ids": [1],
  "scoped_model_ids": []
}
```
All fields are optional (partial update).

## Response for `POST /tokens`
```json
{
  "id": 42,
  "user_id": 7,
  "name": "my-prod-key",
  "token": "raw_token_shown_once",
  "token_prefix": "abcdef12",
  "is_enabled": true,
  "scoped_instance_ids": [1, 3],
  "scoped_model_ids": ["meta-llama/Llama-3-8B"],
  "expires_at": "2027-03-10T00:00:00Z",
  "last_used_at": null,
  "created_at": "2026-03-10T10:00:00Z",
  "owner_username": "alice",
  "owner_queue_priority_role": "medium_priority"
}
```
**`token` (raw value) is returned only on creation and never retrievable again.**

## Contracts
- Only the bcrypt hash of the token is persisted; the raw value cannot be recovered after creation.
- Listing tokens returns `token: null` (raw value omitted); only `token_prefix` (first 8 chars) is shown for identification.
- `DELETE /tokens/{id}` **permanently deletes** the row (hard delete) — there is no soft-revoke.
- Only the token owner or an admin may update or delete a token.
