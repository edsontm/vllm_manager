# frontend/src/__tests__/

## Purpose
Vitest + React Testing Library test suite for the frontend. Uses MSW (Mock Service Worker) to intercept API calls and return controlled fixtures.

## Structure
```
frontend/src/__tests__/
├── setup.ts                 vitest globals, @testing-library/jest-dom matchers, MSW server lifecycle
├── mocks/
│   ├── server.ts            MSW Node server (used in Vitest)
│   ├── handlers/
│   │   ├── auth.ts          Mock /auth/* endpoints
│   │   ├── instances.ts     Mock /instances/* endpoints
│   │   ├── metrics.ts       Mock /metrics/* endpoints
│   │   ├── models.ts        Mock /models/* endpoints
│   │   ├── tokens.ts        Mock /tokens/* endpoints
│   │   └── queue.ts         Mock /queue/* endpoints
├── pages/
│   ├── Dashboard.test.tsx   Renders instance cards; suggestion banner appears/dismisses
│   ├── Instances.test.tsx   CRUD table; form validation; start/stop button states
│   ├── Models.test.tsx      HF search; deploy wizard steps; progress SSE
│   ├── Users.test.tsx       Admin guard; CRUD form; delete confirmation
│   ├── Tokens.test.tsx      Generate modal; one-time reveal; revoke
│   ├── Queue.test.tsx       Depth gauge colours; slider config update
│   └── TestInterface.test.tsx  Send request; stream rendering; context length display
└── components/
    └── CodeExample.test.tsx  All three code tabs; copy button; HTTPS URL assertion
```

## Running Tests
```bash
# inside frontend container or with pnpm locally
pnpm test              # watch mode
pnpm test --run        # CI mode (single pass)
pnpm test --coverage   # with coverage report
```

## Key Assertions
- `CodeExample` — asserts generated URLs always contain `https://llm.ufms.br` and never a bare port.
- `Tokens` — asserts raw token is visible in reveal modal but not in the token list table.
- `Users` — asserts admin-only routes redirect non-admin users.
- `Instances` — asserts form fields are disabled when `status !== "stopped"`.
