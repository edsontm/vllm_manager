# frontend/Dockerfile

## Purpose
Multi-stage Docker image for the React/Vite frontend. In development, the Vite dev server is used directly via `docker-compose.override.yml`. In production, a static build is served from the `backend` nginx static files location or a separate lightweight nginx container.

## Build Stages

### Stage 1: `deps`
- Base: `node:22-alpine`
- Installs pnpm; runs `pnpm install --frozen-lockfile`

### Stage 2: `build`
- Base: inherits from `deps`
- Runs `pnpm build` (Vite builds to `dist/`)
- Sets `VITE_API_BASE_URL=/api` so all API calls are relative to the same origin (proxied by nginx)

### Stage 3: `runtime`
- Base: `nginx:alpine`
- Copies `dist/` from `build` stage into `/usr/share/nginx/html`
- Copies a minimal `nginx.conf` that:
  - Serves `index.html` for all routes (`try_files $uri /index.html`)
  - Sets appropriate cache headers (`Cache-Control: max-age=31536000` for hashed assets)
- Exposes port 80 (nginx → picked up by the outer nginx reverse proxy)

## Development (override)
In `docker-compose.override.yml`:
- Uses `node:22-alpine` directly (no multi-stage)
- Volume-mounts `./frontend:/app`
- CMD: `pnpm dev --host 0.0.0.0 --port 5174`
- No build step; Vite serves with HMR

## Environment Variables (build-time)
| Variable | Value in prod | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `/api` | Base URL for API calls; nginx proxies `/api` → backend:8080 |
| `VITE_APP_TITLE` | `vLLM Manager` | Browser tab title |
