"""Cada criterio de `specs/` tiene un test.

Esto es lo que convierte "spec-driven" en algo que CI verifica en vez de una
intencion que se erosiona. La cadena es: criterio con id -> test cuyo nombre
empieza con ese id -> implementacion.

El test tambien corre al reves: un id de test que no existe en ningun spec es un
error, porque significa que alguien escribio una prueba para un comportamiento
que nadie acordo, o que renombro un criterio y dejo el test huerfano.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"
TESTS = ROOT / "tests"

CRITERION = re.compile(r"^-\s+\*\*([A-Z][A-Z0-9]*-\d+)\*\*", re.MULTILINE)
TEST_NAME = re.compile(r"^test_([a-z][a-z0-9]*)_(\d+)_")


def _criteria() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(SPECS.glob("*.md")):
        if path.name == "README.md":
            continue
        for match in CRITERION.finditer(path.read_text(encoding="utf-8")):
            criterion_id = match.group(1)
            assert criterion_id not in found, (
                f"{criterion_id} esta definido dos veces: en {found[criterion_id].name} "
                f"y en {path.name}. Un id identifica un solo comportamiento."
            )
            found[criterion_id] = path
    return found


def _tested_ids() -> dict[str, str]:
    """Los ids que las funciones de test declaran cubrir."""
    covered: dict[str, str] = {}
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            match = TEST_NAME.match(node.name)
            if match:
                domain, number = match.groups()
                covered[f"{domain.upper()}-{number}"] = f"{path.name}::{node.name}"
    return covered


def test_spec_coverage_todo_criterio_tiene_test():
    faltantes = sorted(set(_criteria()) - set(_tested_ids()))
    assert not faltantes, (
        "Criterios sin test: " + ", ".join(faltantes) + ".\n"
        "Escribe el test en rojo antes de implementar, o borra el criterio si ya no lo queremos."
    )


def test_spec_coverage_todo_test_tiene_criterio():
    huerfanos = sorted(set(_tested_ids()) - set(_criteria()))
    assert not huerfanos, (
        "Tests que dicen cubrir criterios inexistentes: "
        + ", ".join(f"{i} ({_tested_ids()[i]})" for i in huerfanos)
        + ".\nAgrega el criterio a specs/ o corrige el nombre del test."
    )


def test_spec_coverage_hay_criterios_que_verificar():
    """Una red de seguridad vacia pasa siempre. Esto detecta specs/ roto."""
    assert len(_criteria()) >= 10
