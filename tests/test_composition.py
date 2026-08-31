"""Criterios de `specs/composition.md`.

Ningun test de aca toca la base de datos ni HTTP: `composition` es puro, y estas
pruebas son la demostracion de que lo es.
"""

import hashlib
import io
import time

import pytest
from PIL import Image

from app.domains.composition import api as composition
from app.domains.composition import assembly, fonts, template, typography


@pytest.fixture
def fotos(tmp_path):
    """Fotos sinteticas con colores planos: se pueden comprobar por pixel."""

    def guardar(nombre, size, color, modo="RGBA"):
        ruta = tmp_path / nombre
        Image.new(modo, size, color).save(ruta)
        return ruta

    return {
        "fondo": guardar("fondo.png", (1920, 1080), (20, 80, 20, 255)),
        "conductor": guardar("conductor.png", (600, 900), (255, 0, 0, 255)),
        "invitado": guardar("invitado.png", (600, 900), (0, 0, 255, 255)),
        "objeto": guardar("objeto.png", (300, 300), (255, 255, 0, 255)),
        "logo": guardar("logo.png", (800, 200), (255, 0, 255, 255)),
    }


def _brief(fotos, title="EL RING", **roles):
    photos = {rol: [fotos[rol]] for rol in roles or ("conductor", "invitado", "logo")}
    return composition.Brief(title=title, photos=photos)


def _abrir(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGB")


# --- el armado -----------------------------------------------------------


def test_composition_01_el_mismo_brief_da_los_mismos_bytes(fotos):
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1, objeto=1)

    primera = composition.compose(brief)
    segunda = composition.compose(brief)

    assert hashlib.sha256(primera.final).hexdigest() == hashlib.sha256(segunda.final).hexdigest()
    assert primera.base == segunda.base


def test_composition_02_la_salida_es_un_png_de_1280x720(fotos):
    resultado = composition.compose(_brief(fotos))

    for png in (resultado.base, resultado.final):
        with Image.open(io.BytesIO(png)) as img:
            assert img.format == "PNG"
            assert img.size == (1280, 720)


def test_composition_03_sin_fondo_se_usa_el_degradado_de_la_paleta(fotos):
    """La ausencia es una entrada valida (SPEC 11.8), no un error."""
    resultado = composition.compose(_brief(fotos, conductor=1))
    imagen = _abrir(resultado.final)

    desde, hasta = template.PALETTE.gradient
    arriba = imagen.getpixel((20, 8))
    abajo = imagen.getpixel((20, 712))

    # Arriba se parece al primer color de la paleta, abajo al segundo.
    assert sum(abs(a - b) for a, b in zip(arriba, desde, strict=True)) < 40
    assert sum(abs(a - b) for a, b in zip(abajo, hasta, strict=True)) < 40
    assert arriba != abajo, "el degradado no degrada"


def test_composition_04_un_brief_vacio_sigue_dando_un_png_valido():
    """SPEC 11.4: el armado siempre es salida valida."""
    resultado = composition.compose(composition.Brief())

    with Image.open(io.BytesIO(resultado.final)) as img:
        assert img.size == (1280, 720)


def test_composition_05_el_conductor_va_delante_del_invitado(fotos):
    """En la zona donde ambos caen, se ve el conductor.

    Se deriva la zona de superposicion de las propias imagenes en vez de sondear
    una coordenada: asi el test sigue valiendo cuando cambien los numeros del
    template, que es justo lo que paso al ajustar la escala con fotos reales.
    """
    solo_conductor = _abrir(composition.compose(_brief(fotos, conductor=1)).base)
    solo_invitado = _abrir(composition.compose(_brief(fotos, invitado=1)).base)
    ambos = _abrir(composition.compose(_brief(fotos, conductor=1, invitado=1)).base)
    fondo = _abrir(composition.compose(composition.Brief()).base)

    superpuestos = [
        (x, y)
        for y in range(0, 720, 4)
        for x in range(0, 1280, 4)
        if solo_conductor.getpixel((x, y)) != fondo.getpixel((x, y))
        and solo_invitado.getpixel((x, y)) != fondo.getpixel((x, y))
    ]
    assert superpuestos, "el template ya no superpone conductor e invitado"

    ganados = sum(ambos.getpixel(p) == solo_conductor.getpixel(p) for p in superpuestos)
    assert ganados == len(superpuestos), (
        f"el invitado tapa al conductor en {len(superpuestos) - ganados} "
        f"de {len(superpuestos)} puntos de la superposición"
    )


