"""Contrato publico de episodes."""

from app.domains.composition.api import (
    AJUSTES,
    DEGRADADO_POR_DEFECTO,
    DEGRADADOS,
    ROLES_MOVIBLES,
    ROLES_VOLTEABLES,
    SIN_AJUSTE,
    TEMPLATE,
    TIPOGRAFIA,
    Ajuste,
    acotar,
)
from app.domains.episodes.repo import Assembly, Episode
from app.domains.episodes.router import router
from app.domains.episodes.service import (
    MAXIMOS,
    MINIMOS,
    build_assembly,
    capa,
    create_episode,
    get_episode,
    latest_assembly,
    lienzo,
    list_episodes,
    preview,
    set_title,
)
from app.domains.finishing.api import DEFAULT_STRENGTH, STRENGTHS

__all__ = [
    "AJUSTES",
    "TIPOGRAFIA",
    "DEFAULT_STRENGTH",
    "DEGRADADOS",
    "DEGRADADO_POR_DEFECTO",
    "MAXIMOS",
    "MINIMOS",
    "ROLES_MOVIBLES",
    "ROLES_VOLTEABLES",
    "SIN_AJUSTE",
    "TEMPLATE",
    "STRENGTHS",
    "Ajuste",
    "Assembly",
    "Episode",
    "acotar",
    "build_assembly",
    "capa",
    "create_episode",
    "get_episode",
    "latest_assembly",
    "lienzo",
    "list_episodes",
    "preview",
    "set_title",
    "router",
]
