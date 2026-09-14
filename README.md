# notification-hub

A small self-hosted notification gateway for personal infrastructure and applications. Callers use one authenticated HTTP API; Telegram and SMTP credentials stay centralized on the hub.

## Architecture

```text
Trading / cron / VPS scripts / applications
                  |
                  | HTTPS + Bearer token
                  v
         notification-hub (FastAPI)
                  |
           channel routing
                  |
                Apprise
             /            \
        Telegram          Email
```

The API contract is intentionally independent from Apprise. Apprise is an internal delivery engine and can be replaced later without changing every caller.

## MVP API

### Health

```http
GET /health
```

No authentication. Returns only status and version.

### Service status

```http
GET /api/v1/status
Authorization: Bearer <API_TOKEN>
```

Shows configured provider aliases and channel routing without exposing credentials.

### Send notification

```http
POST /api/v1/notify
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

```json
{
  "channel": "ops",
  "level": "warning",
  "title": "VPS CPU High",
  "message": "CPU usage reached 92%",
  "source": "vps-us-01",
  "metadata": {"cpu": 92}
}
```

`channel` is optional; when omitted the server uses `DEFAULT_CHANNEL`.

Built-in routes are `default`, `ops`, `trading`, `warning`, and `critical`. Routes map only to server-side provider aliases, so callers cannot turn the hub into an arbitrary email/Telegram relay.

## Configuration

```bash
cp .env.example .env
```

At minimum set a random `API_TOKEN` plus Telegram and/or SMTP settings. `API_TOKEN` must be at least 16 characters; 32 random bytes or more are recommended.

Example Telegram-only setup:

```env
API_TOKEN=replace-with-a-long-random-token
TELEGRAM_BOT_TOKEN=123456:replace-me
TELEGRAM_CHAT_IDS=123456789
```

Example routing:

```env
ROUTE_DEFAULT=telegram
ROUTE_OPS=telegram
ROUTE_TRADING=telegram
ROUTE_WARNING=telegram,email
ROUTE_CRITICAL=telegram,email
```

If a route names an unconfigured provider and at least one configured provider succeeds, the response is `partial` and lists the skipped provider. If no provider on the route is configured, the API returns `503`.

Advanced users can set `TELEGRAM_APPRISE_URL` or `EMAIL_APPRISE_URL` directly; those values override the friendly provider-specific fields.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# edit .env
uvicorn app.main:create_app --factory --reload --port 8080
```

In non-production environments, OpenAPI docs are available at `/docs`.

## Docker

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

The Compose service binds `8080` only to `127.0.0.1`; use an HTTPS reverse proxy for calls from other VPSes. See [docs/deployment.md](docs/deployment.md).

## Python caller example

```python
import os
import requests

base_url = os.environ["NOTIFICATION_API_URL"].rstrip("/")
token = os.environ["NOTIFICATION_API_TOKEN"]

response = requests.post(
    f"{base_url}/api/v1/notify",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "channel": "trading",
        "level": "info",
        "title": "Market data updated",
        "message": "Daily data refresh completed successfully.",
        "source": "market-regime-lab",
    },
    timeout=10,
)
response.raise_for_status()
```

## Security boundaries

- Provider secrets stay in server-side `.env`; never commit them.
- Callers choose a channel, not an arbitrary recipient address/chat ID.
- Bearer authentication is required for notification/status endpoints.
- A simple in-memory rate limit protects the MVP from accidental message storms.
- Production API documentation is disabled by default.
- The container runs as a non-root user with a read-only filesystem, dropped Linux capabilities, and `no-new-privileges`.

For a future multi-user or higher-throughput version, replace the single API token and in-memory limiter with per-client credentials and a shared store/queue.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
python -m compileall -q app tests
```

GitHub Actions runs linting, tests, bytecode compilation, and a Docker image build.
