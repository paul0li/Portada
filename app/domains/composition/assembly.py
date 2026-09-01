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
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.domains.composition import fonts, typography
from app.domains.composition.template import (
    BASE_ROLES,
    DEGRADADO_POR_DEFECTO,
    ROLES_MOVIBLES,
    TEMPLATE,
    BackgroundTreatment,
    Palette,
    Slot,
    Template,
)

# El preview se sirve a la mitad de lado -- un cuarto de pixeles -- y en JPEG.
# No es otra composicion: es LA composicion, reducida. Un PNG de 1280 cuesta
# ~49 ms de codificacion y ~750 KB; este JPEG cuesta ~10 ms y ~60 KB, que es la
# diferencia entre un preview que sigue al dedo y uno que llega tarde.
PREVIEW_SIZE = (640, 360)
PREVIEW_QUALITY = 82


@dataclass(frozen=True, slots=True)
class Ajuste:
    """El empujon de UN rol: cuanto se mueve y en que capa queda.

    `capa` es relativa a la del template, no absoluta: `+1` es "adelante de
    donde estabas". Asi el cero significa "como manda el template" y el dia que
    cambie el z de un slot, un episodio ajustado se mueve con el, en vez de
    quedarse clavado en un numero que ya no significa lo mismo.
    """

    dx: int = 0
    dy: int = 0
    capa: int = 0


# "Donde diga el template". Es un singleton y no un `Ajuste()` por llamada para
# poder usarlo de valor por defecto y de comparacion sin construir nada.
SIN_AJUSTE = Ajuste()


@dataclass(frozen=True, slots=True)
class Brief:
    """Lo que cambia cada semana: unas fotos, un titulo y que fondo por defecto.

    `photos` va de rol a rutas de archivo. Nada mas: ni ids, ni filas, ni
    usuario. Un rol ausente es una entrada valida (SPEC 11.8).

    `degradado` solo se ve cuando NO hay foto de fondo -- que es el caso normal.
    Es el nombre de uno de los degradados de la paleta, no un color: el template
    sigue siendo el unico sitio donde se decide como se ve el canal.
    """

    title: str = ""
    photos: Mapping[str, Sequence[Path]] = field(default_factory=dict)
    degradado: str = DEGRADADO_POR_DEFECTO
    # Rol -> empujon. Un rol ausente es "donde diga el template", que es el caso
    # normal: los ajustes son la excepcion de una semana, no el estado habitual.
    ajustes: Mapping[str, Ajuste] = field(default_factory=dict)

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


def _entre(valor: int, tope: int) -> int:
    return max(-tope, min(tope, valor))


def acotar(role: str, ajuste: Ajuste, template: Template = TEMPLATE) -> Ajuste:
    """El mismo ajuste dentro de los topes del template.

    Se acota aqui y no solo en quien lo recibe porque este modulo tiene que
    poder dibujar cualquier brief (SPEC 11.4): un numero absurdo mueve la figura
    hasta el tope y ya, nunca la saca del cuadro ni lanza.
    """
    if role not in ROLES_MOVIBLES:
        return SIN_AJUSTE
    limites = template.ajustes
    slot = template.slots[role]
    capa = min(max(slot.z + ajuste.capa, limites.capa_min), limites.capa_max)
    return Ajuste(
        dx=_entre(ajuste.dx, limites.max_x),
        dy=_entre(ajuste.dy, limites.max_y),
        capa=capa - slot.z,
    )


def ajuste_de(brief: "Brief", role: str, template: Template = TEMPLATE) -> Ajuste:
    """El ajuste EFECTIVO de un rol: el que se dibuja y el que se hashea.

    Que las dos cosas salgan de la misma funcion es lo que impide que dos briefs
    que dibujan lo mismo tengan checksums distintos -- o peor, al reves.
    """
    return acotar(role, brief.ajustes.get(role, SIN_AJUSTE), template)