# --- base / final --------------------------------------------------------


def test_composition_06_la_base_no_lleva_logo_ni_titulo(fotos):
    resultado = composition.compose(_brief(fotos, conductor=1, logo=1))
    base, final = _abrir(resultado.base), _abrir(resultado.final)

    slot = template.SLOTS["logo"]
    punto_logo = (slot.x + 10, slot.y + 10)
    assert base.getpixel(punto_logo) != final.getpixel(punto_logo), "el logo esta en la base"

    # La regla de acento del titulo: presente en final, ausente en base.
    tipo = template.TYPOGRAPHY
    punto_regla = (tipo.left + 20, tipo.bottom + tipo.rule_gap + tipo.rule_height // 2)
    assert final.getpixel(punto_regla)[:3] == tipo_acento()
    assert base.getpixel(punto_regla)[:3] != tipo_acento()


def tipo_acento():
    return template.PALETTE.accent


def test_composition_07_cambiar_el_titulo_no_toca_la_base(fotos):
    """Por eso corregir un typo es gratis: no hay nada que regenerar."""
    con_typo = composition.compose(_brief(fotos, title="EL RIGN", conductor=1, logo=1))
    corregido = composition.compose(_brief(fotos, title="EL RING", conductor=1, logo=1))

    assert con_typo.base == corregido.base
    assert con_typo.final != corregido.final


def test_composition_08_reapply_pega_logo_y_titulo_sobre_una_base(fotos):
    brief = _brief(fotos, title="EL RING", conductor=1, logo=1)
    resultado = composition.compose(brief)

    rehecho = composition.reapply(resultado.base, brief)

    assert rehecho == resultado.final, "reapply debe reproducir el final exacto"


# --- el marco ------------------------------------------------------------


def test_composition_16_el_marco_va_a_sangre_completa_encima_de_todo(fotos, tmp_path):
    """Incluido encima del titulo: es la ventana por la que se ve el resto."""
    marco = tmp_path / "marco.png"
    # Un marco opaco entero: si se dibuja encima de todo, no debe verse nada mas.
    Image.new("RGBA", (2560, 1440), (233, 40, 39, 255)).save(marco)

    brief = composition.Brief(
        title="TAPADO POR EL MARCO",
        photos={"conductor": [fotos["conductor"]], "marco": [marco]},
    )
    imagen = _abrir(composition.compose(brief).final)

    esquinas_y_centro = [(4, 4), (1276, 716), (640, 360), (100, 480)]
    for punto in esquinas_y_centro:
        assert imagen.getpixel(punto) == (233, 40, 39), (
            f"en {punto} se ve {imagen.getpixel(punto)}: el marco no quedo encima"
        )


def test_composition_17_el_marco_no_esta_en_la_base(fotos, tmp_path):
    """SPEC 11.5: como el logo y el titulo, el marco nunca pasa por el modelo."""
    marco = tmp_path / "marco.png"
    Image.new("RGBA", (2560, 1440), (233, 40, 39, 255)).save(marco)

    brief = composition.Brief(
        title="X", photos={"conductor": [fotos["conductor"]], "marco": [marco]}
    )
    resultado = composition.compose(brief)

    base = _abrir(resultado.base)
    assert base.getpixel((4, 4)) != (233, 40, 39), "el marco se colo en la base"
    # Y reapply lo vuelve a poner: la base terminada se re-enmarca igual.
    assert composition.reapply(resultado.base, brief) == resultado.final


# --- recortes ------------------------------------------------------------


def test_composition_18_un_recorte_se_escala_por_el_sujeto(tmp_path):
    """Un recorte real trae padding transparente arbitrario alrededor.

    Sin recortar al alfa primero, la geometria del slot mide el LIENZO en vez de
    la PERSONA y la figura sale mas pequena de lo pedido. Salio con fotos reales:
    una traia 372px transparentes a la izquierda.
    """
    sujeto = Image.new("RGBA", (200, 400), (255, 0, 0, 255))

    ajustado = tmp_path / "ajustado.png"
    sujeto.save(ajustado)

    # El mismo sujeto, con 600px de margen transparente alrededor.
    holgado = tmp_path / "holgado.png"
    lienzo = Image.new("RGBA", (1400, 1000), (0, 0, 0, 0))
    lienzo.paste(sujeto, (600, 300))
    lienzo.save(holgado)

    def alto_visible(path):
        imagen = _abrir(composition.compose(composition.Brief(photos={"conductor": [path]})).base)
        filas = [
            y
            for y in range(720)
            if any(imagen.getpixel((x, y))[0] > 200 for x in range(0, 1280, 4))
        ]
        return max(filas) - min(filas) if filas else 0

    assert alto_visible(ajustado) == alto_visible(holgado), (
        "el margen transparente cambio el tamano de la figura"
    )


# --- logo y titulo -------------------------------------------------------


@pytest.mark.parametrize(
    ("origen", "esperado"),
    [((800, 200), (200, 50)), ((200, 800), (22, 90)), ((100, 40), (100, 40))],
)
def test_composition_09_el_logo_nunca_se_deforma(origen, esperado):
    """SPEC 11.5: escalado uniforme o ninguno. Una imagen pequena no se agranda."""
    ajustada = assembly._fit_within(Image.new("RGBA", origen), 200, 90)

    assert ajustada.size == esperado
    proporcion_original = origen[0] / origen[1]
    proporcion_final = ajustada.size[0] / ajustada.size[1]
    assert abs(proporcion_original - proporcion_final) < 0.05


def test_composition_10_el_titulo_va_en_mayusculas():
    escrito = "la verdad sobre el caso"
    puesto = typography.layout(escrito, template.TYPOGRAPHY)

    completo = " ".join(puesto.lines)
    assert completo == escrito.upper()
    # Se afirma el texto, no donde corta: donde corta depende del tamano elegido
    # y del ancho de la tipografia, y eso lo cubre COMPOSITION-11 y 12.
    assert completo.isupper()


def test_composition_11_un_titulo_largo_se_achica_no_desborda():
    corto = typography.layout("EL RING", template.TYPOGRAPHY)
    largo = typography.layout(
        "LA VERDAD COMPLETA SOBRE EL CASO QUE NADIE QUISO CONTAR", template.TYPOGRAPHY
    )

    assert corto.size == template.TYPOGRAPHY.size_max
    assert largo.size < corto.size
    assert largo.size >= template.TYPOGRAPHY.size_min, "no baja del minimo legible"


def test_composition_12_el_corte_nunca_parte_una_palabra():
    texto = "EXTRAORDINARIAMENTE COMPLICADO PERO VERDADERO"
    puesto = typography.layout(texto, template.TYPOGRAPHY)

    palabras_originales = texto.split()
    palabras_puestas = " ".join(puesto.lines).split()
    assert palabras_puestas == palabras_originales[: len(palabras_puestas)]


def test_composition_19_el_titulo_nunca_se_pisa_con_la_regla(fotos):
    """El titulo no puede bajar de `rule_y`: ahi empieza la regla de acento.

    Se comprueba difiendo el PNG contra el mismo armado sin titulo, y no
    mirando los pixeles de la regla, porque la regla se dibuja DESPUES y tapa
    al titulo: sus pixeles son del acento aunque el titulo este debajo. Lo que
    delata la invasion es el bloque del titulo (572px) siendo mucho mas ancho
    que la regla (200px): lo que se cuela por fuera de la regla no lo tapa nada.

    Y se comprueba sobre pixeles, no sobre metricas de la fuente, porque el bug
    que motivo este test -- anclar a la ascendente en vez de a la linea base --
    pasaba cualquier test de geometria: la ascendente la elige cada tipografia
    a su gusto, y Anton la tiene 18px mas abajo que Impact.
    """
    tipo = template.TYPOGRAPHY
    regla_y = tipo.bottom + tipo.rule_gap

    def _en_la_regla(x: int, y: int) -> bool:
        return (
            tipo.left <= x <= tipo.left + tipo.rule_width
            and regla_y <= y <= regla_y + tipo.rule_height
        )

    for texto in ("NADIE LE CREYO", "LA VERDAD SOBRE EL ASADO", "SE FUE DEL PAIS Y VOLVIO"):
        con = _abrir(composition.compose(_brief(fotos, title=texto, conductor=1)).final)
        sin = _abrir(composition.compose(_brief(fotos, title="", conductor=1)).final)

        for y in range(regla_y, template.CANVAS[1]):
            for x in range(tipo.left, tipo.right):
                if _en_la_regla(x, y):
                    continue
                assert con.getpixel((x, y)) == sin.getpixel((x, y)), (
                    f"«{texto}»: el pixel ({x}, {y}) cambia al poner el titulo, y "
                    f"esta por debajo de la regla (y={regla_y}). El titulo la invade."
                )


def test_composition_20_la_tipografia_viene_del_repo():
    assert fonts.is_bundled(), (
        f"La tipografia se resolvio a {fonts.resolve()}, que es del sistema.\n"
        "Mientras no haya una en composition/typefaces/, el mismo brief da "
        "pixeles distintos en dos maquinas y el armado no es determinista."
    )


# --- identidad del armado ------------------------------------------------


def test_composition_13_el_checksum_distingue_lo_que_debe(fotos):
    base = _brief(fotos, title="EL RING", conductor=1)
    igual = _brief(fotos, title="EL RING", conductor=1)
    otro_titulo = _brief(fotos, title="OTRO", conductor=1)
    otras_fotos = _brief(fotos, title="EL RING", conductor=1, invitado=1)

    assert composition.brief_checksum(base) == composition.brief_checksum(igual)
    assert composition.brief_checksum(base) != composition.brief_checksum(otro_titulo)
    assert composition.brief_checksum(base) != composition.brief_checksum(otras_fotos)


# Sube este numero A PROPOSITO cuando cambies el template, junto con
# TEMPLATE_VERSION. El test existe para que cambiar el layout sea una decision
# consciente y no un efecto secundario.
HUELLA_DEL_TEMPLATE = "f2e031c3d254a4ca"


def test_composition_14_editar_el_template_obliga_a_subir_la_version():
    huella = hashlib.sha256(
        repr(
            (
                template.CANVAS,
                sorted(template.SLOTS.items()),
                template.TYPOGRAPHY,
                template.PALETTE,
                template.BACKGROUND,
                template.TITLE_Z,
                # La tipografia no vive en template.py pero decide cada pixel del
                # titulo: cambiarla sin subir la version deja el canal con dos
                # fuentes, porque `brief_checksum` incluye la version y el armado
                # es idempotente por ese checksum. Es como se colo el cambio a
                # Anton la primera vez. Va el nombre, no la ruta: la ruta depende
                # de la maquina.
                fonts.resolve().name,
            )
        ).encode()
    ).hexdigest()[:16]

    assert huella == HUELLA_DEL_TEMPLATE, (
        f"El template cambió (huella {huella}).\n"
        "Cambiar el layout es declarar que las miniaturas nuevas no coinciden con "
        "las viejas. Sube TEMPLATE_VERSION y actualiza HUELLA_DEL_TEMPLATE, en ese "
        "orden y a propósito."
    )
    assert template.TEMPLATE_VERSION >= 1


@pytest.mark.perf
def test_composition_15_armar_tarda_menos_de_400ms(fotos):
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1, objeto=1)
    composition.compose(brief)  # calienta la cache de tipografias

    empezo = time.perf_counter()
    composition.compose(brief)
    transcurrido = (time.perf_counter() - empezo) * 1000

    assert transcurrido < 400, f"el armado tardo {transcurrido:.0f} ms"


