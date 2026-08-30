"""Quien esta pidiendo, sin que nadie tenga que importar `identity`.

La dependencia esta invertida a proposito. `core` no puede importar un dominio
(ver CLAUDE.md), y ademas ningun dominio deberia depender de COMO se autentico
el usuario, solo de que hay un `UserId`. Asi que `main.py` cuelga un autenticador
en `app.state` y esto lo llama.

El resultado: cambiar magic link por OAuth, o meter una API key para un cliente
movil, no toca ni una linea de `library`, `episodes` o `processing`.
"""

from typing import Annotated, Protocol

from fastapi import Depends, Request

from app.core.errors import Unauthorized

SESSION_COOKIE = "portada_session"


class Authenticator(Protocol):
    def __call__(self, session_token: str | None) -> str | None: ...


def _resolve(request: Request) -> str | None:
    authenticator: Authenticator | None = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        raise RuntimeError("No hay autenticador montado en app.state. Lo instala create_app().")
    return authenticator(request.cookies.get(SESSION_COOKIE))


def current_user(request: Request) -> str:
    """El `user_id` del que pide, o 401. Es la puerta de todo endpoint privado."""
    user_id = _resolve(request)
    if user_id is None:
        raise Unauthorized("Necesitas iniciar sesión.", code="IDENTITY_NO_SESSION")
    # Queda en el contexto de logging: desde aca, cada linea del request lo lleva.
    from app.core.logging import user_id_var

    user_id_var.set(user_id)
    return user_id


def optional_user(request: Request) -> str | None:
    return _resolve(request)


CurrentUser = Annotated[str, Depends(current_user)]
OptionalUser = Annotated[str | None, Depends(optional_user)]
