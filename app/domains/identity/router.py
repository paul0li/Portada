"""HTTP de identity. Traduce peticiones a llamadas al service y nada mas.

El unico lugar del sistema que sabe que existe una cookie llamada
`portada_session` es este archivo, junto con `set_session_cookie`.
"""

from fastapi import APIRouter, Request, Response, status

from app.core.auth import OptionalUser
from app.core.deps import Config, Db
from app.core.errors import NotFound
from app.core.logging import user_id_var
from app.core.middleware import client_ip
from app.domains.identity import errors, service
from app.domains.identity.schemas import MagicLinkRequest, UserOut, VerifyRequest

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "portada_session"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    """El unico sitio del sistema que sabe como es la cookie de sesion.

    Se exporta por `api.py` para que la pantalla de entrar la ponga llamando
    aqui, y no copiando las banderas. Copiarlas significaria que el dia que
    `secure` cambie, un camino se queda con la version insegura en silencio.
    """
    settings = request.app.state.settings
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,  # JavaScript no puede leerla: corta el robo por XSS
        samesite="lax",  # no viaja en peticiones cross-site: corta CSRF
        secure=settings.cookie_secure,
        path="/",
    )


@router.post("/magic-link", status_code=status.HTTP_202_ACCEPTED)
def request_magic_link(body: MagicLinkRequest, request: Request, db: Db, settings: Config) -> dict:
    if settings.acceso == "tailnet":
        # No hay enlace que pedir: se entra por la red de Tailscale (IDENTITY-27).
        raise NotFound("Esta instancia no usa enlaces para entrar.", code="IDENTITY_SIN_ENLACE")
    service.request_magic_link(
        db,
        settings,
        request.app.state.mailer,
        raw_email=body.email,
        ip=client_ip(request),
    )
    # La misma respuesta exista o no la cuenta.
    return {"status": "sent"}


@router.post("/verify")
def verify(
    body: VerifyRequest, request: Request, response: Response, db: Db, settings: Config
) -> UserOut:
    grant = service.verify_magic_link(db, settings, token=body.token)
    set_session_cookie(response, request, grant.token)
    user_id_var.set(grant.user_id)
    user = service.load_user(db, grant.user_id)
    assert user is not None
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)


@router.get("/me")
def me(db: Db, user_id: OptionalUser) -> UserOut:
    # Por el autenticador montado y no por la cookie: con acceso por tailnet no
    # hay cookie, y `/auth/me` tiene que decir lo mismo que el resto de la app.
    if user_id is None:
        raise errors.SinSesion("Necesitas iniciar sesión.")
    user = service.load_user(db, user_id)
    if user is None:
        raise errors.SinSesion("Necesitas iniciar sesión.")
    user_id_var.set(user.id)
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)


def clear_session_cookie(response: Response) -> None:
    """El par de `set_session_cookie`. Mismo motivo para vivir aqui."""
    response.delete_cookie(COOKIE_NAME, path="/")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Db) -> Response:
    service.logout(db, request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=response.headers)
