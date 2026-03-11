# frontend/src/pages/Login.tsx

## Purpose
Authentication entry page for the web UI. Collects username/password, requests a JWT from the backend, loads user profile data, stores auth state, and redirects to the main dashboard.

## Layout
```
┌─────────────────────────────────────────┐
│               vLLM Manager              │
│ ┌─────────────────────────────────────┐ │
│ │ USERNAME                            │ │
│ │ [..................................]│ │
│ │ PASSWORD                            │ │
│ │ [..................................]│ │
│ │ [ Sign in ]                         │ │
│ └─────────────────────────────────────┘ │
│         Inline error (if any)          │
└─────────────────────────────────────────┘
```

## State and Flow
- Local state: `username`, `password`, `error`, `loading`.
- On submit (`handleSubmit`):
1. Prevent default form submit.
2. Call `authApi.login(username, password)`.
3. Fetch profile with `authApi.me(access_token)`.
4. Persist auth using `useAuthStore().setAuth(access_token, me)`.
5. Navigate to `/` with `replace: true`.
- On failure: show user-friendly inline error message.

## Dependencies
- `useNavigate` from React Router for redirect.
- `useAuthStore` from Zustand store for auth persistence.
- `authApi.login` and `authApi.me` for auth handshake.

## Contracts
- Credentials are sent only on explicit form submit.
- Submit button is disabled while request is running to prevent duplicate requests.
- On auth failure, user remains on login page and receives readable feedback.
- No token is stored until both login and `/me` calls succeed.
