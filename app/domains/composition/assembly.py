"""El armado deterministico: mismo brief, mismos pixeles.

Produce DOS imagenes, y la separacion es la tuberia de SPEC 7:

    base   = fondo + objetos + invitado + conductor      (sin logo, sin titulo)
    final  = base + logo + titulo

El modelo de acabado, cuando exista, recibe `base` y devuelve una `base`
mejorada; entonces `reapply` vuelve a pegar logo y titulo encima a fidelidad
completa. Por eso el logo nunca se reinterpreta (SPEC 11.5) y el titulo siempre
sale nitido (SPEC 11.6): ninguno de los dos pasa jamas por el modelo.

Este modulo no sabe que existe una base de datos, un usuario ni un episodio.
Recibe rutas de archivo y un titulo. Es lo que permite responder la pregunta de
SPEC 15.1 con un script y fotos reales, sin levantar nada.
"""

import hashlib
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.domains.composition import fonts, typography
from app.domains.composition.template import (
    TEMPLATE,
    BackgroundTreatment,
    Palette,
    Slot,
    Template,
)


@dataclass(frozen=True, slots=True)
class Brief:
    """Lo que cambia cada semana: unas fotos y un titulo.

    `photos` va de rol a rutas de archivo. Nada mas: ni ids, ni filas, ni
    usuario. Un rol ausente es una entrada valida (SPEC 11.8).
    """

    title: str = ""
    photos: Mapping[str, Sequence[Path]] = field(default_factory=dict)

    def for_role(self, role: str) -> list[Path]:
        return list(self.photos.get(role, ()))


@dataclass(frozen=True, slots=True)
class Composition:
    base: bytes  # PNG sin logo ni titulo: lo que veria el modelo
    final: bytes  # PNG publicable
    template_version: int
    font: str
    title_size: int
    title_fits: bool


# --- utilidades de imagen ------------------------------------------------


