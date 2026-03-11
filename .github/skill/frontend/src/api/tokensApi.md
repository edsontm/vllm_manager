# frontend/src/api/tokensApi.ts

## Purpose
Typed API client for generating, listing, and revoking API tokens.

## Exported Functions

| Function | HTTP | Path |
|---|---|---|
| `listTokens(userId?)` | GET | `/tokens?user_id={userId}` |
| `createToken(data)` | POST | `/tokens` |
| `revokeToken(id)` | DELETE | `/tokens/{id}` |

## Key Types
```ts
interface TokenCreate {
  name: string;
  scoped_instance_ids?: number[];  // null = all instances
  expires_at?: string;             // ISO datetime, null = never
}

interface TokenCreateResponse {
  id: number;
  name: string;
  token: string;         // RAW token — shown only once, copy immediately
  scoped_instance_ids: number[] | null;
  created_at: string;
  expires_at: string | null;
}

interface TokenRead {
  id: number;
  name: string;
  scoped_instance_ids: number[] | null;
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
  // NOTE: raw token is NEVER returned by list/get endpoints
}
```
