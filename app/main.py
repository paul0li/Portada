"""Punto de entrada.

`create_app` es una factory y no un modulo con un `app` global a medio construir:
cada test crea su propia app con su propia base y su propio directorio de medios,
y el aislamiento entre tests deja de depender de recordar limpiar algo.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.core import handlers, middleware
from app.core.db import Database
from app.core.logging import configure, get_logger
from app.core.migrations import migrate
from app.domains.episodes import api as episodes_api
from app.domains.finishing import api as finishing_api
from app.domains.identity import api as identity_api
from app.domains.identity import email as identity_email
from app.domains.library import api as library_api
from app.domains.processing import api as processing_api
from app.domains.web import api as web_api

log = get_logger("portada.app")

# Los routers de cada dominio se montan aca a medida que existen.
# Orden alfabetico, sin logica: si montar dos routers en distinto orden cambia
# el comportamiento, el problema son las rutas, no el orden.
ROUTERS = [episodes_api.router, identity_api.router, library_api.router, web_api.router]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    applied = migrate(app.state.db)
    log.info(
        "app.started",
        extra={
            "env": settings.env,
            "database": str(settings.database_path),
            "migrations_applied": len(applied),
        },
    )
    yield
    log.info("app.stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure(settings.log_level)

    app = FastAPI(
        title="Portada",
        version="0.1.0",
        description="Armado deterministico de miniaturas para podcast.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database(settings.database_path)
    app.state.trust_proxy = settings.is_production

    settings.media_dir.mkdir(parents=True, exist_ok=True)

    # Se cuelgan en app.state en vez de importarse: es lo que permite que ningun
    # dominio dependa de identity ni del backend de correo (ver core/auth.py).
    app.state.authenticator = identity_api.make_authenticator(app.state.db, settings)
    app.state.mailer = identity_email.build_sender(settings)
    app.state.cutout_provider = processing_api.build_provider(settings.cutout_provider)
    app.state.finisher = finishing_api.build_finisher(settings.finisher)

    middleware.install(app)
    handlers.install(app)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    for router in ROUTERS:
        app.include_router(router)

    # Las pantallas se sirven desde el propio proceso: mismo origen, sin CORS
    # y sin aflojar la cookie. Es la postura que la cookie httponly+lax ya
    # daba por supuesta.
    web_api.mount_static(app)

    return app


app = create_app()
