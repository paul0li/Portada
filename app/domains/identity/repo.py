"""SQL de identity. Sin reglas de negocio: decide el service.

Las funciones reciben una conexion en vez de abrirla. Asi el service compone
varias en una sola transaccion -- marcar el token como usado y crear la sesion
tienen que ser atomicos, o un token vale por dos sesiones.
"""

import sqlite3
from dataclasses import dataclass

from app.core.db import utcnow
from app.core.ids import new_id


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    created_at: str
    last_login_at: str | None


@dataclass(frozen=True, slots=True)
class MagicToken:
    id: str
    user_id: str
    expires_at: str
    used_at: str | None
    invalidated_at: str | None


# --- usuarios ------------------------------------------------------------


def get_user_by_email(conn: sqlite3.Connection, email: str) -> User | None:
    row = conn.execute("SELECT * FROM identity_users WHERE email = ?", (email,)).fetchone()
    return User(**dict(row)) if row else None


def get_user(conn: sqlite3.Connection, user_id: str) -> User | None:
    row = conn.execute("SELECT * FROM identity_users WHERE id = ?", (user_id,)).fetchone()
    return User(**dict(row)) if row else None


def create_user(conn: sqlite3.Connection, email: str) -> User:
    user = User(id=new_id(), email=email, created_at=utcnow(), last_login_at=None)
    conn.execute(
        "INSERT INTO identity_users (id, email, created_at, last_login_at) VALUES (?, ?, ?, ?)",
        (user.id, user.email, user.created_at, user.last_login_at),
    )
    return user


def touch_login(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("UPDATE identity_users SET last_login_at = ? WHERE id = ?", (utcnow(), user_id))


# --- magic tokens --------------------------------------------------------


def invalidate_pending_tokens(conn: sqlite3.Connection, user_id: str) -> int:
    cursor = conn.execute(
        "UPDATE identity_magic_tokens SET invalidated_at = ? "
        "WHERE user_id = ? AND used_at IS NULL AND invalidated_at IS NULL",
        (utcnow(), user_id),
    )
    return cursor.rowcount


def create_magic_token(
    conn: sqlite3.Connection, *, user_id: str, token_hash: str, expires_at: str
) -> str:
    token_id = new_id()
    conn.execute(
        "INSERT INTO identity_magic_tokens (id, user_id, token_hash, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token_id, user_id, token_hash, utcnow(), expires_at),
    )
    return token_id


def find_magic_token(conn: sqlite3.Connection, token_hash: str) -> MagicToken | None:
    row = conn.execute(
        "SELECT id, user_id, expires_at, used_at, invalidated_at "
        "FROM identity_magic_tokens WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    return MagicToken(**dict(row)) if row else None


def mark_token_used(conn: sqlite3.Connection, token_id: str) -> int:
    """Devuelve las filas afectadas.

    El `AND used_at IS NULL` no es redundante con la validacion del service: es
    lo que hace que dos canjes simultaneos del mismo token no puedan ganar los
    dos. El segundo actualiza cero filas y el service aborta.
    """
    cursor = conn.execute(
        "UPDATE identity_magic_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
        (utcnow(), token_id),
    )
    return cursor.rowcount


# --- sesiones ------------------------------------------------------------


def create_session(
    conn: sqlite3.Connection, *, session_id: str, user_id: str, expires_at: str
) -> None:
    conn.execute(
        "INSERT INTO identity_sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, utcnow(), expires_at),
    )


def find_live_session_user(conn: sqlite3.Connection, session_id: str) -> str | None:
    """El dueno de una sesion viva, o None. Un solo lookup por clave primaria."""
    row = conn.execute(
        "SELECT user_id FROM identity_sessions "
        "WHERE id = ? AND revoked_at IS NULL AND expires_at > ?",
        (session_id, utcnow()),
    ).fetchone()
    return row[0] if row else None


def revoke_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "UPDATE identity_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
        (utcnow(), session_id),
    )


# --- rate limiting -------------------------------------------------------


def record_link_request(conn: sqlite3.Connection, *, email: str, ip: str) -> None:
    conn.execute(
        "INSERT INTO identity_link_requests (id, email, ip, created_at) VALUES (?, ?, ?, ?)",
        (new_id(), email, ip, utcnow()),
    )


def count_link_requests(
    conn: sqlite3.Connection, *, email: str, ip: str, since: str
) -> tuple[int, int]:
    """(por email, por IP) dentro de la ventana. Una consulta, no dos."""
    row = conn.execute(
        "SELECT COALESCE(SUM(email = ?), 0), COALESCE(SUM(ip = ?), 0) "
        "FROM identity_link_requests WHERE created_at > ?",
        (email, ip, since),
    ).fetchone()
    return int(row[0]), int(row[1])
