"""EL template del show. Datos puros, sin logica.

Este es el archivo del que habla SPEC 6: "los numeros viven en un archivo, y
editarlos cambia todas las miniaturas futuras a la vez". Es la identidad visual
del show, y el unico lugar donde se decide el layout.

Cambiar cualquier valor de aqui es cambiar como se ve el canal. Por eso lleva
`TEMPLATE_VERSION`: subirlo es declarar que las miniaturas nuevas no van a
coincidir con las viejas, y hay un test que falla si se edita sin subirlo.
"""

from dataclasses import dataclass, field
from typing import Literal

TEMPLATE_VERSION = 4
# v4 (2026-08-31): el degradado que responde a "no hay fondo" pasa de oscuro a
#   claro. Solo se ve cuando el episodio no trae foto de fondo, pero eso es
#   justo el caso por defecto: es el fondo que tiene una miniatura cuando nadie
#   eligio uno.
# v3 (2026-08-30): Anton entra al repo como tipografia del titulo, y el titulo
#   pasa a anclarse a la linea base en vez de a la ascendente. Ninguna de las dos
#   cosas esta en este archivo, pero las dos mueven cada pixel del titulo: sin
#   subir la version, un episodio ya armado se queda en Impact -- el armado es
#   idempotente por `brief_checksum`, que incluye esta version -- y el canal
#   acaba con dos tipografias.
# v2 (2026-08-28): entra el rol `marco` -- un PNG 16:9 a sangre completa que va
#   encima de todo y que ya trae el nombre del show en una banda inferior. Eso
#   obligo a subir el titulo por encima de esa banda. Ver Typography.bottom.

CANVAS = (1280, 720)  # SPEC 10: la especificacion de miniatura de YouTube

Anchor = Literal["bottom-center", "center", "top-left"]


@dataclass(frozen=True, slots=True)
class Slot:
    """Donde va un rol. `z` decide quien tapa a quien."""

    role: str
    z: int
    anchor: Anchor
    x: int = 0
    y: int = 0
    height: int | None = None  # alto objetivo en px; el ancho sale del aspecto
    max_width: int | None = None
    max_height: int | None = None
    max_items: int = 1
    shadow: bool = False


# --- los cinco roles de SPEC 6 -------------------------------------------
#
# Leido de izquierda a derecha: titulo a la izquierda, invitado al centro,
# conductor mas grande y al frente a la derecha, logo arriba a la izquierda,
# fondo detras de todo. Conductor e invitado se superponen a proposito: esa
# superposicion es parte del look del show.

SLOTS: dict[str, Slot] = {
    "fondo": Slot(role="fondo", z=0, anchor="center", x=640, y=360),
    # x=700 y no 640: a 640 el objeto invade el bloque de titulo, que termina
    # en x=620. Se ve en la primera prueba con fotos -- por eso la fase 4 se
    # hace mirando PNGs y no leyendo el SPEC.
    "objeto": Slot(
        role="objeto",
        z=1,
        anchor="center",
        x=700,
        y=286,
        max_height=200,
        max_items=2,
        shadow=True,
    ),
    # `y` cae dentro de la banda del marco: la figura se apoya en ella en vez de
    # sangrar por el borde inferior del lienzo.
    #
    # Las alturas son menores que las de SPEC 6 (600 y 680) porque aquel numero
    # asumia una foto de torso. Con un busto -- que es lo que llega de verdad --
    # 680px de "figura" es una cabeza que se come el cuadro y tapa al invitado.
    # Con estos valores el invitado pasa de aportar 9,9% de los pixeles a 11,8%,
    # y visualmente el salto es mucho mayor que ese numero.
    "invitado": Slot(role="invitado", z=2, anchor="bottom-center", x=700, y=556, height=520),
    "conductor": Slot(role="conductor", z=3, anchor="bottom-center", x=1010, y=560, height=560),
    "logo": Slot(
        role="logo",
        z=5,
        anchor="top-left",
        x=44,
        y=40,
        max_width=200,
        max_height=90,
    ),
    # El marco: un PNG 16:9 con el centro transparente que enmarca la miniatura
    # y suele traer el nombre del show. Va a sangre completa y ENCIMA de todo,
    # incluido el titulo -- es la ventana por la que se ve el resto.
    #
    # Como el logo, se pega tal cual y no pasa jamas por un modelo (SPEC 11.5).
    "marco": Slot(role="marco", z=6, anchor="center", x=640, y=360),
}

TITLE_Z = 4  # entre el conductor y el logo

# Zona util cuando hay marco: por debajo de esto, la banda con el nombre del
# show tapa lo que se dibuje. Medido sobre el marco real de "El Club de las 3
# de la Tarde": borde de 16px y banda inferior desde y=552.
SAFE_BOTTOM = 552


# --- tipografia del titulo -----------------------------------------------


