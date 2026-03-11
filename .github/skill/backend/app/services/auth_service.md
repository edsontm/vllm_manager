# backend/app/services/auth_service.py

## Purpose
Authentication service logic used by the auth router. Validates username and password credentials against the database and enforces user active status before issuing JWTs.

## Exported Functions

### `async authenticate_user(username: str, password: str, db: AsyncSession) -> User`
- Queries `User` by `username`.
- Verifies password with `core.security.verify_password()`.
- Rejects disabled users (`is_active == False`).
- Returns the authenticated `User` ORM object.

## Dependencies
- `sqlalchemy.ext.asyncio.AsyncSession`
- `app.models.user.User`
- `app.core.security.verify_password`
- `app.core.exceptions.UnauthorizedError`

## Error Behavior
- Raises `UnauthorizedError("Incorrect username or password")` when the user does not exist or password verification fails.
- Raises `UnauthorizedError("User is inactive")` when credentials are valid but the account is disabled.

## Contracts
- Passwords are never compared in plain text; hash verification is always delegated to `verify_password`.
- The function does not create tokens or mutate user state; it only authenticates credentials.
- Returned `User` is considered trusted input for downstream token creation in the auth router.
