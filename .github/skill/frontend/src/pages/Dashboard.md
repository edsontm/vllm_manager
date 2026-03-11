# frontend/src/pages/Dashboard.tsx

## Purpose
Landing page of the application. Displays a real-time overview card for each vLLM instance: status, GPU utilisation, throughput, average context length, and any active context-length adjustment suggestions.

## Layout
```
┌─────────────────────────────────────────┐
│  Dashboard          [Refresh] [Settings] │
├──────────┬──────────┬────────────────────┤
│ Instance │ Instance │ + Add Instance     │
│   Card   │   Card   │                   │
│  GPU 87% │  GPU 42% │                   │
│  342 t/s │  189 t/s │                   │
│  ⚠ Ctx  │           │                   │
└──────────┴──────────┴────────────────────┘
```

## Key Components Used
- `InstanceCard` — single instance status widget (status badge, spark-line GPU chart, key metrics)
- `ContextSuggestionBanner` — dismissible yellow banner shown when `metricsApi.getContextSuggestion()` returns a suggestion
- `AddInstanceButton` — opens the Instances page with the create form pre-opened

## Data Fetching
- `useQuery(["metrics", "summary"], getMetricsSummary, { refetchInterval: 5000 })` — polls every 5 s
- On mount, also queries `getContextSuggestion` for each running instance

## Contracts
- Auto-refresh via `refetchInterval`; user can disable polling with a toggle.
- Clicking an instance card navigates to `/instances/{id}`.
- Suggestion banner links to the Instances page with the relevant instance pre-selected.

## Typography
- **Page title "Dashboard"**: `Bricolage Grotesque` 900, `48px` — dominant, zero ambiguity
- **Instance card metric values** (GPU %, tokens/s): `JetBrains Mono` 600, `36px` — numbers must feel data-dense and precise
- **Card labels** ("GPU Utilisation", "Throughput"): `IBM Plex Sans` 200, `12px` — extreme weight contrast against the metric value above
- **Status badges** (running / stopped / error): `Bricolage Grotesque` 800, uppercase, `11px` — small but punchy
- **Suggestion banner body text**: `IBM Plex Sans` 400, `14px`

Size jump rule: card metric number (`36px`) to label (`12px`) = 3× — enforce this strictly.
