# frontend/src/api/authApi.ts

## Purpose
Typed API client for authentication endpoints.

## Exported Functions

### `login(username: string, password: string): Promise<LoginResponse>`
`POST /auth/login` → stores JWT in localStorage and returns `{ access_token, expires_in }`.

### `logout(): Promise<void>`
`POST /auth/logout` → clears localStorage token.

### `refresh(): Promise<LoginResponse>`
`POST /auth/refresh` → replaces stored JWT with a new one.

## Types
```ts
interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // seconds
}
```

## Usage
```ts
import { login } from "@/api/authApi";
await login("admin", "secret");
```
