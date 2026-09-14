from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.schemas import NotifyRequest

logger = logging.getLogger(__name__)


class UnknownChannelError(ValueError):
    pass


class NoProviderConfiguredError(RuntimeError):
    pass


class DeliveryFailedError(RuntimeError):
    def __init__(self, failures: dict[str, str], skipped: list[str]) -> None:
        super().__init__("All configured notification deliveries failed")
        self.failures = failures
        self.skipped = skipped


@dataclass(slots=True)
class DeliveryResult:
    channel: str
    delivered_to: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "sent" if not self.failed and not self.skipped else "partial"


class NotificationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, payload: NotifyRequest) -> DeliveryResult:
        channel = payload.channel or self.settings.default_channel
        routes = self.settings.routes
        if channel not in routes:
            raise UnknownChannelError(channel)

        provider_urls = self.settings.provider_urls
        providers = routes[channel]
        result = DeliveryResult(channel=channel)

        if not providers:
            raise NoProviderConfiguredError(f"Channel '{channel}' has no providers")

        body = self._render_body(payload)
        for provider in providers:
            url = provider_urls.get(provider)
            if not url:
                result.skipped.append(provider)
                continue

            try:
                if self._send_with_apprise(url, payload.title, body, payload.level):
                    result.delivered_to.append(provider)
                else:
                    result.failed[provider] = "Provider returned an unsuccessful result"
            except Exception as exc:  # provider/network boundary
                logger.exception(
                    "Notification provider failed",
                    extra={"provider": provider, "channel": channel},
                )
                result.failed[provider] = type(exc).__name__

        if not result.delivered_to:
            if result.failed:
                raise DeliveryFailedError(result.failed, result.skipped)
            raise NoProviderConfiguredError(
                f"No configured providers are available for channel '{channel}'"
            )

        return result

    @staticmethod
    def _render_body(payload: NotifyRequest) -> str:
        parts = [payload.message]
        if payload.source:
            parts.append(f"Source: {payload.source}")
        if payload.metadata:
            parts.append(
                "Metadata:\n"
                + json.dumps(payload.metadata, ensure_ascii=False, sort_keys=True, default=str)
            )
        return "\n\n".join(parts)

    @staticmethod
    def _send_with_apprise(url: str, title: str, body: str, level: str) -> bool:
        # Import lazily so configuration/health checks do not need to initialize
        # provider plugins until a message is actually sent.
        import apprise

        notify_type = {
            "info": apprise.NotifyType.INFO,
            "success": apprise.NotifyType.SUCCESS,
            "warning": apprise.NotifyType.WARNING,
            "error": apprise.NotifyType.FAILURE,
            "critical": apprise.NotifyType.FAILURE,
        }[level]

        client = apprise.Apprise()
        if not client.add(url):
            raise ValueError("Invalid Apprise provider URL")
        return bool(client.notify(title=title, body=body, notify_type=notify_type))
