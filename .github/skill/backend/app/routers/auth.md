# backend/app/routers/auth.py

## Purpose
Authentication endpoints. Issues JWT access tokens and handles session lifecycle.

## Endpoints

### `POST /auth/login`
- **Body**: `LoginRequest { username, password }`
- **Response**: `LoginResponse { access_token, token_type: "bearer", expires_in }`
- Validates credentials via `services.auth_service.authenticate_user()`.
- Returns 401 on invalid credentials.

### `POST /auth/refresh`
- **Header**: `Authorization: Bearer <jwt>`
- **Response**: new `LoginResponse` with refreshed token.
- Only accepted if token is not yet expired.

### `POST /auth/logout`
- **Header**: `Authorization: Bearer <jwt>`
- **Response**: `204 No Content`
- Adds the JWT `jti` claim to a Redis blocklist for the remainder of its TTL.

## Dependencies
- `get_db`, `get_redis`
- `services.auth_service`

## Contracts
- No user data is stored in the JWT beyond `sub` (user ID), `role`, and `exp`.
- The blocklist check in `get_current_user` ensures logged-out tokens are rejected.
