"""Traduccion de excepciones a respuestas.

Un solo formato de error para toda la API:

    {"error": {"code", "message", "request_id", "details"}}

`code` es estable y lleva prefijo de dominio: el cliente ramifica sobre el.
`message` es para humanos y puede cambiar sin aviso.

Regla que sostiene todo lo demas: un error inesperado se loguea completo del
lado servidor y sale como 500 generico. El cliente nunca recibe un traceback,
un nombre de tabla ni una ruta del sistema de archivos.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.errors import AppError
from app.core.logging import get_logger, request_id_var

log = get_logger("portada.errors")


def _body(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_var.get(),
            "details": details or {},
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    # 4xx es el cliente equivocandose (esperado, INFO). 5xx somos nosotros.
    level = log.warning if exc.status >= 500 else log.info
    level(
        "app.error",
        extra={
            "code": exc.code,
            "status": exc.status,
            "path": request.url.path,
            "detail_keys": sorted(exc.details),
        },
    )
    return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.details))


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Se reexpone el detalle de pydantic con las claves que el cliente necesita
    # para marcar el campo, sin el `input` -- ahi va lo que el usuario escribio,
    # y en /auth/verify eso es el token.
    fields = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "reason": e["msg"]} for e in exc.errors()
    ]
    log.info(
        "app.validation_error",
        extra={"path": request.url.path, "fields": [f["field"] for f in fields]},
    )
    return JSONResponse(
        status_code=422,
        content=_body("VALIDATION_ERROR", "La peticion no es valida.", {"fields": fields}),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # 404 de ruta inexistente, 405, y lo que Starlette lance por su cuenta.
    codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHORIZED"}
    code = codes.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception(
        "app.unhandled",
        extra={"path": request.url.path, "method": request.method, "kind": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        content=_body("INTERNAL_ERROR", "Algo fallo de nuestro lado."),
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_handler)
