"""Contrato publico de library."""

from app.domains.library.repo import Photo
from app.domains.library.router import router
from app.domains.library.service import (
    ROLES,
    add_photo,
    delete_photo,
    get_photo,
    list_photos,
    resolve_media,
    stats,
)

__all__ = [
    "ROLES",
    "Photo",
    "add_photo",
    "delete_photo",
    "get_photo",
    "list_photos",
    "resolve_media",
    "router",
    "stats",
]
