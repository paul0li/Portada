"""Contrato publico de composition.

Este dominio no tiene router ni base de datos: entra un `Brief` con rutas y un
titulo, sale un PNG. Todo lo demas es de quien lo llama.
"""

from app.domains.composition.assembly import (
    BASES,
    Brief,
    Composition,
    base_checksum,
    brief_checksum,
    compose,
    preview,
    reapply,
)
from app.domains.composition.template import (
    DEGRADADO_POR_DEFECTO,
    DEGRADADOS,
    TEMPLATE,
    TEMPLATE_VERSION,
    Template,
)

__all__ = [
    "BASES",
    "DEGRADADOS",
    "DEGRADADO_POR_DEFECTO",
    "TEMPLATE",
    "TEMPLATE_VERSION",
    "Brief",
    "Composition",
    "Template",
    "base_checksum",
    "brief_checksum",
    "compose",
    "preview",
    "reapply",
]
