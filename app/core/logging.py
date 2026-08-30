"""Logs JSON con contexto de request, sin dependencias.

Cada linea lleva `request_id` y `user_id` sin que quien loguea tenga que pasarlos:
viven en contextvars y el filtro los inyecta. Eso es lo que permite tomar el
`X-Request-Id` de una respuesta rota y sacar la traza completa con un grep.

Lo que NUNCA se loguea (ver CLAUDE.md): tokens en claro, cookies, email completo.
Para emails hay `mask_email`, que conserva el dominio -- suficiente para depurar
entregabilidad, insuficiente para identificar a nadie.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

# Atributos que LogRecord trae de fabrica: todo lo demas es contexto del autor
# de la linea y va al JSON tal cual.
_RESERVED = frozenset(
    (
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
        # uvicorn adjunta la version con codigos ANSI de su propio mensaje.
        # En un log JSON eso es ruido con escapes, no color.
        "color_message",
    )
)


def mask_email(email: str) -> str:
    """`paula@ejemplo.cl` -> `p***@ejemplo.cl`."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    head = local[:1] if local else ""
    return f"{head}***@{domain}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if (rid := request_id_var.get()) is not None:
            payload["request_id"] = rid
        if (uid := user_id_var.get()) is not None:
            payload["user_id"] = uid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure(level: str = "INFO", *, stream: Any = None) -> None:
    """Idempotente: se puede llamar en cada arranque de app y en cada test."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # uvicorn duplica el log de acceso; el nuestro lleva request_id y user_id.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("uvicorn", "uvicorn.error"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
