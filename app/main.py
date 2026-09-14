from __future__ import annotations

import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app import __version__
from app.config import Settings, get_settings
from app.notifier import (
    DeliveryFailedError,
    NoProviderConfiguredError,
    NotificationService,
    UnknownChannelError,
)
from app.schemas import NotifyRequest, NotifyResponse, StatusResponse
from app.security import SlidingWindowRateLimiter, require_api_token

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    notifier: NotificationService | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, runtime_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=runtime_settings.app_name,
        version=__version__,
        docs_url=None if runtime_settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.state.settings = runtime_settings
    app.state.notifier = notifier or NotificationService(runtime_settings)
    app.state.rate_limiter = SlidingWindowRateLimiter(
        runtime_settings.rate_limit_per_minute
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get(
        "/api/v1/status",
        response_model=StatusResponse,
        dependencies=[Depends(require_api_token)],
        tags=["system"],
    )
    async def service_status(request: Request) -> StatusResponse:
        cfg: Settings = request.app.state.settings
        return StatusResponse(
            configured_providers=sorted(cfg.provider_urls),
            routes=cfg.routes,
            default_channel=cfg.default_channel,
        )

    @app.post(
        "/api/v1/notify",
        response_model=NotifyResponse,
        dependencies=[Depends(require_api_token)],
        tags=["notifications"],
    )
    async def notify(payload: NotifyRequest, request: Request) -> NotifyResponse:
        request_id = uuid.uuid4().hex
        service: NotificationService = request.app.state.notifier
        try:
            result = await run_in_threadpool(service.send, payload)
        except UnknownChannelError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown notification channel: {exc}",
            ) from exc
        except NoProviderConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except DeliveryFailedError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": str(exc),
                    "failed": exc.failures,
                    "skipped": exc.skipped,
                },
            ) from exc

        logger.info(
            "Notification processed",
            extra={
                "request_id": request_id,
                "channel": result.channel,
                "source": payload.source,
                "delivered_to": result.delivered_to,
                "failed_providers": sorted(result.failed),
            },
        )
        return NotifyResponse(
            request_id=request_id,
            status=result.status,  # type: ignore[arg-type]
            channel=result.channel,
            delivered_to=result.delivered_to,
            skipped=result.skipped,
            failed=result.failed,
        )

    return app
