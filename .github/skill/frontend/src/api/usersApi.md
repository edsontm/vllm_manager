# frontend/src/api/usersApi.ts

## Purpose
Typed API client for user management (admin operations + own profile).

## Exported Functions

| Function | HTTP | Path | Auth |
|---|---|---|---|
| `listUsers(page?, size?, search?)` | GET | `/users` | admin |
| `getMe()` | GET | `/users/me` | any |
| `getUser(id)` | GET | `/users/{id}` | admin |
| `createUser(data)` | POST | `/users` | admin |
| `updateUser(id, data)` | PATCH | `/users/{id}` | admin/self |
| `deleteUser(id)` | DELETE | `/users/{id}` | admin |

## Key Types
```ts
interface UserRead {
  id: number;
  username: string;
  email: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
}

interface UserCreate {
  username: string;
  email: string;
  password: string;
  role?: "admin" | "user";
}

interface UserUpdate {
  email?: string;
  password?: string;
  is_active?: boolean;
  role?: "admin" | "user"; // admin-only field
}
```
