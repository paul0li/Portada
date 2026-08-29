"""Los proveedores de recorte.

Hoy hay uno solo y no hace nada. Eso es deliberado: el MVP apuesta a que el
armado deterministico ya es publicable (SPEC 15.1), y esta interfaz existe desde
el dia 1 para que meter rembg despues sea agregar una clase y cambiar una
variable de entorno, no reescribir `library` ni `composition`.

Un proveedor recibe la ruta de una imagen y devuelve la ruta de un PNG con el
fondo quitado, o levanta una excepcion. Nada mas.
"""

from pathlib import Path
from typing import Protocol


class CutoutProvider(Protocol):
    name: str

    def cutout(self, source: Path) -> Path:
        """La imagen sin fondo. Puede devolver `source` si no hay nada que hacer."""
        ...


class PassthroughCutout:
    """No recorta nada: devuelve la imagen tal cual.

    Sirve de verdad, no es un stub: si la foto ya viene como PNG con
    transparencia -- que es como se piden las fotos en el MVP -- el recorte ya
    esta hecho y no hay nada que computar.
    """

    name = "passthrough"

    def cutout(self, source: Path) -> Path:
        return source


def build_provider(name: str) -> CutoutProvider:
    if name == "passthrough":
        return PassthroughCutout()
    raise ValueError(f"Proveedor de recorte desconocido: {name!r}")
