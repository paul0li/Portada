"""Contrato publico de processing."""

from app.domains.processing.providers import (
    CutoutProvider,
    PassthroughCutout,
    RembgCutout,
    build_provider,
)
from app.domains.processing.repo import Derivative
from app.domains.processing.service import (
    clear_cutout,
    cutout_or_source,
    ensure_cutout,
    get_cutout,
)

__all__ = [
    "CutoutProvider",
    "Derivative",
    "PassthroughCutout",
    "RembgCutout",
    "build_provider",
    "clear_cutout",
    "cutout_or_source",
    "ensure_cutout",
    "get_cutout",
]
