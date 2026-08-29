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


def layout(title: str, typography: Typography) -> LaidOutTitle:
    """Elige el tamano mas grande con el que el titulo cabe en su bloque."""
    texto = normalize(title, typography)
    if not texto:
        return LaidOutTitle(lines=(), size=typography.size_min, line_height=0, fits=True)

    words = texto.split()
    # Un lienzo de 1x1: `ImageDraw` solo se necesita para medir, no para dibujar.
    regla = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    ultimo: LaidOutTitle | None = None
    for size in range(typography.size_max, typography.size_min - 1, -typography.size_step):
        font = fonts.load(size)
        lines = _wrap(regla, words, font, typography.block_width)
        line_height = int(size * typography.line_spacing)
        cabe = len(lines) <= typography.max_lines and all(
            _text_width(regla, line, font) <= typography.block_width for line in lines
        )
        ultimo = LaidOutTitle(lines=tuple(lines), size=size, line_height=line_height, fits=cabe)
        if cabe:
            return ultimo

    # Ni al minimo cabe: se devuelve igual, recortado a las lineas permitidas.
    # Preferimos un titulo apretado a no dibujar nada (SPEC 11.4: el armado
    # siempre es salida valida).
    assert ultimo is not None
    return LaidOutTitle(
        lines=ultimo.lines[: typography.max_lines],
        size=ultimo.size,
        line_height=ultimo.line_height,
        fits=False,
    )


def draw_title(
    canvas: Image.Image, title: str, typography: Typography, palette: Palette
) -> LaidOutTitle:
    """Dibuja el titulo y su regla de acento. Modifica `canvas` en el sitio."""
    puesto = layout(title, typography)
    if not puesto.lines:
        return puesto

    draw = ImageDraw.Draw(canvas)
    font = fonts.load(puesto.size)

    # Alineado abajo (SPEC 6): se calcula el alto total y se sube desde el borde
    # inferior del bloque, para que el titulo crezca hacia arriba y la regla de
    # acento quede siempre a la misma altura.
    alto_total = puesto.line_height * len(puesto.lines)
    y = typography.bottom - alto_total

    for line in puesto.lines:
        draw.text(
            (typography.left, y),
            line,
            font=font,
            fill=palette.title,
            stroke_width=typography.stroke_width,
            stroke_fill=palette.title_stroke,
            anchor="la",
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
