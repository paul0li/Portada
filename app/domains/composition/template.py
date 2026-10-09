"""EL template del show. Datos puros, sin logica.

Este es el archivo del que habla SPEC 6: "los numeros viven en un archivo, y
editarlos cambia todas las miniaturas futuras a la vez". Es la identidad visual
del show, y el unico lugar donde se decide el layout.

Cambiar cualquier valor de aqui es cambiar como se ve el canal. Por eso lleva
`TEMPLATE_VERSION`: subirlo es declarar que las miniaturas nuevas no van a
coincidir con las viejas, y hay un test que falla si se edita sin subirlo.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Literal

TEMPLATE_VERSION = 14
# v14 (2026-10-09): una foto de fondo se ve con sus colores. "Que los fondos que
#   el usuario sube no se muestren con un filtro (ahora se ven deslavados)".
#   Fuera la desaturacion (0.35) y el desenfoque (2 px) que quedaban de v12, y
#   con ellos el tratamiento entero. Sin foto de fondo -- el degradado -- no
#   cambia ni un pixel.
# v13 (2026-10-08): el titulo se puede alinear a la izquierda, al centro o a la
#   derecha de su bloque, y la regla de acento va con el. "Permite elegir centrar
#   el texto o alinear a la izquierda o a la derecha." A la izquierda, que es
#   el default, no cambia ni un pixel.
# v12 (2026-10-07): una foto de fondo ya no se oscurece ni lleva vineta. "Elimina
#   la capa de oscuridad que se le pone a las imagenes cuando elijo ponerlas como
#   fondo." El tratamiento existia para que el fondo "se quedara detras" (SPEC
#   6), pero quien elige una foto de fondo la elige para que se vea. Se quedan la
#   desaturacion y el desenfoque, que no oscurecen. Sin foto de fondo -- el
#   degradado -- no cambia ni un pixel.
# v11 (2026-10-07): mover deja de ser empujar. "Que las imagenes se puedan mover
#   libremente, como en Photoshop o Canva": las figuras van a donde se las lleve
#   y se ESCALAN, y el bloque del titulo tambien se mueve. Lo que desaparece son
#   los topes de +-400/+-200, que estaban justo para que empujar no acabara
#   siendo "colocar donde sea" -- que es ahora lo que se pide. Lo que queda es
#   lo fisico: el centro de una figura no sale del lienzo (perderla no es
#   moverla), la escala tiene un rango, y la capa sigue entre el fondo y el
#   titulo. El template sigue diciendo de donde se parte y hasta donde se llega.
#   Con todo en cero no cambia ni un pixel.
# v10 (2026-09-16): el tamano de la letra del titulo deja de ser cosa unica del
#   auto-ajuste. Con un solo mando -- el ancho del bloque -- ensanchar subia el
#   tamano y el titulo se cortaba en las MISMAS lineas, solo que mas grande: el
#   ancho se lo comia el auto-ajuste antes de llegar al corte. Ahora son dos
#   decisiones: el bloque dice DONDE cortan las lineas y el tamano CUANTO ocupa
#   cada palabra. Lo que el episodio elige es el TECHO del auto-ajuste, no el
#   tamano final, asi que la regla de siempre sigue en pie: el tamano se ajusta
#   al texto, no al reves, y ningun techo puede desbordar el bloque.
#   Y con ellas entra la tercera: el TECHO DEL BLOQUE. `top` valia 150 por un
#   logo que este show no usa, y era lo unico que decidia cuantas lineas entran
#   -- o sea con cuantas palabras cabe "una palabra por linea". Ahora el rango
#   se autora contra el marco, que es el mobiliario que el show si tiene.
#   Con el techo en su sitio no cambia ni un pixel; sube igual porque el
#   template decide algo nuevo, y ese numero mueve pixeles.
# v9 (2026-09-02): el bloque del titulo deja de ser de un solo ancho. Termina en
#   x=620 porque ahi empieza el invitado, y con eso las palabras se apilaban
#   enseguida -- pero el titulo se dibuja ENCIMA de las figuras, asi que
#   invadirlas es una decision de la semana y no un error. El template autora el
#   rango y el paso; el episodio elige dentro, y puede ademas pedir una palabra
#   por linea. Entra tambien `Typography.top`, que hasta ahora no hacia falta:
#   con tres lineas el titulo nunca llegaba al logo, y apilando si.
# v8 (2026-09-02): un episodio puede VOLTEAR una figura, de izquierda a derecha
#   o de arriba a abajo. Es el mismo tipo de decision que el empujon de v6 --
#   arregla UNA miniatura en vez de cambiar el canal -- y el template sigue
#   decidiendo lo suyo: QUE se puede voltear (`ROLES_VOLTEABLES`) y que no. Con
#   nada volteado no cambia ni un pixel; sube igual porque el template decide
#   algo nuevo, y porque la huella de un ajuste cambia de forma.
# v7 (2026-09-02): el `invitado` deja de ser uno. Un slot que admite varias
#   figuras las reparte por la cantidad que TRAE, no por la que admite, y el
#   reparto lo autora este archivo: cuanto se separan y cuanto se encogen
#   (`Grupo`). Con un solo invitado no cambia ni un pixel -- un slot con una
#   figura se dibuja donde siempre -- pero con un solo OBJETO si: hasta aqui un
#   objeto se colocaba a media separacion a la izquierda del centro del slot,
#   por repartir para dos aunque solo hubiera uno. Eso era el hueco de la foto
#   que no vino, y ahora no existe.
# v6 (2026-09-01): el template deja de decidir la posicion FINAL de una figura y
#   pasa a decidir la DE PARTIDA: un episodio puede empujar conductor, invitado
#   y objeto dentro de los limites de `Ajustes`, y reordenarlos entre ellos. Con
#   los ajustes en cero no cambia ni un pixel; sube igual porque el template
#   decide algo nuevo -- cuanto es un empujon y hasta donde llega -- y esos
#   numeros mueven pixeles de cualquier episodio que use uno.
# v5 (2026-09-01): el degradado que responde a "no hay fondo" deja de ser uno.
#   El template autora DOS -- claro y oscuro -- y el episodio elige cual. Sigue
#   sin haber nada generado: son dos constantes de esta paleta, no una perilla
#   libre (SPEC 11.1 y 11.3). Sube la version porque `Palette` cambia de forma,
#   y con ella el checksum de todo armado.
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
class Grupo:
    """Como se reparte un slot cuando trae mas de una figura.

    `separacion` es en pixeles del LIENZO y no en anchos de imagen. Los recortes
    reales llegan con encuadres muy distintos -- un busto cuadrado mide 520px de
    ancho a 520 de alto, y uno de medio cuerpo 400 -- asi que repartir por el
    ancho de la foto haria que la posicion de una cara la decidiera como venia
    recortado el archivo. Donde va una cara lo decide el template.

    `x` es el centro del grupo, y por defecto es el del slot. Existe porque
    "donde va uno" y "donde va el centro de dos" no tienen por que coincidir:
    dos invitados centrados donde iba uno caen sobre el titulo y sobre el
    conductor a la vez.

    Lo que NO hay aqui es un factor de encogido, y no por falta de ganas: la
    primera version encogia a los acompanantes y se veia peor. Las figuras se
    anclan por su BASE, asi que encogerlas les baja la cabeza -- justo hacia la
    banda donde estan el titulo y el brazo del conductor -- y la cabeza es lo
    unico que tiene que quedar despejado. A tamano completo las cabezas se
    quedan arriba, y como son estrechas dos bustos pueden solaparse de hombros
    sin taparse la cara. Se ve en los PNG, no se deduce.
    """

    separacion: int
    x: int | None = None


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
    # Como se reparten cuando son varias. Un slot de una figura no lo necesita.
    grupo: Grupo | None = None
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
        # 240px entre centros. Antes era "el ancho de la imagen mas 32", que
        # hacia que la posicion de un objeto dependiera de como venia recortado.
        grupo=Grupo(separacion=240),
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
    #
    # `max_items=2`: en la semana en que vienen dos, vienen dos. Tres no caben,
    # y no por el lienzo sino por como se MIRA una miniatura -- a ~320px de
    # ancho en un feed, tres caras en la banda central son tres manchas.
    "invitado": Slot(
        role="invitado",
        z=2,
        anchor="bottom-center",
        x=700,
        y=556,
        height=520,
        max_items=2,
        # 240px entre centros y el grupo centrado en 620, no en 700: medido
        # sobre las fotos reales del show, ahi es donde las dos caras caen en el
        # hueco que dejan el titulo (termina en x=620, pero mas abajo) y el
        # brazo del conductor (empieza sobre x=780, pero mas abajo tambien).
        grupo=Grupo(separacion=240, x=620),
    ),
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

# Cuantas figuras admite cada rol. Sale de los SLOTS y no de una lista escrita
# aparte: el dia que el template admita dos invitados, la API y la pantalla se
# enteran solas. Con dos listas, una de las dos habria seguido diciendo uno --
# y quien la creyera rechazaria una seleccion que el armado dibuja sin problema.
MAX_POR_ROL: Mapping[str, int] = MappingProxyType(
    {role: slot.max_items for role, slot in SLOTS.items()}
)


# --- lo que un episodio puede mover --------------------------------------
#
# SPEC 11.1 sigue mandando -- el layout es del template y no de la semana --
# pero "fijo" resulto ser demasiado fijo. Con fotos reales pasa que el invitado
# queda tapado o que un objeto pisa el titulo, y arreglarlo pedia editar este
# archivo: cambiar el canal entero para arreglar UNA miniatura.
#
# Desde v11 mover es libre y se puede escalar: el template dice de donde se
# parte, y la semana a donde se llega. Lo que sigue sin poderse: perder una
# figura fuera del cuadro, esconderla debajo del fondo o taparle el titulo. La
# consistencia de SPEC 15.3 vive ahora en el PUNTO DE PARTIDA -- un episodio que
# no toca nada sale exactamente como el canal -- y no en impedir tocar.

# Los roles que un episodio puede mover y escalar. El fondo y el marco van a
# sangre completa -- no hay donde moverlos -- y el logo es mobiliario de marca
# (SPEC 11.5). El titulo SI se mueve, pero no es una figura: su bloque tiene sus
# propios mandos en `Typography`.
ROLES_MOVIBLES = ("objeto", "invitado", "conductor")

# Los roles que un episodio puede VOLTEAR. Son mas que los que puede mover, y
# no por descuido: el fondo no tiene donde moverse -- va a sangre completa --
# pero voltearlo es lo que arregla un fondo cuyo motivo cae justo donde va el
# titulo.
#
# Los que faltan son el logo y el marco, y tampoco por descuido: los dos llevan
# el nombre del show escrito. Un texto en espejo es exactamente "reinterpretar
# el logo", que es lo unico que SPEC 11.5 prohibe de plano.
ROLES_VOLTEABLES = ("fondo", "objeto", "invitado", "conductor")


@dataclass(frozen=True, slots=True)
class Ajustes:
    """Hasta donde llega lo que un episodio le hace a una figura.

    Desde v11 no hay topes de movimiento: el unico limite es que el CENTRO de la
    figura siga dentro del lienzo, y ese no es un numero de aqui sino del lienzo
    mismo (ver `assembly.acotar`). Una figura con el centro fuera es una figura
    perdida, y desde un telefono no hay forma de agarrarla para traerla de vuelta.

    `paso` sigue existiendo para los pads sin JS: 20px porque una miniatura se
    mira a ~320px de ancho, y ahi 20px son 5 -- el empujon mas chico que se nota.
    En el lienzo no cuenta: un pixel es un movimiento valido.
    """

    paso: int = 20
    # La escala, en porcentaje del tamano que el slot le da. 40 y no menos: a
    # 320px de feed una figura al 40% del conductor ya es una cara de 30px. Y
    # 200 y no mas: un busto al doble es una cabeza que llena el cuadro, y a
    # partir de ahi lo que se esta pidiendo es otra foto, no otra escala.
    escala_min: int = 40
    escala_max: int = 200
    # La capa efectiva se queda entre el fondo (z=0) y el titulo (z=4): una
    # figura no puede esconderse detras del degradado ni taparle el titulo.
    capa_min: int = 1
    capa_max: int = 3


AJUSTES = Ajustes()

# --- tipografia del titulo -----------------------------------------------


@dataclass(frozen=True, slots=True)
class Typography:
    left: int = 48
    right: int = 620  # el bloque de titulo de SPEC 6: x 48 -> 620
    # El techo del bloque: hasta donde puede crecer un titulo alineado abajo.
    # Con tres lineas como maximo nunca se llegaba hasta aqui, asi que no hacia
    # falta decirlo. Apilando una palabra por linea, si.
    #
    # 150 es de cuando el show tenia logo, que ocupa hasta y=130 por la
    # izquierda -- justo por donde crece el titulo. Sigue siendo el techo POR
    # DEFECTO, pero ya no es el unico posible: el episodio lo mueve dentro de
    # `alto_menos`/`alto_mas`, y ese rango se autora contra el MARCO, que es el
    # mobiliario que el show usa de verdad.
    top: int = 150
    # SPEC 6 decia 604. Con marco, la banda con el nombre del show (en el marco
    # con el que se afino, desde y=552) se comia el titulo entero. 500 deja la
    # regla de acento en 522-531, con 21px de aire sobre la banda. Alineado
    # abajo: el titulo crece hacia arriba y la regla queda siempre a la misma
    # altura. Un marco con la banda en otro sitio se arregla moviendo el titulo
    # en el lienzo, o cambiando este numero.
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

    # Lo que un episodio puede ensanchar o angostar el bloque, y de cuanto en
    # cuanto. Es la respuesta a "las palabras se apilan demasiado pronto": el
    # bloque termina en x=620 porque ahi empieza el invitado, pero el titulo va
    # ENCIMA de las figuras, asi que meterse sobre una es una decision de la
    # semana. Los topes son los de siempre: que "ensanchar" no acabe siendo
    # "poner el titulo donde sea".
    #
    # `ancho_mas` llega justo a x=980: el marco tiene 16px de borde y por la
    # derecha esta el conductor, que a partir de ahi ya no se ve.
    ancho_paso: int = 40
    # Hasta 212px de bloque. Angostar tanto solo tiene sentido desde que el
    # tamano es un mando: con el auto-ajuste al mando, un bloque estrecho no
    # apila las palabras, las ACHICA hasta que entran -- que es lo contrario de
    # lo que uno quiere al angostar. Con el tamano puesto, angostar es apilar.
    ancho_menos: int = 360
    ancho_mas: int = 360

    # Cuanto puede mover un episodio el techo del auto-ajuste, y de cuanto en
    # cuanto. Es la otra mitad de "las letras tienen muy poco espacio": con el
    # ancho solo, ensanchar el bloque no repartia el texto -- el auto-ajuste se
    # comia el hueco subiendo el tamano, y el titulo se cortaba en las mismas
    # lineas, solo que mas grande. Separados, el bloque dice DONDE cortan las
    # lineas y el tamano CUANTO ocupa cada palabra, que es lo que decide cuantas
    # caben en una.
    #
    # Sube TAMBIEN, y no por simetria: medido, `size_max` es lo unico que frena
    # a un titulo corto. "NADIE LO VIO" sale a 104px en una linea de 99px dentro
    # de un bloque de 350 -- 250px de alto sin usar, y nada fisico que lo impida.
    # Solo en un titulo largo manda el bloque (cuatro lineas son 360px y no
    # caben). Asi que hacia arriba SI hay algo que dar, en la mayoria de los
    # titulos.
    #
    # `tamano_mas` llega a 200px. Con el auto-ajuste al mando no habria servido
    # -- tres lineas a 152px ya son 428px y no entran en el bloque --, pero con
    # el tamano puesto el titulo se reparte en las lineas que haga falta, asi
    # que una palabra grande y sola es una miniatura posible y no un desborde.
    #
    # Lo que se elige sigue siendo el TECHO y no el tamano final: pedir 152 no
    # impone 152, empieza a probar ahi. La regla 2 de `typography` queda intacta
    # -- el tamano se ajusta al texto, no al reves -- y por eso este mando no
    # puede desbordar el bloque por mucho que se suba.
    #
    # `tamano_paso` es 8 y no 2 como `size_step`: a los ~320px a los que se mira
    # una miniatura, 2px de 104 son medio pixel. Un paso del mando tiene que
    # verse donde se mira, igual que la regla de acento.
    tamano_paso: int = 8
    tamano_menos: int = 40  # 104 - 40 = 64 = `size_min`: por debajo no se lee
    tamano_mas: int = 96  # 104 + 96 = 200

    # Cuanto puede mover un episodio el TECHO del bloque, y de cuanto en cuanto.
    # Es el tercer mando del titulo y hace lo tercero: el ancho dice donde
    # cortan las lineas, el tamano cuanto ocupa cada palabra, y el alto CUANTAS
    # lineas entran antes de que el auto-ajuste tenga que achicar. Es el que
    # decide si "una palabra por linea" cabe con cinco palabras o con siete.
    #
    # El titulo NO se mueve: sigue apoyado en `bottom` y crece hacia arriba. Lo
    # que se mueve es hasta donde puede crecer.
    #
    # `alto_mas` llega a y=10, o sea a lo alto del lienzo entero. Con el
    # auto-ajuste al mando sobraba con y=50 -- el marco tiene 16px de borde y
    # ahi arriba ya casi no hay miniatura --, pero con el tamano puesto el alto
    # es lo que decide si angostar el bloque APILA las palabras o las achica: si
    # el bloque no da, lo que cede es el tamano, y entonces el mando del ancho
    # vuelve a parecer un mando de tamano. Que llegue arriba del todo es lo que
    # deja apilar seis lineas grandes sin que nada ceda por detras.
    #
    # Pasarse del borde del marco es una decision de la semana, como invadir a
    # una figura con el titulo: se ve en el preview mientras se elige. Y si el
    # show usara logo, un titulo subido del todo se le pondria ENCIMA, porque el
    # titulo se dibuja despues (`_draw_overlay`).
    alto_paso: int = 20
    alto_menos: int = 100  # el techo baja hasta y=250
    alto_mas: int = 140  # y sube hasta y=10

    # Cuanto se puede MOVER el bloque entero -- texto, techo y regla juntos --
    # respecto de donde lo pone el template (v11). Los topes son el lienzo y no
    # una opinion: la regla de acento no se sale por ningun lado, y el bloque
    # no baja de y=120, donde ya no cabe ni una linea al tamano minimo.
    mover_izquierda: int = 48  # left llega a x=0
    mover_derecha: int = 1032  # la regla (200px) termina justo en x=1280
    mover_arriba: int = 380  # bottom sube hasta y=120
    mover_abajo: int = 184  # la regla (gap 22 + 14) termina justo en y=720

    @property
    def block_width(self) -> int:
        return self.right - self.left

    def ensanche(self, extra: int) -> int:
        """El ensanche pedido, dentro de los topes. Nunca lanza (SPEC 11.4)."""
        return max(-self.ancho_menos, min(self.ancho_mas, extra))

    def ancho(self, extra: int = 0) -> int:
        """El ancho del bloque con el ensanche de este episodio."""
        return self.block_width + self.ensanche(extra)

    def cambio_de_tamano(self, extra: int) -> int:
        """Cuanto se mueve el techo, dentro de los topes. Nunca lanza (SPEC 11.4)."""
        return max(-self.tamano_menos, min(self.tamano_mas, extra))

    def tamano(self, extra: int = 0) -> int:
        """El techo del auto-ajuste con el cambio de este episodio.

        Nunca por debajo de `size_min`: el suelo es una regla sobre como se LEE
        un titulo en un feed, y bajar el techo no puede saltarsela.
        """
        return max(self.size_min, self.size_max + self.cambio_de_tamano(extra))

    def cambio_de_alto(self, extra: int) -> int:
        """Cuanto se mueve el techo, dentro de los topes. Nunca lanza (SPEC 11.4).

        Positivo es MAS ALTO, como en `ensanche`: los mandos del titulo dicen
        cuanto sitio hay, no hacia donde va la coordenada.
        """
        return max(-self.alto_menos, min(self.alto_mas, extra))

    def techo(self, extra: int = 0) -> int:
        """La `y` del techo del bloque con el alto que pidio este episodio.

        Se RESTA porque en el lienzo arriba es menos: mas alto es un techo mas
        arriba, o sea una `y` mas chica.
        """
        return self.top - self.cambio_de_alto(extra)

    def desplazamiento(self, dx: int, dy: int) -> tuple[int, int]:
        """Cuanto se mueve el bloque, dentro del lienzo. Nunca lanza (SPEC 11.4)."""
        return (
            max(-self.mover_izquierda, min(self.mover_derecha, dx)),
            max(-self.mover_arriba, min(self.mover_abajo, dy)),
        )

    def movida(self, dx: int = 0, dy: int = 0) -> "Typography":
        """La misma tipografia con el bloque en otro sitio.

        Se mueve el bloque ENTERO: izquierda, derecha, techo y base. Asi el
        ancho y el alto siguen significando lo mismo -- el corte y el tamano no
        cambian por mover --, y la regla de acento va con el texto porque se
        dibuja desde `left` y `bottom`.
        """
        dx, dy = self.desplazamiento(dx, dy)
        if not dx and not dy:
            return self
        return replace(
            self,
            left=self.left + dx,
            right=self.right + dx,
            top=self.top + dy,
            bottom=self.bottom + dy,
        )

    def max_lineas(self, apilado: bool = False, alto: int = 0) -> int:
        """Cuantas lineas se admiten.

        Apilado son las que quepan de verdad entre el techo y `bottom` al tamano
        minimo, y no el tres de siempre: tres lineas es una regla sobre como se
        LEE un titulo en un feed, y una palabra por linea es otra forma de
        leerlo. Lo que no cambia es que el alto es fisico -- por eso subir el
        techo deja entrar mas palabras apiladas, y bajarlo, menos.
        """
        if not apilado:
            return self.max_lines
        alto_linea = max(1, int(self.size_min * self.line_spacing))
        return max(1, (self.bottom - self.techo(alto)) // alto_linea)


TYPOGRAPHY = Typography()

# Como se alinean las lineas del titulo DENTRO de su bloque (v13), y la regla de
# acento con ellas. El bloque no se mueve por alinear: sigue empezando en `left`
# y midiendo `ancho`, asi que las asas del lienzo significan lo mismo con
# cualquier alineacion. Centrar en la miniatura es centrar el bloque, y eso ya
# se hace moviendolo. El primero es el de siempre: un episodio que no dice nada
# sale como salia.
ALINEACIONES = ("izquierda", "centro", "derecha")
ALINEACION_POR_DEFECTO = ALINEACIONES[0]


# --- paleta --------------------------------------------------------------


Color = tuple[int, int, int]
Degradado = tuple[Color, Color]

# Los dos degradados que responden a "no hay fondo" (SPEC 6). Los DOS estan
# autorados aqui: elegir entre ellos es elegir contenido dentro del template,
# no aflojar el layout (SPEC 11.1). Y son una lista cerrada de nombres, no una
# perilla libre, que es lo que SPEC 11.3 pide de cualquier eleccion.
#
# Los dos son neutros frios por lo mismo que en v2: sobre cualquier cosa rojiza
# la regla de acento no se ve y el marco rojo del show pierde fuerza, asi que el
# rojo tiene que ser lo unico rojo.
#
# `claro` no es gratis, y por eso conviene poder no usarlo: el titulo es blanco
# con contorno oscuro, asi que sobre el se lee por el CONTORNO y no por el
# relleno (comprobado a 320px, el tamano al que se ve en un feed). `oscuro` es
# el degradado que el template tuvo hasta v3, y ahi el titulo se lee por el
# relleno. Cual conviene lo decide la miniatura de la semana, no este archivo:
# de eso trata poder elegirlo.
DEGRADADOS: Mapping[str, Degradado] = MappingProxyType(
    {
        "claro": ((238, 240, 245), (188, 194, 208)),
        "oscuro": ((38, 42, 58), (16, 17, 22)),
    }
)

# El que vale cuando nadie elige. Sigue siendo el claro (v4): es el fondo que
# tiene una miniatura cuando nadie toco nada.
DEGRADADO_POR_DEFECTO = "claro"


@dataclass(frozen=True, slots=True)
class Palette:
    """Los colores del show.

    `degradados` es la respuesta a "no hay fondo" (SPEC 6): degradados
    deterministicos, no imagenes generadas. Consistencia sobre novedad -- un
    fondo generado seria el unico elemento que cambia cada semana sin motivo.
    Elegir entre dos constantes de la paleta no es eso: la semana que viene el
    mismo brief da los mismos pixeles.
    """

    title: Color = (255, 255, 255)
    title_stroke: Color = (12, 12, 16)
    # El color de la marca, muestreado del marco del canal: la regla de acento
    # repite la marca en vez de competir con ella. La interfaz lee este mismo
    # valor (WEB-54), asi que adaptar Portada a otro canal es cambiarlo aqui.
    accent: Color = (233, 40, 39)
    degradados: Mapping[str, Degradado] = DEGRADADOS
    shadow: Color = (0, 0, 0)

    def degradado(self, nombre: str = DEGRADADO_POR_DEFECTO) -> Degradado:
        """El degradado de ese nombre. Uno desconocido cae en el por defecto.

        No lanza a proposito: un nombre invalido lo rechaza quien recibe la
        peticion, y aqui abajo la regla es la de SPEC 11.4 -- el armado siempre
        es salida valida, nunca una excepcion a mitad de dibujar.
        """
        return self.degradados.get(nombre, self.degradados[DEGRADADO_POR_DEFECTO])


PALETTE = Palette()


@dataclass(frozen=True, slots=True)
class Template:
    version: int = TEMPLATE_VERSION
    canvas: tuple[int, int] = CANVAS
    slots: dict[str, Slot] = field(default_factory=lambda: dict(SLOTS))
    typography: Typography = TYPOGRAPHY
    palette: Palette = PALETTE
    title_z: int = TITLE_Z
    ajustes: Ajustes = AJUSTES


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
