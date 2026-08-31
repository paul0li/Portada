"""Las reglas de identity.

Tres decisiones que explican el archivo:

1. **Pedir un enlace nunca revela si la cuenta existe.** Un email nuevo y uno
   conocido siguen exactamente el mismo camino y devuelven la misma respuesta.
   Por eso `request_magic_link` crea el usuario en vez de fallar.

2. **Canjear un enlace es atomico.** Marcar el token como usado y crear la
   sesion ocurren en una transaccion, y el UPDATE lleva `AND used_at IS NULL`.
   Sin las dos cosas, dos canjes simultaneos del mismo enlace dan dos sesiones.

3. **El rate limit cuenta intentos, no exitos.** Contar solo los que llegaron a
   un usuario real convertiria el contador en un oraculo de que cuentas existen.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.config import Settings
from app.core.db import Database
from app.core.logging import get_logger, mask_email
from app.core.security import hash_token, new_token
from app.domains.identity import email as email_mod
from app.domains.identity import errors, repo

log = get_logger("portada.identity")

# Deliberadamente permisiva salvo en lo que importa: exactamente un `@`, algo a
# cada lado, un punto en el dominio y ningun espacio. Validar direcciones de
# correo con precision es imposible; el unico veredicto real es si el correo
# llega. Esto solo descarta lo que con certeza no es una direccion.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")
_MAX_EMAIL = 254  # RFC 5321


@dataclass(frozen=True, slots=True)
class SessionGrant:
    """Lo que el router necesita para poner la cookie."""

    token: str
    user_id: str
    email: str
    expires_at: str


def normalize_email(raw: str) -> str:
    """Minusculas y sin bordes: `  Paula@Ejemplo.CL ` es `paula@ejemplo.cl`.

    La parte local de una direccion es sensible a mayusculas segun el RFC, pero
    ningun proveedor real lo aplica. Normalizar evita que la misma persona
    termine con dos cuentas por haber escrito su correo distinto.
    """
    return raw.strip().lower()


def validate_email(raw: str) -> str:
    email = normalize_email(raw)
    if not email or len(email) > _MAX_EMAIL or not _EMAIL.match(email):
        raise errors.EmailInvalido("Ese correo no parece una dirección válida.")
    return email


def _window_start(settings: Settings) -> str:
    inicio = datetime.now(UTC) - timedelta(minutes=settings.rate_limit_window_minutes)
    return inicio.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _expiry(minutes: int = 0, days: int = 0) -> str:
    fin = datetime.now(UTC) + timedelta(minutes=minutes, days=days)
    return fin.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def request_magic_link(
    db: Database,
    settings: Settings,
    sender: email_mod.EmailSender,
    *,
    raw_email: str,
    ip: str,
) -> None:
    email = validate_email(raw_email)

    with db.transaction() as conn:
        por_email, por_ip = repo.count_link_requests(
            conn, email=email, ip=ip, since=_window_start(settings)
        )
        if por_email >= settings.magic_links_per_email or por_ip >= settings.magic_links_per_ip:
            log.warning(
                "identity.magic_link.rate_limited",
                extra={"email": mask_email(email), "by_email": por_email, "by_ip": por_ip},
            )
            raise errors.DemasiadasSolicitudes(
                "Demasiadas solicitudes. Espera unos minutos e inténtalo de nuevo."
            )
        repo.record_link_request(conn, email=email, ip=ip)

        user = repo.get_user_by_email(conn, email)
        creado = user is None
        if user is None:
            user = repo.create_user(conn, email)

        # Un solo enlace vivo por persona: pedir otro invalida el anterior. Si no,
        # cada solicitud dejaria una llave usable flotando en una bandeja.
        repo.invalidate_pending_tokens(conn, user.id)

        token = new_token()
        repo.create_magic_token(
            conn,
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=_expiry(minutes=settings.magic_link_ttl_minutes),
        )

    # El correo se manda FUERA de la transaccion: SMTP puede tardar segundos y
    # una transaccion abierta bloquea al unico escritor de SQLite.
    # Apunta a una PAGINA, no a `/auth/verify`, que solo acepta POST -- abrir el
    # enlace daba 405 y nadie lo vio, porque los tests extraian el token y lo
    # posteaban en vez de abrir el enlace, que es lo unico que hace una persona.
    #
    # Y sigue sin haber un GET que canjee: la pagina pinta el token en un campo y
    # hace falta pulsar el boton. Asi ningun GET cambia estado -- que es lo que
    # hace que `samesite=lax` baste como defensa CSRF -- y un escaner de enlaces
    # corporativo no gasta el token de un solo uso antes de que lo abras.
    link = f"{settings.public_url}/entrar?token={quote(token)}"
    sender.send(
        email_mod.magic_link_message(
            to=email, link=link, ttl_minutes=settings.magic_link_ttl_minutes
        )
    )
    log.info(
        "identity.magic_link.sent",
        extra={"email": mask_email(email), "user_created": creado, "user_id": user.id},
    )


def verify_magic_link(db: Database, settings: Settings, *, token: str) -> SessionGrant:
    token_hash = hash_token(token)

    with db.transaction() as conn:
        registro = repo.find_magic_token(conn, token_hash)
        if registro is None or registro.invalidated_at is not None:
            log.warning("identity.verify.failed", extra={"reason": "invalid"})
            raise errors.TokenInvalido("Ese enlace no es válido.")
        if registro.used_at is not None:
            log.warning("identity.verify.failed", extra={"reason": "used"})
            raise errors.TokenYaUsado("Ese enlace ya se usó. Pide uno nuevo.")
        if registro.expires_at <= _expiry():
            log.warning("identity.verify.failed", extra={"reason": "expired"})
            raise errors.TokenExpirado("Ese enlace venció. Pide uno nuevo.")

        if repo.mark_token_used(conn, registro.id) != 1:
            # Otro canje simultaneo gano la carrera.
            raise errors.TokenYaUsado("Ese enlace ya se usó. Pide uno nuevo.")

        session_token = new_token()
        expires_at = _expiry(days=settings.session_ttl_days)
        repo.create_session(
            conn,
            session_id=hash_token(session_token),
            user_id=registro.user_id,
            expires_at=expires_at,
        )
        repo.touch_login(conn, registro.user_id)
        user = repo.get_user(conn, registro.user_id)

    assert user is not None  # la FK lo garantiza dentro de la misma transaccion
    log.info("identity.session.created", extra={"user_id": user.id})
    return SessionGrant(
        token=session_token, user_id=user.id, email=user.email, expires_at=expires_at
    )


def authenticate(db: Database, session_token: str | None) -> str | None:
    """El `user_id` detras de una cookie, o None. Sin efectos secundarios.

    No escribe (no hay `last_seen_at`): esto corre en CADA request autenticado,
    y una escritura por request contra el unico escritor de SQLite es
    exactamente el cuello de botella que no queremos construir.
    """
    if not session_token:
        return None
    with db.connection() as conn:
        return repo.find_live_session_user(conn, hash_token(session_token))


def logout(db: Database, session_token: str | None) -> None:
    """Idempotente: cerrar una sesion inexistente no es un error."""
    if not session_token:
        return
    with db.transaction() as conn:
        repo.revoke_session(conn, hash_token(session_token))


def load_user(db: Database, user_id: str) -> repo.User | None:
    with db.connection() as conn:
        return repo.get_user(conn, user_id)


__all__ = [
    "SessionGrant",
    "authenticate",
    "load_user",
    "logout",
    "normalize_email",
    "request_magic_link",
    "validate_email",
    "verify_magic_link",
]
