# backend/app/routers/proxy.py

## Purpose
The core inference proxy. Authenticates static Bearer tokens, enqueues or directly forwards requests to the appropriate vLLM instance, and streams responses back to the caller.

## Route Pattern
```
ANY /v1/{slug}/{path:path}
```
- `slug` — identifies the `VllmInstance` (e.g. `mistral-7b`).
- `path` — forwarded verbatim to vLLM (e.g. `chat/completions`, `completions`, `embeddings`).
- Supports `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`.

## Full Public URL (via nginx)
```
POST https://llm.ufms.br/v1/{slug}/chat/completions
Authorization: Bearer <api_token>
```

## Request Flow
1. Extract `Authorization: Bearer <token>` header and validate via `get_vllm_token` dependency (checks bcrypt hash, scope, expiry, `is_enabled`).
2. Look up `VllmInstance` by `slug`.
3. Validate token's `scoped_instance_ids` (if non-empty) and `scoped_model_ids` (if non-empty and request body contains `model`).
4. **All requests** (streaming and non-streaming) are pushed to the Redis priority queue via `queue_service.enqueue()`, keyed by the requesting user's `queue_priority_role`.
5. The `queue_worker` picks up the job, strips the `stream` flag, and forwards to vLLM as a regular (non-streaming) request via httpx.
6. The result is published back via Redis pub/sub; the proxy awaits `subscribe_result()` (660 s timeout).
7. For requests that originally had `stream=True`, the proxy wraps the complete response as a single SSE event: `data: {body}\n\ndata: [DONE]\n\n`.
8. Logs `context_length` + `latency_ms` via `log_inference_request()`.

## Streaming Behaviour
vLLM is always called with streaming disabled by the queue worker. The proxy reconstructs an SSE envelope for clients that requested `stream=True`, ensuring compatibility with OpenAI streaming clients while decoupling from vLLM's server-sent events.

## Queue Depth Header
Every response includes `X-Queue-Depth: <n>` reporting the queue depth at time of enqueue.

## Example (Python openai library)
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://llm.ufms.br/v1/mistral-7b",
    api_key="your_api_token"
)

response = client.chat.completions.create(
    model="mistralai/Mistral-7B-Instruct-v0.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Example (curl)
```bash
curl -X POST https://llm.ufms.br/v1/mistral-7b/chat/completions \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"model": "mistralai/Mistral-7B-Instruct-v0.2", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Contracts
- This router ONLY accepts requests via nginx on port 443. Internal port 8080 must not be exposed externally.
- Token validation uses constant-time bcrypt comparison to prevent timing attacks.
- `context_length` is derived from `max_tokens` or `max_new_tokens` in the request body (logged as-is, not verified against actual usage).
