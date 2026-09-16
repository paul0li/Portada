"""Formas de entrada y salida HTTP de episodes."""

from pydantic import BaseModel, Field

from app.domains.composition import api as composition


class AjusteIn(BaseModel):
    """Lo que un episodio le hace a un rol: moverlo, cambiarle la capa, voltearlo.

    `capa` es relativa a la del template (+1 = adelante). Los tres enteros van
    sin tope aquí: los topes los pone el template y el service acota contra
    ellos, así que un número grande se convierte en «hasta donde llega» en vez
    de en un 422. Lo que sí es un 422 es pedir mover un rol que no se mueve, o
    voltear uno que no se voltea.
    """

    dx: int = 0
    dy: int = 0
    capa: int = 0
    # Por el eje del movimiento, como `dx` y `dy`: `voltear_x` cambia izquierda
    # por derecha. Ver `composition.Ajuste`.
    voltear_x: bool = False
    voltear_y: bool = False

    def a_ajuste(self) -> composition.Ajuste:
        return composition.Ajuste(
            dx=self.dx,
            dy=self.dy,
            capa=self.capa,
            voltear_x=self.voltear_x,
            voltear_y=self.voltear_y,
        )


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
    # Cómo se pone el título, respecto de lo que dice el template: cuánto se
    # ensancha su bloque, cuánto se mueve el tamaño de la letra, cuánto sube su
    # techo, y si va a una palabra por línea. Los números se acotan contra los
    # topes del template en vez de rechazarse, como los empujones: lo que el
    # template dice es hasta dónde llega, no cuál es inválido.
    titulo_ancho: int = 0
    titulo_tamano: int = 0
    titulo_alto: int = 0
    titulo_apilado: bool = False
    # rol -> un ajuste por FIGURA, en el orden de sus fotos. Se acepta uno
    # suelto o una lista, igual que `selection`: el caso normal es un rol con
    # una figura, y pedirle una lista de uno sería ceremonia.
    ajustes: dict[str, list[AjusteIn] | AjusteIn] = Field(default_factory=dict)

    def normalized_ajustes(self) -> dict[str, list[composition.Ajuste]]:
        return {
            role: [a.a_ajuste() for a in ([value] if isinstance(value, AjusteIn) else value)]
            for role, value in self.ajustes.items()
        }

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
    # Ya acotados: lo que se va a dibujar, no lo que se pidió.
    titulo_ancho: int = 0
    titulo_tamano: int = 0
    titulo_alto: int = 0
    titulo_apilado: bool = False
    # Solo los roles ajustados, y con los valores ya acotados: lo que se dibuja.
    # Siempre una lista, aunque entre suelto: a la salida no hay dos formas.
    ajustes: dict[str, list[AjusteIn]] = Field(default_factory=dict)
    selection: dict[str, list[str]]
    created_at: str
    assembly: AssemblyOut | None = None
