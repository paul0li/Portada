"""Contrato publico de identity.

Lo unico que otro dominio puede importar. Y lo que expone es minimo a proposito:
un `UserId`. Ningun otro dominio necesita saber que existe un email, un token o
una cookie -- solo de quien es la foto que esta mirando.
"""

from app.core.db import Database
from app.domains.identity.router import COOKIE_NAME, router
from app.domains.identity.service import authenticate as _authenticate

UserId = str


def make_authenticator(db: Database):
    """Un autenticador listo para colgar en `app.state`.

    Se registra asi, y no se importa directo, para que ningun dominio dependa de
    `identity`: `core.auth` resuelve al usuario llamando a lo que haya en
    `app.state.authenticator`. Cambiar magic link por OAuth no toca a nadie mas.
    """

    def authenticator(session_token: str | None) -> UserId | None:
        return _authenticate(db, session_token)

    return authenticator


__all__ = ["COOKIE_NAME", "UserId", "make_authenticator", "router"]
