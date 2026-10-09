"""El armado deterministico: mismo brief, mismos pixeles.

Produce DOS imagenes, y la separacion es la tuberia de SPEC 7:

    base   = fondo + objetos + invitado + conductor      (sin logo, sin titulo)
    final  = base + logo + titulo

Y las dos se arman APILANDO CAPAS (ver `capas`): fondo, cada figura, logo,
titulo y marco, cada una con su sitio. El navegador recibe esas mismas capas para
mover una figura bajo el dedo, y como el armado no es mas que apilarlas, lo que
enseña el editor es lo que se descarga por construccion (COMPOSITION-42).

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
from collections import Counter, OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter

from app.domains.composition import fonts, typography
from app.domains.composition.template import (
    ALINEACION_POR_DEFECTO,
    ALINEACIONES,
    BASE_ROLES,
    DEGRADADO_POR_DEFECTO,
    ROLES_MOVIBLES,
    ROLES_VOLTEABLES,
    TEMPLATE,
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
    """Lo que un episodio le hace a UN rol: moverlo, cambiarle la capa, voltearlo.

    `capa` es relativa a la del template, no absoluta: `+1` es "adelante de
    donde estabas". Asi el cero significa "como manda el template" y el dia que
    cambie el z de un slot, un episodio ajustado se mueve con el, en vez de
    quedarse clavado en un numero que ya no significa lo mismo.

    Los volteos se llaman por el eje del movimiento que YA vive en esta clase:
    `voltear_x` voltea a lo largo de la x, igual que `dx` mueve a lo largo de la
    x -- o sea izquierda por derecha. `voltear_y`, arriba por abajo. "Eje
    horizontal" habria sido ambiguo justo aqui, que es donde no puede serlo.
    """

    dx: int = 0
    dy: int = 0
    capa: int = 0
    voltear_x: bool = False
    voltear_y: bool = False
    # Porcentaje del tamano que le da el slot. Entero y no float: viaja en una
    # URL, se guarda en SQLite y se hashea, y en los tres sitios 1.0000001 y 1.0
    # serian dos escalas distintas que dibujan lo mismo.
    escala: int = 100


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
    # Rol -> un ajuste por FIGURA, en el mismo orden que sus fotos. Un rol
    # ausente, o una lista mas corta que sus fotos, es "donde diga el template":
    # el caso normal, porque un ajuste es la excepcion de una semana.
    #
    # Por figura y no por rol porque un rol puede traer dos: dos invitados
    # comparten slot pero no comparten sitio, y moverlos juntos es no poder
    # separarlos.
    ajustes: Mapping[str, Sequence[Ajuste]] = field(default_factory=dict)
    # Como se pone el titulo: cuanto se ensancha su bloque, cuanto se mueve el
    # techo del auto-ajuste de tamano, cuanto sube el techo del bloque, y si va
    # a una palabra por linea. Todos son OVERLAY: no tocan la base, asi que
    # cambiarlos cuesta lo mismo que corregir una errata.
    #
    # Son tres campos y no uno porque hacen tres cosas: el ancho decide donde
    # cortan las lineas, el tamano cuanto ocupa cada palabra, y el alto cuantas
    # lineas entran antes de que el auto-ajuste tenga que achicar.
    titulo_ancho: int = 0
    titulo_tamano: int = 0
    titulo_alto: int = 0
    titulo_apilado: bool = False
    # Donde se movio el bloque entero del titulo (v11), en pixeles del lienzo.
    # Tambien overlay: mover el titulo no toca lo de abajo.
    titulo_x: int = 0
    titulo_y: int = 0
    # Como se alinean las lineas dentro del bloque (v13). Overlay, como todo lo
    # del titulo. Un nombre que no esta en `ALINEACIONES` se dibuja a la
    # izquierda: el armado no falla por un mando (SPEC 11.4).
    titulo_alineacion: str = ALINEACION_POR_DEFECTO

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
    # Si el titulo se apilo DE VERDAD. Se puede pedir y no caber, y entonces se
    # vuelve al corte normal en vez de perder palabras: quien pregunta tiene que
    # poder decirlo en pantalla.
    title_apilado: bool = False


# --- utilidades de imagen ------------------------------------------------


def _alto_dibujado(slot: Slot, escala: int) -> int | None:
    """El alto con el que se dibuja una figura de ese slot, sin abrir la foto.

    Solo se sabe en los slots que fijan el alto (`height`); en los demas lo
    decide la foto, y por eso esos se apoyan por el centro y no lo necesitan.
    """
    return round(slot.height * escala / 100) if slot.height else None


def acotar(
    role: str, ajuste: Ajuste, template: Template = TEMPLATE, desplazamiento: int = 0
) -> Ajuste:
    """El mismo ajuste dentro de lo que el template permite para ese rol.

    Se acota aqui y no solo en quien lo recibe porque este modulo tiene que
    poder dibujar cualquier brief (SPEC 11.4): un numero absurdo mueve la figura
    hasta el borde y ya, nunca la saca del cuadro ni lanza.

    "El borde" es que el CENTRO de la figura siga dentro del lienzo (v11). Se
    calcula con la figura que se DIBUJA -- escalada, y en el sitio que le toca en
    su grupo (`desplazamiento`) --, no con la del template: una figura al doble
    tiene el centro el doble de alto. Quien no sabe el desplazamiento (el
    borrador de una pantalla) acota sin el y deja que `ajuste_de` lo afine.

    Mover y voltear no van juntos: el `fondo` se puede voltear y no se puede
    mover, porque va a sangre completa y no hay donde. Por eso son dos listas y
    no una, y por eso lo que se cae de una no arrastra a la otra.
    """
    volteos = {
        "voltear_x": ajuste.voltear_x and role in ROLES_VOLTEABLES,
        "voltear_y": ajuste.voltear_y and role in ROLES_VOLTEABLES,
    }
    if role not in ROLES_MOVIBLES:
        return Ajuste(**volteos)
    limites = template.ajustes
    slot = template.slots[role]
    capa = min(max(slot.z + ajuste.capa, limites.capa_min), limites.capa_max)
    escala = min(max(ajuste.escala, limites.escala_min), limites.escala_max)

    ancho, alto = template.canvas
    centro_x = slot.x + desplazamiento
    centro_y = slot.y
    if slot.anchor == "bottom-center":
        centro_y -= (_alto_dibujado(slot, escala) or 0) // 2
    return Ajuste(
        dx=min(max(ajuste.dx, -centro_x), ancho - centro_x),
        dy=min(max(ajuste.dy, -centro_y), alto - centro_y),
        capa=capa - slot.z,
        escala=escala,
        **volteos,
    )


def ajuste_de(brief: "Brief", role: str, index: int = 0, template: Template = TEMPLATE) -> Ajuste:
    """El ajuste EFECTIVO de UNA figura: el que se dibuja y el que se hashea.

    Que las dos cosas salgan de la misma funcion es lo que impide que dos briefs
    que dibujan lo mismo tengan checksums distintos -- o peor, al reves.

    Una figura sin ajuste pedido -- porque el rol no trae ninguno, o porque trae
    menos que figuras -- es "donde diga el template".
    """
    pedidos = brief.ajustes.get(role, ())
    pedido = pedidos[index] if index < len(pedidos) else SIN_AJUSTE
    slot = template.slots[role]
    dibujadas = len(brief.for_role(role)[: slot.max_items])
    return acotar(role, pedido, template, reparto(slot, dibujadas, index))


def _z_efectivo(brief: "Brief", role: str, index: int, template: Template) -> int:
    return template.slots[role].z + ajuste_de(brief, role, index, template).capa


def _open(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _voltear(img: Image.Image, ajuste: Ajuste) -> Image.Image:
    """La imagen volteada segun el ajuste. Sin volteos devuelve la misma.

    Se voltea la FIGURA en su sitio, no el lienzo: dos invitados volteados
    siguen estando uno a la izquierda del otro, cada uno mirando al otro lado.
    Voltear el grupo entero seria reordenarlos, que es otra cosa y ya la hace
    elegirlos en otro orden.
    """
    if ajuste.voltear_x:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if ajuste.voltear_y:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img


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


def _fondo_de_foto(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """La foto a sangre completa, con sus colores: sin desaturar ni desenfocar (v14)."""
    return _cover_fit(img, size).convert("RGBA")


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


def reparto(slot: Slot, total: int, index: int) -> int:
    """Cuanto se aparta del slot la figura `index` de las `total` que trae.

    Se reparte por las figuras que HAY, no por las que el slot admite. Repartir
    por `max_items` deja el hueco de la foto que no vino: un slot de dos con una
    sola figura la colocaba a media separacion del centro, o sea descentrada por
    algo que no esta en el cuadro.

    Con una sola figura devuelve 0, que es "donde diga el slot": por eso un
    invitado solo se dibuja exactamente donde se dibujaba antes de que el slot
    admitiera dos.
    """
    grupo = slot.grupo
    if grupo is None or total <= 1:
        return 0
    centro = 0 if grupo.x is None else grupo.x - slot.x
    return round(centro + (index - (total - 1) / 2) * grupo.separacion)


def _destino(slot: Slot, img: Image.Image, ancla: tuple[int, int]) -> tuple[int, int]:
    """Donde cae la esquina de una imagen para que se apoye en `ancla`.

    El slot decide COMO se apoya la figura (por su base, por su centro, por su
    esquina); el episodio solo mueve el punto. Por eso escalar una figura no la
    despega del suelo: crece desde donde se apoya.
    """
    x, y = ancla
    if slot.anchor == "top-left":
        return x, y
    if slot.anchor == "bottom-center":
        return x - img.width // 2, y - img.height
    return x - img.width // 2, y - img.height // 2  # center


# --- las capas -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Capa:
    """Una imagen y su sitio en el lienzo. El armado es apilarlas en orden.

    `nombre` es `fondo`, `logo`, `titulo`, `marco`, o `rol.posicion` para una
    figura (`invitado.1`). `ancla` solo la tienen las figuras: es el punto en el
    que se apoyan, y desde el que el navegador las escala sin preguntar nada.
    """

    nombre: str
    imagen: Image.Image
    x: int
    y: int
    ancla: tuple[int, int] | None = None
    # Como se apoya en `ancla`: por la base o por el centro. Lo dice el slot, y
    # viaja con la capa para que nadie fuera de aqui tenga que leer el template.
    apoyo: str | None = None
    # El ajuste EFECTIVO de la figura o del fondo: el que se dibujo, ya acotado
    # con su sitio en el grupo. Es del que tiene que partir quien la arrastra;
    # partir del pedido daria una zona muerta junto a los bordes.
    ajuste: "Ajuste | None" = None
    # Solo el titulo: el tamano de letra con el que salio DE VERDAD. Con el
    # tamano en automatico es el que eligio el auto-ajuste, y es desde donde la
    # esquina del lienzo empieza a agrandar.
    tamano: int | None = None
    # Solo las figuras: el nombre del archivo del que salio. Como los medios se
    # direccionan por contenido, es su hash: cambia cuando cambia la foto -- por
    # ejemplo al quitarle el fondo --, y por eso sirve de version en su URL.
    fuente: str | None = None


class CacheDeImagenes:
    """Las ultimas imagenes dibujadas, en memoria.

    Existe por una sola razon: dibujar la base cuesta ~215 ms y repintar el
    overlay cuesta ~21 ms. Sin esto, escribir el titulo con el preview delante
    recompondria el fondo y los recortes en cada tecla. Y desde v11
    hay una segunda: el lienzo pide las figuras de una en una, y recortar y
    escalar una foto real es la parte cara de cada una.

    Es explicita y no un `@lru_cache` a proposito: asi se puede vaciar en un
    test y se puede MIRAR si hubo acierto, que es lo que hace comprobable a
    COMPOSITION-22 en vez de una intencion.

    Las claves se calculan con los NOMBRES de los archivos. Funciona por lo
    mismo que `brief_checksum`: los medios se direccionan por contenido, asi que
    el nombre de un archivo ya es el hash de lo que contiene. Fuera de esa regla
    -- un archivo que cambia sin cambiar de nombre -- esta cache serviria
    pixeles viejos.
    """

    def __init__(self, maxsize: int = 8) -> None:
        # Una base RGBA de 1280x720 son ~3,7 MB: ocho caben de sobra en la
        # unica instancia que hay, y no hay una novena que valga la pena.
        self.maxsize = maxsize
        # Cuantas veces hubo que dibujar de verdad, EN TODA LA VIDA del proceso:
        # solo sube, y `clear` no lo toca. Si se reseteara, vaciar la cache
        # seria invisible para quien vigila los aciertos -- y un `clear` de mas
        # escondido en una ruta es justo el bug que hay que poder ver. Quien
        # mida, mide diferencias.
        self.dibujadas = 0
        self._entradas: OrderedDict[str, Image.Image] = OrderedDict()

    def clear(self) -> None:
        """Vacia las imagenes guardadas. No toca el contador (ver arriba)."""
        self._entradas.clear()

    def __len__(self) -> int:
        return len(self._entradas)

    def obtener(self, clave: str, dibujar: Callable[[], Image.Image]) -> Image.Image:
        """La imagen de esa clave. Devuelve una COPIA: quien la recibe la pinta."""
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


# Las figuras ya recortadas, volteadas y escaladas. 32 porque una semana de
# trabajo son unas pocas fotos con unas pocas escalas, y cada una pesa menos
# que una base.
FIGURAS = CacheDeImagenes(maxsize=32)
FONDOS = CacheDeImagenes(maxsize=8)


def _dibujar_figura(path: Path, slot: Slot, ajuste: Ajuste, template: Template) -> Image.Image:
    # Se recorta al sujeto ANTES de escalar: el slot mide la persona.
    img = _trim_alpha(_voltear(_open(path), ajuste))
    if slot.height:
        # Desde la foto y no desde la figura ya escalada: una sola pasada de
        # LANCZOS, y en 100 exactamente la misma que antes de que hubiera escala.
        img = _scale_to_height(img, _alto_dibujado(slot, ajuste.escala) or slot.height)
    if slot.max_height or slot.max_width:
        img = _fit_within(
            img, slot.max_width or template.canvas[0], slot.max_height or template.canvas[1]
        )
        if ajuste.escala != 100 and not slot.height:
            # La caja del slot no amplia (SPEC 11.5: nunca deformar, y tampoco
            # inventar resolucion), asi que la escala va despues, sobre lo que
            # cupo. Es la escala de lo que el template dibujaba, que es lo que
            # el porcentaje dice.
            img = img.resize(
                (
                    max(1, round(img.width * ajuste.escala / 100)),
                    max(1, round(img.height * ajuste.escala / 100)),
                ),
                Image.LANCZOS,
            )
    if slot.shadow:
        img = _with_shadow(img, template.palette)
    return img


def figura(path: Path, role: str, ajuste: Ajuste = SIN_AJUSTE, template: Template = TEMPLATE):
    """La imagen de UNA figura como se dibuja: sin sitio, solo la imagen.

    Depende de la foto, del rol, de la escala y de los volteos -- no de donde se
    ponga --, y por eso la clave de la cache no lleva `dx` ni `dy`: arrastrar una
    figura por el lienzo no vuelve a recortar nada.
    """
    slot = template.slots[role]
    ajuste = acotar(role, ajuste, template)
    clave = (
        f"{Path(path).name}:{role}:{ajuste.escala}:{int(ajuste.voltear_x)}:{int(ajuste.voltear_y)}"
        f":v{template.version}"
    )
    return FIGURAS.obtener(clave, lambda: _dibujar_figura(Path(path), slot, ajuste, template))


def _capa_fondo(brief: Brief, template: Template) -> Capa:
    fondos = brief.for_role("fondo")
    if not fondos:
        return Capa("fondo", _gradient(template.canvas, template.palette, brief.degradado), 0, 0)
    # El fondo no se puede mover -- va a sangre completa -- pero si voltear:
    # es lo que arregla un fondo cuyo motivo cae justo detras del titulo.
    ajuste = ajuste_de(brief, "fondo", 0, template)
    clave = f"{Path(fondos[0]).name}:{int(ajuste.voltear_x)}:{int(ajuste.voltear_y)}"
    clave += f":v{template.version}"
    imagen = FONDOS.obtener(
        clave,
        lambda: _fondo_de_foto(_voltear(_open(fondos[0]), ajuste), template.canvas),
    )
    return Capa("fondo", imagen, 0, 0, ajuste=ajuste)


def _capas_figuras(brief: Brief, template: Template) -> list[Capa]:
    """Las figuras, en orden de dibujo.

    El orden sale de la capa EFECTIVA, no del z del template: es lo que deja que
    un episodio ponga al invitado delante del conductor sin tocar el archivo.

    El desempate es el propio empujon, y no solo el z del template, porque el z
    de las tres figuras va de uno en uno: con el template desempatando, un toque
    de "atras" empataba al conductor con el invitado y NO cambiaba nada -- hacian
    falta dos para ver algo, o sea que el primero era un boton que miente.
    Empatados, manda quien se movio hacia adelante; a igualdad de empujon, el
    template; y entre dos figuras del mismo rol, el orden en que se eligieron.
    Es un orden total, asi que el armado sigue siendo determinista.

    Y se ordenan FIGURAS, no roles: es lo que deja poner al segundo invitado
    delante del primero.
    """
    figuras = [
        (role, index, path)
        for role in BASE_ROLES
        if role != "fondo"
        for index, path in enumerate(brief.for_role(role)[: template.slots[role].max_items])
    ]
    cuantas = Counter(role for role, _, _ in figuras)

    capas = []
    for role, index, path in sorted(
        figuras,
        key=lambda f: (
            _z_efectivo(brief, f[0], f[1], template),
            ajuste_de(brief, f[0], f[1], template).capa,
            template.slots[f[0]].z,
            f[1],
        ),
    ):
        slot = template.slots[role]
        ajuste = ajuste_de(brief, role, index, template)
        img = figura(path, role, ajuste, template)
        ancla = (slot.x + ajuste.dx + reparto(slot, cuantas[role], index), slot.y + ajuste.dy)
        capas.append(
            Capa(
                f"{role}.{index}",
                img,
                *_destino(slot, img, ancla),
                ancla=ancla,
                apoyo=slot.anchor,
                ajuste=ajuste,
                fuente=Path(path).name,
            )
        )
    return capas


def _capa_logo(brief: Brief, template: Template) -> Capa | None:
    logos = brief.for_role("logo")
    if not logos:
        return None
    slot = template.slots["logo"]
    logo = _fit_within(_open(logos[0]), slot.max_width or 200, slot.max_height or 90)
    return Capa("logo", logo, *_destino(slot, logo, (slot.x, slot.y)))


def _capa_titulo(brief: Brief, template: Template):
    """El titulo como capa, y como se puso.

    Se dibuja en un lienzo transparente y se recorta a lo que tiene tinta: asi es
    una capa que se puede arrastrar, y no un repintado.
    """
    lienzo = Image.new("RGBA", template.canvas, (0, 0, 0, 0))
    puesto = typography.draw_title(
        lienzo,
        brief.title,
        template.typography.movida(brief.titulo_x, brief.titulo_y),
        template.palette,
        brief.titulo_ancho,
        brief.titulo_apilado,
        brief.titulo_tamano,
        brief.titulo_alto,
        brief.titulo_alineacion,
    )
    caja = lienzo.getbbox()
    capa = Capa("titulo", lienzo.crop(caja), caja[0], caja[1], tamano=puesto.size) if caja else None
    return capa, puesto


def _capa_marco(brief: Brief, template: Template) -> Capa | None:
    # El marco va el ULTIMO y a sangre completa: es la ventana por la que se ve
    # todo lo demas, asi que va por encima incluso del titulo.
    marcos = brief.for_role("marco")
    if not marcos:
        return None
    return Capa("marco", _cover_fit(_open(marcos[0]), template.canvas), 0, 0)


def _capas_overlay(brief: Brief, template: Template):
    """Logo, titulo y marco, en ese orden. Devuelve tambien como se puso el titulo.

    Los tres son mobiliario de marca y van en el overlay, no en la base: igual
    que el logo y el titulo, el marco no puede pasar nunca por un modelo
    (SPEC 11.5). El modelo recibe la base y nada de esto.
    """
    titulo, puesto = _capa_titulo(brief, template)
    capas = [_capa_logo(brief, template), titulo, _capa_marco(brief, template)]
    return [c for c in capas if c is not None], puesto


def _apilar(canvas: Image.Image, capas: Sequence[Capa]) -> Image.Image:
    for capa in capas:
        canvas.alpha_composite(capa.imagen, (capa.x, capa.y))
    return canvas


def _draw_base(brief: Brief, template: Template) -> Image.Image:
    canvas = Image.new("RGBA", template.canvas, (0, 0, 0, 255))
    return _apilar(canvas, [_capa_fondo(brief, template), *_capas_figuras(brief, template)])


def _draw_overlay(canvas: Image.Image, brief: Brief, template: Template):
    """Logo, titulo y marco sobre una base. Modifica `canvas` en el sitio."""
    capas, puesto = _capas_overlay(brief, template)
    _apilar(canvas, capas)
    return puesto


def capas(brief: Brief, template: Template = TEMPLATE) -> list[Capa]:
    """El armado sin apilar: lo que el navegador necesita para mover cosas.

    No es otra implementacion: `compose` es exactamente apilar esto, asi que lo
    que el editor ensena y lo que se descarga no pueden separarse
    (COMPOSITION-42).
    """
    overlay, _ = _capas_overlay(brief, template)
    return [_capa_fondo(brief, template), *_capas_figuras(brief, template), *overlay]


def capa(brief: Brief, nombre: str, template: Template = TEMPLATE) -> Capa | None:
    """UNA capa de `capas`, dibujando solo esa.

    Es lo que sirve el navegador imagen por imagen: pedir una figura no puede
    costar el titulo, el marco y el fondo. Un nombre que no existe en este brief
    es `None`, no un error (SPEC 11.4).
    """
    if nombre == "fondo":
        return _capa_fondo(brief, template)
    if nombre == "logo":
        return _capa_logo(brief, template)
    if nombre == "titulo":
        return _capa_titulo(brief, template)[0]
    if nombre == "marco":
        return _capa_marco(brief, template)
    return next((c for c in _capas_figuras(brief, template) if c.nombre == nombre), None)


BASES = CacheDeImagenes()


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


def entregar(capa: Capa, template: Template = TEMPLATE) -> tuple[bytes, str]:
    """Una capa como se sirve al navegador: a la escala del preview.

    A la mitad de lado por lo mismo que el preview: el lienzo se mira en un
    telefono, y a 1280 cada figura pesaria cuatro veces mas para no verse mejor.
    El fondo es opaco y a sangre completa, asi que va en JPEG; lo demas lleva
    alfa y va en PNG, con la compresion mas rapida -- se sirve, no se archiva.
    """
    factor = PREVIEW_SIZE[0] / template.canvas[0]
    img = capa.imagen.resize(
        (max(1, round(capa.imagen.width * factor)), max(1, round(capa.imagen.height * factor))),
        Image.LANCZOS,
    )
    if capa.nombre == "fondo":
        return _to_jpeg(img), "image/jpeg"
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue(), "image/png"


def compose(brief: Brief, template: Template = TEMPLATE) -> Composition:
    """Arma la miniatura. Determinista: mismo brief, mismos bytes.

    La base sale de la cache igual que en `preview`, y por el mismo motivo: es
    lo que hace que SPEC 7 paso 3 -- "corregir una errata no cuesta una
    regeneracion" -- sea cierto tambien para el armado final, y no solo para el
    preview. Sin esto, cambiar una letra del titulo recomponia el fondo, los
    recortes: ~215 ms para volver a dibujar exactamente lo mismo.

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
        title_apilado=puesto.apilado,
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
    """Los ajustes que CAMBIAN algo, ya acotados, figura por figura.

    Se hashea el efecto y no lo pedido: dos empujones desmedidos que acaban en
    el mismo tope dibujan la misma imagen, y tienen que dar el mismo checksum.
    Y un ajuste que no mueve nada no se escribe, para que pedirlo en cero sea
    indistinguible de no pedirlo -- que es lo que es.

    Por eso mismo solo cuentan las figuras que se DIBUJAN: un ajuste para un
    segundo invitado que no vino no cambia un pixel, asi que no puede cambiar el
    checksum. El error a evitar es el contrario -- hashear de menos haria reusar
    un armado que ya no corresponde -- y por eso el limite se calcula igual que
    en `_draw_base`, con `max_items` incluido.
    """
    for role in sorted(set(ROLES_MOVIBLES) | set(ROLES_VOLTEABLES)):
        dibujadas = len(brief.for_role(role)[: template.slots[role].max_items])
        for index in range(min(len(brief.ajustes.get(role, ())), dibujadas)):
            ajuste = ajuste_de(brief, role, index, template)
            if ajuste == SIN_AJUSTE:
                continue
            digest.update(
                f"\najuste:{role}.{index}={ajuste.dx},{ajuste.dy},{ajuste.capa}"
                f",{int(ajuste.voltear_x)},{int(ajuste.voltear_y)},{ajuste.escala}".encode()
            )


