# frontend/src/pages/TestInterface.tsx

## Purpose
An interactive chat/completion test UI for evaluating vLLM instance reliability, response quality, and performance. Allows users to send requests using their own token and inspect raw API traffic.

## Layout
```
┌─────────────────────────────────────────────────┐
│ Test Interface         Instance: [mistral-7b ▾] │
├───────────────────────┬─────────────────────────┤
│   Chat Window         │  Request / Response      │
│                       │  (raw JSON)              │
│  [User]: Hello!       │  POST /v1/mistral-7b/    │
│  [AI]: Hi there! ...  │  chat/completions         │
│                       │  {                        │
│                       │    "model": "...",        │
│  [────────────────]   │    "messages": [...]      │
│  [Send]  [Clear]      │  }                        │
│                       │  ─────── response ─────── │
│  Token: [input]       │  Context: 1 024 tokens    │
│  Mode: Chat | Compl.  │  Latency: 342 ms          │
└───────────────────────┴─────────────────────────┘
```

## Features
- **Instance selector** — dropdown of running instances
- **Token input** — user enters an API token (stored in component state only, never persisted)
- **Mode toggle** — Chat Completions vs Plain Completions
- **System prompt** — collapsible textarea for chat mode
- **Stream toggle** — enables `stream: true` in the request; response rendered token-by-token
- **Raw JSON panel** — shows exact request body sent and full response received
- **Metrics bar** — displays `context_length` (prompt + completion tokens) and `latency_ms` per request
- **Request history** — last 10 requests listed with timestamp, context length, latency

## Contracts
- All requests are made client-side to `https://llm.ufms.br/v1/{slug}/chat/completions` — never to internal ports.
- The token entered here is used as the `Authorization: Bearer` header (same as any external client).
- Streaming mode uses `EventSource` / `fetch` with `ReadableStream` to render tokens as they arrive.
- Context length is parsed from the response `usage.prompt_tokens + usage.completion_tokens` field.

## Typography
- **Page title "Test Interface"**: `Bricolage Grotesque` 900, `48px`
- **Chat bubble — AI response text**: `IBM Plex Sans` 400, `15px` — readable body weight here (exception: content, not UI)
- **Chat bubble — User input**: `IBM Plex Sans` 700, `15px` — heavier to visually distinguish user from AI
- **Raw JSON panel content**: `JetBrains Mono` 300, `12px` — tight, dense, information-rich
- **Metric bar values** (context tokens, latency): `JetBrains Mono` 900, `28px` — these numbers are the point of the interface; treat them as the headline
- **Metric bar labels** ("Context", "Latency"): `IBM Plex Sans` 200, `11px` uppercase — ultralight vs the 900-weight value above creates maximum contrast
- **Request history timestamps**: `JetBrains Mono` 200, `11px`