@dataclass(frozen=True, slots=True)
class Typography:
    left: int = 48
    right: int = 620  # el bloque de titulo de SPEC 6: x 48 -> 620
    # SPEC 6 decia 604. Con marco, la banda con el nombre del show empieza en
    # y=552 y se comia el titulo entero. 500 deja la regla de acento en 522-531,
    # con 21px de aire sobre la banda. Alineado abajo: el titulo crece hacia
    # arriba y la regla queda siempre a la misma altura.
    bottom: int = 500
    size_max: int = 104  # el auto-ajuste empieza aqui y baja
    size_min: int = 64  # ...y no baja de aqui: por debajo no se lee en un feed
    size_step: int = 2
    max_lines: int = 3
    line_spacing: float = 0.94  # < 1: las mayusculas admiten lineas apretadas
    uppercase: bool = True

    # La regla de acento bajo el titulo (SPEC 6).
    # 14px y no 9: una miniatura se mira a ~320px de ancho en un feed, donde
    # 9px se convierten en 2 y el acento desaparece. Los tamanos se eligen para
    # como se VE la miniatura, no para como se ve el PNG a tamano completo.
    rule_width: int = 200
    rule_height: int = 14
    rule_gap: int = 22

    # Contorno oscuro: es lo que hace legible un titulo claro sobre una foto
    # cualquiera, sin tener que saber que hay detras.
    stroke_width: int = 5

    @property
    def block_width(self) -> int:
        return self.right - self.left


TYPOGRAPHY = Typography()


# --- paleta --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Palette:
    """Los colores del show.

    `gradient` es la respuesta a "no hay fondo" (SPEC 6): un degradado
    deterministico, no una imagen generada. Consistencia sobre novedad -- un
    fondo generado seria el unico elemento que cambia cada semana sin motivo.
    """

    title: tuple[int, int, int] = (255, 255, 255)
    title_stroke: tuple[int, int, int] = (12, 12, 16)
    # El rojo exacto del marco del show, muestreado de marco.png. La regla de
    # acento repite la marca en vez de competir con ella.
    accent: tuple[int, int, int] = (233, 40, 39)
    # Claro, y neutro frio. Lo de "neutro frio" viene de v2 y sigue mandando:
    # sobre cualquier cosa rojiza la regla de acento no se ve y el marco rojo
    # del show pierde fuerza, asi que el rojo tiene que ser lo unico rojo.
    # Lo de "claro" es de v4, y no es gratis: el titulo es blanco con contorno
    # oscuro, asi que sobre este degradado se lee por el CONTORNO y no por el
    # relleno. Se comprobo a 320px, que es el tamano al que se ve en un feed.
    gradient: tuple[tuple[int, int, int], tuple[int, int, int]] = (
        (238, 240, 245),
        (188, 194, 208),
    )
    shadow: tuple[int, int, int] = (0, 0, 0)


PALETTE = Palette()


# --- tratamiento del fondo (SPEC 6: "debe quedarse detras") ---------------


@dataclass(frozen=True, slots=True)
class BackgroundTreatment:
    """Desaturar + oscurecer + vineta se COMPONEN.

    Los primeros valores (0.55 y 0.75) dejaban negro cualquier fondo de estudio,
    que ya es oscuro de entrada: tres efectos suaves se multiplican en uno
    brutal. Estos numeros salen de mirar el PNG, no de razonarlo.
    """

    saturation: float = 0.35  # desaturar
    brightness: float = 0.72  # oscurecer
    blur_radius: float = 2.0
    vignette: float = 0.55  # 0 = sin vineta, 1 = bordes negros


BACKGROUND = BackgroundTreatment()


@dataclass(frozen=True, slots=True)
class Template:
    version: int = TEMPLATE_VERSION
    canvas: tuple[int, int] = CANVAS
    slots: dict[str, Slot] = field(default_factory=lambda: dict(SLOTS))
    typography: Typography = TYPOGRAPHY
    palette: Palette = PALETTE
    background: BackgroundTreatment = BACKGROUND
    title_z: int = TITLE_Z


TEMPLATE = Template()

# Los roles que el armado dibuja, en el orden en que se dibujan.
DRAW_ORDER = tuple(slot.role for slot in sorted(SLOTS.values(), key=lambda s: s.z))

# Mobiliario de marca: va en el overlay junto al titulo y NUNCA pasa por un
# modelo (SPEC 11.5). Esta division es la de SPEC 7 -- base / final -- y ahora
# tambien es lo que hace barato el preview en vivo: el titulo, el logo y el
# marco se repintan sin volver a componer lo que hay debajo, que es lo caro.
OVERLAY_ROLES = ("logo", "marco")

# Lo que forma la base, en orden de dibujo. Sale de SLOTS y no de una lista
# escrita a mano: un rol nuevo cae en el sitio que le toque sin tocar nada.
BASE_ROLES = tuple(role for role in DRAW_ORDER if role not in OVERLAY_ROLES)
