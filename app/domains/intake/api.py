"""Contrato publico de intake.

Lo que otro dominio necesita saber de los bytes: guardarlos, recuperarlos por id
y saber donde estan en disco. Nada mas.
"""

from app.domains.intake.repo import MediaFile
from app.domains.intake.service import get, path, store

MediaId = str

__all__ = ["MediaFile", "MediaId", "get", "path", "store"]
