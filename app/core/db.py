"""Acceso a SQLite.

Dos decisiones que explican el resto del archivo:

1. `isolation_level=None` desactiva el manejo implicito de transacciones de
   sqlite3. Las abrimos nosotros con BEGIN IMMEDIATE. Sin esto, sqlite3 decide
   por su cuenta cuando empezar y terminar una transaccion, y "un solo escritor"
   deja de ser una disciplina que podamos sostener.

2. Las fechas se guardan como texto ISO-8601 UTC. Ordenan lexicograficamente,
   se leen en un log, y evitan los adaptadores de datetime que Python 3.12
   marco como obsoletos.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

# WAL: lectores concurrentes sin bloquear al escritor.
# synchronous=NORMAL: en WAL no se pierde integridad, solo la ultima transaccion
#   ante un corte de energia. Para una libreria de fotos es el trato correcto.
# busy_timeout: en vez de fallar con SQLITE_BUSY, el escritor espera su turno.
_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA temp_store = MEMORY",
)


def utcnow() -> str:
    """El unico reloj del backend. Texto ISO-8601 en UTC, con `Z`."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Database:
    """Duena de la ruta del archivo y de como se abre una conexion.

    Se instancia una vez por proceso (y una vez por test). No guarda conexiones:
    cada request abre la suya y la cierra, que es lo que mantiene las
    transacciones cortas.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent != Path():
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        for pragma in _PRAGMAS:
            conn.execute(pragma)
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Una transaccion de escritura, corta por contrato.

        IMMEDIATE toma el lock de escritura al abrir en vez de al primer INSERT.
        Eso convierte una posible carrera al final en una espera ordenada al
        principio, que es lo que `busy_timeout` sabe manejar.

        Nunca se procesa una imagen dentro de este bloque (ver CLAUDE.md).
        """
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                # `in_transaction` no es paranoia: hay sentencias (executescript)
                # que cierran la transaccion por su cuenta. Sin esta guarda, el
                # ROLLBACK falla y su error tapa el error real que veniamos a
                # propagar, que es el unico que le sirve a quien depura.
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            if conn.in_transaction:
                conn.execute("COMMIT")
