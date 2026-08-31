"""Las reglas de library.

Coordina el ciclo de vida de una foto: entra por `intake` (bytes), se le pide el
recorte a `processing`, y queda en el catalogo con su rol.

Los roles y sus minimos son de SPEC 6 y viven aca ademas de en el CHECK de la
migracion. La duplicacion es a proposito: el CHECK impide una fila invalida,
esta constante da un mensaje de error util.
"""

from typing import BinaryIO

from app.config import Settings
from app.core.db import Database
from app.core.logging import get_logger
from app.domains.intake import api as intake
from app.domains.library import errors, repo
from app.domains.processing import api as processing

log = get_logger("portada.library")

# `marco` es el sexto: mobiliario de marca, como el logo, y como el logo vive
# aca y no en el template. El template es de quien escribe el codigo; el marco
# es del show. Meterlo en template.py seria meter el PNG de un cliente en el
# repo, y dejaria el armado de SPEC 15.3 sin reproducir por HTTP.
ROLES = ("conductor", "invitado", "objeto", "fondo", "logo", "marco")

# Los roles que se componen como recorte (SPEC 6). `fondo` va a sangre completa,
# y `logo` y `marco` se pegan tal cual con la transparencia que ya traen:
# pedirles un recorte no tendria sentido.
ROLES_CON_RECORTE = frozenset({"conductor", "invitado", "objeto"})

MAX_LABEL = 120
MAX_DESCRIPTION = 500


def validate_role(role: str) -> str:
    normalizado = role.strip().lower()
    if normalizado not in ROLES:
        raise errors.RolInvalido(
            f"Rol desconocido: {role!r}.",
            details={"role": role, "valid": list(ROLES)},
        )
    return normalizado


def add_photo(
    db: Database,
    settings: Settings,
    provider: processing.CutoutProvider,
    *,
    user_id: str,
    role: str,
    stream: BinaryIO,
    filename: str | None = None,
    declared_mime: str | None = None,
    label: str | None = None,
    description: str | None = None,
) -> repo.Photo:
    role = validate_role(role)

    media = intake.store(db, settings, stream, filename=filename, declared_mime=declared_mime)

    with db.transaction() as conn:
        photo = repo.insert(
            conn,
            user_id=user_id,
            media_id=media.id,
            role=role,
            label=(label or "").strip()[:MAX_LABEL] or None,
            description=(description or "").strip()[:MAX_DESCRIPTION] or None,
        )

    # El recorte se computa ahora, no al armar la miniatura (SPEC 6): asi el
    # camino semanal nunca lo espera. Se hace FUERA de la transaccion de arriba
    # porque puede tardar segundos y bloquearia al unico escritor de SQLite.
    if role in ROLES_CON_RECORTE:
        processing.ensure_cutout(db, settings, provider, media_id=media.id)

    log.info(
        "library.photo.created",
        extra={"photo_id": photo.id, "role": role, "media_id": media.id},
    )
    return photo


def get_photo(db: Database, *, user_id: str, photo_id: str) -> repo.Photo:
    with db.connection() as conn:
        photo = repo.get(conn, user_id=user_id, photo_id=photo_id)
    if photo is None:
        raise errors.FotoNoEncontrada("Esa foto no existe en tu librería.")
    return photo


def list_photos(db: Database, *, user_id: str, role: str | None = None) -> list[repo.Photo]:
    if role is not None:
        role = validate_role(role)
    with db.connection() as conn:
        return repo.list_photos(conn, user_id=user_id, role=role)


def delete_photo(db: Database, *, user_id: str, photo_id: str) -> None:
    """Soft delete. Idempotente: borrar dos veces no es un error la segunda."""
    with db.transaction() as conn:
        afectadas = repo.soft_delete(conn, user_id=user_id, photo_id=photo_id)
        if afectadas == 0 and repo.get(conn, user_id=user_id, photo_id=photo_id) is None:
            # Ni viva ni recien borrada: o no existe, o no es suya. No se
            # distingue a proposito (ver errors.FotoNoEncontrada).
            existe = conn.execute(
                "SELECT 1 FROM library_photos WHERE id = ? AND user_id = ?",
                (photo_id, user_id),
            ).fetchone()
            if existe is None:
                raise errors.FotoNoEncontrada("Esa foto no existe en tu librería.")
    log.info("library.photo.deleted", extra={"photo_id": photo_id})


def resolve_media(db: Database, settings: Settings, photo: repo.Photo):
    """El archivo a servir o componer: el recorte si esta listo, si no el original."""
    media_id = (
        processing.cutout_or_source(db, photo.media_id)
        if photo.role in ROLES_CON_RECORTE
        else photo.media_id
    )
    media = intake.get(db, media_id) or intake.get(db, photo.media_id)
    if media is None:
        raise errors.ArchivoNoEncontrado("El archivo de esa foto no está disponible.")
    return media


def stats(db: Database, *, user_id: str) -> dict[str, int]:
    with db.connection() as conn:
        conteo = repo.count_by_role(conn, user_id=user_id)
    return {role: conteo.get(role, 0) for role in ROLES}
