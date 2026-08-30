"""Errores de identity.

Los codigos distinguen POR QUE fallo el canje (expirado / ya usado / invalido)
porque el usuario puede actuar distinto en cada caso: pedir otro enlace, revisar
si ya entro en otra pestana, o sospechar del enlace. Distinguirlos no filtra
nada: para llegar a cualquiera de los tres hay que traer un token.

Lo que si es deliberadamente indistinguible es pedir un enlace: un email que
existe y uno que no producen la misma respuesta byte a byte.
"""

from app.core.errors import RateLimited, Unauthorized, ValidationError


class EmailInvalido(ValidationError):
    code = "IDENTITY_EMAIL_INVALID"


class DemasiadasSolicitudes(RateLimited):
    code = "IDENTITY_RATE_LIMITED"


class TokenInvalido(Unauthorized):
    code = "IDENTITY_TOKEN_INVALID"


class TokenExpirado(Unauthorized):
    code = "IDENTITY_TOKEN_EXPIRED"


class TokenYaUsado(Unauthorized):
    code = "IDENTITY_TOKEN_USED"


class SinSesion(Unauthorized):
    code = "IDENTITY_NO_SESSION"