def _z_efectivo(brief: "Brief", role: str, template: Template) -> int:
    return template.slots[role].z + ajuste_de(brief, role, template).capa


def _open(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


# Por debajo de esto, un pixel no es parte de la persona: es la basura que deja
# un modelo de segmentacion. Medido con rembg sobre una foto real: ~15.000
# pixeles con alfa entre 1 y 8 desperdigados por el lienzo.
UMBRAL_ALFA = 8


def _trim_alpha(img: Image.Image) -> Image.Image:
    """Recorta el margen transparente de un recorte.

    Un recorte real trae padding arbitrario alrededor del sujeto: `che.png` viene
    con 372px transparentes a la izquierda. Sin esto, la geometria del slot mide
    el LIENZO en vez de la PERSONA, y la figura sale mas pequena de lo pedido y
    descentrada. El slot dice "680px de alto": eso es alto de persona.

    Y el margen se mide con UMBRAL, no con `getbbox()` pelado, que cuenta
    cualquier alfa distinto de cero. Un recorte a mano deja ceros duros; uno
    automatico no. Con `isnet` ese ruido llegaba a las esquinas y el bbox de una
    foto real saltaba de 912 a 1200 px de ancho: el encuadre volvia a medir el
    lienzo, en silencio y sin romper ningun test. (COMPOSITION-25.)
    """
    if img.mode != "RGBA":
        return img
    solido = img.getchannel("A").point(lambda v: 255 if v > UMBRAL_ALFA else 0)
    bbox = solido.getbbox()
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


def _gradient(
    size: tuple[int, int], palette: Palette, nombre: str = DEGRADADO_POR_DEFECTO
) -> Image.Image:
    """La respuesta a "no hay fondo" (SPEC 6).

    Deterministico, no generado: un fondo inventado por un modelo seria el unico
    elemento que cambia cada semana sin motivo, y eso es exactamente lo que el
    producto existe para evitar. Que haya DOS degradados no lo cambia: los dos
    estan escritos en la paleta, y el nombre elige, no describe.
    """
    ancho, alto = size
    desde, hasta = palette.degradado(nombre)
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


def _paste(
    canvas: Image.Image,
    img: Image.Image,
    slot: Slot,
    index: int = 0,
    ajuste: Ajuste = SIN_AJUSTE,
) -> None:
    """Pega segun el ancla del slot. `index` reparte cuando hay varios objetos.

    `ajuste` empuja el punto de anclaje, no la imagen: el slot sigue decidiendo
    COMO se apoya la figura (por su base, por su centro), y el episodio solo
    mueve donde cae ese punto.
    """
    if slot.anchor == "top-left":
        canvas.alpha_composite(img, (slot.x + ajuste.dx, slot.y + ajuste.dy))
        return

    x = slot.x + ajuste.dx
    if slot.max_items > 1:
        # Varios objetos se separan horizontalmente alrededor del centro del slot.
        paso = img.width + 32
        desplazamiento = (index - (slot.max_items - 1) / 2) * paso
        x = round(x + desplazamiento)

    y = slot.y + ajuste.dy
    if slot.anchor == "bottom-center":
        destino = (x - img.width // 2, y - img.height)
    else:  # center
        destino = (x - img.width // 2, y - img.height // 2)
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
        canvas.alpha_composite(_gradient(template.canvas, template.palette, brief.degradado))

    # El orden de dibujo sale de la capa EFECTIVA, no del z del template: es lo
    # que deja que un episodio ponga al invitado delante del conductor sin tocar
    # el archivo.
    #
    # El desempate es el propio empujon, y no solo el z del template, porque el
    # z de las tres figuras va de uno en uno: con el template desempatando, un
    # toque de "atras" empataba al conductor con el invitado y NO cambiaba nada
    # -- hacian falta dos para ver algo, o sea que el primero era un boton que
    # miente. Empatados, manda quien se movio hacia adelante; y a igualdad de
    # empujon, el template. Es un orden total, asi que el armado sigue siendo
    # determinista.
    figuras = [role for role in BASE_ROLES if role != "fondo"]
    for role in sorted(
        figuras,
        key=lambda r: (
            _z_efectivo(brief, r, template),
            ajuste_de(brief, r, template).capa,
            template.slots[r].z,
        ),
    ):
        slot = template.slots[role]
        ajuste = ajuste_de(brief, role, template)
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
            _paste(canvas, img, slot, index, ajuste)

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


class CacheDeBases:
    """Las ultimas bases dibujadas, en memoria.

    Existe por una sola razon: dibujar la base cuesta ~215 ms y repintar el
    overlay cuesta ~21 ms. Sin esto, escribir el titulo con el preview delante
    recompondria el fondo, los recortes y la vineta en cada tecla.

    Es explicita y no un `@lru_cache` a proposito: asi se puede vaciar en un
    test y se puede MIRAR si hubo acierto, que es lo que hace comprobable a
    COMPOSITION-22 en vez de una intencion.

    La clave es el checksum de la base, que se calcula con los NOMBRES de los
    archivos. Funciona por lo mismo que `brief_checksum`: los medios se
    direccionan por contenido, asi que el nombre de un archivo ya es el hash de
    lo que contiene. Fuera de esa regla -- un archivo que cambia sin cambiar de
    nombre -- esta cache serviria pixeles viejos.
    """

    def __init__(self, maxsize: int = 8) -> None:
        # Una base RGBA de 1280x720 son ~3,7 MB: ocho caben de sobra en la
        # unica instancia que hay, y no hay una novena que valga la pena.
        self.maxsize = maxsize
        # Cuantas veces hubo que componer de verdad, EN TODA LA VIDA del
        # proceso: solo sube, y `clear` no lo toca. Si se reseteara, vaciar la
        # cache seria invisible para quien vigila los aciertos -- y un `clear`
        # de mas escondido en una ruta es justo el bug que hay que poder ver.
        # Quien mida, mide diferencias.
        self.dibujadas = 0
        self._entradas: OrderedDict[str, Image.Image] = OrderedDict()

    def clear(self) -> None:
        """Vacia las bases guardadas. No toca el contador (ver arriba)."""
        self._entradas.clear()

    def __len__(self) -> int:
        return len(self._entradas)

    def obtener(self, clave: str, dibujar: Callable[[], Image.Image]) -> Image.Image:
        """La base de esa clave. Devuelve una COPIA: quien la recibe la pinta."""
        guardada = self._entradas.get(clave)
        if guardada is None:
            guardada = dibujar()
            self.dibujadas += 1
            self._entradas[clave] = guardada
            while len(self._entradas) > self.maxsize:
                self._entradas.popitem(last=False)
        else:
            self._entradas.move_to_end(clave)
        return guardada.copy()


BASES = CacheDeBases()


def _to_jpeg(img: Image.Image, quality: int = PREVIEW_QUALITY) -> bytes:
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=False)
    return buffer.getvalue()


def _to_png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    # `optimize=False`: comprimir mas cuesta ~150ms y el PNG no se archiva, se
    # descarga una vez. `compress_level` fijo mantiene la salida reproducible.
    img.convert("RGB").save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def compose(brief: Brief, template: Template = TEMPLATE) -> Composition:
    """Arma la miniatura. Determinista: mismo brief, mismos bytes.

    La base sale de la cache igual que en `preview`, y por el mismo motivo: es
    lo que hace que SPEC 7 paso 3 -- "corregir una errata no cuesta una
    regeneracion" -- sea cierto tambien para el armado final, y no solo para el
    preview. Sin esto, cambiar una letra del titulo recomponia el fondo, los
    recortes y la vineta: ~215 ms para volver a dibujar exactamente lo mismo.

    Sigue siendo determinista: la cache guarda la MISMA imagen que dibujaria
    `_draw_base`, y `obtener` devuelve una copia, asi que nadie puede
    contaminarla.
    """
    base = BASES.obtener(base_checksum(brief, template), lambda: _draw_base(brief, template))
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


def preview(brief: Brief, template: Template = TEMPLATE) -> bytes:
    """La miniatura en pequeno y en JPEG, para el preview en vivo (SPEC 8.4).

    NO es otra implementacion del template: dibuja exactamente lo mismo que
    `compose` y despues lo reduce. Si fuera otra, «el layout vive en un archivo»
    dejaria de ser cierto y las dos se irian separando sin que nada fallara.

    Lo unico que cambia es lo caro: la base se reusa de la cache cuando solo
    cambio el titulo, y sale JPEG en vez de PNG.
    """
    canvas = BASES.obtener(base_checksum(brief, template), lambda: _draw_base(brief, template))
    _draw_overlay(canvas, brief, template)
    return _to_jpeg(canvas.resize(PREVIEW_SIZE, Image.LANCZOS))


def _huella_de_ajustes(digest, brief: Brief, template: Template) -> None:
    """Los ajustes que MUEVEN algo, ya acotados.

    Se hashea el efecto y no lo pedido: dos empujones desmedidos que acaban en
    el mismo tope dibujan la misma imagen, y tienen que dar el mismo checksum.
    Y un ajuste que no mueve nada no se escribe, para que pedirlo en cero sea
    indistinguible de no pedirlo -- que es lo que es.
    """
    for role in sorted(ROLES_MOVIBLES):
        ajuste = ajuste_de(brief, role, template)
        if ajuste == SIN_AJUSTE:
            continue
        digest.update(f"\najuste:{role}={ajuste.dx},{ajuste.dy},{ajuste.capa}".encode())


def _huella_de_fotos(digest, brief: Brief, roles) -> None:
    for role in sorted(roles):
        rutas = brief.photos.get(role)
        if not rutas:
            continue
        nombres = sorted(Path(p).name for p in rutas)
        digest.update(f"\n{role}={','.join(nombres)}".encode())


def base_checksum(brief: Brief, template: Template = TEMPLATE) -> str:
    """Identifica la BASE: lo que hay debajo del logo, el marco y el titulo.

    Los tres son overlay (SPEC 7), asi que cambiarlos no invalida lo de abajo.
    Ese es el motivo entero de que el preview en vivo sea barato, y es una
    propiedad que ya existia -- se construyo para que el modelo recibiera la
    base sin logo ni titulo, y resulta que sirve para lo mismo aqui.
    """
    digest = hashlib.sha256()
    digest.update(f"base:v{template.version}\n".encode())
    # El degradado SI va aqui: se dibuja debajo de todo, asi que cambiarlo
    # invalida la base. Es lo contrario del titulo, y por eso cambiar de fondo
    # cuesta una composicion entera y corregir una errata no.
    digest.update(f"degradado={brief.degradado}\n".encode())
    _huella_de_ajustes(digest, brief, template)
    _huella_de_fotos(digest, brief, BASE_ROLES)
    return digest.hexdigest()


def brief_checksum(brief: Brief, template: Template = TEMPLATE) -> str:
    """Identifica un armado sin leer un solo byte de las fotos.

    Funciona porque los archivos se direccionan por contenido: el NOMBRE de un
    archivo ya es el hash de lo que contiene (ver `intake`). Asi que hashear los
    nombres es hashear el contenido, gratis.
    """
    digest = hashlib.sha256()
    digest.update(f"v{template.version}\n".encode())
    digest.update(typography.normalize(brief.title, template.typography).encode())
    digest.update(f"\ndegradado={brief.degradado}".encode())
    _huella_de_ajustes(digest, brief, template)
    for role in sorted(brief.photos):
        nombres = sorted(Path(p).name for p in brief.photos[role])
        digest.update(f"\n{role}={','.join(nombres)}".encode())
    return digest.hexdigest()
