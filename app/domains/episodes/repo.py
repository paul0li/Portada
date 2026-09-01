"""SQL de episodes. Todo filtra por `user_id`."""

import sqlite3
from dataclasses import dataclass, field

from app.core.db import utcnow
from app.core.ids import new_id


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
    created_at: str
    deleted_at: str | None
    slots: dict[str, list[str]] = field(default_factory=dict)  # rol -> photo_ids


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


def insert(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    title: str,
    strength: str,
    degradado: str,
    selection: dict[str, list[str]],
) -> Episode:
    episode_id = new_id()
    creado = utcnow()
    conn.execute(
        "INSERT INTO episodes_jobs (id, user_id, title, strength, degradado, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (episode_id, user_id, title, strength, degradado, creado),
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
        created_at=creado,
        deleted_at=None,
        slots=selection,
    )


def get(conn: sqlite3.Connection, *, user_id: str, episode_id: str) -> Episode | None:
    row = conn.execute(
        "SELECT * FROM episodes_jobs WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (episode_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return Episode(**dict(row), slots=_slots(conn, episode_id))


def list_episodes(conn: sqlite3.Connection, *, user_id: str, limit: int = 50) -> list[Episode]:
    rows = conn.execute(
        "SELECT * FROM episodes_jobs WHERE user_id = ? AND deleted_at IS NULL "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [Episode(**dict(r), slots=_slots(conn, r["id"])) for r in rows]


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
