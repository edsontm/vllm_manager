# frontend/src/pages/StressTest.tsx

## Purpose
Load-testing UI for vLLM chat completions. Measures latency and throughput under controlled concurrency while surfacing tail latency and failure patterns.

## Core Workflow
1. User selects a running instance and provides a token.
2. Pre-flight request validates auth/model reachability.
3. A bounded concurrency pool sends streaming requests.
4. Live stats are updated per completed request.
5. Final aggregates are rendered (TTFT, ITL, E2EL, RPS, TPS, error rate).

## Key Functions

### `runRequest(...) -> Promise<RequestResult>`
- Sends a streaming chat completion request to `/v1/{slug}/chat/completions`.
- Tracks `ttft` (time to first token), `itl[]` (inter-token intervals), `e2el` (end-to-end latency), and `outputTokens`.
- Handles timeout, abort, HTTP errors, and SSE-embedded errors.

### `runPool(concurrency, total, task, onResult, signal)`
- Worker-pool scheduler that runs up to `concurrency` in-flight tasks.
- Applies per-task timeout safety wrapper.
- Reports each result through `onResult` for live UI updates.

### `computeMetrics(liveStats)`
- Produces TTFT/ITL/E2EL distribution stats (mean, P50, P95, P99, min, max).
- Produces scalar KPIs: RPS, TPS, elapsed wall time, and error rate.

### `handleRun()`
- Normalizes token input and builds messages payload.
- Executes pre-flight non-streaming check with `PREFLIGHT_TIMEOUT_MS`.
- Starts run with global timeout (`RUN_TIMEOUT_MS`).
- Streams updates into React state for progress and charts.

### `handleStop()`
- Aborts current run via `AbortController`.

## Metrics Definitions
- `TTFT`: elapsed time before first generated token.
- `ITL`: time between successive generated tokens.
- `E2EL`: full request duration.
- `RPS`: completed requests per second.
- `TPS`: generated output tokens per second.

## Contracts
- Test traffic uses reverse-proxy route paths (`/v1/{slug}/...`), not internal container ports.
- Run button is disabled until instance and token requirements are satisfied.
- Pre-flight failure blocks the run and surfaces a clear error reason.
- Live result panel remains usable even with partial failures.
