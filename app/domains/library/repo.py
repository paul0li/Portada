"""SQL de library.

Todas las consultas filtran por `user_id`. No hay una funcion que busque una
foto solo por su id: si existiera, alguien la usaria en un endpoint y ahi
estaria la fuga.
"""

import sqlite3
from dataclasses import dataclass

from app.core.db import utcnow
from app.core.ids import new_id


@dataclass(frozen=True, slots=True)
class Photo:
    id: str
    user_id: str
    media_id: str
    role: str
    label: str | None
    description: str | None
    created_at: str
    deleted_at: str | None


def insert(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    media_id: str,
    role: str,
    label: str | None,
    description: str | None,
) -> Photo:
    photo = Photo(
        id=new_id(),
        user_id=user_id,
        media_id=media_id,
        role=role,
        label=label,
        description=description,
        created_at=utcnow(),
        deleted_at=None,
    )
    conn.execute(
        "INSERT INTO library_photos "
        "(id, user_id, media_id, role, label, description, created_at, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            photo.id,
            photo.user_id,
            photo.media_id,
            photo.role,
            photo.label,
            photo.description,
            photo.created_at,
            photo.deleted_at,
        ),
    )
    return photo


def get(conn: sqlite3.Connection, *, user_id: str, photo_id: str) -> Photo | None:
    row = conn.execute(
        "SELECT * FROM library_photos WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (photo_id, user_id),
    ).fetchone()
    return Photo(**dict(row)) if row else None


def list_photos(conn: sqlite3.Connection, *, user_id: str, role: str | None = None) -> list[Photo]:
    sql = "SELECT * FROM library_photos WHERE user_id = ? AND deleted_at IS NULL"
    params: list[str] = [user_id]
    if role is not None:
        sql += " AND role = ?"
        params.append(role)
    sql += " ORDER BY created_at DESC, id DESC"
    return [Photo(**dict(r)) for r in conn.execute(sql, params)]


def soft_delete(conn: sqlite3.Connection, *, user_id: str, photo_id: str) -> int:
    cursor = conn.execute(
        "UPDATE library_photos SET deleted_at = ? "
        "WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (utcnow(), photo_id, user_id),
    )
    return cursor.rowcount


def count_by_role(conn: sqlite3.Connection, *, user_id: str) -> dict[str, int]:
    """Las estadisticas de la pantalla de inicio (SPEC 9)."""
    rows = conn.execute(
        "SELECT role, COUNT(*) FROM library_photos "
        "WHERE user_id = ? AND deleted_at IS NULL GROUP BY role",
        (user_id,),
    )
    return {role: total for role, total in rows}
