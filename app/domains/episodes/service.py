"""Las reglas de episodes.

Este dominio ORQUESTA y no calcula. Su trabajo entero es la tuberia de SPEC 7:

    library    -> resuelve la seleccion a rutas de archivo
    composition-> arma (base sin logo/titulo, y final)
    finishing  -> pasa la base por el modelo (hoy: no hace nada)
    composition-> vuelve a pegar logo y titulo sobre la base terminada
    intake     -> guarda los dos PNG

Ninguna de esas cinco cosas sabe que existe un episodio, y este archivo no sabe
como se recorta una imagen ni donde va el titulo.
"""

import io

from app.config import Settings
from app.core.db import Database
from app.core.logging import get_logger
from app.domains.composition import api as composition
from app.domains.episodes import errors, repo
from app.domains.finishing import api as finishing
from app.domains.intake import api as intake
from app.domains.library import api as library

log = get_logger("portada.episodes")

MAX_TITLE = 140

# SPEC 6: minimos por rol. El conductor es el unico obligatorio -- sin el no hay
# miniatura del show, solo una imagen. Todo lo demas es opcional (SPEC 11.8).
MINIMOS = {"conductor": 1}

# Cuantas admite cada rol NO se decide aqui: lo dice el template, que es quien
# sabe donde caben. Escribirlo otra vez seria una segunda verdad, y la que se
# quedaria vieja es esta -- rechazando con un 422 una seleccion que el armado
# dibuja perfectamente.
MAXIMOS = composition.MAX_POR_ROL


def _normalize_title(title: str) -> str:
    return " ".join((title or "").split())[:MAX_TITLE]


def _validate_selection(
    db: Database,
    *,
    user_id: str,
    selection: dict[str, list[str]],
    exigir_minimos: bool = True,
) -> dict[str, list[str]]:
    """Comprueba roles, cantidades y propiedad. Devuelve la seleccion limpia."""
    limpia: dict[str, list[str]] = {}

    for role, photo_ids in selection.items():
        if role not in library.ROLES:
            raise errors.SeleccionInvalida(
                f"Rol desconocido: {role!r}.", details={"role": role, "valid": list(library.ROLES)}
            )
        ids = [p for p in dict.fromkeys(photo_ids) if p]
        if not ids:
            continue
        tope = MAXIMOS.get(role, 1)
        if len(ids) > tope:
            raise errors.SeleccionInvalida(
                f"El rol {role!r} admite como máximo {tope} foto(s).",
                details={"role": role, "max": tope, "given": len(ids)},
            )
        # get_photo lanza 404 si no existe o es de otra persona: con eso queda
        # comprobada la propiedad, sin una consulta aparte y sin filtrar nada.
        for photo_id in ids:
            library.get_photo(db, user_id=user_id, photo_id=photo_id)
        limpia[role] = ids

    if not exigir_minimos:
        return limpia

    for role, minimo in MINIMOS.items():
        if len(limpia.get(role, [])) < minimo:
            raise errors.FaltaConductor(
                "Necesitas al menos una foto de conductor.", details={"role": role}
            )

    return limpia


def _validate_alineacion(alineacion: str) -> str:
    """La alineacion del titulo, o 422. Abajo un nombre raro cae a la izquierda;
    la puerta de entrada es donde un nombre invalido SI es un error."""
    if alineacion not in composition.ALINEACIONES:
        raise errors.SeleccionInvalida(
            f"Alineación desconocida: {alineacion!r}.",
            details={"valid": list(composition.ALINEACIONES)},
        )
    return alineacion


def _validate_degradado(degradado: str) -> str:
    """El nombre del fondo por defecto, o 422.

    Se valida aqui y no en `composition`: el armado no puede fallar a mitad de
    dibujar (SPEC 11.4), asi que abajo un nombre raro cae en el por defecto. El
    sitio donde un nombre invalido SI es un error es la puerta de entrada, que
    es esto.
    """
    if degradado not in composition.DEGRADADOS:
        raise errors.SeleccionInvalida(
            f"Fondo desconocido: {degradado!r}.",
            details={"valid": list(composition.DEGRADADOS)},
        )
    return degradado


