# nginx/vllm_manager.conf

## Purpose
Nginx server block configuration for `llm.ufms.br`. This file must be placed at `/etc/nginx/sites-available/vllm_manager.conf` and symlinked to `/etc/nginx/sites-enabled/vllm_manager.conf`.

**This is the sole external entry point for all traffic. Ports 80 and 443 only. No vLLM internal port is ever exposed externally.**

## Enabling the Config

```bash
# ── 1. Verify ports 80 and 443 are free or already held by nginx ─
for port in 80 443; do
  ss -tlnp | grep ":${port} " | grep -q nginx \
    && echo "port $port OK (nginx)" \
    || { ss -tlnp | grep -q ":${port} " \
         && echo "PORT $port IN USE by another process — resolve before proceeding" \
         || echo "port $port free"; }
done

# ── 2. Verify the upstream backend is reachable ───────────────────
ss -tlnp | grep -q ':8088' \
  && echo 'backend :8088 OK' \
  || echo 'WARNING: backend not listening on :8088 — start the stack first'

# ── 3. Enable and reload ──────────────────────────────────────────
sudo ln -s /etc/nginx/sites-available/vllm_manager.conf \
           /etc/nginx/sites-enabled/vllm_manager.conf
sudo nginx -t
sudo systemctl reload nginx
```

## Obtaining the SSL Certificate

```bash
sudo certbot --nginx -d llm.ufms.br
```

## Port Routing Map

| External | nginx location | Upstream | Notes |
|---|---|---|---|
| 80 | all | — | Redirect to 443 |
| 443 | `/api/` | `127.0.0.1:8088` | FastAPI; 300 s timeout |
| 443 | `/api/ws/` | `127.0.0.1:8088` | WebSocket upgrade |
| 443 | `/v1/` | `127.0.0.1:8088/v1/` | vLLM proxy; 660 s timeout; 1 GB body; `proxy_buffering off` |
| 443 | `/.well-known/acme-challenge/` | `/var/www/certbot` | Let's Encrypt |
| 443 | `/` | `127.0.0.1:5174` (dev) or `frontend/dist` (prod) | SPA; `try_files $uri /index.html` |

## Key Directives

```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name llm.ufms.br;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name llm.ufms.br;

    ssl_certificate     /etc/letsencrypt/live/llm.ufms.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/llm.ufms.br/privkey.pem;

    client_max_body_size 1G;

    # vLLM inference proxy (token-authenticated; streamed)
    location /v1/ {
        proxy_pass         http://127.0.0.1:8088/v1/;
        proxy_buffering    off;
        proxy_read_timeout 660s;
        proxy_send_timeout 660s;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # FastAPI REST + WebSocket
    location /api/ {
        proxy_pass         http://127.0.0.1:8088/;
        proxy_read_timeout 300s;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # React SPA (production: static files)
    location / {
        root  /home/vllm/dev/vllm_manager/frontend/dist;
        try_files $uri /index.html;
        add_header Cache-Control "no-cache" always;
        location ~* \.(js|css|png|jpg|svg|ico|woff2)$ {
            add_header Cache-Control "public, max-age=31536000, immutable";
        }
    }
}
```

## Constraints
- `proxy_buffering off` on `/v1/` is required for streaming LLM responses.
- The upstream addresses are always `127.0.0.1:<port>` — Docker containers bind to localhost only.
- Modifying `/etc/nginx/nginx.conf` is not permitted; only `sites-available/vllm_manager.conf`.

## Relation to Existing Sites
- `agendanacional.ufms.br` uses ports 8000/8001/15004 — no conflict.
- `siginterpdf.ufms.br` uses port 9052 (vLLM) and 3300 (API) — no conflict with this application's ports (8088/5174).
