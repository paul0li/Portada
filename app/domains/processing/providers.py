"""Los proveedores de recorte.

Un proveedor recibe la ruta de una imagen y devuelve la ruta de un PNG con el
fondo quitado, o levanta una excepcion. Nada mas.

Hay dos. `passthrough` no recorta y sirve de verdad: si la foto ya viene como
PNG con transparencia, el recorte ya esta hecho. `rembg` recorta con u2net y es
lo que corre cuando alguien pide "sacale el fondo" al subir la foto.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PIL import Image

# El modelo por defecto. Se eligio midiendo, no leyendo:
#
#   u2net                 0,44 s   borde suave, sin halo
#   isnet-general-use     1,2  s   leve resplandor
#   birefnet-general-lite 13,4 s   el borde mas nitido de todos
#
# birefnet gana mirando el PNG a 1280. Esa ventaja NO sobrevive a 320 px, que es
# como se ve una miniatura en un feed, y cuesta 30 veces mas tiempo.
MODELO = "u2net"


class CutoutProvider(Protocol):
    name: str

    # Si este proveedor de verdad quita fondos. `passthrough` no, y quien dibuja
    # una pantalla necesita saberlo: ofrecer "quitarle el fondo" con passthrough
    # puesto es un boton que no hace nada y no lo dice.
    quita_fondo: bool

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
    quita_fondo = False

    def cutout(self, source: Path) -> Path:
        return source


class RembgCutout:
    """Recorte real, con rembg corriendo u2net en CPU.

    El import de `rembg` vive DENTRO del recorte, no arriba del modulo, y eso es
    un requisito y no una optimizacion: importar rembg cuesta ~190 MB de RSS y
    ~0,7 s, y cargar la sesion sube a ~470 MB. Como el recorte es opcional -- se
    pide con una casilla al subir la foto -- un proceso de Portada donde nadie
    marca la casilla no tiene por que pagar nada de eso. (PROCESSING-06.)

    Medido en una Mac, con `u2net`: 1,2 s el primer recorte (0,73 importar +
    0,09 cargar el modelo + 0,42 recortar) y 0,42 s cada uno despues.

    El modelo son 177 MB que NO estan en el repo: se bajan una vez con
    `make cutout-model`. Si falta, `cutout` levanta y `ensure_cutout` deja la
    derivada en `failed`, que es como termina cualquier otro recorte roto: la
    foto queda con su original y la subida no se entera (PROCESSING-07).
    """

    name = "rembg"
    quita_fondo = True

    def __init__(
        self,
        modelo: str = MODELO,
        quitar_fondo: Callable[[Image.Image], Image.Image] | None = None,
    ) -> None:
        self._modelo = modelo
        # Inyectable para poder probar el contrato del proveedor sin bajar los
        # 177 MB del modelo en CI.
        self._quitar_fondo = quitar_fondo

    def cutout(self, source: Path) -> Path:
        quitar_fondo = self._quitar_fondo or self._rembg()
        with Image.open(source) as imagen:
            recortada = quitar_fondo(imagen.convert("RGBA"))

        # A un directorio temporal propio, no junto al origen: `ensure_cutout` lo
        # guarda por contenido en el almacen de medios y borra esto despues. La
        # carpeta de medios no admite archivos que no sean content-addressed.
        destino = Path(tempfile.mkdtemp(prefix="portada-recorte-")) / "recorte.png"
        recortada.save(destino, "PNG")
        return destino

    def _rembg(self) -> Callable[[Image.Image], Image.Image]:
        from rembg import new_session, remove

        sesion = getattr(self, "_sesion", None)
        if sesion is None:
            sesion = new_session(self._modelo)
            self._sesion = sesion
        return lambda imagen: remove(imagen, session=sesion)


def build_provider(name: str) -> CutoutProvider:
    if name == "passthrough":
        return PassthroughCutout()
    if name == "rembg":
        # Ojo: construirlo NO importa rembg. Ver PROCESSING-06.
        return RembgCutout()
    raise ValueError(f"Proveedor de recorte desconocido: {name!r}")
