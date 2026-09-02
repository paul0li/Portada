"""Tipografia del titulo: cortar, ajustar y dibujar.

El titulo es la unica parte del armado que no es "pegar una imagen en un sitio",
y es la que decide si la miniatura se lee en un feed. Tres reglas:

1. **Se compone, nunca se genera** (SPEC 11.6). Por eso corregir un typo es
   gratis: se vuelve a componer sin pasar por ningun modelo.
2. **El tamano se ajusta al texto, no al reves.** Se prueba de 104px hacia abajo
   hasta que el titulo cabe en el bloque. Un titulo largo se ve mas pequeno, no
   desbordado ni recortado.
3. **El corte respeta las palabras.** Nunca parte una palabra: prefiere bajar el
   tamano. Una palabra sola mas ancha que el bloque es el unico caso en que se
   acepta que sobresalga, porque la alternativa es no dibujarla.
4. **Nunca se pierde una palabra.** El episodio puede pedir una palabra por
   linea; si no caben, se vuelve al corte normal y se DICE. Apilar es un look,
   y ninguna forma de verse justifica tragarse media frase.
"""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from app.domains.composition import fonts
from app.domains.composition.template import Palette, Typography

MAX_TITLE_CHARS = 140


@dataclass(frozen=True, slots=True)
class LaidOutTitle:
    lines: tuple[str, ...]
    size: int
    line_height: int
    fits: bool  # False: se uso el tamano minimo y aun asi no cabia
    # Si se apilo DE VERDAD. Se pide apilar y no siempre se puede: con seis
    # palabras no caben seis lineas, y la salida es volver al corte normal, no
    # perder palabras. Quien pregunta puede decirlo en pantalla.
    apilado: bool = False


def normalize(title: str, typography: Typography) -> str:
    texto = " ".join(title.split())[:MAX_TITLE_CHARS]
    return texto.upper() if typography.uppercase else texto


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    # `textlength` mide el avance real, incluida la separacion entre caracteres;
    # `getbbox` mide la tinta y se queda corto al encadenar palabras.
    return int(draw.textlength(text, font=font))


def _wrap(
    draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont, width: int
) -> list[str]:
    """Corta por palabras. Nunca parte una."""
    lines: list[str] = []
    actual = ""
    for palabra in words:
        tentativa = f"{actual} {palabra}".strip()
        if actual and _text_width(draw, tentativa, font) > width:
            lines.append(actual)
            actual = palabra
        else:
            actual = tentativa
    if actual:
        lines.append(actual)
    return lines


def _probar(
    words: list[str], typography: Typography, ancho: int, apilado: bool
) -> tuple[LaidOutTitle, bool]:
    """El titulo al tamano mas grande con el que cabe, y si cabio.

    El alto tambien manda, no solo el numero de lineas: una palabra por linea
    puede dar cinco, y cinco lineas grandes se salen del bloque por arriba, que
    es donde esta el logo.
    """
    regla = ImageDraw.Draw(Image.new("RGB", (1, 1)))  # 1x1: es para medir
    alto_disponible = typography.bottom - typography.top
    maximo = typography.max_lineas(apilado)

    ultimo: LaidOutTitle | None = None
    for size in range(typography.size_max, typography.size_min - 1, -typography.size_step):
        font = fonts.load(size)
        lines = list(words) if apilado else _wrap(regla, words, font, ancho)
        line_height = int(size * typography.line_spacing)
        cabe = (
            len(lines) <= maximo
            and line_height * len(lines) <= alto_disponible
            and all(_text_width(regla, line, font) <= ancho for line in lines)
        )
        ultimo = LaidOutTitle(
            lines=tuple(lines),
            size=size,
            line_height=line_height,
            fits=cabe,
            apilado=apilado,
        )
        if cabe:
            return ultimo, True

    assert ultimo is not None
    return ultimo, False


def layout(
    title: str, typography: Typography, ancho: int = 0, apilado: bool = False
) -> LaidOutTitle:
    """Elige el tamano mas grande con el que el titulo cabe en su bloque.

    `ancho` es el ensanche que pidio el episodio, y `apilado` si pidio una
    palabra por linea. Los dos son elecciones de la semana dentro de lo que el
    template permite: el bloque no cambia de sitio ni el titulo de tipografia.
    """
    texto = normalize(title, typography)
    if not texto:
        return LaidOutTitle(lines=(), size=typography.size_min, line_height=0, fits=True)

    words = texto.split()
    util = typography.ancho(ancho)

    if apilado:
        puesto, cupo = _probar(words, typography, util, apilado=True)
        if cupo:
            return puesto
        # No caben apiladas. Se vuelve al corte normal en vez de tirar palabras:
        # un look no vale media frase. `apilado` sale en False y quien pregunte
        # puede decirlo en pantalla.

    puesto, cupo = _probar(words, typography, util, apilado=False)
    if cupo:
        return puesto

    # Ni al minimo cabe: se devuelve igual, recortado a las lineas permitidas.
    # Preferimos un titulo apretado a no dibujar nada (SPEC 11.4: el armado
    # siempre es salida valida).
    return LaidOutTitle(
        lines=puesto.lines[: typography.max_lines],
        size=puesto.size,
        line_height=puesto.line_height,
        fits=False,
    )


def draw_title(
    canvas: Image.Image,
    title: str,
    typography: Typography,
    palette: Palette,
    ancho: int = 0,
    apilado: bool = False,
) -> LaidOutTitle:
    """Dibuja el titulo y su regla de acento. Modifica `canvas` en el sitio."""
    puesto = layout(title, typography, ancho, apilado)
    if not puesto.lines:
        return puesto

    draw = ImageDraw.Draw(canvas)
    font = fonts.load(puesto.size)

    # Alineado abajo (SPEC 6): el titulo crece hacia arriba desde `bottom`, para
    # que la regla de acento quede siempre a la misma altura.
    #
    # Se ancla a la LINEA BASE (`ls`), no a la ascendente (`la`). La ascendente
    # es una metrica que cada tipografia elige a su gusto -- Anton la tiene en
    # 123px donde Impact la tiene en 105 -- asi que anclar a ella hace que
    # `bottom` signifique una altura distinta segun la fuente, y con Anton la
    # ultima linea se comia la regla. La linea base es la misma idea en
    # cualquier tipografia: `bottom` es donde se apoya el titulo.
    y = typography.bottom - puesto.line_height * (len(puesto.lines) - 1)

    for line in puesto.lines:
        draw.text(
            (typography.left, y),
            line,
            font=font,
            fill=palette.title,
            stroke_width=typography.stroke_width,
            stroke_fill=palette.title_stroke,
            anchor="ls",
        )
        y += puesto.line_height

    rule_y = typography.bottom + typography.rule_gap
    draw.rectangle(
        (
            typography.left,
            rule_y,
            typography.left + typography.rule_width,
            rule_y + typography.rule_height,
        ),
        fill=palette.accent,
    )
    return puesto
