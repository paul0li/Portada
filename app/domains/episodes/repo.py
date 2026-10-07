"""SQL de episodes. Todo filtra por `user_id`."""

import sqlite3
from dataclasses import dataclass, field

from app.core.db import utcnow
from app.core.ids import new_id
from app.domains.composition import api as composition


@dataclass(frozen=True, slots=True)
class Episode:
    id: str
    user_id: str
    title: str
    strength: str
    # `claro` u `oscuro`: cual de los degradados de la paleta responde a "no hay
    # foto de fondo". Se guarda por nombre, no por color: los colores viven en
    # el template y nadie mas los escribe.
    degradado: str
    # Como se puso el titulo: cuanto se ensancho su bloque, cuanto se movio el
    # tamano de la letra, cuanto subio el techo del bloque, y si va a una palabra
    # por linea. Todos son OVERLAY: cambiarlos cuesta lo mismo que corregir una
    # errata, no una composicion entera. Y son tres numeros porque hacen tres
    # cosas -- donde cortan las lineas, cuanto ocupa cada palabra, y cuantas
    # lineas entran.
    titulo_ancho: int
    titulo_tamano: int
    titulo_alto: int
    titulo_apilado: bool
    # Cuanto se movio el bloque entero del titulo en el lienzo (v11). Overlay.
    titulo_x: int
    titulo_y: int
    created_at: str
    deleted_at: str | None
    slots: dict[str, list[str]] = field(default_factory=dict)  # rol -> photo_ids
    # Rol -> un ajuste por FIGURA, en el orden de sus fotos. Vacio es lo normal:
    # "donde diga el template". El tipo es el de `composition` y no uno propio
    # de aqui -- un ajuste es un concepto de composicion, y tener dos copias del
    # mismo dato es tener dos verdades.
    ajustes: dict[str, list[composition.Ajuste]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Assembly:
    id: str
    episode_id: str
    brief_checksum: str
    template_version: int
    base_media_id: str
    final_media_id: str
    finish_applied: bool
    finish_provider: str | None
    finish_detail: str | None
    created_at: str


def _assembly(row: sqlite3.Row) -> Assembly:
    data = dict(row)
    data["finish_applied"] = bool(data["finish_applied"])
    return Assembly(**data)


def _slots(conn: sqlite3.Connection, episode_id: str) -> dict[str, list[str]]:
    rows = conn.execute(
        "SELECT role, photo_id FROM episodes_slots WHERE episode_id = ? ORDER BY role, position",
        (episode_id,),
    )
    seleccion: dict[str, list[str]] = {}
    for role, photo_id in rows:
        seleccion.setdefault(role, []).append(photo_id)
    return seleccion


def _ajustes(conn: sqlite3.Connection, episode_id: str) -> dict[str, list[composition.Ajuste]]:
    """Rol -> un ajuste por figura, en orden y sin huecos.

    Solo se guardan las figuras ajustadas, asi que una lista puede empezar por
    una figura que nadie toco: los huecos se rellenan con `SIN_AJUSTE`, que es
    lo que significa no tener fila.
    """
    rows = conn.execute(
        "SELECT role, posicion, dx, dy, capa, voltear_x, voltear_y, escala FROM episodes_ajustes "
        "WHERE episode_id = ? ORDER BY role, posicion",
        (episode_id,),
    )
    puestos: dict[str, list[composition.Ajuste]] = {}
    for role, posicion, dx, dy, capa, vx, vy, escala in rows:
        figuras = puestos.setdefault(role, [])
        figuras.extend([composition.SIN_AJUSTE] * (posicion + 1 - len(figuras)))
        figuras[posicion] = composition.Ajuste(
            dx=dx, dy=dy, capa=capa, voltear_x=bool(vx), voltear_y=bool(vy), escala=escala
        )
    return puestos


def insert(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    title: str,
    strength: str,
    degradado: str,
    titulo_ancho: int,
    titulo_tamano: int,
    titulo_alto: int,
    titulo_apilado: bool,
    selection: dict[str, list[str]],
    titulo_x: int = 0,
    titulo_y: int = 0,
    ajustes: dict[str, list[composition.Ajuste]] | None = None,
) -> Episode:
    episode_id = new_id()
    creado = utcnow()
    conn.execute(
        "INSERT INTO episodes_jobs "
        "(id, user_id, title, strength, degradado, titulo_ancho, titulo_tamano, "
        "titulo_alto, titulo_apilado, titulo_x, titulo_y, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            episode_id,
            user_id,
            title,
            strength,
            degradado,
            titulo_ancho,
            titulo_tamano,
            titulo_alto,
            int(titulo_apilado),
            titulo_x,
            titulo_y,
            creado,
        ),
    )
    # Una fila por figura AJUSTADA: las que estan donde dice el template no se
    # escriben, y por eso `_ajustes` rellena los huecos al leer.
    conn.executemany(
        "INSERT INTO episodes_ajustes "
        "(episode_id, role, posicion, dx, dy, capa, voltear_x, voltear_y, escala) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                episode_id,
                role,
                posicion,
                ajuste.dx,
                ajuste.dy,
                ajuste.capa,
                int(ajuste.voltear_x),
                int(ajuste.voltear_y),
                ajuste.escala,
            )
            for role, figuras in (ajustes or {}).items()
            for posicion, ajuste in enumerate(figuras)
            if ajuste != composition.SIN_AJUSTE
        ],
    )
    conn.executemany(
        "INSERT INTO episodes_slots (episode_id, role, photo_id, position) VALUES (?, ?, ?, ?)",
        [
            (episode_id, role, photo_id, position)
            for role, photo_ids in selection.items()
            for position, photo_id in enumerate(photo_ids)
        ],
    )
    return Episode(
        id=episode_id,
        user_id=user_id,
        title=title,
        strength=strength,
        degradado=degradado,
        titulo_ancho=titulo_ancho,
        titulo_tamano=titulo_tamano,
        titulo_alto=titulo_alto,
        titulo_apilado=titulo_apilado,
        titulo_x=titulo_x,
        titulo_y=titulo_y,
        created_at=creado,
        deleted_at=None,
        slots=selection,
        ajustes={role: list(figuras) for role, figuras in (ajustes or {}).items()},
    )


