"""Contrato publico de composition.

Este dominio no tiene router ni base de datos: entra un `Brief` con rutas y un
titulo, sale un PNG. Todo lo demas es de quien lo llama.
"""

from app.domains.composition.assembly import (
    Brief,
    Composition,
    brief_checksum,
    compose,
    reapply,
)
from app.domains.composition.template import TEMPLATE, TEMPLATE_VERSION, Template

__all__ = [
    "TEMPLATE",
    "TEMPLATE_VERSION",
    "Brief",
    "Composition",
    "Template",
    "brief_checksum",
    "compose",
    "reapply",
]