def _validate_ajustes(
    ajustes: dict[str, list[composition.Ajuste]] | None,
) -> dict[str, list[composition.Ajuste]]:
    """Los ajustes de cada figura, acotados a lo que el template permite.

    Un rol que no se puede mover es un 422 y no un ajuste ignorado: pedir mover
    el marco y que no pase nada es la clase de botón que miente. Los NÚMEROS, en
    cambio, se acotan en vez de rechazarse -- lo que el template dice es hasta
    dónde llega un empujón, no cuál es un empujón inválido -- y se guardan ya
    acotados, para que la fila diga lo que se va a dibujar.

    Mover y voltear se preguntan por separado porque son dos permisos distintos:
    el `fondo` se voltea y no se mueve. Preguntarlos juntos habría hecho una de
    dos cosas mal -- rechazar un volteo de fondo perfectamente válido, o aceptar
    en silencio un empujón que nadie iba a dibujar.

    Ajustar más figuras de las que un rol admite es 422 por lo mismo: un ajuste
    para un tercer invitado no lo va a dibujar nadie nunca.
    """
    limpios: dict[str, list[composition.Ajuste]] = {}
    for role, pedidos in (ajustes or {}).items():
        tope = MAXIMOS.get(role, 1)
        if len(pedidos) > tope:
            raise errors.SeleccionInvalida(
                f"El rol {role!r} tiene como máximo {tope} figura(s) que ajustar.",
                details={"role": role, "max": tope, "given": len(pedidos)},
            )
        for ajuste in pedidos:
            mueve = ajuste.dx or ajuste.dy or ajuste.capa or ajuste.escala != 100
            if mueve and role not in composition.ROLES_MOVIBLES:
                raise errors.SeleccionInvalida(
                    f"Ese rol no se puede mover: {role!r}.",
                    details={"role": role, "valid": list(composition.ROLES_MOVIBLES)},
                )
            if (ajuste.voltear_x or ajuste.voltear_y) and role not in (
                composition.ROLES_VOLTEABLES
            ):
                raise errors.SeleccionInvalida(
                    f"Ese rol no se puede voltear: {role!r}.",
                    details={"role": role, "valid": list(composition.ROLES_VOLTEABLES)},
                )
        acotados = [composition.acotar(role, ajuste) for ajuste in pedidos]
        if any(a != composition.SIN_AJUSTE for a in acotados):
            limpios[role] = acotados
    return limpios


def _solo_las_figuras_elegidas(
    ajustes: dict[str, list[composition.Ajuste]], seleccion: dict[str, list[str]]
) -> dict[str, list[composition.Ajuste]]:
    """Tira los ajustes de figuras que no existen en ESTA selección.

    Un ajuste para el segundo invitado cuando solo vino uno no dibuja nada, así
    que guardarlo dejaría una fila diciendo algo que no se ve. Se cae aquí y no
    en un 422 porque llega solo: en el flujo se ajusta y después se cambia de
    idea sobre una foto, y eso no es un error de nadie.
    """
    recortados = {}
    for role, pedidos in ajustes.items():
        quedan = pedidos[: len(seleccion.get(role, []))]
        while quedan and quedan[-1] == composition.SIN_AJUSTE:
            quedan.pop()
        if quedan:
            recortados[role] = quedan
    return recortados


def create_episode(
    db: Database,
    *,
    user_id: str,
    title: str,
    selection: dict[str, list[str]],
    strength: str = finishing.DEFAULT_STRENGTH,
    degradado: str = composition.DEGRADADO_POR_DEFECTO,
    ajustes: dict[str, list[composition.Ajuste]] | None = None,
    titulo_ancho: int = 0,
    titulo_tamano: int = 0,
    titulo_alto: int = 0,
    titulo_apilado: bool = False,
    titulo_x: int = 0,
    titulo_y: int = 0,
    titulo_alineacion: str = composition.ALINEACION_POR_DEFECTO,
) -> repo.Episode:
    if strength not in finishing.STRENGTHS:
        raise errors.SeleccionInvalida(
            f"Intensidad desconocida: {strength!r}.",
            details={"valid": list(finishing.STRENGTHS)},
        )
    _validate_degradado(degradado)
    _validate_alineacion(titulo_alineacion)
    limpios = _validate_ajustes(ajustes)
    limpia = _validate_selection(db, user_id=user_id, selection=selection)
    limpios = _solo_las_figuras_elegidas(limpios, limpia)
    movido = composition.TEMPLATE.typography.desplazamiento(titulo_x, titulo_y)

    with db.transaction() as conn:
        episode = repo.insert(
            conn,
            user_id=user_id,
            title=_normalize_title(title),
            strength=strength,
            degradado=degradado,
            # Se guarda ya acotado, como los ajustes: la fila dice lo que se va
            # a dibujar, no lo que se pidió.
            titulo_ancho=composition.TEMPLATE.typography.ensanche(titulo_ancho),
            titulo_tamano=composition.TEMPLATE.typography.cambio_de_tamano(titulo_tamano),
            titulo_alto=composition.TEMPLATE.typography.cambio_de_alto(titulo_alto),
            titulo_apilado=titulo_apilado,
            titulo_x=movido[0],
            titulo_y=movido[1],
            titulo_alineacion=titulo_alineacion,
            selection=limpia,
            ajustes=limpios,
        )
    log.info(
        "episodes.created",
        extra={"episode_id": episode.id, "roles": sorted(limpia)},
    )
    return episode