# --- el preview ----------------------------------------------------------


@pytest.fixture(autouse=True)
def _cache_limpia():
    """La cache de bases es estado de proceso: cada test empieza sin ella.

    Se puede vaciar a proposito y no por un decorador escondido, que es lo que
    permite que COMPOSITION-22 mire si hubo acierto en vez de suponerlo.
    """
    assembly.BASES.clear()
    yield
    assembly.BASES.clear()


def test_composition_21_el_checksum_de_la_base_ignora_el_overlay(fotos, tmp_path):
    """Logo, marco y titulo son overlay: cambiarlos no toca lo que hay debajo.

    OJO al escribir este test: comprobar que el checksum CAMBIA con las fotos
    pasa igual con el titulo colado dentro del hash. Lo que delata el bug es
    cambiar SOLO el titulo y exigir que el checksum sea identico.
    """
    marco = tmp_path / "marco.png"
    Image.new("RGBA", (1280, 720), (233, 40, 39, 120)).save(marco)

    base = composition.Brief(
        title="UNO", photos={"conductor": [fotos["conductor"]], "fondo": [fotos["fondo"]]}
    )
    otro_titulo = composition.Brief(title="OTRO TITULO DISTINTO", photos=base.photos)
    con_logo = composition.Brief(
        title="UNO",
        photos={**base.photos, "logo": [fotos["logo"]], "marco": [marco]},
    )
    otra_foto = composition.Brief(
        title="UNO", photos={**base.photos, "invitado": [fotos["invitado"]]}
    )

    assert composition.base_checksum(base) == composition.base_checksum(otro_titulo)
    assert composition.base_checksum(base) == composition.base_checksum(con_logo)
    assert composition.base_checksum(base) != composition.base_checksum(otra_foto)


