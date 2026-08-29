"""De donde sale la tipografia del titulo.

Cadena de resolucion, en orden:

1. Un `.ttf`/`.otf` en `composition/typefaces/` -- la del show, cuando exista.
2. Una del sistema, de una lista de candidatas conocidas.
3. Error claro, nunca la fuente de mapa de bits de Pillow: un titulo a 90px con
   la fuente por defecto no es un fallback, es un resultado inservible.

Cual se resolvio queda registrado en el resultado del armado. Importa: mientras
no haya una tipografia en el repo, el mismo brief en dos maquinas distintas
produce pixeles distintos, y eso hay que poder verlo.
"""

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# `typefaces/` y no `fonts/`: una carpeta con el mismo nombre que este modulo
# seria un paquete de espacio de nombres compitiendo con `fonts.py`. Python
# resuelve a favor del modulo, pero es una trampa que no hay por que dejar puesta.
BUNDLED_DIR = Path(__file__).resolve().parent / "typefaces"

# Ordenadas por que tan bien funcionan en una miniatura: condensadas y pesadas
# primero. Un titulo en mayusculas a 90px necesita peso; una regular se pierde.
SYSTEM_CANDIDATES = (
    # macOS
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
)


class SinTipografia(RuntimeError):
    pass


@lru_cache(maxsize=1)
def resolve() -> Path:
    """La tipografia a usar. Cacheada: se resuelve una vez por proceso."""
    bundled = sorted(p for p in BUNDLED_DIR.glob("*") if p.suffix.lower() in (".ttf", ".otf"))
    if bundled:
        return bundled[0]

    for candidate in SYSTEM_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path

    raise SinTipografia(
        "No hay ninguna tipografía disponible. Deja un .ttf en "
        f"{BUNDLED_DIR} (ver el README de esa carpeta)."
    )


@lru_cache(maxsize=64)
def load(size: int, path: str | None = None) -> ImageFont.FreeTypeFont:
    """Una tipografia a un tamano. Cacheada: el auto-ajuste prueba muchos tamanos."""
    return ImageFont.truetype(str(path or resolve()), size)


def is_bundled() -> bool:
    """True si la tipografia viene del repo y no del sistema.

    Mientras sea False, el armado no es reproducible entre maquinas.
    """
    return resolve().is_relative_to(BUNDLED_DIR)