def get_episode(db: Database, *, user_id: str, episode_id: str) -> repo.Episode:
    with db.connection() as conn:
        episode = repo.get(conn, user_id=user_id, episode_id=episode_id)
    if episode is None:
        raise errors.EpisodioNoEncontrado("Ese episodio no existe.")
    return episode


def list_episodes(db: Database, *, user_id: str) -> list[repo.Episode]:
    with db.connection() as conn:
        return repo.list_episodes(conn, user_id=user_id)


def delete_episode(db: Database, *, user_id: str, episode_id: str) -> None:
    with db.transaction() as conn:
        if repo.soft_delete(conn, user_id=user_id, episode_id=episode_id) == 0:
            existe = conn.execute(
                "SELECT 1 FROM episodes_jobs WHERE id = ? AND user_id = ?",
                (episode_id, user_id),
            ).fetchone()
            if existe is None:
                raise errors.EpisodioNoEncontrado("Ese episodio no existe.")


def set_title(db: Database, *, user_id: str, episode_id: str, title: str) -> repo.Episode:
    """Cambiar el titulo no invalida el armado: se vuelve a componer sobre la
    misma base, gratis (SPEC 7, paso 3)."""
    episode = get_episode(db, user_id=user_id, episode_id=episode_id)
    with db.transaction() as conn:
        repo.update_title(conn, episode_id=episode.id, title=_normalize_title(title))
    return get_episode(db, user_id=user_id, episode_id=episode_id)


# --- el armado -----------------------------------------------------------


def _brief_de(
    db: Database,
    settings: Settings,
    *,
    user_id: str,
    slots: dict[str, list[str]],
    title: str,
    degradado: str = composition.DEGRADADO_POR_DEFECTO,
    ajustes: dict[str, list[composition.Ajuste]] | None = None,
    titulo_ancho: int = 0,
    titulo_tamano: int = 0,
    titulo_alto: int = 0,
    titulo_apilado: bool = False,
    titulo_x: int = 0,
    titulo_y: int = 0,
    titulo_alineacion: str = composition.ALINEACION_POR_DEFECTO,
    referencia: str = "",
) -> composition.Brief:
    """Resuelve una seleccion a rutas de archivo.

    Una foto borrada de la libreria se omite en vez de romper nada
    (SPEC 11.11): el resultado se degrada, no falla.
    """
    photos: dict[str, list] = {}
    for role, photo_ids in slots.items():
        rutas = []
        for photo_id in photo_ids:
            try:
                photo = library.get_photo(db, user_id=user_id, photo_id=photo_id)
            except Exception:
                log.warning(
                    "episodes.photo_missing",
                    extra={"episode_id": referencia, "photo_id": photo_id, "role": role},
                )
                continue
            media = library.resolve_media(db, settings, photo)
            rutas.append(intake.path(settings, media))
        if rutas:
            photos[role] = rutas
    return composition.Brief(
        title=title,
        photos=photos,
        degradado=degradado,
        ajustes=dict(ajustes or {}),
        titulo_ancho=titulo_ancho,
        titulo_tamano=titulo_tamano,
        titulo_alto=titulo_alto,
        titulo_apilado=titulo_apilado,
        titulo_x=titulo_x,
        titulo_y=titulo_y,
        titulo_alineacion=titulo_alineacion,
    )


def _build_brief(db: Database, settings: Settings, episode: repo.Episode) -> composition.Brief:
    return _brief_de(
        db,
        settings,
        user_id=episode.user_id,
        slots=episode.slots,
        title=episode.title,
        degradado=episode.degradado,
        ajustes=episode.ajustes,
        titulo_ancho=episode.titulo_ancho,
        titulo_tamano=episode.titulo_tamano,
        titulo_alto=episode.titulo_alto,
        titulo_apilado=episode.titulo_apilado,
        titulo_x=episode.titulo_x,
        titulo_y=episode.titulo_y,
        titulo_alineacion=episode.titulo_alineacion,
        referencia=episode.id,
    )


