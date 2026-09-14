# VPS deployment

This guide targets a small Linux VPS (including 1 vCPU / 1 GB RAM) with Docker Compose and an HTTPS reverse proxy.

## 1. Clone and configure

```bash
git clone https://github.com/captainamari/notification-hub.git
cd notification-hub
cp .env.example .env
openssl rand -hex 32
```

Put the generated value in `API_TOKEN` and configure Telegram and/or SMTP in `.env`.

For Telegram, create a bot with BotFather and set:

```env
TELEGRAM_BOT_TOKEN=123456:replace-me
TELEGRAM_CHAT_IDS=123456789
```

For SMTP, set the host, credentials, sender and recipient fields. Provider secrets remain only on the notification-hub VPS; callers never need them.

## 2. Start the service

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 notification-hub
curl http://127.0.0.1:8080/health
```

The Compose file binds to loopback only. Other VPSes should call the service through HTTPS on an Nginx/Caddy reverse proxy, not port 8080 directly.

## 3. Nginx reverse proxy

Example server block (replace the hostname):

```nginx
server {
    listen 443 ssl http2;
    server_name notify.example.com;

    # Configure ssl_certificate / ssl_certificate_key using your normal TLS setup.

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        client_max_body_size 128k;
    }
}
```

Do not expose the container's port 8080 to the public Internet if the reverse proxy is available.

## 4. Verify authenticated delivery

```bash
curl -X POST https://notify.example.com/api/v1/notify \
  -H "Authorization: Bearer $NOTIFICATION_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "notification-hub online",
    "message": "Deployment test succeeded",
    "channel": "default",
    "source": "notification-hub"
  }'
```

Expected success response contains `status`, `delivered_to`, `skipped`, and a `request_id`.

## 5. Call from another VPS

Each caller needs only the hub URL, API token, and optionally a channel:

```env
NOTIFICATION_API_URL=https://notify.example.com
NOTIFICATION_API_TOKEN=replace-me
NOTIFICATION_CHANNEL=ops
```

The caller should not contain Telegram bot tokens or SMTP passwords.

## Operational notes

- Keep `.env` out of Git; it is ignored by the repository.
- Back up the `.env` securely because it contains provider credentials.
- Use one Uvicorn worker on a 1C1G VPS. The in-memory rate limiter is intentionally scoped to this single-worker MVP.
- `/health` is unauthenticated and reveals only service status/version.
- `/api/v1/status` and `/api/v1/notify` require the Bearer token.
- If this VPS itself fails, it cannot notify about its own outage. Use an external monitor (for example Uptime Kuma on another failure domain) for hub availability.
