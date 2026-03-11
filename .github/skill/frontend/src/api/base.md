# frontend/src/api/base.ts

## Purpose
Shared Axios instance used by all API client modules. Injects authentication, handles token expiry, and standardises error shape.

## Configuration
- `baseURL`: `https://llm.ufms.br/api` in production; `http://localhost:8080` in development (via Vite proxy).
- `timeout`: 30 000 ms for regular requests; individual clients override for long-running operations (model downloads: no timeout; inference via proxy: 660 000 ms matching nginx timeout).

## Request Interceptor
- Reads JWT from `localStorage` (key: `vllm_manager_token`).
- Adds `Authorization: Bearer <token>` header if present.

## Response Interceptor
- On `401` → clears stored token, redirects to `/login`.
- On `5xx` → extracts `error` and `message` from JSON body; throws a typed `ApiError`.
- On network error → throws `ApiError` with `message: "Network error"`.

## Exported
- `apiClient: AxiosInstance` — used by all `*Api.ts` modules.
- `ApiError: class` — `{ error: string, message: string, requestId: string }`.

## Contracts
- No business logic here — only HTTP wiring.
- The `base_url` is constructed from env var `VITE_API_BASE_URL` (set at build time).
