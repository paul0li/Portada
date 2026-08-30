"""Las reglas de intake: que entra, y como se guarda.

La regla que gobierna el archivo: **manda el contenido, nunca lo que dice el
cliente**. El nombre del archivo, su extension y su `content-type` son texto
que cualquiera puede escribir. El formato se decide abriendo la imagen; la ruta
se deriva del hash. Asi no hay nada que sanitizar, porque no hay nada de lo que
mando el cliente participando en una decision.
"""

from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.core.db import Database
from app.core.logging import get_logger
from app.domains.intake import errors, repo, storage

log = get_logger("portada.intake")

# Solo lo que el armado sabe componer. Un formato de mas aca es un formato que
# Pillow tiene que decodificar y que nadie probo.
FORMATS_SOPORTADOS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}

# Pillow avisa (o falla) por su cuenta con imagenes absurdas. Se desactiva su
# techo global para aplicar el nuestro, que es configurable y da un error de
# dominio con un mensaje util en vez de un warning.
Image.MAX_IMAGE_PIXELS = None


def _inspect(path: Path, max_pixels: int) -> tuple[str, int, int, bool]:
    """Formato, ancho, alto y transparencia. Sin decodificar los pixeles."""
    try:
        # Una pasada para validar la estructura. `verify()` deja el objeto
        # inutilizable, por eso se abre de nuevo abajo para leer los metadatos.
        with Image.open(path) as probe:
            probe.verify()
        with Image.open(path) as imagen:
            image_format = imagen.format or ""
            width, height = imagen.size
            has_alpha = imagen.mode in ("RGBA", "LA", "PA") or "transparency" in imagen.info
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise errors.NoEsImagen("Eso no parece una imagen.") from exc

    if image_format not in FORMATS_SOPORTADOS:
        raise errors.FormatoNoSoportado(
            f"Formato no soportado: {image_format or 'desconocido'}. Usa PNG, JPEG o WEBP.",
            details={"format": image_format, "supported": sorted(FORMATS_SOPORTADOS)},
        )

    # Se comprueba DESPUES de leer el encabezado y ANTES de decodificar: un PNG
    # de un color plano pesa unos KB y puede declarar 40.000 x 40.000 pixeles.
    if width * height > max_pixels:
        raise errors.ImagenDemasiadoGrande(
            "Esa imagen tiene demasiados píxeles.",
            details={"width": width, "height": height, "max_pixels": max_pixels},
        )

    return image_format, width, height, has_alpha


def store(
    db: Database,
    settings: Settings,
    stream: BinaryIO,
    *,
    filename: str | None = None,
    declared_mime: str | None = None,
) -> repo.MediaFile:
    """Valida y persiste un archivo. Devuelve el media, nuevo o ya existente.

    `filename` y `declared_mime` se aceptan solo para poder registrarlos en el
    log: no influyen en donde se guarda ni en como se interpreta el archivo.
    """
    try:
        temp, sha256, size_bytes = storage.spool(
            stream, media_dir=settings.media_dir, max_bytes=settings.max_upload_bytes
        )
    except storage._TooLarge as exc:
        raise errors.ArchivoDemasiadoGrande(
            "Ese archivo pesa demasiado.",
            details={"max_bytes": settings.max_upload_bytes, "seen_bytes": exc.seen},
        ) from exc

    try:
        image_format, width, height, has_alpha = _inspect(temp, settings.max_image_pixels)
    except BaseException:
        temp.unlink(missing_ok=True)  # nada rechazado queda en el directorio
        raise

    # El contenido ya conocido no se vuelve a escribir ni a registrar. Es el caso
    # normal, no la excepcion: el logo del show entra igual todas las semanas.
    with db.connection() as conn:
        existente = repo.get_by_sha256(conn, sha256)
    if existente is not None:
        temp.unlink(missing_ok=True)
        log.info("intake.media.deduplicated", extra={"media_id": existente.id})
        return existente

    relative = storage.relative_path(sha256, image_format)
    storage.commit(temp, media_dir=settings.media_dir, relative=relative)

    with db.transaction() as conn:
        # Otra subida del mismo contenido pudo ganar la carrera entre la
        # comprobacion de arriba y este INSERT. El archivo en disco es el mismo
        # (la ruta es el hash), asi que basta con quedarse con la fila que gano.
        existente = repo.get_by_sha256(conn, sha256)
        if existente is not None:
            return existente
        media = repo.insert(
            conn,
            sha256=sha256,
            path=relative,
            mime=FORMATS_SOPORTADOS[image_format],
            image_format=image_format,
            width=width,
            height=height,
            size_bytes=size_bytes,
            has_alpha=has_alpha,
        )

    log.info(
        "intake.media.stored",
        extra={
            "media_id": media.id,
            "format": media.format,
            "width": width,
            "height": height,
            "bytes": size_bytes,
        },
    )
    return media


def get(db: Database, media_id: str) -> repo.MediaFile | None:
    with db.connection() as conn:
        return repo.get(conn, media_id)


def path(settings: Settings, media: repo.MediaFile) -> Path:
    return storage.absolute_path(settings.media_dir, media.path)
