"""Tipografia del titulo: cortar, ajustar y dibujar.

El titulo es la unica parte del armado que no es "pegar una imagen en un sitio",
y es la que decide si la miniatura se lee en un feed. Tres reglas:

1. **Se compone, nunca se genera** (SPEC 11.6). Por eso corregir un typo es
   gratis: se vuelve a componer sin pasar por ningun modelo.
2. **El tamano se ajusta al texto, no al reves.** Se prueba de 104px hacia abajo
   hasta que el titulo cabe en el bloque. Un titulo largo se ve mas pequeno, no
   desbordado ni recortado. El episodio puede mover el TECHO desde el que se
   empieza a probar, no fijar el tamano final: bajarlo mete mas palabras en cada
   linea -- que es como se reparte de otra forma un titulo que se apilaba -- y
   subirlo deja crecer al titulo corto, al que solo frenaba el techo.
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
    words: list[str],
    typography: Typography,
    ancho: int,
    techo: int,
    apilado: bool,
    alto: int = 0,
) -> tuple[LaidOutTitle, bool]:
    """El titulo al tamano mas grande con el que cabe, y si cabio.

    Se empieza por `techo` -- el tamano que eligio el episodio, o el del
    template si no eligio ninguno -- y se baja hasta `size_min`. El techo es de
    donde se PARTE, no donde se llega: un titulo que no cabe ahi sigue bajando.

    El alto tambien manda, no solo el numero de lineas: una palabra por linea
    puede dar cinco, y cinco lineas grandes se salen del bloque por arriba. Y
    hasta donde llega "por arriba" tambien lo elige el episodio (`alto`).
    """
    regla = ImageDraw.Draw(Image.new("RGB", (1, 1)))  # 1x1: es para medir
    alto_disponible = typography.bottom - typography.techo(alto)
    maximo = typography.max_lineas(apilado, alto)

    ultimo: LaidOutTitle | None = None
    for size in range(techo, typography.size_min - 1, -typography.size_step):
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


def _directo(
    words: list[str],
    typography: Typography,
    ancho: int,
    pedido: int,
    arriba: int,
    apilado: bool,
) -> LaidOutTitle:
    """El titulo al tamano que PIDIO el episodio, repartido en su bloque.

    Aqui no hay auto-ajuste compensando: el tamano es el que se pidio y el texto
    se reparte en el ancho que hay. Menos ancho son mas lineas, no letras mas
    chicas; mas ancho son menos lineas, no letras mas grandes. Es la diferencia
    entre mover un mando y pedirle a un algoritmo que interprete lo que quisiste.

    Por eso aqui tampoco rige `max_lines`. Ese tres es una regla sobre como se
    LEE un titulo en un feed, y vale mientras el tamano lo elija el template:
    con el tamano en la mano, "tres lineas" deja de ser una regla y pasa a ser
    justo lo que impide que angostar el bloque apile las palabras.

    Lo unico que sigue mandando es el BLOQUE: si el texto no entra en su alto,
    se baja el tamano hasta que entre. Un titulo que se sale del cuadro por
    arriba no es una decision, es un titulo perdido -- y el alto tambien es un
    mando, asi que la salida de "lo quiero mas grande" es subirlo.
    """
    regla = ImageDraw.Draw(Image.new("RGB", (1, 1)))  # 1x1: es para medir
    alto_disponible = typography.bottom - arriba

    def _armar(size: int, apilar: bool) -> tuple[list[str], int, bool]:
        font = fonts.load(size)
        lines = list(words) if apilar else _wrap(regla, words, font, ancho)
        line_height = int(size * typography.line_spacing)
        return lines, line_height, line_height * len(lines) <= alto_disponible

    for size in range(pedido, typography.size_min - 1, -typography.size_step):
        lines, line_height, cabe = _armar(size, apilado)
        if cabe:
            return LaidOutTitle(
                lines=tuple(lines),
                size=size,
                line_height=line_height,
                fits=size == pedido,
                apilado=apilado,
            )

    # Ni al minimo entra en el alto. Si se pedia apilar, el corte normal suele
    # entrar: apilar es un look y ningun look justifica perder media frase.
    if apilado:
        return _directo(words, typography, ancho, pedido, arriba, apilado=False)

    # Se dibuja igual, creciendo por encima del bloque: preferimos un titulo
    # que se sale a un titulo con palabras de menos (SPEC 11.4). No se recorta
    # a `max_lines` como hace el camino automatico -- eso se come una frase.
    lines, line_height, _ = _armar(typography.size_min, False)
    return LaidOutTitle(
        lines=tuple(lines), size=typography.size_min, line_height=line_height, fits=False
    )


def layout(
    title: str,
    typography: Typography,
    ancho: int = 0,
    apilado: bool = False,
    tamano: int = 0,
    alto: int = 0,
) -> LaidOutTitle:
    """Elige el tamano mas grande con el que el titulo cabe en su bloque.

    `ancho` es el ancho del bloque, `tamano` el tamano de la letra, `alto` hasta
    donde puede crecer hacia arriba, y `apilado` si va una palabra por linea.
    Los cuatro son elecciones de la semana dentro de lo que el template permite:
    el bloque no cambia de sitio ni el titulo de tipografia.

    Hay DOS caminos, y los separa el tamano:

    - Con el tamano en cero manda el template: se prueba de `size_max` hacia
      abajo hasta que el titulo cabe en tres lineas. Es el Portada de siempre.
    - En cuanto el tamano se toca, mandan los mandos (`_directo`): el tamano es
      el que se pidio y el texto se reparte en el ancho que hay. Ahi deja de
      regir el maximo de tres lineas, que es justo lo que impedia que angostar
      el bloque apilara las palabras en vez de achicarlas.

    Son tres mandos y no uno porque hacen tres cosas: el ancho decide DONDE
    cortan las lineas, el tamano CUANTO ocupa cada palabra, y el alto CUANTAS
    lineas entran antes de que el auto-ajuste tenga que achicar. Con uno solo,
    ensanchar el bloque no repartia el texto: el hueco se lo llevaba el
    auto-ajuste subiendo el tamano, y el corte se quedaba igual.
    """
    texto = normalize(title, typography)
    if not texto:
        return LaidOutTitle(lines=(), size=typography.size_min, line_height=0, fits=True)

    words = texto.split()
    util = typography.ancho(ancho)
    techo = typography.tamano(tamano)

    # Tocar el tamano apaga el auto-ajuste: a partir de ahi mandan los mandos y
    # el texto se reparte en el bloque que dicen. En cero manda el template,
    # que es como se veia Portada antes de que existiera este mando -- y por eso
    # ningun episodio de antes cambia ni un pixel.
    if tamano:
        return _directo(words, typography, util, techo, typography.techo(alto), apilado)

    if apilado:
        puesto, cupo = _probar(words, typography, util, techo, apilado=True, alto=alto)
        if cupo:
            return puesto
        # No caben apiladas. Se vuelve al corte normal en vez de tirar palabras:
        # un look no vale media frase. `apilado` sale en False y quien pregunte
        # puede decirlo en pantalla.

    puesto, cupo = _probar(words, typography, util, techo, apilado=False, alto=alto)
    if cupo:
        return puesto

    # Ni al minimo cabe: se dibuja igual, creciendo por encima del bloque.
    # Preferimos un titulo apretado a no dibujar nada (SPEC 11.4), pero NO
    # recortado: hasta aqui se devolvia `puesto.lines[:max_lines]`, y eso con un
    # bloque estrecho se comia media frase en silencio -- seis palabras salian
    # tres. Es la regla 4 de este modulo, que valia para apilar y tiene que
    # valer para todo: ninguna forma de verse justifica perder una palabra.
    return LaidOutTitle(
        lines=puesto.lines,
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
    tamano: int = 0,
    alto: int = 0,
) -> LaidOutTitle:
    """Dibuja el titulo y su regla de acento. Modifica `canvas` en el sitio."""
    puesto = layout(title, typography, ancho, apilado, tamano, alto)
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
