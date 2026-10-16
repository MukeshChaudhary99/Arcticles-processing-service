import json
import logging
import re
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
path_context: ContextVar[str] = ContextVar("url_path", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        record.url_path = path_context.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": record.request_id,
            "url_path": record.url_path,
            "message": record.getMessage(),
        }
        for field in ("status_code", "duration_ms", "method"):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Emit one access event from our middleware with request context.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("x-request-id", "")
        request_id = (
            supplied
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", supplied)
            else str(uuid4())
        )
        id_token = request_id_context.set(request_id)
        path_token = path_context.set(scope["path"])
        start = time.monotonic()
        status_code = 500
        started = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, started
            if message["type"] == "http.response.start":
                started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception:
            logging.getLogger(__name__).exception("Unhandled request error")
            if started:
                raise
            response = JSONResponse(
                {"detail": "Internal server error", "request_id": request_id},
                status_code=500,
            )
            await response(scope, receive, send_with_context)
        finally:
            logging.getLogger("app.access").info(
                "request completed",
                extra={
                    "status_code": status_code,
                    "method": scope["method"],
                    "duration_ms": round((time.monotonic() - start) * 1000, 2),
                },
            )
            request_id_context.reset(id_token)
            path_context.reset(path_token)
