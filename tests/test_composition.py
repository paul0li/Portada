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

    def asimetrica(nombre, size=(600, 900)):
        """Una figura con una marca en una esquina.

        Un color plano volteado es el mismo color plano: con las de arriba, un
        test del volteo pasaria con el volteo desconectado. La marca dice ademas
        en que direccion se volteo.
        """
        from PIL import ImageDraw

        ruta = tmp_path / nombre
        img = Image.new("RGBA", size, (0, 0, 255, 255))
        ImageDraw.Draw(img).rectangle((0, 0, size[0] // 3, size[1] // 4), fill=(255, 0, 255, 255))
        img.save(ruta)
        return ruta

    return {
        "fondo": guardar("fondo.png", (1920, 1080), (20, 80, 20, 255)),
        "conductor": guardar("conductor.png", (600, 900), (255, 0, 0, 255)),
        "invitado": guardar("invitado.png", (600, 900), (0, 0, 255, 255)),
        # El segundo invitado de la semana. Otro color para poder contestar por
        # pixel la unica pregunta que importa: si los dos se dibujaron.
        "invitado_b": guardar("invitado-b.png", (600, 900), (0, 255, 0, 255)),
        "objeto": guardar("objeto.png", (300, 300), (255, 255, 0, 255)),
        "logo": guardar("logo.png", (800, 200), (255, 0, 255, 255)),
        "asimetrica": asimetrica("asimetrica.png"),
        # En 16:9: el fondo se recorta a `cover`, y una foto vertical pierde
        # justo la esquina donde esta la marca.
        "asimetrica_ancha": asimetrica("asimetrica-ancha.png", (1920, 1080)),
    }


def _brief(fotos, title="EL SHOW", **roles):
    photos = {rol: [fotos[rol]] for rol in roles or ("conductor", "invitado", "logo")}
    return composition.Brief(title=title, photos=photos)


def _abrir(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGB")


# --- el armado -----------------------------------------------------------


def test_composition_44_la_foto_de_fondo_conserva_sus_colores(fotos):
    """Con la desaturacion de antes, el verde salia gris: (20, 80, 20) no volvia."""
    brief = composition.Brief(photos={"fondo": [fotos["fondo"]]})
    base = _abrir(composition.compose(brief).base)
    for punto in ((20, 20), (640, 360), (1260, 700)):
        assert base.getpixel(punto) == (20, 80, 20)


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

    desde, hasta = template.PALETTE.degradado()
    arriba = imagen.getpixel((20, 8))
    abajo = imagen.getpixel((20, 712))

    # Arriba se parece al primer color de la paleta, abajo al segundo.
    assert sum(abs(a - b) for a, b in zip(arriba, desde, strict=True)) < 40
    assert sum(abs(a - b) for a, b in zip(abajo, hasta, strict=True)) < 40
    assert arriba != abajo, "el degradado no degrada"


def test_composition_27_un_ajuste_mueve_la_figura_y_su_capa(fotos):
    """El template decide la posicion DE PARTIDA; el episodio, la final.

    Se comprueban las dos mitades: que el desplazamiento mueve pixeles, y que la
    capa cambia quien tapa a quien -- que es lo que COMPOSITION-05 fija al reves
    (el conductor delante del invitado) y lo que un ajuste puede invertir.
    """
    quieto = _brief(fotos, conductor=1, invitado=1)
    movido = composition.Brief(
        title=quieto.title,
        photos=quieto.photos,
        ajustes={"conductor": [composition.Ajuste(dx=-120)]},
    )
    en_cero = composition.Brief(
        title=quieto.title,
        photos=quieto.photos,
        ajustes={"conductor": [composition.Ajuste()]},
    )

    assert composition.compose(movido).final != composition.compose(quieto).final
    # Un ajuste que no mueve nada es exactamente no ajustar: mismos bytes.
    assert composition.compose(en_cero).final == composition.compose(quieto).final

    # La capa: el conductor (z=3, rojo) tapa al invitado (z=2, azul) donde se
    # superponen. UN solo toque de "atras" tiene que invertirlo -- si hicieran
    # falta dos, el primero seria un boton que no hace nada.
    encima = _abrir(composition.compose(quieto).final)
    debajo = _abrir(
        composition.compose(
            composition.Brief(
                title=quieto.title,
                photos=quieto.photos,
                ajustes={"conductor": [composition.Ajuste(capa=-1)]},
            )
        ).final
    )
    solapan = [
        (x, y)
        for x in range(760, 900, 10)
        for y in range(300, 520, 10)
        if encima.getpixel((x, y)) == (255, 0, 0) and debajo.getpixel((x, y)) == (0, 0, 255)
    ]
    assert solapan, "mandar el conductor atras no cambio quien tapa a quien"


def test_composition_28_un_ajuste_desmedido_se_acota(fotos):
    """SPEC 11.4: el armado siempre es salida valida. Un numero absurdo mueve
    hasta el borde y ya -- nunca saca la figura del cuadro ni lanza.

    "El borde" es que el CENTRO de la figura siga dentro del lienzo. No hay
    pasos ni topes fijos (v11): moverla es libre, perderla no.
    """
    limites = template.AJUSTES
    ancho, alto = template.CANVAS
    slot = template.SLOTS["conductor"]

    def _con(ajuste):
        return composition.Brief(
            photos={"conductor": [fotos["conductor"]]}, ajustes={"conductor": [ajuste]}
        )

    acotado = composition.acotar("conductor", composition.Ajuste(dx=99999, dy=-99999, capa=99))
    # El conductor se apoya por la base: su centro esta media altura por encima.
    assert slot.x + acotado.dx == ancho
    assert slot.y - slot.height // 2 + acotado.dy == 0

    desmedido = _con(composition.Ajuste(dx=99999, dy=-99999, capa=99))
    en_el_borde = _con(composition.Ajuste(dx=acotado.dx, dy=acotado.dy, capa=99))
    assert composition.compose(desmedido).final == composition.compose(en_el_borde).final

    # Ningun paso: un pixel es un movimiento valido.
    assert composition.acotar("conductor", composition.Ajuste(dx=7, dy=-3)).dx == 7

    # Escalada al doble mide 1120 de alto, asi que su centro sube con ella: el
    # borde se calcula con la figura que se DIBUJA, no con la del template.
    grande = composition.acotar("conductor", composition.Ajuste(dy=-99999, escala=200))
    assert slot.y - slot.height + grande.dy == 0

    # Y con el sitio que le toca en el grupo: el primero de dos invitados no
    # empieza donde dice el slot, asi que su borde tampoco.
    dos = composition.Brief(
        photos={"invitado": [fotos["invitado"], fotos["invitado_b"]]},
        ajustes={"invitado": [composition.Ajuste(dx=-99999)]},
    )
    invitado = template.SLOTS["invitado"]
    primero = composition.ajuste_de(dos, "invitado", 0)
    assert invitado.x + assembly.reparto(invitado, 2, 0) + primero.dx == 0

    # Y la capa no deja esconder la figura bajo el fondo ni ponerla sobre el
    # titulo: el z efectivo se queda entre los dos.
    for pedida, esperada in ((99, limites.capa_max), (-99, limites.capa_min)):
        acotado = composition.acotar("conductor", composition.Ajuste(capa=pedida))
        assert slot.z + acotado.capa == esperada

    # Un rol que no se mueve no se mueve, se pida lo que se pida.
    assert composition.acotar("marco", composition.Ajuste(dx=200)) == composition.SIN_AJUSTE
    assert composition.acotar("fondo", composition.Ajuste(escala=150)) == composition.SIN_AJUSTE


def test_composition_40_una_figura_se_puede_escalar(fotos):
    """La escala es un porcentaje del tamano que da el template, y la figura
    sigue apoyada en su punto: el conductor por la base, un objeto por el centro.
    """
    slot = template.SLOTS["conductor"]

    def _base(**ajuste):
        brief = composition.Brief(
            photos={"conductor": [fotos["conductor"]]},
            ajustes={"conductor": [composition.Ajuste(**ajuste)]},
        )
        return brief, _abrir(composition.compose(brief).base)

    quieto, normal = _base()
    _, chico = _base(escala=50)
    rojo = (255, 0, 0)

    # A la mitad mide 280: la cabeza baja, los pies se quedan donde estaban.
    cabeza_normal = slot.y - slot.height + 10
    cabeza_chica = slot.y - slot.height // 2 + 10
    assert normal.getpixel((slot.x, cabeza_normal)) == rojo
    assert chico.getpixel((slot.x, cabeza_normal)) != rojo, "escalar no achico la figura"
    assert chico.getpixel((slot.x, cabeza_chica)) == rojo
    assert chico.getpixel((slot.x, slot.y - 5)) == rojo, "achicar levanto los pies del suelo"

    # En 100 no hay ajuste: mismos bytes y mismo checksum.
    cien, _ = _base(escala=100)
    sin_ajuste = composition.Brief(photos={"conductor": [fotos["conductor"]]})
    assert composition.compose(cien).final == composition.compose(sin_ajuste).final
    assert composition.base_checksum(cien) == composition.base_checksum(sin_ajuste)

    # Escalar invalida la base: la figura esta debajo del titulo.
    escalado, _ = _base(escala=50)
    assert composition.base_checksum(escalado) != composition.base_checksum(quieto)

    # Fuera del rango se acota, no se rompe.
    limites = template.AJUSTES
    for pedida, esperada in ((9999, limites.escala_max), (1, limites.escala_min)):
        assert composition.acotar("conductor", composition.Ajuste(escala=pedida)).escala == esperada

    # Un objeto se apoya por el centro: escalado, su centro no se mueve.
    objeto = template.SLOTS["objeto"]
    amarillo = (255, 255, 0)
    con_objeto = composition.Brief(
        photos={"objeto": [fotos["objeto"]]},
        ajustes={"objeto": [composition.Ajuste(escala=150)]},
    )
    grande = _abrir(composition.compose(con_objeto).base)
    assert grande.getpixel((objeto.x, objeto.y)) == amarillo
    # A 150 mide 300: a 130 px del centro sigue siendo objeto, y a 100 no lo era.
    assert grande.getpixel((objeto.x, objeto.y - 130)) == amarillo


def test_composition_29_los_ajustes_van_en_el_checksum_de_la_base(fotos):
    """Mover invalida lo de abajo, al reves que el titulo: la figura ESTA en la
    base. Y dos briefs que dibujan lo mismo tienen que dar el mismo checksum."""
    quieto = _brief(fotos, conductor=1, invitado=1)

    def _con(ajuste):
        return composition.Brief(
            title=quieto.title, photos=quieto.photos, ajustes={"conductor": [ajuste]}
        )

    movido = _con(composition.Ajuste(dx=60))

    assert composition.base_checksum(movido) != composition.base_checksum(quieto)
    assert composition.brief_checksum(movido) != composition.brief_checksum(quieto)

    # Un ajuste nulo no es un ajuste: mismo dibujo, mismo checksum.
    assert composition.base_checksum(_con(composition.Ajuste())) == composition.base_checksum(
        quieto
    )

    # Y dos empujones desmedidos que acaban en el mismo borde tampoco se
    # distinguen: se hashea el efecto, no lo pedido.
    tope = composition.acotar("conductor", composition.Ajuste(dx=99999)).dx
    assert composition.base_checksum(_con(composition.Ajuste(dx=tope + 500))) == (
        composition.base_checksum(_con(composition.Ajuste(dx=tope)))
    )


# --- voltear una figura --------------------------------------------------


def _marca(imagen):
    """El centro de la marca magenta de la foto asimetrica, o `None`."""
    caja = _caja(imagen, (255, 0, 255))
    return None if caja is None else ((caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2)


def test_composition_33_un_ajuste_puede_voltear_la_figura(fotos):
    """Y se ve en QUE direccion se volteo, no solo que algo cambio."""

    def _brief_con(**campos):
        return composition.Brief(
            photos={"invitado": [fotos["asimetrica"]]},
            ajustes={"invitado": [composition.Ajuste(**campos)]} if campos else {},
        )

    quieto = _brief_con()
    espejo = _brief_con(voltear_x=True)
    boca_abajo = _brief_con(voltear_y=True)

    derecho = _abrir(composition.compose(quieto).final)
    volteado = _abrir(composition.compose(espejo).final)
    invertido = _abrir(composition.compose(boca_abajo).final)

    figura = _caja(derecho, (0, 0, 255))
    centro_x = (figura[0] + figura[2]) / 2
    antes, despues = _marca(derecho), _marca(volteado)

    assert antes and despues, "la marca de la figura desaparecio"
    assert antes[0] < centro_x < despues[0], "voltear en x no cambio la marca de lado"
    assert abs((centro_x - antes[0]) - (despues[0] - centro_x)) <= 6, "no es un espejo"

    # Y el otro eje es OTRO volteo, no el mismo: la marca baja en vez de cruzar.
    abajo = _marca(invertido)
    assert abajo and abajo[1] > antes[1] and abs(abajo[0] - antes[0]) <= 6

    # Con el ajuste en cero, ni un pixel: pedir no voltear es no pedir nada.
    assert composition.compose(_brief_con(dx=0)).final == composition.compose(quieto).final

    # El volteo va en el checksum de la BASE: la figura esta debajo del titulo,
    # asi que voltearla invalida lo de abajo, al reves que corregir una errata.
    assert composition.base_checksum(espejo) != composition.base_checksum(quieto)
    assert composition.base_checksum(boca_abajo) != composition.base_checksum(espejo)


def test_composition_34_la_marca_no_se_voltea_y_el_fondo_si(fotos):
    """SPEC 11.5: el logo y el marco llevan el nombre del show escrito.

    Un texto en espejo es reinterpretar la marca, que es justo lo unico que la
    regla prohibe de plano. El fondo es el caso contrario, y por eso hay DOS
    listas: se voltea aunque no se pueda mover.
    """
    for role in ("logo", "marco"):
        assert role not in template.ROLES_VOLTEABLES
        assert composition.acotar(role, composition.Ajuste(voltear_x=True)) == (
            composition.SIN_AJUSTE
        )

    con_logo = {"logo": [fotos["asimetrica"]]}
    pedido = composition.Brief(
        photos=con_logo, ajustes={"logo": [composition.Ajuste(voltear_x=True)]}
    )
    assert composition.compose(pedido).final == (
        composition.compose(composition.Brief(photos=con_logo)).final
    )

    assert "fondo" in template.ROLES_VOLTEABLES
    assert "fondo" not in template.ROLES_MOVIBLES
    fondo = {"fondo": [fotos["asimetrica_ancha"]]}
    volteado = composition.Brief(
        photos=fondo, ajustes={"fondo": [composition.Ajuste(voltear_x=True)]}
    )
    assert composition.compose(volteado).final != (
        composition.compose(composition.Brief(photos=fondo)).final
    )
    # Y pedirle al fondo un empujon no lo mueve: no hay donde.
    empujado = composition.Brief(photos=fondo, ajustes={"fondo": [composition.Ajuste(dx=200)]})
    assert composition.compose(empujado).final == (
        composition.compose(composition.Brief(photos=fondo)).final
    )


# --- cuando el invitado no es uno ----------------------------------------


def _caja(imagen, color, tolerancia=30):
    """La caja de los pixeles de ese color. `None` si no hay ninguno."""
    ancho, alto = imagen.size
    puntos = [
        (x, y)
        for x in range(0, ancho, 2)
        for y in range(0, alto, 4)
        if sum(abs(a - b) for a, b in zip(imagen.getpixel((x, y)), color, strict=True)) < tolerancia
    ]
    if not puntos:
        return None
    xs = [x for x, _ in puntos]
    ys = [y for _, y in puntos]
    return min(xs), min(ys), max(xs), max(ys)


def test_composition_30_un_slot_se_reparte_por_las_figuras_que_trae(fotos):
    """Con una sola figura no hay nada que repartir.

    Repartir por `max_items` -- que es lo que se hacia -- dejaba el hueco de la
    foto que NO vino: un objeto solo se colocaba a media separacion del centro
    del slot, descentrado por algo que no esta en el cuadro.
    """
    slot = template.SLOTS["objeto"]
    assert slot.max_items > 1 and slot.grupo, "este test necesita un slot de varios"

    uno = _abrir(composition.compose(_brief(fotos, objeto=1)).final)
    izquierda, _, derecha, _ = _caja(uno, (255, 255, 0))

    assert abs((izquierda + derecha) // 2 - slot.x) <= 4, (
        "un objeto solo no cae en el centro de su slot"
    )

    # Y con dos, el grupo sigue centrado ahi, con la separacion del template.
    dos = _abrir(
        composition.compose(
            composition.Brief(photos={"objeto": [fotos["objeto"], fotos["invitado_b"]]})
        ).final
    )
    amarillo = _caja(dos, (255, 255, 0))
    verde = _caja(dos, (0, 255, 0))
    assert amarillo and verde, "con dos objetos no se dibujaron los dos"
    # Por sus CENTROS y no por sus bordes: los dos objetos tienen aspectos
    # distintos, y lo que el template separa es donde cae cada uno, no cuanto
    # mide. Es la misma razon por la que la separacion esta en pixeles del
    # lienzo y no en anchos de imagen.
    centros = [(caja[0] + caja[2]) / 2 for caja in (amarillo, verde)]
    assert abs((centros[1] - centros[0]) - slot.grupo.separacion) <= 4
    assert abs(sum(centros) / 2 - slot.x) <= 4, "el grupo no quedo centrado en el slot"


def test_composition_31_el_invitado_puede_ser_mas_de_uno(fotos):
    """Dos invitados se dibujan los DOS, y dentro del cuadro."""
    slot = template.SLOTS["invitado"]
    assert slot.max_items >= 2, "el template ya no admite dos invitados"

    dos = _abrir(
        composition.compose(
            composition.Brief(
                title="EL SHOW",
                photos={"invitado": [fotos["invitado"], fotos["invitado_b"]]},
            )
        ).final
    )
    azul = _caja(dos, (0, 0, 255))
    verde = _caja(dos, (0, 255, 0))

    assert azul and verde, "el segundo invitado no se dibujo"
    # El primero queda a la izquierda del segundo, a la distancia que dice el
    # template. Se comparan los bordes IZQUIERDOS: el del primero es el unico
    # que no puede taparlo el segundo, que se dibuja encima y a su derecha.
    assert abs((verde[0] - azul[0]) - slot.grupo.separacion) <= 4
    assert azul[0] >= 0 and verde[2] < template.CANVAS[0], "un invitado se salio del cuadro"


def test_composition_35_cada_figura_lleva_su_ajuste(fotos):
    """Dos invitados comparten slot y no comparten sitio.

    Mientras el ajuste fue del ROL, moverlos juntos era lo único posible: el
    empujón que arreglaba a uno se llevaba al otro por delante.
    """
    photos = {"invitado": [fotos["invitado"], fotos["invitado_b"]]}
    quieto = _abrir(composition.compose(composition.Brief(photos=photos)).final)
    solo_el_segundo = _abrir(
        composition.compose(
            composition.Brief(
                photos=photos,
                ajustes={"invitado": [composition.SIN_AJUSTE, composition.Ajuste(dx=120)]},
            )
        ).final
    )

    # Los bordes IZQUIERDOS: el del primero es el único que el segundo no puede
    # tapar, y el del segundo se mueve exactamente lo que se pidió.
    assert _caja(solo_el_segundo, (0, 0, 255))[0] == _caja(quieto, (0, 0, 255))[0], (
        "mover al segundo invitado movió al primero"
    )
    assert _caja(solo_el_segundo, (0, 255, 0))[0] - _caja(quieto, (0, 255, 0))[0] == 120

    # Y la capa también es de cada figura: el primero puede pasar al frente del
    # segundo, que es lo que el orden por rol no sabía decir.
    delante = _abrir(
        composition.compose(
            composition.Brief(photos=photos, ajustes={"invitado": [composition.Ajuste(capa=1)]})
        ).final
    )
    solapan = [
        (x, y)
        for x in range(580, 660, 10)
        for y in range(200, 500, 20)
        if quieto.getpixel((x, y)) == (0, 255, 0) and delante.getpixel((x, y)) == (0, 0, 255)
    ]
    assert solapan, "adelantar al primer invitado no cambió quién tapa a quién"


def test_composition_32_el_orden_dentro_de_un_rol_cambia_el_checksum(fotos):
    """El orden es parte del brief, asi que tiene que estar en el checksum.

    Hashear los nombres ORDENADOS daba el mismo checksum a dos miniaturas
    distintas. Con eso, intercambiar los dos invitados de un episodio devolvia
    el armado viejo -- misma clave de cache, misma fila -- y la miniatura no
    cambiaba, sin que fallara nada.
    """
    ab = composition.Brief(photos={"invitado": [fotos["invitado"], fotos["invitado_b"]]})
    ba = composition.Brief(photos={"invitado": [fotos["invitado_b"], fotos["invitado"]]})

    assert composition.compose(ab).final != composition.compose(ba).final
    assert composition.brief_checksum(ab) != composition.brief_checksum(ba)
    assert composition.base_checksum(ab) != composition.base_checksum(ba)


def test_composition_26_el_brief_elige_el_degradado_por_defecto(fotos):
    """Claro u oscuro: dos constantes de la paleta, no una perilla libre.

    Se comprueban las tres cosas del criterio -- que los pixeles cambian, que la
    BASE cambia (el degradado va debajo de todo, al reves que el titulo) y que
    un nombre inventado no rompe el armado.
    """
    claro = composition.Brief(photos={}, degradado="claro")
    oscuro = composition.Brief(photos={}, degradado="oscuro")

    arriba_claro = _abrir(composition.compose(claro).final).getpixel((20, 8))
    arriba_oscuro = _abrir(composition.compose(oscuro).final).getpixel((20, 8))

    assert sum(arriba_claro) > sum(arriba_oscuro) + 200, "el fondo oscuro no salio oscuro"
    for pedido, esperado in (("claro", arriba_claro), ("oscuro", arriba_oscuro)):
        desde, _ = template.PALETTE.degradado(pedido)
        assert sum(abs(a - b) for a, b in zip(esperado, desde, strict=True)) < 40

    # El degradado se dibuja DEBAJO de todo, asi que invalida la base: es lo
    # contrario del titulo, y por eso cambiar de fondo cuesta una composicion.
    assert composition.base_checksum(claro) != composition.base_checksum(oscuro)
    assert composition.brief_checksum(claro) != composition.brief_checksum(oscuro)

    # SPEC 11.4: abajo, un nombre raro no lanza -- cae en el por defecto. Quien
    # rechaza un nombre invalido es la puerta de entrada (EPISODES-17).
    inventado = composition.Brief(photos={}, degradado="fucsia")
    assert composition.compose(inventado).final == composition.compose(claro).final


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


# --- como se pone el titulo ----------------------------------------------


LARGO = "LA VERDAD SOBRE EL CASO"


def test_composition_36_el_titulo_puede_ensancharse(fotos):
    """Más ancho, menos líneas. Y ensanchar cuesta lo que corregir una errata."""
    tipografia = template.TYPOGRAPHY
    estrecho = typography.layout(LARGO, tipografia)
    ancho = typography.layout(LARGO, tipografia, tipografia.ancho_mas)

    # Que entren más palabras en la primera línea ES lo que «se apilan menos»
    # quiere decir. Contar líneas no serviría: con el bloque ancho un título de
    # dos líneas sigue siendo de dos, solo que cortadas mucho más tarde.
    assert len(ancho.lines[0].split()) > len(estrecho.lines[0].split()), (
        "ensanchar no cambió el corte"
    )
    assert len(ancho.lines) <= len(estrecho.lines)

    def _con(**campos):
        return composition.Brief(title=LARGO, photos={"conductor": [fotos["conductor"]]}, **campos)

    quieto, ensanchado = _con(), _con(titulo_ancho=tipografia.ancho_mas)
    assert composition.compose(ensanchado).final != composition.compose(quieto).final
    # Es OVERLAY: la base no se entera, así que no hay que volver a componerla.
    assert composition.base_checksum(ensanchado) == composition.base_checksum(quieto)
    assert composition.brief_checksum(ensanchado) != composition.brief_checksum(quieto)

    # Un ensanche desmedido se acota, no rompe: es la regla de los empujones.
    assert composition.brief_checksum(_con(titulo_ancho=99999)) == (
        composition.brief_checksum(ensanchado)
    )


# El titulo con el que se vio el problema: a cualquier ancho entre -120 y +160
# se cortaba en las MISMAS tres lineas, y lo unico que cambiaba era el tamano
# (74 -> 94 -> 104). Ensanchar no repartia el texto: lo agrandaba.
APRETADO = "NADIE ESPERABA ESTA RESPUESTA DEL INVITADO"
# Y uno corto, al que no lo frena el bloque sino el techo: una sola línea de
# 99px en un bloque de 350. Es el que demuestra que subir el techo hace algo.
CORTO = "NADIE LO VIO"


def test_composition_38_con_el_tamano_puesto_mandan_los_mandos(fotos):
    """Tocar el tamaño le pasa el mando al episodio: ese es el tamaño."""
    tipografia = template.TYPOGRAPHY

    def _puesto(**campos):
        return typography.layout(APRETADO, tipografia, **campos)

    # El síntoma, que es lo que se separa: con el tamaño en cero manda el
    # template, y ensanchar el bloque no cambia el corte — sube el tamaño y el
    # título se parte en las MISMAS líneas, más grande. Se comprueba para que la
    # diferencia con el modo directo signifique algo.
    assert _puesto(ancho=160).lines == _puesto().lines
    assert _puesto(ancho=160).size > _puesto().size

    # En cuanto se toca el tamaño, ese es el tamaño. Al píxel.
    chico = -16
    ancho_libre = {"alto": tipografia.alto_mas}
    normal = _puesto(tamano=chico, **ancho_libre)
    assert normal.size == tipografia.tamano(chico)

    # Y entonces angostar APILA en vez de achicar, que es todo el punto: el
    # ancho reparte las palabras y el tamaño no compensa por detrás.
    angosto = _puesto(ancho=-tipografia.ancho_menos, tamano=chico, **ancho_libre)
    assert len(angosto.lines) > len(normal.lines), "angostar no repartió el texto"
    assert normal.size - angosto.size <= tipografia.size_step, "angostar achicó la letra"

    # Ensanchar hace lo contrario, y tampoco toca el tamaño.
    ancho = _puesto(ancho=tipografia.ancho_mas, tamano=chico, **ancho_libre)
    assert len(ancho.lines) < len(normal.lines)
    assert ancho.size == normal.size

    # Nunca se pierde una palabra, por ningún camino: ni apilando seis líneas en
    # un bloque de 212px ni cayéndose del modo directo.
    entero = typography.normalize(APRETADO, tipografia)
    assert " ".join(angosto.lines) == entero
    assert " ".join(_puesto(ancho=-tipografia.ancho_menos).lines) == entero

    # Hacia arriba también: a un título corto solo lo frena el techo. CORTO sale
    # a 104 px en una línea de 99 dentro de un bloque de 350 — el alto sobra.
    corto = typography.layout(CORTO, tipografia)
    assert corto.size == tipografia.size_max
    assert corto.line_height * len(corto.lines) < tipografia.bottom - tipografia.top
    grande = typography.layout(CORTO, tipografia, tamano=tipografia.tamano_mas, **ancho_libre)
    assert grande.size == tipografia.tamano(tipografia.tamano_mas)

    # Lo único que sigue cediendo es lo físico: un tamaño que no entra ni con
    # todo el lienzo baja hasta que entra, en vez de salirse del cuadro.
    apretado = _puesto(tamano=tipografia.tamano_mas)
    assert apretado.size < tipografia.tamano(tipografia.tamano_mas)
    assert " ".join(apretado.lines) == entero

    def _con(**campos):
        return composition.Brief(
            title=APRETADO, photos={"conductor": [fotos["conductor"]]}, **campos
        )

    quieto, achicado = _con(), _con(titulo_tamano=chico)
    assert composition.compose(achicado).final != composition.compose(quieto).final
    # Overlay, como el ensanche: la base no se entera.
    assert composition.base_checksum(achicado) == composition.base_checksum(quieto)
    assert composition.brief_checksum(achicado) != composition.brief_checksum(quieto)
    # Un tamaño desmedido se acota, no rompe.
    assert composition.brief_checksum(_con(titulo_tamano=-99999)) == (
        composition.brief_checksum(_con(titulo_tamano=-tipografia.tamano_menos))
    )


def test_composition_41_el_titulo_se_puede_mover(fotos):
    """El bloque entero se mueve: texto, techo y regla. Ni el corte ni el tamano
    cambian, y la base tampoco -- el titulo es overlay."""
    tipografia = template.TYPOGRAPHY
    acento = template.PALETTE.accent
    quieto = _brief(fotos, title="NADIE LO VIO VENIR", conductor=1)

    def _movido(dx, dy):
        return composition.Brief(title=quieto.title, photos=quieto.photos, titulo_x=dx, titulo_y=dy)

    movido = _movido(400, -200)
    antes, despues = composition.compose(quieto), composition.compose(movido)

    regla = (tipografia.left + 20, tipografia.bottom + tipografia.rule_gap + 5)
    assert _abrir(antes.final).getpixel(regla) == acento
    assert _abrir(despues.final).getpixel((regla[0] + 400, regla[1] - 200)) == acento
    assert _abrir(despues.final).getpixel(regla) != acento, "la regla se quedo donde estaba"

    # Mismo corte, mismo tamano: mover no es reinterpretar.
    assert despues.title_size == antes.title_size
    assert typography.layout(quieto.title, tipografia.movida(400, -200)) == typography.layout(
        quieto.title, tipografia
    )

    # Overlay: no toca la base, si el armado.
    assert composition.base_checksum(movido) == composition.base_checksum(quieto)
    assert composition.brief_checksum(movido) != composition.brief_checksum(quieto)

    # Desmedido se acota: el bloque no se va del lienzo.
    tope = tipografia.desplazamiento(99999, 99999)
    assert tipografia.left + tope[0] + tipografia.rule_width == template.CANVAS[0]
    regla_abajo = tipografia.bottom + tope[1] + tipografia.rule_gap + tipografia.rule_height
    assert regla_abajo == template.CANVAS[1]
    assert composition.compose(_movido(99999, 99999)).final == (
        composition.compose(_movido(*tope)).final
    )
    assert tipografia.desplazamiento(-99999, 0)[0] == -tipografia.left


def test_composition_39_el_bloque_del_titulo_puede_ser_mas_alto(fotos):
    """El techo sube y baja; el título sigue apoyado donde dice el template."""
    tipografia = template.TYPOGRAPHY

    # Subir el techo es subirlo de verdad, y bajarlo, bajarlo.
    assert tipografia.techo(tipografia.alto_mas) < tipografia.top
    assert tipografia.techo(-tipografia.alto_menos) > tipografia.top

    # Donde más se ve es apilando: SEIS palabras no caben en el bloque de
    # siempre —ni al tamaño mínimo entran seis líneas— y se vuelve al corte
    # normal sin perder ninguna (COMPOSITION-37). Con el techo arriba, caben.
    seis = "UNO DOS TRES CUATRO CINCO SEIS"
    assert typography.layout(seis, tipografia, apilado=True).apilado is False
    subido = typography.layout(seis, tipografia, apilado=True, alto=tipografia.alto_mas)
    assert subido.apilado is True
    assert subido.lines == tuple(seis.split())

    # Y bajarlo aprieta: el bloque tiene menos alto, así que el auto-ajuste
    # responde achicando. El título no se mueve de donde se apoya.
    apretado = typography.layout(APRETADO, tipografia, alto=-tipografia.alto_menos)
    assert apretado.size < typography.layout(APRETADO, tipografia).size

    def _con(**campos):
        return composition.Brief(
            title=seis, photos={"conductor": [fotos["conductor"]]}, titulo_apilado=True, **campos
        )

    quieto, alto = _con(), _con(titulo_alto=tipografia.alto_mas)
    assert composition.compose(alto).final != composition.compose(quieto).final
    # Overlay, como los otros dos mandos del título.
    assert composition.base_checksum(alto) == composition.base_checksum(quieto)
    assert composition.brief_checksum(alto) != composition.brief_checksum(quieto)
    assert composition.brief_checksum(_con(titulo_alto=99999)) == composition.brief_checksum(alto)


def test_composition_37_el_titulo_puede_ir_una_palabra_por_linea():
    """Y si no caben, se vuelve al corte normal SIN perder una palabra."""
    tipografia = template.TYPOGRAPHY

    apilado = typography.layout("NADIE LO VIO", tipografia, apilado=True)
    assert apilado.apilado is True
    assert apilado.lines == ("NADIE", "LO", "VIO")

    # Ocho palabras no caben apiladas: ni al tamaño mínimo entran ocho líneas
    # entre el logo y la regla de acento.
    demasiadas = "UNO DOS TRES CUATRO CINCO SEIS SIETE OCHO"
    caido = typography.layout(demasiadas, tipografia, apilado=True)

    assert caido.apilado is False, "dijo que apiló y no apiló"
    assert " ".join(caido.lines) == demasiadas, "se perdió una palabra por un look"


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
    corregido = composition.compose(_brief(fotos, title="EL SHOW", conductor=1, logo=1))

    assert con_typo.base == corregido.base
    assert con_typo.final != corregido.final


def test_composition_08_reapply_pega_logo_y_titulo_sobre_una_base(fotos):
    brief = _brief(fotos, title="EL SHOW", conductor=1, logo=1)
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


def test_composition_25_el_encuadre_ignora_el_alfa_residual(tmp_path):
    """Un recorte automatico no deja ceros duros: deja alfa 1..8 desperdigado.

    Medido con rembg sobre una foto real: unos 15.000 pixeles casi transparentes,
    y con el modelo `isnet` llegaban hasta el borde del lienzo. `getbbox()` cuenta
    cualquier alfa distinto de cero, asi que el encuadre pasaba a medir el LIENZO:
    el bbox saltaba de 912 a 1200 px de ancho. La figura sale mas chica y
    descentrada, sin romper nada y sin avisar. Es COMPOSITION-18 otra vez, pero
    con la causa al reves: no es padding, es ruido subumbral.
    """
    sujeto = Image.new("RGBA", (200, 400), (255, 0, 0, 255))

    limpio = tmp_path / "limpio.png"
    lienzo = Image.new("RGBA", (1400, 1000), (0, 0, 0, 0))
    lienzo.paste(sujeto, (600, 300))
    lienzo.save(limpio)

    # El mismo recorte, con la basura que deja un modelo de verdad: un pixel
    # casi transparente en cada esquina.
    con_ruido = tmp_path / "con-ruido.png"
    sucio = lienzo.copy()
    for xy in ((0, 0), (1399, 0), (0, 999), (1399, 999)):
        sucio.putpixel(xy, (120, 120, 120, 3))
    sucio.save(con_ruido)

    def alto_visible(path):
        imagen = _abrir(composition.compose(composition.Brief(photos={"conductor": [path]})).base)
        filas = [
            y
            for y in range(720)
            if any(imagen.getpixel((x, y))[0] > 200 for x in range(0, 1280, 4))
        ]
        return max(filas) - min(filas) if filas else 0

    assert alto_visible(con_ruido) == alto_visible(limpio), (
        "el alfa residual encuadro por el lienzo en vez de por la persona"
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
    corto = typography.layout("EL SHOW", template.TYPOGRAPHY)
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
    base = _brief(fotos, title="EL SHOW", conductor=1)
    igual = _brief(fotos, title="EL SHOW", conductor=1)
    otro_titulo = _brief(fotos, title="OTRO", conductor=1)
    otras_fotos = _brief(fotos, title="EL SHOW", conductor=1, invitado=1)

    assert composition.brief_checksum(base) == composition.brief_checksum(igual)
    assert composition.brief_checksum(base) != composition.brief_checksum(otro_titulo)
    assert composition.brief_checksum(base) != composition.brief_checksum(otras_fotos)


# Sube este numero A PROPOSITO cuando cambies el template, junto con
# TEMPLATE_VERSION. El test existe para que cambiar el layout sea una decision
# consciente y no un efecto secundario.
HUELLA_DEL_TEMPLATE = "847a2540fa75e4a0"


def test_composition_14_editar_el_template_obliga_a_subir_la_version():
    huella = hashlib.sha256(
        repr(
            (
                template.CANVAS,
                sorted(template.SLOTS.items()),
                template.TYPOGRAPHY,
                template.PALETTE,
                template.TITLE_Z,
                # Cuanto es un empujon y hasta donde llega: son numeros de
                # layout como los demas, y cambiarlos mueve los pixeles de
                # cualquier episodio que use un ajuste.
                template.AJUSTES,
                template.ROLES_MOVIBLES,
                # Que roles se pueden voltear es una decision del template como
                # las demas: quitarle el volteo a un rol cambia los pixeles de
                # cualquier episodio que lo usara, en silencio.
                template.ROLES_VOLTEABLES,
                # Que alineaciones del titulo existen: quitar una cambia los
                # pixeles de cualquier episodio que la usara (v13).
                template.ALINEACIONES,
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
def test_composition_42_las_capas_apiladas_son_el_armado(fotos, tmp_path):
    """El navegador apila; no compone. Si apilar las capas donde dicen no diera
    la miniatura final, el editor ensenaria una que no es la que se descarga."""
    from PIL import ImageDraw

    marco = Image.new("RGBA", (1280, 720), (233, 40, 39, 255))
    ImageDraw.Draw(marco).rectangle((16, 16, 1263, 551), fill=(0, 0, 0, 0))
    marco.save(tmp_path / "marco.png")

    brief = composition.Brief(
        title="LAS CAPAS NO MIENTEN",
        photos={
            "fondo": [fotos["fondo"]],
            "conductor": [fotos["conductor"]],
            "invitado": [fotos["invitado"], fotos["asimetrica"]],
            "objeto": [fotos["objeto"]],
            "logo": [fotos["logo"]],
            "marco": [tmp_path / "marco.png"],
        },
        ajustes={
            "conductor": [composition.Ajuste(dx=-333, dy=41, escala=73, capa=-1)],
            "invitado": [composition.SIN_AJUSTE, composition.Ajuste(voltear_x=True, escala=131)],
            "objeto": [composition.Ajuste(dx=9999, escala=170)],
        },
        titulo_x=210,
        titulo_y=-77,
    )
    capas = composition.capas(brief)

    # En orden de dibujo, y cada figura con nombre propio.
    nombres = [c.nombre for c in capas]
    assert nombres[0] == "fondo" and nombres[-3:] == ["logo", "titulo", "marco"]
    assert sorted(nombres[1:-3]) == ["conductor.0", "invitado.0", "invitado.1", "objeto.0"]
    # El conductor se mando atras: queda debajo de los dos invitados.
    assert nombres.index("conductor.0") < nombres.index("invitado.1")

    lienzo = Image.new("RGBA", template.CANVAS, (0, 0, 0, 255))
    for capa in capas:
        lienzo.alpha_composite(capa.imagen, (capa.x, capa.y))
    assert lienzo.convert("RGB").tobytes() == _abrir(composition.compose(brief).final).tobytes()

    # Las figuras dicen tambien donde se apoyan: es el punto desde el que el
    # navegador escala sin pedir nada al servidor.
    conductor = next(c for c in capas if c.nombre == "conductor.0")
    slot = template.SLOTS["conductor"]
    ajuste = composition.ajuste_de(brief, "conductor", 0)
    assert conductor.ancla == (slot.x + ajuste.dx, slot.y + ajuste.dy)
    assert conductor.y + conductor.imagen.height == conductor.ancla[1]


def test_composition_24_repintar_por_titulo_tarda_menos_de_60ms(fotos):
    brief = _brief(fotos, conductor=1, invitado=1, fondo=1, logo=1, objeto=1)
    composition.preview(brief)  # deja la base en la cache

    empezo = time.perf_counter()
    composition.preview(composition.Brief(title="UN TITULO NUEVO", photos=brief.photos))
    transcurrido = (time.perf_counter() - empezo) * 1000

    assert transcurrido < 60, f"repintar por titulo tardo {transcurrido:.0f} ms"


def test_composition_43_el_titulo_se_alinea_dentro_de_su_bloque():
    """Izquierda, centro y derecha dentro del bloque, con la regla detrás."""
    tipografia = template.TYPOGRAPHY
    paleta = template.PALETTE
    util = tipografia.ancho()

    def _tinta(alineacion=None):
        lienzo = Image.new("RGBA", template.CANVAS, (0, 0, 0, 0))
        extra = {} if alineacion is None else {"alineacion": alineacion}
        typography.draw_title(lienzo, "HOLA", tipografia, paleta, **extra)
        return lienzo

    def _regla(lienzo):
        """La caja de la regla de acento: la franja bajo la línea base."""
        y = tipografia.bottom + tipografia.rule_gap + tipografia.rule_height // 2
        franja = lienzo.crop((0, y, template.CANVAS[0], y + 1))
        caja = franja.getbbox()
        return caja[0], caja[2]

    izquierda = _tinta("izquierda")
    centro = _tinta("centro")
    derecha = _tinta("derecha")

    # La de siempre no cambia ni un píxel.
    assert izquierda.tobytes() == _tinta().tobytes()

    # Lo que se mira es DÓNDE quedó la tinta, no que haya cambiado.
    medio = tipografia.left + util // 2
    x0, _, x1, _ = centro.getbbox()
    assert abs((x0 + x1) / 2 - medio) <= tipografia.stroke_width + 2, "no quedó centrado"
    assert abs(derecha.getbbox()[2] - (tipografia.left + util)) <= tipografia.stroke_width + 2
    assert abs(izquierda.getbbox()[0] - tipografia.left) <= tipografia.stroke_width + 2

    # La regla va con el texto.
    assert _regla(izquierda)[0] == tipografia.left
    assert abs(sum(_regla(centro)) / 2 - medio) <= 1
    assert _regla(derecha)[1] == tipografia.left + util + 1

    # El checksum: la de siempre no cambia el de un armado de antes, y las
    # otras dos sí cambian.
    base = composition.Brief(title="HOLA")
    assert composition.brief_checksum(
        composition.Brief(title="HOLA", titulo_alineacion="izquierda")
    ) == composition.brief_checksum(base)
    distintos = {
        composition.brief_checksum(composition.Brief(title="HOLA", titulo_alineacion=a))
        for a in template.ALINEACIONES
    }
    assert len(distintos) == 3
    # Es overlay: la base no se entera.
    assert composition.base_checksum(
        composition.Brief(title="HOLA", titulo_alineacion="derecha")
    ) == composition.base_checksum(base)
