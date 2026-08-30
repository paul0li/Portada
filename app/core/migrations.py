"""Migraciones por dominio.

Cada dominio es dueno de su esquema: sus `.sql` viven en
`app/domains/<dominio>/migrations/NNN_nombre.sql` y se registran bajo su nombre.

Como ninguna FOREIGN KEY cruza dominios (ver CLAUDE.md), el orden ENTRE dominios
es irrelevante: se aplican en orden alfabetico solo para que el resultado sea
reproducible. Dentro de un dominio manda el numero del archivo.

Una migracion ya aplicada se verifica por checksum. Editar un `.sql` que ya
corrio en algun lado es un error silencioso caro -- este runner lo vuelve ruidoso.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.db import Database, utcnow
from app.core.logging import get_logger

log = get_logger("portada.migrations")

DOMAINS_DIR = Path(__file__).resolve().parent.parent / "domains"
_FILENAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS core_schema_version (
    domain     TEXT NOT NULL,
    version    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    checksum   TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    PRIMARY KEY (domain, version)
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    domain: str
    version: int
    name: str
    path: Path
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()[:16]


class MigrationError(RuntimeError):
    """El esquema en disco y el esquema aplicado no concuerdan."""


def discover(domains_dir: Path = DOMAINS_DIR) -> list[Migration]:
    found: list[Migration] = []
    for migrations_dir in sorted(domains_dir.glob("*/migrations")):
        domain = migrations_dir.parent.name
        seen: set[int] = set()
        for path in sorted(migrations_dir.glob("*.sql")):
            match = _FILENAME.match(path.name)
            if not match:
                raise MigrationError(
                    f"{path}: el nombre debe ser NNN_snake_case.sql (ej. 001_init.sql)"
                )
            version = int(match.group(1))
            if version in seen:
                raise MigrationError(f"{domain}: version {version:03d} duplicada")
            seen.add(version)
            found.append(
                Migration(
                    domain=domain,
                    version=version,
                    name=path.stem,
                    path=path,
                    sql=path.read_text(encoding="utf-8"),
                )
            )
    return found


def applied(db: Database) -> dict[tuple[str, int], str]:
    with db.connection() as conn:
        conn.execute(_BOOTSTRAP)
        rows = conn.execute("SELECT domain, version, checksum FROM core_schema_version")
        return {(r["domain"], r["version"]): r["checksum"] for r in rows}


def migrate(db: Database, *, domains_dir: Path = DOMAINS_DIR) -> list[Migration]:
    """Aplica lo que falte y devuelve lo aplicado en esta corrida."""
    already = applied(db)
    pending: list[Migration] = []

    for migration in discover(domains_dir):
        key = (migration.domain, migration.version)
        if key not in already:
            pending.append(migration)
        elif already[key] != migration.checksum:
            raise MigrationError(
                f"{migration.path.name} de '{migration.domain}' cambio despues de aplicarse "
                f"(aplicado {already[key]}, en disco {migration.checksum}). "
                "Una migracion aplicada es inmutable: escribe una nueva."
            )

    for migration in pending:
        # Una transaccion por migracion: si la tercera falla, las dos primeras
        # quedan aplicadas y registradas, y reintentar retoma donde quedo.
        #
        # El BEGIN va DENTRO del script, no en db.transaction(): executescript
        # hace COMMIT de la transaccion pendiente antes de empezar, asi que una
        # transaccion abierta por fuera no sobreviviria. Abierta por dentro si,
        # y como el DDL de SQLite es transaccional, una migracion a medias no
        # existe: o estan todas sus tablas, o ninguna.
        with db.connection() as conn:
            try:
                conn.executescript("BEGIN IMMEDIATE;\n" + migration.sql)
                conn.execute(
                    "INSERT INTO core_schema_version "
                    "(domain, version, name, checksum, applied_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        migration.domain,
                        migration.version,
                        migration.name,
                        migration.checksum,
                        utcnow(),
                    ),
                )
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                log.error(
                    "core.migration.failed",
                    extra={"domain": migration.domain, "version": migration.version},
                )
                raise
        log.info(
            "core.migration.applied",
            extra={
                "domain": migration.domain,
                "version": migration.version,
                "migration": migration.name,
            },
        )

    return pending


def main() -> None:
    from app.config import get_settings
    from app.core.logging import configure

    settings = get_settings()
    configure(settings.log_level)
    db = Database(settings.database_path)
    done = migrate(db)
    if not done:
        log.info("core.migration.up_to_date", extra={"database": str(settings.database_path)})


if __name__ == "__main__":
    main()
