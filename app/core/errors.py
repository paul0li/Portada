"""Errores de aplicacion.

Solo la capa `service` de un dominio lanza estos. El router no los construye y el
repo no los conoce: el repo devuelve `None` y el service decide que significa eso.

`code` es un string estable con prefijo de dominio (`LIBRARY_PHOTO_NOT_FOUND`).
El cliente ramifica sobre el `code`, nunca sobre el `message`, que puede cambiar.
"""

from typing import Any


class AppError(Exception):
    """Un fallo que el cliente puede entender y sobre el que puede actuar."""

    status: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code is not None:
            self.code = code


class ValidationError(AppError):
    status = 422
    code = "VALIDATION_ERROR"


class Unauthorized(AppError):
    status = 401
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN"


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status = 409
    code = "CONFLICT"


class PayloadTooLarge(AppError):
    status = 413
    code = "PAYLOAD_TOO_LARGE"


class UnsupportedMedia(AppError):
    status = 415
    code = "UNSUPPORTED_MEDIA"


class RateLimited(AppError):
    status = 429
    code = "RATE_LIMITED"


class Unavailable(AppError):
    status = 503
    code = "UNAVAILABLE"