def _open(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _trim_alpha(img: Image.Image) -> Image.Image:
    """Recorta el margen transparente de un recorte.

    Un recorte real trae padding arbitrario alrededor del sujeto: `che.png` viene
    con 372px transparentes a la izquierda. Sin esto, la geometria del slot mide
    el LIENZO en vez de la PERSONA, y la figura sale mas pequena de lo pedido y
    descentrada. El slot dice "680px de alto": eso es alto de persona.
    """
    bbox = img.getchannel("A").getbbox() if img.mode == "RGBA" else None
    return img.crop(bbox) if bbox else img


def _cover_fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Escala para llenar y recorta el sobrante. Nunca deforma."""
    ancho, alto = size
    escala = max(ancho / img.width, alto / img.height)
    escalada = img.resize(
        (max(1, round(img.width * escala)), max(1, round(img.height * escala))),
        Image.LANCZOS,
    )
    izquierda = (escalada.width - ancho) // 2
    arriba = (escalada.height - alto) // 2
    return escalada.crop((izquierda, arriba, izquierda + ancho, arriba + alto))


def _scale_to_height(img: Image.Image, height: int) -> Image.Image:
    escala = height / img.height
    return img.resize((max(1, round(img.width * escala)), height), Image.LANCZOS)


def _fit_within(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Escalado UNIFORME dentro de una caja. Nunca deforma (SPEC 11.5)."""
    escala = min(max_w / img.width, max_h / img.height, 1.0)
    if escala >= 1.0:
        return img
    return img.resize(
        (max(1, round(img.width * escala)), max(1, round(img.height * escala))),
        Image.LANCZOS,
    )


def _vignette_mask(size: tuple[int, int], strength: float) -> Image.Image:
    """Mascara radial, construida en pequeno y ampliada.

    Un desenfoque gaussiano de radio ~150px sobre 1280x720 cuesta cientos de
    milisegundos. Sobre 160x90 cuesta nada, y al ampliar queda igual de suave:
    una vineta no tiene detalle que perder.
    """
    ancho, alto = size
    chico = (ancho // 8, alto // 8)
    mask = Image.new("L", chico, 0)
    margen_x, margen_y = chico[0] * 0.18, chico[1] * 0.18
    ImageDraw.Draw(mask).ellipse(
        (margen_x, margen_y, chico[0] - margen_x, chico[1] - margen_y),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(chico[0] * 0.16))
    mask = mask.resize(size, Image.BICUBIC)
    if strength < 1.0:
        mask = mask.point(lambda v: int(255 - (255 - v) * strength))
    return mask


def _gradient(size: tuple[int, int], palette: Palette) -> Image.Image:
    """La respuesta a "no hay fondo" (SPEC 6).

    Deterministico, no generado: un fondo inventado por un modelo seria el unico
    elemento que cambia cada semana sin motivo, y eso es exactamente lo que el
    producto existe para evitar.
    """
    ancho, alto = size
    desde, hasta = palette.gradient
    # Se dibuja en una columna de 1px de ancho y se estira: una interpolacion
    # por fila en vez de una por pixel.
    columna = Image.new("RGB", (1, alto))
    pixeles = columna.load()
    assert pixeles is not None
    for y in range(alto):
        t = y / max(1, alto - 1)
        pixeles[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(desde, hasta, strict=True))
    return columna.resize(size, Image.BILINEAR).convert("RGBA")


def _treat_background(
    img: Image.Image, treatment: BackgroundTreatment, size: tuple[int, int]
) -> Image.Image:
    """Desatura, oscurece, desenfoca y aplica vineta: el fondo debe quedarse detras."""
    fondo = _cover_fit(img, size).convert("RGB")
    fondo = ImageEnhance.Color(fondo).enhance(treatment.saturation)
    fondo = ImageEnhance.Brightness(fondo).enhance(treatment.brightness)
    if treatment.blur_radius:
        fondo = fondo.filter(ImageFilter.GaussianBlur(treatment.blur_radius))
    if treatment.vignette:
        negro = Image.new("RGB", size, (0, 0, 0))
        fondo = Image.composite(fondo, negro, _vignette_mask(size, treatment.vignette))
    return fondo.convert("RGBA")


def _with_shadow(img: Image.Image, palette: Palette) -> Image.Image:
    """Sombra proyectada a partir del propio alfa. Devuelve una imagen mas grande."""
    desenfoque, desplazamiento = 12, 10
    margen = desenfoque * 2 + desplazamiento
    lienzo = Image.new("RGBA", (img.width + margen * 2, img.height + margen * 2), (0, 0, 0, 0))

    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    silueta = Image.new("RGBA", img.size, (*palette.shadow, 190))
    sombra.paste(silueta, (margen, margen + desplazamiento), img)
    sombra = sombra.filter(ImageFilter.GaussianBlur(desenfoque))

    lienzo.alpha_composite(sombra)
    lienzo.alpha_composite(img, (margen, margen))
    return lienzo


def _paste(canvas: Image.Image, img: Image.Image, slot: Slot, index: int = 0) -> None:
    """Pega segun el ancla del slot. `index` reparte cuando hay varios objetos."""
    if slot.anchor == "top-left":
        canvas.alpha_composite(img, (slot.x, slot.y))
        return

    x = slot.x
    if slot.max_items > 1:
        # Varios objetos se separan horizontalmente alrededor del centro del slot.
        paso = img.width + 32
        desplazamiento = (index - (slot.max_items - 1) / 2) * paso
        x = round(slot.x + desplazamiento)

    if slot.anchor == "bottom-center":
        destino = (x - img.width // 2, slot.y - img.height)
    else:  # center
        destino = (x - img.width // 2, slot.y - img.height // 2)
    canvas.alpha_composite(img, destino)


# --- el armado -----------------------------------------------------------


def _draw_base(brief: Brief, template: Template) -> Image.Image:
    canvas = Image.new("RGBA", template.canvas, (0, 0, 0, 255))

    fondos = brief.for_role("fondo")
    if fondos:
        canvas.alpha_composite(
            _treat_background(_open(fondos[0]), template.background, template.canvas)
        )
    else:
        canvas.alpha_composite(_gradient(template.canvas, template.palette))

    for role in ("objeto", "invitado", "conductor"):
        slot = template.slots[role]
        for index, path in enumerate(brief.for_role(role)[: slot.max_items]):
            # Se recorta al sujeto ANTES de escalar: el slot mide la persona.
            img = _trim_alpha(_open(path))
            if slot.height:
                img = _scale_to_height(img, slot.height)
            if slot.max_height or slot.max_width:
                img = _fit_within(
                    img, slot.max_width or template.canvas[0], slot.max_height or template.canvas[1]
                )
            if slot.shadow:
                img = _with_shadow(img, template.palette)
            _paste(canvas, img, slot, index)

    return canvas


def _draw_overlay(canvas: Image.Image, brief: Brief, template: Template):
    """Logo, titulo y marco sobre una base. Modifica `canvas` en el sitio.

    Los tres son mobiliario de marca y van en el overlay, no en la base: igual
    que el logo y el titulo, el marco no puede pasar nunca por un modelo
    (SPEC 11.5). El modelo recibe la base y nada de esto.
    """
    logos = brief.for_role("logo")
    if logos:
        slot = template.slots["logo"]
        logo = _fit_within(_open(logos[0]), slot.max_width or 200, slot.max_height or 90)
        _paste(canvas, logo, slot)

    puesto = typography.draw_title(canvas, brief.title, template.typography, template.palette)

    # El marco se dibuja el ULTIMO y a sangre completa: es la ventana por la que
    # se ve todo lo demas, asi que va por encima incluso del titulo.
    marcos = brief.for_role("marco")
    if marcos:
        canvas.alpha_composite(_cover_fit(_open(marcos[0]), template.canvas))

    return puesto


def _to_png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    # `optimize=False`: comprimir mas cuesta ~150ms y el PNG no se archiva, se
    # descarga una vez. `compress_level` fijo mantiene la salida reproducible.
    img.convert("RGB").save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def compose(brief: Brief, template: Template = TEMPLATE) -> Composition:
    """Arma la miniatura. Determinista: mismo brief, mismos bytes."""
    base = _draw_base(brief, template)
    final = base.copy()
    puesto = _draw_overlay(final, brief, template)

    return Composition(
        base=_to_png(base),
        final=_to_png(final),
        template_version=template.version,
        font=fonts.resolve().name,
        title_size=puesto.size,
        title_fits=puesto.fits,
    )


def reapply(base_png: bytes, brief: Brief, template: Template = TEMPLATE) -> bytes:
    """Vuelve a pegar logo y titulo sobre una base ya terminada (SPEC 7, paso 3).

    Es lo que hace que corregir un typo sea gratis: se vuelve a componer sobre la
    misma base, sin regenerar y sin costo.
    """
    with Image.open(io.BytesIO(base_png)) as abierta:
        canvas = abierta.convert("RGBA")
    if canvas.size != template.canvas:
        canvas = _cover_fit(canvas, template.canvas)
    _draw_overlay(canvas, brief, template)
    return _to_png(canvas)


def brief_checksum(brief: Brief, template: Template = TEMPLATE) -> str:
    """Identifica un armado sin leer un solo byte de las fotos.

    Funciona porque los archivos se direccionan por contenido: el NOMBRE de un
    archivo ya es el hash de lo que contiene (ver `intake`). Asi que hashear los
    nombres es hashear el contenido, gratis.
    """
    digest = hashlib.sha256()
    digest.update(f"v{template.version}\n".encode())
    digest.update(typography.normalize(brief.title, template.typography).encode())
    for role in sorted(brief.photos):
        nombres = sorted(Path(p).name for p in brief.photos[role])
        digest.update(f"\n{role}={','.join(nombres)}".encode())
    return digest.hexdigest()