def _brief_del_borrador(
    db: Database,
    settings: Settings,
    *,
    user_id: str,
    selection: dict[str, list[str]],
    title: str = "",
    degradado: str = composition.DEGRADADO_POR_DEFECTO,
    ajustes: dict[str, list[composition.Ajuste]] | None = None,
    titulo_ancho: int = 0,
    titulo_tamano: int = 0,
    titulo_alto: int = 0,
    titulo_apilado: bool = False,
    titulo_x: int = 0,
    titulo_y: int = 0,
    titulo_alineacion: str = composition.ALINEACION_POR_DEFECTO,
) -> composition.Brief:
    """El brief de una seleccion que todavia no es un episodio.

    La seleccion se valida igual que al crear -- `get_photo` lanza 404 si la foto
    no es tuya -- pero sin los MINIMOS: a mitad del flujo todavia no hay
    conductor, y eso no es un error, es el paso 1.
    """
    limpia = _validate_selection(db, user_id=user_id, selection=selection, exigir_minimos=False)
    return _brief_de(
        db,
        settings,
        user_id=user_id,
        slots=limpia,
        title=title,
        degradado=degradado,
        ajustes=_solo_las_figuras_elegidas(_validate_ajustes(ajustes), limpia),
        titulo_ancho=titulo_ancho,
        titulo_tamano=titulo_tamano,
        titulo_alto=titulo_alto,
        titulo_apilado=titulo_apilado,
        titulo_x=titulo_x,
        titulo_y=titulo_y,
        titulo_alineacion=titulo_alineacion,
    )


def preview(db: Database, settings: Settings, **borrador) -> bytes:
    """La miniatura en pequeno de una seleccion que todavia no es un episodio.

    No escribe nada: ni fila, ni archivo. Es lo que permite que el flujo semanal
    ensene el resultado en cada toque sin dejar episodios a medias por el camino
    (SPEC 8.4), y lo que hace que el episodio se cree solo cuando se confirma.
    `borrador` son los argumentos de `_brief_del_borrador`.
    """
    return composition.preview(_brief_del_borrador(db, settings, **borrador))


def lienzo(db: Database, settings: Settings, **borrador) -> list[composition.Capa]:
    """El mismo borrador que `preview`, sin apilar: las capas y su sitio.

    Tampoco escribe nada. Es lo que el navegador apila para mover una figura
    bajo el dedo, y apilarlo da lo mismo que `preview` (COMPOSITION-42).
    """
    return composition.capas(_brief_del_borrador(db, settings, **borrador))


def capa(db: Database, settings: Settings, nombre: str, **borrador) -> tuple[bytes, str] | None:
    """UNA capa del lienzo, lista para servir. `None` si ese borrador no la tiene."""
    puesta = composition.capa(_brief_del_borrador(db, settings, **borrador), nombre)
    return composition.entregar(puesta) if puesta else None


def build_assembly(
    db: Database,
    settings: Settings,
    finisher: finishing.Finisher,
    *,
    user_id: str,
    episode_id: str,
) -> repo.Assembly:
    """Arma la miniatura. Idempotente: mismo brief, mismo armado."""
    episode = get_episode(db, user_id=user_id, episode_id=episode_id)
    brief = _build_brief(db, settings, episode)
    checksum = composition.brief_checksum(brief)

    with db.connection() as conn:
        existente = repo.find_assembly(conn, episode_id=episode.id, brief_checksum=checksum)
    if existente is not None:
        log.info("episodes.assembly.reused", extra={"episode_id": episode.id})
        return existente

    resultado = composition.compose(brief)

    # SPEC 7 pasos 2 y 3: el modelo recibe la BASE (sin logo ni titulo) y lo que
    # devuelve se vuelve a componer con logo y titulo a fidelidad completa. Por
    # eso ninguno de los dos pasa jamas por el modelo.
    acabado = finishing.safe_finish(finisher, resultado.base, strength=episode.strength)
    final = composition.reapply(acabado.png, brief) if acabado.applied else resultado.final

    base_media = intake.store(db, settings, io.BytesIO(acabado.png))
    final_media = intake.store(db, settings, io.BytesIO(final))

    with db.transaction() as conn:
        # Otro armado simultaneo del mismo brief pudo ganar la carrera; los
        # bytes son identicos, asi que basta con quedarse con el que gano.
        ya = repo.find_assembly(conn, episode_id=episode.id, brief_checksum=checksum)
        if ya is not None:
            return ya
        assembly = repo.insert_assembly(
            conn,
            episode_id=episode.id,
            brief_checksum=checksum,
            template_version=resultado.template_version,
            base_media_id=base_media.id,
            final_media_id=final_media.id,
            finish_applied=acabado.applied,
            finish_provider=acabado.provider,
            finish_detail=acabado.detail,
        )

    log.info(
        "episodes.assembly.rendered",
        extra={
            "episode_id": episode.id,
            "template_version": resultado.template_version,
            "finish_applied": acabado.applied,
            "title_size": resultado.title_size,
        },
    )
    return assembly


def latest_assembly(db: Database, *, user_id: str, episode_id: str) -> repo.Assembly:
    episode = get_episode(db, user_id=user_id, episode_id=episode_id)
    with db.connection() as conn:
        assembly = repo.latest_assembly(conn, episode_id=episode.id)
    if assembly is None:
        raise errors.SinArmado("Ese episodio todavía no se ha armado.")
    return assembly
