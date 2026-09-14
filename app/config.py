from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote, urlencode

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "notification-hub"
    environment: str = "production"
    log_level: str = "INFO"
    api_token: str = Field(min_length=16)
    default_channel: str = "default"
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)

    telegram_apprise_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_ids: str | None = None

    email_apprise_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    smtp_use_tls: bool = True

    route_default: str = "telegram"
    route_ops: str = "telegram"
    route_trading: str = "telegram"
    route_warning: str = "telegram,email"
    route_critical: str = "telegram,email"

    @model_validator(mode="after")
    def normalize_channels(self) -> "Settings":
        self.default_channel = self.default_channel.strip().lower()
        return self

    @staticmethod
    def _split_csv(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def routes(self) -> dict[str, list[str]]:
        return {
            "default": self._split_csv(self.route_default),
            "ops": self._split_csv(self.route_ops),
            "trading": self._split_csv(self.route_trading),
            "warning": self._split_csv(self.route_warning),
            "critical": self._split_csv(self.route_critical),
        }

    @property
    def provider_urls(self) -> dict[str, str]:
        providers: dict[str, str] = {}

        telegram = self._telegram_url()
        if telegram:
            providers["telegram"] = telegram

        email = self._email_url()
        if email:
            providers["email"] = email

        return providers

    def _telegram_url(self) -> str | None:
        if self.telegram_apprise_url:
            return self.telegram_apprise_url.strip()

        if not self.telegram_bot_token or not self.telegram_chat_ids:
            return None

        token = quote(self.telegram_bot_token.strip(), safe=":")
        targets = [quote(target, safe="@+-_") for target in self._split_csv(self.telegram_chat_ids)]
        if not targets:
            return None
        return f"tgram://{token}/{'/'.join(targets)}"

    def _email_url(self) -> str | None:
        if self.email_apprise_url:
            return self.email_apprise_url.strip()

        required = (
            self.smtp_host,
            self.smtp_username,
            self.smtp_password,
            self.email_from,
            self.email_to,
        )
        if not all(required):
            return None

        scheme = "mailtos" if self.smtp_use_tls else "mailto"
        username = quote(self.smtp_username or "", safe="")
        password = quote(self.smtp_password or "", safe="")
        host = (self.smtp_host or "").strip()
        query = urlencode(
            {
                "from": (self.email_from or "").strip(),
                "to": ",".join(self._split_csv(self.email_to)),
            }
        )
        return f"{scheme}://{username}:{password}@{host}:{self.smtp_port}/?{query}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
