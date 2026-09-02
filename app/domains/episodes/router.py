"""HTTP de episodes."""

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import FileResponse

from app.core.auth import CurrentUser
from app.core.deps import Config, Db
from app.domains.episodes import errors, repo, service
from app.domains.episodes.schemas import (
    AjusteIn,
    AssemblyOut,
    CreateEpisode,
    EpisodeOut,
    UpdateTitle,
)
from app.domains.intake import api as intake

router = APIRouter(prefix="/episodes", tags=["episodes"])

# Ver la nota larga en `library/router.py`: esta URL sirve EL ULTIMO armado del
# episodio, y corregir el titulo produce otro. Con `immutable` el navegador hacia
# lo correcto -- no volver a pedirla en un ano -- y la persona veia la miniatura
# vieja despues de arreglar una errata. Solo se ve en un navegador de verdad:
# `TestClient` no implementa una cache HTTP.
CACHE_CONTROL = "private, no-cache"


def _assembly_out(assembly: repo.Assembly | None) -> AssemblyOut | None:
    if assembly is None:
        return None
    return AssemblyOut(
        id=assembly.id,
        template_version=assembly.template_version,
        finish_applied=assembly.finish_applied,
        finish_provider=assembly.finish_provider,
        created_at=assembly.created_at,
    )


def _out(db, episode: repo.Episode) -> EpisodeOut:
    with db.connection() as conn:
        assembly = repo.latest_assembly(conn, episode_id=episode.id)
    return EpisodeOut(
        id=episode.id,
        title=episode.title,
        strength=episode.strength,
        degradado=episode.degradado,
        titulo_ancho=episode.titulo_ancho,
        titulo_apilado=episode.titulo_apilado,
        ajustes={
            role: [
                AjusteIn(
                    dx=a.dx, dy=a.dy, capa=a.capa, voltear_x=a.voltear_x, voltear_y=a.voltear_y
                )
                for a in ajustes
            ]
            for role, ajustes in episode.ajustes.items()
        },
        selection=episode.slots,
        created_at=episode.created_at,
        assembly=_assembly_out(assembly),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_episode(body: CreateEpisode, db: Db, user_id: CurrentUser) -> EpisodeOut:
    episode = service.create_episode(
        db,
        user_id=user_id,
        title=body.title,
        selection=body.normalized_selection(),
        strength=body.strength,
        degradado=body.degradado,
        ajustes=body.normalized_ajustes(),
        titulo_ancho=body.titulo_ancho,
        titulo_apilado=body.titulo_apilado,
    )
    return _out(db, episode)


@router.get("")
def list_episodes(db: Db, user_id: CurrentUser) -> list[EpisodeOut]:
    return [_out(db, e) for e in service.list_episodes(db, user_id=user_id)]


@router.get("/{episode_id}")
def get_episode(db: Db, user_id: CurrentUser, episode_id: str) -> EpisodeOut:
    return _out(db, service.get_episode(db, user_id=user_id, episode_id=episode_id))


@router.patch("/{episode_id}")
def update_title(body: UpdateTitle, db: Db, user_id: CurrentUser, episode_id: str) -> EpisodeOut:
    episode = service.set_title(db, user_id=user_id, episode_id=episode_id, title=body.title)
    return _out(db, episode)


# `def` y no `async def`: dentro corre Pillow. FastAPI lo manda al threadpool y
# no bloquea el event loop (ver CLAUDE.md).
@router.post("/{episode_id}/assembly", status_code=status.HTTP_201_CREATED)
def build_assembly(
    request: Request, db: Db, settings: Config, user_id: CurrentUser, episode_id: str
) -> AssemblyOut:
    assembly = service.build_assembly(
        db,
        settings,
        request.app.state.finisher,
        user_id=user_id,
        episode_id=episode_id,
    )
    salida = _assembly_out(assembly)
    assert salida is not None
    return salida


@router.get("/{episode_id}/assembly/file")
def get_assembly_file(
    request: Request,
    db: Db,
    settings: Config,
    user_id: CurrentUser,
    episode_id: str,
    variant: str = "final",
) -> Response:
    """`variant=final` (publicable) o `variant=base` (sin logo ni título)."""
    assembly = service.latest_assembly(db, user_id=user_id, episode_id=episode_id)
    media_id = assembly.base_media_id if variant == "base" else assembly.final_media_id

    media = intake.get(db, media_id)
    if media is None:
        raise errors.SinArmado("El archivo de ese armado no está disponible.")

    etag = f'"{media.sha256}"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
        )

    return FileResponse(
        intake.path(settings, media),
        media_type=media.mime,
        headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
    )


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(db: Db, user_id: CurrentUser, episode_id: str) -> Response:
    service.delete_episode(db, user_id=user_id, episode_id=episode_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
