"""Las fronteras entre dominios, verificadas.

Este test es el que hace que la arquitectura del plan sea real y no una
intencion. Un dominio solo puede importar el `api.py` de otro; nunca su `repo`,
su `service` ni su `router`. Sin esta prueba, la modularidad dura hasta el
primer viernes en que sea mas rapido importar el repo de al lado.

La tabla de abajo ES la documentacion de dependencias. Ampliarla es una decision
de diseno explicita, que se toma editando este archivo y justificandola.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
DOMAINS_DIR = APP / "domains"

# Que api.py puede importar cada dominio. Todos pueden importar app.core y app.config.
ALLOWED: dict[str, set[str]] = {
    "identity": set(),
    "intake": set(),
    "composition": set(),  # puro: ni siquiera toca la base de datos
    "processing": {"intake"},
    "library": {"intake", "processing"},
    "finishing": {"intake"},
    "episodes": {"library", "composition", "intake", "finishing"},
}


def _domains() -> list[str]:
    return sorted(
        p.name for p in DOMAINS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")
    )


def _imports(path: Path) -> list[tuple[str, int]]:
    """Todo modulo `app.*` importado por un archivo, con su linea.

    `from app.domains.intake import api` y `from app.domains.intake.api import x`
    se normalizan los dos a `app.domains.intake.api`. Son la misma dependencia
    escrita de dos formas, y la regla es sobre lo que se importa, no sobre como
    se teclea.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(a.name, node.lineno) for a in node.names if a.name.startswith("app.")]
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.startswith("app.")
        ):
            if node.module.count(".") == 2 and node.module.startswith("app.domains."):
                # `from app.domains.X import a, b`: cada nombre es un submodulo.
                found += [(f"{node.module}.{a.name}", node.lineno) for a in node.names]
            else:
                found.append((node.module, node.lineno))
    return found


def test_arch_01_dominios_declarados_existen():
    """Cada carpeta en domains/ tiene una fila en ALLOWED, y viceversa."""
    assert _domains() == sorted(ALLOWED), (
        "domains/ y la tabla ALLOWED se desincronizaron. "
        "Un dominio nuevo declara sus dependencias aca antes de tener codigo."
    )


@pytest.mark.parametrize("domain", _domains())
def test_arch_02_un_dominio_solo_importa_el_api_de_otro(domain: str):
    permitidos = ALLOWED[domain]
    for path in sorted((DOMAINS_DIR / domain).rglob("*.py")):
        for module, line in _imports(path):
            parts = module.split(".")
            if parts[:2] != ["app", "domains"]:
                continue  # app.core / app.config: libre para todos
            otro = parts[2]
            donde = f"{path.relative_to(APP.parent)}:{line}"
            if otro == domain:
                continue  # dentro de casa, sin restricciones
            assert otro in permitidos, (
                f"{donde} importa el dominio '{otro}', que no esta en "
                f"ALLOWED['{domain}'] = {sorted(permitidos) or '{}'}"
            )
            assert parts[3:4] == ["api"], (
                f"{donde} importa '{module}'. Desde fuera de un dominio solo se "
                f"importa su api.py: usa 'app.domains.{otro}.api'."
            )


def test_arch_03_core_no_conoce_ningun_dominio():
    """core es infraestructura. Si conoce un dominio, deja de ser reusable."""
    for path in sorted((APP / "core").rglob("*.py")):
        for module, line in _imports(path):
            assert not module.startswith("app.domains"), (
                f"app/core/{path.name}:{line} importa '{module}'. core no puede "
                "depender de un dominio; invierte la dependencia."
            )


def test_arch_04_composition_no_toca_la_base_de_datos():
    """El armado recibe rutas y un titulo, no filas.

    Es lo que permite responder la pregunta de SPEC 15.1 con un script y fotos
    reales, sin servidor, sin auth y sin migraciones.
    """
    for path in sorted((DOMAINS_DIR / "composition").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for prohibido in ("app.core.db", "sqlite3"):
            assert prohibido not in source, (
                f"composition/{path.name} menciona '{prohibido}'. Este dominio es "
                "puro: entra un Brief con rutas, sale un PNG."
            )
