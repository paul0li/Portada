"""HTTP de library."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import CurrentUser
from app.core.deps import Config, Db
from app.domains.intake import api as intake
from app.domains.library import errors, service
from app.domains.library.schemas import PhotoListOut, PhotoOut

router = APIRouter(prefix="/photos", tags=["library"])

# El ARCHIVO es inmutable -- su ruta en disco es el hash de su contenido -- pero
# esta URL no es el archivo: es un PUNTERO. `resolve_media` sirve el recorte si
# esta listo y si no el original, asi que los mismos bytes de URL pueden devolver
# bytes distintos el dia que el recorte se calcule en segundo plano.
#
# `no-cache` no significa "no guardes": significa "guarda, pero pregunta antes de
# usar". Con el ETag de por medio, preguntar cuesta un 304 -- medido en 3,4 ms --
# y a cambio nunca se sirve una imagen vieja.
#
# `private` y no `public`: la respuesta depende de la cookie, y una cache
# compartida no debe poder guardar la foto de alguien bajo una URL que otro
# podria pedir.
CACHE_CONTROL = "private, no-cache"


def _out(photo, media) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        role=photo.role,
        label=photo.label,
        description=photo.description,
        width=media.width,
        height=media.height,
        has_alpha=media.has_alpha,
        created_at=photo.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_photo(
    request: Request,
    db: Db,
    settings: Config,
    user_id: CurrentUser,
    role: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    label: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    recortar: Annotated[bool, Form()] = False,
) -> PhotoOut:
    photo = service.add_photo(
        db,
        settings,
        request.app.state.cutout_provider,
        user_id=user_id,
        role=role,
        stream=file.file,
        filename=file.filename,
        declared_mime=file.content_type,
        label=label,
        description=description,
        recortar=recortar,
    )
    media = service.resolve_media(db, settings, photo)
    return _out(photo, media)


@router.get("")
def list_photos(
    db: Db,
    settings: Config,
    user_id: CurrentUser,
    role: Annotated[str | None, Query()] = None,
) -> PhotoListOut:
    photos = service.list_photos(db, user_id=user_id, role=role)
    return PhotoListOut(
        photos=[_out(p, service.resolve_media(db, settings, p)) for p in photos],
        stats=service.stats(db, user_id=user_id),
    )


@router.get("/{photo_id}")
def get_photo(db: Db, settings: Config, user_id: CurrentUser, photo_id: str) -> PhotoOut:
    photo = service.get_photo(db, user_id=user_id, photo_id=photo_id)
    return _out(photo, service.resolve_media(db, settings, photo))


@router.get("/{photo_id}/file")
def get_photo_file(
    request: Request, db: Db, settings: Config, user_id: CurrentUser, photo_id: str
) -> Response:
    photo = service.get_photo(db, user_id=user_id, photo_id=photo_id)
    media = service.resolve_media(db, settings, photo)

    # El ETag es el hash del contenido, no un numero de version inventado.
    etag = f'"{media.sha256}"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
        )

    ruta = intake.path(settings, media)
    if not ruta.exists():
        raise errors.ArchivoNoEncontrado("El archivo de esa foto no está disponible.")

    return FileResponse(
        ruta,
        media_type=media.mime,
        headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
    )


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(db: Db, user_id: CurrentUser, photo_id: str) -> Response:
    service.delete_photo(db, user_id=user_id, photo_id=photo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
