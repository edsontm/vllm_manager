# frontend/vite.config.ts

## Purpose
Vite build and dev-server configuration. Defines the proxy rules used in development so the frontend on `:5174` can reach the FastAPI backend on `:8080` without CORS issues.

## Dev Server Proxy
```ts
server: {
  proxy: {
    "/api": {
      target: "http://localhost:8080",
      rewrite: (path) => path.replace(/^\/api/, ""),
      changeOrigin: true,
    },
    "/v1": {
      target: "http://localhost:8080",
      changeOrigin: true,
    },
  }
}
```
This mirrors the production nginx routing so frontend code works identically in both environments.

## Build Output
- `outDir: "dist"` — production bundle picked up by the nginx `runtime` Docker stage.
- `sourcemap: false` in production (enable with `VITE_SOURCEMAP=true` for debugging).

## Aliases
```ts
resolve: {
  alias: { "@": "/src" }
}
```
Used throughout the codebase as `import { ... } from "@/api/authApi"`.

## Environment Variables
All `VITE_*` variables from `.env` are statically substituted at build time and embedded in the bundle.

## Contracts
- The proxy only runs in development (`vite dev`). In production, nginx handles routing.
- No secrets should ever be placed in `VITE_*` variables — they are embedded in the client bundle.

## Typography
Fonts are loaded from Google Fonts in `index.html` (not via a Vite plugin, to keep build output deterministic):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,200;12..96,800;12..96,900&family=IBM+Plex+Sans:wght@200;400;700&family=JetBrains+Mono:wght@300;600&display=swap" rel="stylesheet">
```

### Font Roles

| Font | Weights | Role |
|---|---|---|
| `Bricolage Grotesque` | 800 / 900 | Page titles, section headers, status badges — display use only |
| `IBM Plex Sans` | 200 / 700 | All body text, labels, table content — never 400 vs 600 |
| `JetBrains Mono` | 300 / 600 | Code blocks, token strings, raw JSON, metric numbers |

### Scale Rules
- Heading → body size jump must be **≥ 3×** (e.g. `48px` title, `14px` body)
- Use weight extremes: `200` for captions/secondary, `800`/`900` for headings — never `400 vs 600`
- Metric readouts (GPU %, tokens/s) use `JetBrains Mono` at `900` weight and large size to create visual punch

### Never use
`Inter`, `Roboto`, `Open Sans`, `Lato`, or any default system font stack as a primary typeface.
