import pytest

from app.config import Settings
from app.notifier import NoProviderConfiguredError, NotificationService, UnknownChannelError
from app.schemas import NotifyRequest


def settings(**overrides):
    values = {"api_token": "x" * 32}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_unknown_channel_is_rejected():
    service = NotificationService(settings())
    with pytest.raises(UnknownChannelError):
        service.send(NotifyRequest(title="x", message="y", channel="missing"))


def test_route_without_configured_provider_returns_service_error():
    service = NotificationService(settings())
    with pytest.raises(NoProviderConfiguredError):
        service.send(NotifyRequest(title="x", message="y"))


def test_partial_delivery_when_optional_provider_is_missing(monkeypatch):
    cfg = settings(
        telegram_apprise_url="tgram://token/chat",
        route_warning="telegram,email",
    )
    service = NotificationService(cfg)
    monkeypatch.setattr(service, "_send_with_apprise", lambda *args, **kwargs: True)

    result = service.send(
        NotifyRequest(title="CPU high", message="92%", channel="warning")
    )
    assert result.delivered_to == ["telegram"]
    assert result.skipped == ["email"]
    assert result.status == "partial"
