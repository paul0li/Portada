"""Criterios de `specs/core.md`: el contrato de la infraestructura compartida."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core.db import Database
from app.core.errors import Conflict
from app.core.ids import is_id, new_id
from app.core.migrations import MigrationError, migrate

REQUEST_ID = "X-Request-Id"


# --- el borde HTTP -------------------------------------------------------


def test_core_01_health_responde_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_core_02_toda_respuesta_lleva_request_id(client: TestClient):
    for path in ("/health", "/no-existe"):
        assert is_id(client.get(path).headers[REQUEST_ID])


def test_core_03_se_conserva_un_request_id_entrante_valido(client: TestClient):
    entrante = new_id()
    response = client.get("/health", headers={REQUEST_ID: entrante})
    assert response.headers[REQUEST_ID] == entrante


@pytest.mark.parametrize(
    "malicioso",
    [
        "../../etc/passwd",
        "id con espacios",
        'x" OR 1=1',
        "a" * 200,
        "\n".join(["falso", "log", "inyectado"]),
    ],
)
def test_core_04_se_descarta_un_request_id_entrante_invalido(client: TestClient, malicioso: str):
    response = client.get("/health", headers={REQUEST_ID: malicioso})
    devuelto = response.headers[REQUEST_ID]
    assert devuelto != malicioso
    assert is_id(devuelto)


def test_core_05_ruta_inexistente_usa_el_formato_de_error_estandar(client: TestClient):
    response = client.get("/no-existe")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert set(error) == {"code", "message", "request_id", "details"}


def test_core_06_un_app_error_conserva_status_code_y_request_id(app, settings):
    @app.get("/_prueba/conflicto")
    def _conflicto():
        raise Conflict("Ya existe.", code="LIBRARY_PHOTO_DUPLICADA", details={"photo_id": "01J"})

    with TestClient(app) as client:
        response = client.get("/_prueba/conflicto")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "LIBRARY_PHOTO_DUPLICADA"
    assert error["details"] == {"photo_id": "01J"}
    # El id del cuerpo es el mismo de la cabecera: es lo que hace que el usuario
    # pueda reportar un error y nosotros encontrar su traza.
    assert error["request_id"] == response.headers[REQUEST_ID]


def test_core_07_una_excepcion_no_controlada_no_filtra_nada(app):
    secreto = "clave-de-la-base-de-datos"

    @app.get("/_prueba/explota")
    def _explota():
        raise ZeroDivisionError(f"conectando con {secreto}")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_prueba/explota")

    assert response.status_code == 500
    cuerpo = response.text
    assert secreto not in cuerpo
    assert "ZeroDivisionError" not in cuerpo
    assert "Traceback" not in cuerpo
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


def test_core_08_un_cuerpo_invalido_nombra_el_campo_pero_no_el_valor(app):
    from pydantic import BaseModel

    class Entrada(BaseModel):
        token: str

    @app.post("/_prueba/verify")
    def _verify(body: Entrada):
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post("/_prueba/verify", json={"token": 12345})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"][0]["field"] == "token"
    # El valor enviado no se refleja: en /auth/verify ese campo es el token.
    assert "12345" not in response.text


# --- migraciones ---------------------------------------------------------


def _escribir(tmp_path, dominio: str, nombre: str, sql: str):
    carpeta = tmp_path / "domains" / dominio / "migrations"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text(sql, encoding="utf-8")
    return tmp_path / "domains"


def test_core_09_las_migraciones_son_idempotentes(tmp_path):
    dominios = _escribir(tmp_path, "ejemplo", "001_init.sql", "CREATE TABLE ejemplo_x (id TEXT);")
    db = Database(tmp_path / "t.db")

    primera = migrate(db, domains_dir=dominios)
    segunda = migrate(db, domains_dir=dominios)

    assert len(primera) == 1
    assert segunda == [], "una segunda corrida no debe reaplicar nada"


def test_core_10_editar_una_migracion_aplicada_falla_ruidosamente(tmp_path):
    dominios = _escribir(tmp_path, "ejemplo", "001_init.sql", "CREATE TABLE ejemplo_x (id TEXT);")
    db = Database(tmp_path / "t.db")
    migrate(db, domains_dir=dominios)

    _escribir(tmp_path, "ejemplo", "001_init.sql", "CREATE TABLE ejemplo_x (id TEXT, otro TEXT);")

    with pytest.raises(MigrationError, match="inmutable"):
        migrate(db, domains_dir=dominios)


def test_core_11_una_migracion_que_falla_no_deja_nada_a_medias(tmp_path):
    dominios = _escribir(
        tmp_path,
        "ejemplo",
        "001_init.sql",
        "CREATE TABLE ejemplo_bien (id TEXT);\nESTO NO ES SQL VALIDO;",
    )
    db = Database(tmp_path / "t.db")

    with pytest.raises(sqlite3.OperationalError):
        migrate(db, domains_dir=dominios)

    with db.connection() as conn:
        tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "ejemplo_bien" not in tablas, "el DDL debe revertirse completo"
        aplicadas = conn.execute("SELECT COUNT(*) FROM core_schema_version").fetchone()[0]
        assert aplicadas == 0, "una migracion fallida no queda registrada"


# --- identificadores -----------------------------------------------------


def test_core_12_los_ids_ordenan_por_tiempo_y_no_llevan_separadores(monkeypatch):
    import app.core.ids as ids

    reloj = iter([1_700_000_000.000, 1_700_000_000.500, 1_700_000_001.000])
    monkeypatch.setattr(ids.time, "time", lambda: next(reloj))
    generados = [ids.new_id() for _ in range(3)]

    assert generados == sorted(generados)
    assert all(is_id(i) for i in generados)
    # Un id se usa para construir rutas en disco: no puede escaparse del directorio.
    assert not any(c in i for i in generados for c in "/\\.")
    assert not is_id("../../etc/passwd")


# --- disciplina de logging -----------------------------------------------


def test_core_13_ningun_extra_pisa_un_atributo_reservado():
    """`log.info(..., extra={"name": x})` explota con KeyError en ejecucion.

    Es una trampa cara: stdlib no avisa al escribirlo, y si el nivel de log del
    entorno es alto, el LogRecord ni se construye y el error queda dormido hasta
    produccion. Esta prueba lo caza estaticamente, en TODO el codigo, incluso en
    ramas que ningun test recorre.
    """
    import ast
    from pathlib import Path

    from app.core.logging import _RESERVED

    app_dir = Path(__file__).resolve().parent.parent / "app"
    problemas: list[str] = []

    for path in sorted(app_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
                    continue
                for clave in keyword.value.keys:
                    if isinstance(clave, ast.Constant) and clave.value in _RESERVED:
                        problemas.append(
                            f"{path.name}:{clave.lineno} usa extra={{'{clave.value}': ...}}"
                        )

    assert not problemas, (
        "Nombres reservados de LogRecord en extra=:\n  "
        + "\n  ".join(problemas)
        + "\nRenombra la clave (p. ej. 'name' -> 'migration', 'module' -> 'domain')."
    )
