"""Contrato publico de library."""

from app.domains.library.repo import Photo
from app.domains.library.router import router
from app.domains.library.service import (
    ROLES,
    ROLES_CON_RECORTE,
    add_photo,
    delete_photo,
    get_photo,
    list_photos,
    quitar_fondo,
    resolve_media,
    restaurar_fondo,
    stats,
)

__all__ = [
    "ROLES",
    "ROLES_CON_RECORTE",
    "Photo",
    "add_photo",
    "delete_photo",
    "get_photo",
    "list_photos",
    "quitar_fondo",
    "resolve_media",
    "restaurar_fondo",
    "router",
    "stats",
]
