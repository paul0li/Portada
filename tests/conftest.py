"""Fixtures compartidas.

Cada test recibe una base de datos y un directorio de medios recien creados y
propios. No hay limpieza que recordar ni orden de tests que respetar: si dos
tests se afectan entre si, es un bug de la app, no del arnes de pruebas.

Se usa `TestClient` (sincrono) en vez de httpx async + pytest-asyncio a
proposito: una dependencia menos y tests que se leen de arriba a abajo.
"""

import io
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.db import Database
from app.core.logging import JsonFormatter
from app.core.migrations import migrate
from app.domains.identity.email import Message


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        # DEBUG y no WARNING a proposito: con el nivel alto, `log.info(...)` ni
        # siquiera construye el LogRecord, y un `extra` invalido pasa inadvertido
        # bajo test para reventar recien en dev. Que los tests emitan todo hace
        # que cada linea de log se ejecute de verdad. (Ver CORE-13.)
        log_level="DEBUG",
        database_path=tmp_path / "portada.db",
        media_dir=tmp_path / "media",
        public_url="http://testserver",
    )


@pytest.fixture
def db(settings: Settings) -> Database:
    """Una base migrada y vacia."""
    database = Database(settings.database_path)
    migrate(database)
    return database


class RecordingSender:
    """Guarda los correos en memoria en vez de mandarlos.

    Los tests leen el enlace desde aca, que es exactamente lo que hace una
    persona al abrir su bandeja: el flujo que se prueba es el real, sin SMTP.
    """

    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        self.sent.append(message)


@pytest.fixture
def mailer() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def logs():
    """Todo lo que la app loguea durante el test, como texto.

    Sirve para probar lo que NO debe aparecer: tokens, cookies, emails completos.
    Es la unica forma de verificar una regla de "nunca loguear X" sin leerse el
    codigo a mano cada vez.
    """
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    nivel_previo = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield buffer
    finally:
        root.removeHandler(handler)
        root.setLevel(nivel_previo)


@pytest.fixture
def app(settings: Settings, mailer: RecordingSender):
    from app.main import create_app

    application = create_app(settings)
    application.state.mailer = mailer
    return application


@pytest.fixture
def client(app) -> TestClient:
    """Cliente con el lifespan corrido: las migraciones ya se aplicaron."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def logged_in(client) -> TestClient:
    """Un cliente con sesion iniciada, via el flujo real de magic link.

    No inyecta una cookie a mano: hace el mismo recorrido que una persona. Si
    algun dia el login cambia, estos tests se enteran.
    """
    import re

    client.post("/auth/magic-link", json={"email": "paula@ejemplo.cl"})
    correo = client.app.state.mailer.sent[-1].text
    token = re.search(r"https?://\S+", correo).group(0).rsplit("=", 1)[-1]
    respuesta = client.post("/auth/verify", json={"token": token})
    assert respuesta.status_code == 200
    return client


@pytest.fixture
def imagen():
    """Una imagen PNG valida, distinta cada vez que cambian los parametros."""
    import io

    from PIL import Image

    def build(*, size=(400, 300), color=(180, 40, 40), alpha=False, fmt="PNG"):
        modo = "RGBA" if alpha else "RGB"
        relleno = (*color, 200) if alpha else color
        buffer = io.BytesIO()
        Image.new(modo, size, relleno).save(buffer, format=fmt)
        buffer.seek(0)
        return buffer

    return build
