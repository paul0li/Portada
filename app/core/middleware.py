"""El borde HTTP: contexto de request y log de acceso.

Cada request recibe un id que viaja en tres lugares a la vez: el contextvar (y
por lo tanto cada linea de log que se emita durante el request), la cabecera
`X-Request-Id` de la respuesta, y el cuerpo de un error si lo hubo. Esa es toda
la historia de observabilidad del MVP: el usuario reporta un id, y un grep
devuelve la traza completa.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.ids import new_id
from app.core.logging import get_logger, request_id_var, user_id_var

log = get_logger("portada.access")

REQUEST_ID_HEADER = "X-Request-Id"

# Ruido que no aporta: se sirven cientos de veces y nunca se investigan.
_QUIET_PATHS = frozenset({"/health", "/favicon.ico"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Se respeta un id entrante (proxy, cliente) para poder correlacionar
        # a traves de saltos, pero se valida la forma: es una cabecera que
        # cualquiera puede escribir y termina en nuestros logs.
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if incoming.isalnum() and len(incoming) <= 64 else new_id()

        token_rid = request_id_var.set(request_id)
        token_uid = user_id_var.set(None)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if request.url.path not in _QUIET_PATHS:
                log.info(
                    "http.request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip(request),
                    },
                )
            request_id_var.reset(token_rid)
            user_id_var.reset(token_uid)


def client_ip(request: Request) -> str:
    """La IP con la que se hace rate limiting.

    Solo se confia en `X-Forwarded-For` cuando hay un proxy delante que la
    reescribe. Confiar en ella sin proxy deja el rate limit por IP inutil:
    el cliente elige su propia identidad mandando la cabecera.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and getattr(request.app.state, "trust_proxy", False):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def install(app: ASGIApp) -> None:
    app.add_middleware(RequestContextMiddleware)
