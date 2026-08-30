"""Contrato publico de finishing: la pasada de IA sobre el armado.

Este dominio esta vacio a proposito y su contrato existe desde el dia 1.

Lo que hace `NoopFinisher` -- devolver el armado tal cual -- convierte dos reglas
del SPEC en hechos estructurales en vez de promesas del documento:

- SPEC 4.3 "la IA es opcional": lo es porque la implementacion POR DEFECTO no la
  usa, y es la que corre en todos los tests.
- SPEC 11.4 "el armado siempre es salida valida": lo es porque el camino sin IA
  no es un fallback que alguien tenga que acordarse de programar, es el camino
  normal.

Cuando llegue el modelo sera una clase mas y una variable de entorno. `episodes`
no cambia una linea.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.logging import get_logger

log = get_logger("portada.finishing")

# El unico mando de generacion del producto (SPEC 7).
Strength = Literal["suave", "medio", "fuerte"]
STRENGTHS: tuple[Strength, ...] = ("suave", "medio", "fuerte")
DEFAULT_STRENGTH: Strength = "medio"


@dataclass(frozen=True, slots=True)
class Finish:
    """El resultado de la pasada.

    `png` es la base terminada, SIN logo ni titulo: quien llama los vuelve a
    pegar encima (SPEC 7, paso 3). `applied=False` significa que no hubo pasada
    -- porque no hay modelo, porque fallo, o porque se agoto el tiempo -- y el
    armado original sigue siendo la respuesta.
    """

    png: bytes
    applied: bool
    provider: str
    detail: str | None = None


class Finisher(Protocol):
    name: str

    def finish(self, base_png: bytes, *, strength: Strength) -> Finish:
        """Recibe la BASE (sin logo ni titulo) y devuelve una base terminada."""
        ...


class NoopFinisher:
    """El acabado del MVP: ninguno.

    Devuelve el armado intacto. No es un stub que haya que reemplazar para que el
    producto funcione -- es la configuracion en la que el producto ya funciona.
    """

    name = "noop"

    def finish(self, base_png: bytes, *, strength: Strength) -> Finish:
        return Finish(png=base_png, applied=False, provider=self.name)


def build_finisher(name: str) -> Finisher:
    if name == "noop":
        return NoopFinisher()
    raise ValueError(f"Acabado desconocido: {name!r}")


def safe_finish(finisher: Finisher, base_png: bytes, *, strength: Strength) -> Finish:
    """Aplica el acabado sin que pueda romper el episodio.

    Cualquier excepcion se traga y se devuelve el armado original. Es la
    traduccion literal de SPEC 7: "si el paso 2 falla, expira o el usuario
    cancela, el episodio conserva su armado".
    """
    try:
        return finisher.finish(base_png, strength=strength)
    except Exception as exc:
        log.warning(
            "finishing.failed",
            extra={"provider": getattr(finisher, "name", "?"), "kind": type(exc).__name__},
        )
        return Finish(
            png=base_png,
            applied=False,
            provider=getattr(finisher, "name", "?"),
            detail=str(exc)[:200],
        )


__all__ = [
    "DEFAULT_STRENGTH",
    "STRENGTHS",
    "Finish",
    "Finisher",
    "NoopFinisher",
    "Strength",
    "build_finisher",
    "safe_finish",
]