def _huella_de_fotos(digest, brief: Brief, roles) -> None:
    """Las fotos de esos roles, EN SU ORDEN.

    Los roles se ordenan -- son un conjunto, y da igual por cual se empiece --
    pero las fotos de un mismo rol no: la primera va a la izquierda del grupo y
    la segunda a la derecha (ver `reparto`). Ordenarlas por nombre daba el mismo
    checksum a dos briefs que dibujan cosas distintas, y con eso `build_assembly`
    devolvia el armado viejo al intercambiar dos invitados: la miniatura no
    cambiaba y nada fallaba.
    """
    for role in sorted(roles):
        rutas = brief.photos.get(role)
        if not rutas:
            continue
        nombres = [Path(p).name for p in rutas]
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
    # El ensanche y el apilado van AQUI y no en la base: como el titulo, se
    # dibujan en el overlay, asi que cambiarlos no invalida lo de abajo. Se
    # hashea el efecto -- el ensanche ya acotado -- y no lo pedido, por lo mismo
    # que los ajustes: dos peticiones que dibujan igual tienen que coincidir.
    digest.update(f"\nancho={template.typography.ensanche(brief.titulo_ancho)}".encode())
    # El techo ya resuelto, no el delta: es el numero que el auto-ajuste usa.
    digest.update(f"\ntamano={template.typography.tamano(brief.titulo_tamano)}".encode())
    digest.update(f"\nalto={template.typography.techo(brief.titulo_alto)}".encode())
    digest.update(f"\napilado={int(brief.titulo_apilado)}".encode())
    # El desplazamiento ya acotado, por lo mismo que el resto: el efecto.
    movido = template.typography.desplazamiento(brief.titulo_x, brief.titulo_y)
    digest.update(f"\nmovido={movido[0]},{movido[1]}".encode())
    # Solo si no es la de siempre: un episodio de antes de que existiera este
    # mando conserva su checksum, y con el su armado.
    if brief.titulo_alineacion in ALINEACIONES[1:]:
        digest.update(f"\nalineacion={brief.titulo_alineacion}".encode())
    digest.update(f"\ndegradado={brief.degradado}".encode())
    _huella_de_ajustes(digest, brief, template)
    _huella_de_fotos(digest, brief, brief.photos)
    return digest.hexdigest()
