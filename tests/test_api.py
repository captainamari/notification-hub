from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.notifier import DeliveryResult


class FakeNotifier:
    def send(self, payload):
        return DeliveryResult(channel=payload.channel or "default", delivered_to=["telegram"])


def make_client(*, rate_limit=60):
    settings = Settings(
        _env_file=None,
        api_token="test-token-0123456789abcdef",
        environment="test",
        rate_limit_per_minute=rate_limit,
        telegram_apprise_url="tgram://token/chat",
    )
    return TestClient(create_app(settings=settings, notifier=FakeNotifier()))


def test_health_does_not_require_authentication():
    client = make_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_notify_requires_bearer_token():
    client = make_client()
    response = client.post("/api/v1/notify", json={"title": "x", "message": "y"})
    assert response.status_code == 401


def test_notify_uses_default_channel():
    client = make_client()
    response = client.post(
        "/api/v1/notify",
        headers={"Authorization": "Bearer test-token-0123456789abcdef"},
        json={"title": "Backup complete", "message": "Daily backup succeeded"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "default"
    assert body["delivered_to"] == ["telegram"]
    assert body["status"] == "sent"


def test_rate_limit_is_enforced():
    client = make_client(rate_limit=1)
    headers = {"Authorization": "Bearer test-token-0123456789abcdef"}
    assert client.get("/api/v1/status", headers=headers).status_code == 200
    assert client.get("/api/v1/status", headers=headers).status_code == 429
