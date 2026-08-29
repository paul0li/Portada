"""SQL de intake."""

import sqlite3
from dataclasses import dataclass

from app.core.db import utcnow
from app.core.ids import new_id


@dataclass(frozen=True, slots=True)
class MediaFile:
    id: str
    sha256: str
    path: str
    mime: str
    format: str
    width: int
    height: int
    bytes: int
    has_alpha: bool
    created_at: str


def _row(row: sqlite3.Row) -> MediaFile:
    data = dict(row)
    data["has_alpha"] = bool(data["has_alpha"])
    return MediaFile(**data)


def get(conn: sqlite3.Connection, media_id: str) -> MediaFile | None:
    row = conn.execute("SELECT * FROM intake_media_files WHERE id = ?", (media_id,)).fetchone()
    return _row(row) if row else None


def get_by_sha256(conn: sqlite3.Connection, sha256: str) -> MediaFile | None:
    row = conn.execute("SELECT * FROM intake_media_files WHERE sha256 = ?", (sha256,)).fetchone()
    return _row(row) if row else None


def insert(
    conn: sqlite3.Connection,
    *,
    sha256: str,
    path: str,
    mime: str,
    image_format: str,
    width: int,
    height: int,
    size_bytes: int,
    has_alpha: bool,
) -> MediaFile:
    media = MediaFile(
        id=new_id(),
        sha256=sha256,
        path=path,
        mime=mime,
        format=image_format,
        width=width,
        height=height,
        bytes=size_bytes,
        has_alpha=has_alpha,
        created_at=utcnow(),
    )
    conn.execute(
        "INSERT INTO intake_media_files "
        "(id, sha256, path, mime, format, width, height, bytes, has_alpha, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            media.id,
            media.sha256,
            media.path,
            media.mime,
            media.format,
            media.width,
            media.height,
            media.bytes,
            int(media.has_alpha),
            media.created_at,
        ),
    )
    return media
