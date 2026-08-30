"""Bytes en disco, direccionados por contenido.

La ruta de un archivo es `<sha256[:2]>/<sha256>.<ext>`. Tres consecuencias, y
las tres importan:

1. **El nombre que subio el usuario nunca toca el sistema de archivos.** El path
   traversal no se sanitiza: no existe, porque el nombre no participa.
2. **Deduplicacion gratis.** El mismo logo subido cada semana es un solo archivo.
3. **Los archivos son inmutables.** Se pueden servir con `Cache-Control:
   immutable` sin miedo: si el contenido cambia, la ruta tambien.

El prefijo de dos caracteres reparte los archivos en 256 carpetas, para que
ningun directorio termine con decenas de miles de entradas.
"""

import hashlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

CHUNK = 64 * 1024

EXTENSIONS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


def relative_path(sha256: str, image_format: str) -> str:
    return f"{sha256[:2]}/{sha256}.{EXTENSIONS[image_format]}"


def absolute_path(media_dir: Path, relative: str) -> Path:
    return media_dir / relative


def _chunks(stream: BinaryIO) -> Iterator[bytes]:
    while data := stream.read(CHUNK):
        yield data


def spool(stream: BinaryIO, *, media_dir: Path, max_bytes: int) -> tuple[Path, str, int]:
    """Vuelca el flujo a un archivo temporal contando y hasheando al pasar.

    Devuelve (ruta temporal, sha256, bytes).

    Se lee por trozos y se corta apenas se pasa del limite: un archivo de 2 GB
    nunca llega a estar en memoria ni completo en disco. El temporal vive en el
    mismo sistema de archivos que el destino para que moverlo despues sea un
    rename atomico y no una copia.

    Quien llama es responsable de borrar el temporal si decide no quedarselo.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0

    fd, temp_name = tempfile.mkstemp(dir=media_dir, prefix=".subiendo-")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as salida:
            for chunk in _chunks(stream):
                total += len(chunk)
                if total > max_bytes:
                    raise _TooLarge(total)
                digest.update(chunk)
                salida.write(chunk)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

    return temp, digest.hexdigest(), total


class _TooLarge(Exception):
    """Interno: `service` lo traduce al error de dominio con su mensaje."""

    def __init__(self, seen: int) -> None:
        super().__init__(seen)
        self.seen = seen


def commit(temp: Path, *, media_dir: Path, relative: str) -> Path:
    """Mueve el temporal a su lugar definitivo. Idempotente.

    Si el destino ya existe, el contenido es identico por definicion (la ruta es
    el hash), asi que se descarta el temporal en vez de reescribir.
    """
    destino = absolute_path(media_dir, relative)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        temp.unlink(missing_ok=True)
    else:
        os.replace(temp, destino)
    return destino
