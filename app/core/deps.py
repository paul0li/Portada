"""Dependencias de FastAPI compartidas por todos los dominios.

La conexion a la base vive en `app.state`, no en un global de modulo: eso es lo
que permite que cada test levante su propia app con su propia DB en un archivo
temporal, sin monkeypatching y sin estado que se filtre entre tests.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.core.db import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


Db = Annotated[Database, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings_dep)]
