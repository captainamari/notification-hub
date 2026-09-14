from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


NotificationLevel = Literal["info", "success", "warning", "error", "critical"]


class NotifyRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)
    channel: str | None = Field(default=None, max_length=50)
    level: NotificationLevel = "info"
    source: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] | None = None

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class NotifyResponse(BaseModel):
    request_id: str
    status: Literal["sent", "partial"]
    channel: str
    delivered_to: list[str]
    skipped: list[str]
    failed: dict[str, str]


class StatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
    configured_providers: list[str]
    routes: dict[str, list[str]]
    default_channel: str