def _fila(row: sqlite3.Row) -> dict:
    """La fila como kwargs del dataclass. SQLite devuelve 0/1 donde hay un bool."""
    datos = dict(row)
    datos["titulo_apilado"] = bool(datos["titulo_apilado"])
    return datos


def get(conn: sqlite3.Connection, *, user_id: str, episode_id: str) -> Episode | None:
    row = conn.execute(
        "SELECT * FROM episodes_jobs WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (episode_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return Episode(**_fila(row), slots=_slots(conn, episode_id), ajustes=_ajustes(conn, episode_id))


def list_episodes(conn: sqlite3.Connection, *, user_id: str, limit: int = 50) -> list[Episode]:
    rows = conn.execute(
        "SELECT * FROM episodes_jobs WHERE user_id = ? AND deleted_at IS NULL "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [
        Episode(**_fila(r), slots=_slots(conn, r["id"]), ajustes=_ajustes(conn, r["id"]))
        for r in rows
    ]


def update_title(conn: sqlite3.Connection, *, episode_id: str, title: str) -> None:
    conn.execute("UPDATE episodes_jobs SET title = ? WHERE id = ?", (title, episode_id))


def soft_delete(conn: sqlite3.Connection, *, user_id: str, episode_id: str) -> int:
    cursor = conn.execute(
        "UPDATE episodes_jobs SET deleted_at = ? "
        "WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (utcnow(), episode_id, user_id),
    )
    return cursor.rowcount


# --- armados -------------------------------------------------------------


def find_assembly(
    conn: sqlite3.Connection, *, episode_id: str, brief_checksum: str
) -> Assembly | None:
    row = conn.execute(
        "SELECT * FROM episodes_assemblies WHERE episode_id = ? AND brief_checksum = ?",
        (episode_id, brief_checksum),
    ).fetchone()
    return _assembly(row) if row else None


def latest_assembly(conn: sqlite3.Connection, *, episode_id: str) -> Assembly | None:
    row = conn.execute(
        "SELECT * FROM episodes_assemblies WHERE episode_id = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (episode_id,),
    ).fetchone()
    return _assembly(row) if row else None


def insert_assembly(
    conn: sqlite3.Connection,
    *,
    episode_id: str,
    brief_checksum: str,
    template_version: int,
    base_media_id: str,
    final_media_id: str,
    finish_applied: bool,
    finish_provider: str | None,
    finish_detail: str | None,
) -> Assembly:
    assembly = Assembly(
        id=new_id(),
        episode_id=episode_id,
        brief_checksum=brief_checksum,
        template_version=template_version,
        base_media_id=base_media_id,
        final_media_id=final_media_id,
        finish_applied=finish_applied,
        finish_provider=finish_provider,
        finish_detail=finish_detail,
        created_at=utcnow(),
    )
    conn.execute(
        "INSERT INTO episodes_assemblies "
        "(id, episode_id, brief_checksum, template_version, base_media_id, final_media_id, "
        " finish_applied, finish_provider, finish_detail, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            assembly.id,
            assembly.episode_id,
            assembly.brief_checksum,
            assembly.template_version,
            assembly.base_media_id,
            assembly.final_media_id,
            int(assembly.finish_applied),
            assembly.finish_provider,
            assembly.finish_detail,
            assembly.created_at,
        ),
    )
    return assembly
