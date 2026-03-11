# frontend/src/pages/Queue.tsx

## Purpose
Real-time monitoring and configuration of the per-instance request queues. Shows queue depth, throughput, and allows adjustment of batch parameters.

## Layout
```
┌─────────────────────────────────────────────────┐
│  Queue Monitor                                   │
├───────────┬─────────────────────────────────────┤
│ Instance  │        Queue Depth Gauge             │
│ Selector  │  ████████░░░░░░░░  8 / 512           │
│           │                                      │
│ mistral   │  Batch Size:    [──●────────] 16     │
│ llama-3   │  Batch Timeout: [─────●─────] 200 ms │
│           │                                      │
│           │  Throughput Chart (last 30 min)       │
│           │  ▄▅▆▅▄▃▂▄▅▆▇▆▅▄ tokens/s             │
└───────────┴─────────────────────────────────────┘
```

## Data Fetching
- `useQuery(["queue", instanceId], () => queueApi.getQueueStatus(instanceId), { refetchInterval: 3000 })`
- Refreshes every 3 s for near-real-time feel without WebSocket complexity

## Batch Config Controls (admin only)
- **Batch Size** slider — range 1–512, step 1; calls `queueApi.updateQueueConfig()` on change (debounced 500 ms)
- **Batch Timeout** slider — range 50–5000 ms; same update pattern
- Changes take effect immediately in the worker (no restart required)

## Contracts
- Non-admin users see the queue depth and chart read-only; the sliders are hidden.
- Queue depth gauge colour: green < 25%, yellow < 75%, red ≥ 75% of theoretical max.

## Typography
- **Page title "Queue Monitor"**: `Bricolage Grotesque` 900, `48px`
- **Depth number** (e.g. `8`): `JetBrains Mono` 900, `72px` — this is the primary data point, make it dominate the card
- **Depth denominator** (e.g. `/ 512`): `JetBrains Mono` 200, `24px` — extreme weight contrast with the numerator above it (3× size difference + 700 weight difference)
- **Slider labels** ("Batch Size", "Batch Timeout"): `IBM Plex Sans` 200, `11px` uppercase tracked
- **Slider current value**: `JetBrains Mono` 600, `16px`
- **Chart axis labels**: `IBM Plex Sans` 200, `11px`
- **Chart title**: `IBM Plex Sans` 700, `13px` uppercase
