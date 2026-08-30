"""Contrato publico de identity.

Para un dominio de NEGOCIO lo que expone es minimo a proposito: un `UserId`.
Ni `library` ni `episodes` necesitan saber que existe un email, un token o una
cookie -- solo de quien es la foto que estan mirando. Eso lo garantiza
`core/auth.py` con la dependencia invertida, y la tabla `ALLOWED` lo verifica.

`web` es la excepcion, y es una excepcion con motivo: es quien DIBUJA la pantalla
de entrar. Pedirle que no sepa que existe un magic link seria pedirle que dibuje
un formulario sin saber de que es. Por eso se exponen las dos operaciones de esa
pantalla -- pedir el enlace y canjearlo -- y `set_session_cookie`.

`set_session_cookie` se exporta en vez de dejar que `web` ponga la cookie a mano
porque si no, el nombre y las banderas (`httponly`, `samesite`, `secure`)
existirian en dos sitios, y el dia que cambie uno el otro se queda con la version
insegura sin que nada falle.
"""

from app.core.db import Database
from app.domains.identity.router import (
    COOKIE_NAME,
    clear_session_cookie,
    router,
    set_session_cookie,
)
from app.domains.identity.service import authenticate as _authenticate
from app.domains.identity.service import logout, request_magic_link, verify_magic_link

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


__all__ = [
    "COOKIE_NAME",
    "UserId",
    "clear_session_cookie",
    "logout",
    "make_authenticator",
    "request_magic_link",
    "router",
    "set_session_cookie",
    "verify_magic_link",
]
