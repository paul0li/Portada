"""SQL de processing."""

import sqlite3
from dataclasses import dataclass

from app.core.db import utcnow
from app.core.ids import new_id


@dataclass(frozen=True, slots=True)
class Derivative:
    id: str
    source_media_id: str
    kind: str
    result_media_id: str | None
    status: str
    provider: str
    error: str | None
    created_at: str
    completed_at: str | None

    @property
    def is_ready(self) -> bool:
        return self.status == "ready" and self.result_media_id is not None


def find(conn: sqlite3.Connection, *, source_media_id: str, kind: str) -> Derivative | None:
    row = conn.execute(
        "SELECT * FROM processing_derivatives WHERE source_media_id = ? AND kind = ?",
        (source_media_id, kind),
    ).fetchone()
    return Derivative(**dict(row)) if row else None


def upsert(
    conn: sqlite3.Connection,
    *,
    source_media_id: str,
    kind: str,
    status: str,
    provider: str,
    result_media_id: str | None = None,
    error: str | None = None,
) -> Derivative:
    """Registra el resultado. Reintentar sobrescribe el intento anterior."""
    conn.execute(
        "INSERT INTO processing_derivatives "
        "(id, source_media_id, kind, result_media_id, status, provider, error, "
        " created_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (source_media_id, kind) DO UPDATE SET "
        "  result_media_id = excluded.result_media_id, status = excluded.status, "
        "  provider = excluded.provider, error = excluded.error, "
        "  completed_at = excluded.completed_at",
        (
            new_id(),
            source_media_id,
            kind,
            result_media_id,
            status,
            provider,
            error,
            utcnow(),
            utcnow(),
        ),
    )
    found = find(conn, source_media_id=source_media_id, kind=kind)
    assert found is not None
    return found
