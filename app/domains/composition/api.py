"""Contrato publico de composition.

Este dominio no tiene router ni base de datos: entra un `Brief` con rutas y un
titulo, sale un PNG. Todo lo demas es de quien lo llama.
"""

from app.domains.composition.assembly import (
    BASES,
    SIN_AJUSTE,
    Ajuste,
    Brief,
    Composition,
    acotar,
    ajuste_de,
    base_checksum,
    brief_checksum,
    compose,
    preview,
    reapply,
)
from app.domains.composition.template import (
    AJUSTES,
    DEGRADADO_POR_DEFECTO,
    DEGRADADOS,
    ROLES_MOVIBLES,
    TEMPLATE,
    TEMPLATE_VERSION,
    Template,
)

__all__ = [
    "AJUSTES",
    "BASES",
    "ROLES_MOVIBLES",
    "SIN_AJUSTE",
    "Ajuste",
    "DEGRADADOS",
    "DEGRADADO_POR_DEFECTO",
    "TEMPLATE",
    "TEMPLATE_VERSION",
    "Brief",
    "Composition",
    "Template",
    "acotar",
    "ajuste_de",
    "base_checksum",
    "brief_checksum",
    "compose",
    "preview",
    "reapply",
]
