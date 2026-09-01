"""Formas de entrada y salida HTTP de episodes."""

from pydantic import BaseModel, Field

from app.domains.composition import api as composition


class AjusteIn(BaseModel):
    """El empujón de un rol. `capa` es relativa a la del template (+1 = adelante).

    Los tres son enteros sin tope aquí: los topes los pone el template y el
    service acota contra ellos, así que un número grande se convierte en «hasta
    donde llega» en vez de en un 422. Lo que sí es un 422 es pedir mover un rol
    que no se mueve.
    """

    dx: int = 0
    dy: int = 0
    capa: int = 0

    def a_ajuste(self) -> composition.Ajuste:
        return composition.Ajuste(dx=self.dx, dy=self.dy, capa=self.capa)


class CreateEpisode(BaseModel):
    title: str = Field(default="", max_length=200)
    # rol -> ids de foto. Se acepta un id suelto o una lista.
    selection: dict[str, list[str] | str] = Field(default_factory=dict)
    strength: str = "medio"
    # El fondo por defecto: solo se ve si `selection` no trae `fondo`. El nombre
    # se valida en el service, con los demas: aqui es un `str` para que un valor
    # raro salga como el 422 del dominio y no como uno de pydantic, que hablaria
    # de tipos en vez de decir cual es la lista de fondos.
    degradado: str = composition.DEGRADADO_POR_DEFECTO
    # rol -> empujón. Lo normal es no mandar ninguno.
    ajustes: dict[str, AjusteIn] = Field(default_factory=dict)

    def normalized_ajustes(self) -> dict[str, composition.Ajuste]:
        return {role: ajuste.a_ajuste() for role, ajuste in self.ajustes.items()}

    def normalized_selection(self) -> dict[str, list[str]]:
        return {
            role: ([value] if isinstance(value, str) else list(value))
            for role, value in self.selection.items()
        }


class UpdateTitle(BaseModel):
    title: str = Field(max_length=200)


class AssemblyOut(BaseModel):
    id: str
    template_version: int
    finish_applied: bool
    finish_provider: str | None
    created_at: str


class EpisodeOut(BaseModel):
    id: str
    title: str
    strength: str
    degradado: str
    # Solo los roles ajustados, y con los valores ya acotados: lo que se dibuja.
    ajustes: dict[str, AjusteIn] = Field(default_factory=dict)
    selection: dict[str, list[str]]
    created_at: str
    assembly: AssemblyOut | None = None
