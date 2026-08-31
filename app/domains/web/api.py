"""Contrato publico de web.

Es una hoja: nadie importa este dominio, y por eso lo unico que expone es su
router y como montar sus estaticos. Si algun dia algo importa `web`, es que la
logica se escribio en la pantalla.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.domains.web.router import ESTATICOS, router


def mount_static(app: FastAPI) -> None:
    app.mount("/estatico", StaticFiles(directory=str(ESTATICOS)), name="estatico")


__all__ = ["mount_static", "router"]
