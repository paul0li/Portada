"""Las reglas de processing.

Una sola, y es la que hace que la IA sea opcional de verdad:

> Una derivada que falta, falla o esta pendiente NO es un error. `cutout_or_source`
> devuelve la imagen original y el armado continua.

Es la version, a nivel de recorte, de la regla del SPEC 11.4: el armado siempre
es salida valida. Un recorte roto degrada el resultado; no lo impide.
"""

import shutil

from app.config import Settings
from app.core.db import Database
from app.core.logging import get_logger
from app.domains.intake import api as intake
from app.domains.processing import repo
from app.domains.processing.providers import CutoutProvider

log = get_logger("portada.processing")

CUTOUT = "cutout"


def ensure_cutout(
    db: Database,
    settings: Settings,
    provider: CutoutProvider,
    *,
    media_id: str,
) -> repo.Derivative:
    """Calcula el recorte si no existe. Idempotente.

    Corre al SUBIR la foto, no al armar la miniatura (SPEC 6): el camino semanal
    nunca espera por un recorte.
    """
    with db.connection() as conn:
        existente = repo.find(conn, source_media_id=media_id, kind=CUTOUT)
    if existente is not None and existente.status != "failed":
        return existente

    source = intake.get(db, media_id)
    if source is None:
        with db.transaction() as conn:
            return repo.upsert(
                conn,
                source_media_id=media_id,
                kind=CUTOUT,
                status="failed",
                provider=provider.name,
                error="la imagen de origen no existe",
            )

    try:
        origen = intake.path(settings, source)
        resultado = provider.cutout(origen)
        # El proveedor passthrough devuelve la misma ruta: no hay nada nuevo que
        # guardar y la derivada apunta al propio origen.
        if resultado == origen:
            result_media_id = media_id
        else:
            try:
                with resultado.open("rb") as handle:
                    result_media_id = intake.store(db, settings, handle).id
            finally:
                # El recorte ya vive en el almacen, direccionado por su contenido.
                # El temporal se borra en todos los caminos: un proveedor que
                # recorta no puede ir dejando PNGs de 1 MB por el disco.
                shutil.rmtree(resultado.parent, ignore_errors=True)
    except Exception as exc:
        log.warning(
            "processing.cutout.failed",
            extra={"media_id": media_id, "provider": provider.name, "kind": type(exc).__name__},
        )
        with db.transaction() as conn:
            return repo.upsert(
                conn,
                source_media_id=media_id,
                kind=CUTOUT,
                status="failed",
                provider=provider.name,
                error=str(exc)[:500],
            )

    with db.transaction() as conn:
        derivative = repo.upsert(
            conn,
            source_media_id=media_id,
            kind=CUTOUT,
            status="ready",
            provider=provider.name,
            result_media_id=result_media_id,
        )
    log.info(
        "processing.cutout.ready",
        extra={"media_id": media_id, "provider": provider.name, "result": result_media_id},
    )
    return derivative


def get_cutout(db: Database, media_id: str) -> repo.Derivative | None:
    with db.connection() as conn:
        return repo.find(conn, source_media_id=media_id, kind=CUTOUT)


def cutout_or_source(db: Database, media_id: str) -> str:
    """El media a usar en el armado: el recorte si esta listo, si no el original.

    Nunca levanta. Es el punto exacto donde "la IA es opcional" deja de ser una
    promesa del documento y pasa a ser el comportamiento por defecto del codigo.
    """
    derivative = get_cutout(db, media_id)
    if derivative is not None and derivative.is_ready:
        assert derivative.result_media_id is not None
        return derivative.result_media_id
    return media_id


def clear_cutout(db: Database, *, media_id: str) -> None:
    """Olvida el recorte de una imagen: vuelve a servirse el original.

    Es la vuelta de `ensure_cutout`, y existe porque quitarle el fondo a una foto
    es una capa que se pone y se saca, no una decision que se toma una vez.
    Borrar dos veces no es un error la segunda.
    """
    with db.transaction() as conn:
        repo.delete(conn, source_media_id=media_id, kind=CUTOUT)
    log.info("processing.cutout.cleared", extra={"media_id": media_id})