def test_composition_22_cambiar_el_titulo_reusa_la_base(fotos):
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1)

    composition.preview(brief)
    dibujadas = assembly.BASES.dibujadas

    composition.preview(composition.Brief(title="OTRO TITULO", photos=brief.photos))

    assert assembly.BASES.dibujadas == dibujadas, "volvio a componer la base por un titulo"

    # Y cambiar una foto si la invalida: la cache no puede ser un agujero.
    sin_fondo = {k: v for k, v in brief.photos.items() if k != "fondo"}
    composition.preview(composition.Brief(title="OTRO TITULO", photos=sin_fondo))
    assert assembly.BASES.dibujadas == dibujadas + 1


def test_composition_23_el_preview_es_la_misma_composicion(fotos):
    """Mismo template y mismo layout: solo mas pequeno y en JPEG.

    Si el preview fuera otra implementacion, «el layout vive en un archivo»
    dejaria de ser cierto y las dos se irian separando sin que nada fallara.
    """
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1)

    chico = Image.open(io.BytesIO(composition.preview(brief)))
    grande = _abrir(composition.compose(brief).final)

    assert chico.format == "JPEG"
    assert chico.size == (640, 360)
    assert chico.size[0] / chico.size[1] == grande.size[0] / grande.size[1]

    # El mismo pixel, en la misma posicion relativa, es del mismo color. Se
    # comparan puntos planos (el conductor, el fondo) y con holgura, porque JPEG
    # y el reescalado mueven unidades.
    ampliado = chico.convert("RGB").resize(grande.size, Image.LANCZOS)
    for punto in ((1010, 500), (100, 100), (1240, 60)):
        a, b = ampliado.getpixel(punto), grande.getpixel(punto)
        assert all(abs(x - y) < 24 for x, y in zip(a, b, strict=True)), (
            f"en {punto} el preview dice {a} y el armado {b}: no es la misma composicion"
        )


@pytest.mark.perf
def test_composition_24_repintar_por_titulo_tarda_menos_de_60ms(fotos):
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1, objeto=1)
    composition.preview(brief)  # deja la base en la cache

    empezo = time.perf_counter()
    composition.preview(composition.Brief(title="UN TITULO NUEVO", photos=brief.photos))
    transcurrido = (time.perf_counter() - empezo) * 1000

    assert transcurrido < 60, f"repintar por titulo tardo {transcurrido:.0f} ms"
