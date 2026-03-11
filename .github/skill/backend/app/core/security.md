# backend/app/core/security.py

## Purpose
All cryptographic operations: JWT lifecycle and static API token validation. Enforces the authentication contracts used by `dependencies.py`.

## Exported Functions

### `create_access_token(data: dict, expires_delta: timedelta | None) -> str`
Signs a JWT with `settings.secret_key` / `settings.algorithm`. Embeds `exp` claim.

### `decode_access_token(token: str) -> dict`
Decodes and verifies a JWT. Raises `InvalidTokenError` (mapped to HTTP 401) on failure.

### `hash_password(plain: str) -> str`
bcrypt hash via `passlib.context.CryptContext`.

### `verify_password(plain: str, hashed: str) -> bool`
Constant-time comparison via passlib.

### `generate_api_token() -> tuple[str, str]`
Returns `(raw_token, hashed_token)`. Raw token is shown once to the user; only the hash is stored in the DB. Uses `secrets.token_urlsafe(32)`.

### `verify_api_token(raw: str, hashed: str) -> bool`
Constant-time HMAC comparison to prevent timing attacks.

## Environment Variables Consumed
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

## Contracts
- Passwords are never stored in plain text.
- API tokens are never stored in plain text; only SHA-256 + bcrypt hash is persisted.
- JWT payload contains: `sub` (user ID as string), `role`, `exp`.
