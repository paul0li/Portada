"""Las pantallas.

Este dominio es una capa de ENTREGA, no de negocio. No tiene tablas, no tiene
reglas propias, y todo lo que sabe hacer lo hace llamando al `api.py` de otro.
Si algún día aparece aquí una decisión de producto, está en el sitio equivocado:
significaría que el otro router —el JSON— no la tiene.

Tres cosas, y solo tres, separan a este router del de la API:

1. **Un fallo se convierte en una página, no en un JSON.** Nadie lee
   `INTAKE_NOT_AN_IMAGE`; `MENSAJES` lo traduce a una frase.
2. **Sin sesión se redirige, no se responde 401.** Un 401 es correcto para un
   cliente y es una pantalla en blanco para una persona.
3. **Después de un POST se redirige.** Recargar no vuelve a subir la foto.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import OptionalUser
from app.core.deps import Config, Db
from app.core.errors import AppError
from app.domains.episodes import api as episodes
from app.domains.identity import api as identity
from app.domains.library import api as library

router = APIRouter(tags=["web"], include_in_schema=False)

PLANTILLAS = Path(__file__).parent / "templates"
ESTATICOS = Path(__file__).parent / "static"

TEMPLATES = Jinja2Templates(directory=str(PLANTILLAS))

# Ninguna pantalla privada se guarda en ninguna caché: lo que hay dentro es de
# una sola persona, y el botón «atrás» no debería enseñárselo a la siguiente.
# Los ARCHIVOS sí se cachean un año, porque son inmutables por contenido: esta
# cabecera es para el HTML, no para las fotos.
SIN_CACHE = {"Cache-Control": "no-store, private", "X-Frame-Options": "DENY"}

# El código de error es estable y sirve para ramificar; el mensaje es para leerlo.
# Traducir aquí, y no en el dominio, es lo que deja que la API siga hablando en
# códigos mientras la pantalla habla en español.
MENSAJES = {
    "INTAKE_NOT_AN_IMAGE": "Ese archivo no es una imagen. Prueba con un PNG o un JPG.",
    "INTAKE_FORMAT_UNSUPPORTED": "Ese formato de imagen no lo admitimos. Prueba con PNG o JPG.",
    "INTAKE_FILE_TOO_LARGE": "Esa imagen pesa demasiado. El límite son 10 MB.",
    "INTAKE_IMAGE_TOO_LARGE": "Esa imagen tiene demasiados píxeles para procesarla.",
    "LIBRARY_ROLE_INVALID": "Ese rol no existe.",
    "LIBRARY_PHOTO_NOT_FOUND": "Esa foto ya no está en tu librería.",
    "LIBRARY_FILE_NOT_FOUND": "El archivo de esa foto no está disponible.",
    "IDENTITY_TOKEN_USED": "Ese enlace ya se usó. Pide otro enlace y vuelve a entrar.",
    "IDENTITY_TOKEN_EXPIRED": "Ese enlace venció. Pide otro enlace y vuelve a entrar.",
    "IDENTITY_TOKEN_INVALID": "Ese enlace no sirve. Pide otro enlace y vuelve a entrar.",
    "IDENTITY_RATE_LIMITED": "Demasiados intentos seguidos. Espera unos minutos.",
}

MENSAJE_GENERICO = "Algo falló y no fue culpa tuya. Inténtalo otra vez."

# El orden en que se muestran los roles es el del flujo semanal, no el
# alfabético. `logo` y `marco` van al final porque son marca, no contenido.
ORDEN_ROLES = ("conductor", "invitado", "fondo", "objeto", "logo", "marco")

ETIQUETAS = {
    "conductor": "Conductor",
    "invitado": "Invitados",
    "fondo": "Fondo",
    "objeto": "Objetos",
    "logo": "Logo",
    "marco": "Marco",
}

# El nombre de UNA figura del rol. `ETIQUETAS` está en plural justo donde el rol
# admite varias —«Invitados», «Objetos»— y «ajustar invitados 2» no se entiende:
# lo que se ajusta es un invitado, el segundo. Solo hacen falta los que pueden
# venir de a varios; para el resto vale la etiqueta de siempre.
FIGURAS = {"invitado": "invitado", "objeto": "objeto"}

# Los cinco pasos del trabajo semanal (SPEC §8, pasos 3-8). El prototipo tenía
# seis porque metía «Logo o marco» dentro; pero SPEC §8 ya cuenta subir el logo
# como setup —«el trabajo recurrente son los pasos 3-8»— y la marca se pone una
# vez. El sexto paso del prototipo, «instrucciones personalizadas», no está y no
# puede estar: es prosa dirigiendo a un compositor, y SPEC §11.3 lo prohíbe.
PASOS = ("conductor", "invitado", "fondo", "objeto", "titulo")

# La marca: se elige una vez y el flujo la da por puesta. No la rellena el
# backend —eso haría que subir un marco nuevo cambiara en silencio el checksum
# de episodios que nadie tocó— sino esta pantalla, y lo dice en el resumen.
MARCA = ("logo", "marco")

# Lo que cada rol es, en una línea. Sale del prototipo y de SPEC §6.
# Los topes salen de `episodes`, que los saca del template: escribir «hasta dos»
# a mano seria una tercera copia del mismo numero, y la que se quedaria vieja es
# la de la pantalla -- diciendo que caben dos mientras el flujo deja elegir tres.
AYUDAS = {
    "conductor": "Tú, con distintos gestos. Va a la derecha y al frente.",
    "invitado": (
        f"Quien viene esta semana. Hasta {episodes.MAXIMOS['invitado']}, al centro y detrás de ti."
    ),
    "fondo": "Opcional. Sin foto se usa el degradado del show, claro u oscuro.",
    "objeto": f"Opcional. Hasta {episodes.MAXIMOS['objeto']}, en la banda central.",
    "logo": "Se pega tal cual, arriba a la izquierda. Nunca se reinterpreta.",
    "marco": "El PNG 16:9 del show. Va encima de todo, incluso del título.",
}


def _mensaje(error: AppError) -> str:
    return MENSAJES.get(error.code, MENSAJE_GENERICO)


def _pagina(request: Request, plantilla: str, contexto: dict, status: int = 200) -> Response:
    return TEMPLATES.TemplateResponse(
        request=request,
        name=plantilla,
        context=contexto,
        status_code=status,
        headers=SIN_CACHE,
    )


def _a_entrar() -> RedirectResponse:
    return RedirectResponse("/entrar", status_code=303)


def _vuelta_segura(destino: str, por_defecto: str) -> str:
    """A dónde volver después de subir, sin dejar una redirección abierta.

    `volver` lo manda el cliente. Sin esta comprobación basta un enlace a
    Portada con `volver=https://…` para que la app te saque a otro sitio con
    aire de sitio legítimo. Solo se admite una ruta interna: empieza por una
    barra y no por dos (`//host` es una URL absoluta con el esquema implícito, y
    es el caso que se escapa de comprobar solo la primera barra).
    """
    if destino.startswith("/") and not destino.startswith("//"):
        return destino
    return por_defecto


def _foto(photo, media) -> dict:
    """Una foto lista para pintar. La plantilla no calcula nada."""
    return {
        "id": photo.id,
        "role": photo.role,
        "etiqueta": photo.label or ETIQUETAS[photo.role].lower(),
        "descripcion": photo.description,
        "url": f"/photos/{photo.id}/file",
        "ancho": media.width,
        "alto": media.height,
        # La URL de la foto es un PUNTERO: sirve el recorte si esta listo. Como
        # los mismos bytes de URL pueden devolver bytes distintos, el `<img>`
        # lleva la identidad de lo que hoy sirve. Sin eso, quitar el fondo no se
        # veria hasta recargar a mano -- la trampa del Cache-Control que miente.
        "sin_fondo": media.id != photo.media_id,
        "version": media.id,
    }


def _contexto_modal(request, db, settings, user_id: str, nueva_id: str) -> dict:
    """El modal de la foto recien subida, si `?nueva=` apunta a una foto mia.

    Un id que no resuelve -- ajeno, borrado, inventado -- no es un error: no hay
    modal y la pantalla se pinta igual. Es una decoracion de la URL, no una ruta.
    """
    if not nueva_id:
        return {}
    try:
        photo = library.get_photo(db, user_id=user_id, photo_id=nueva_id)
    except AppError:
        return {}
    aqui = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    limpia = _sin_parametro(aqui, "nueva")
    return {
        "nueva": _foto(photo, library.resolve_media(db, settings, photo)),
        # No se ofrece lo que esta instancia no puede hacer. Con `passthrough`
        # puesto, el boton llamaria al recorte, el recorte devolveria la misma
        # imagen, y no pasaria nada: un boton que miente.
        "recorte_activo": request.app.state.cutout_provider.quita_fondo,
        "aqui_sin_modal": limpia,
        "aqui_con_modal": f"{limpia}{'&' if '?' in limpia else '?'}nueva={photo.id}",
    }


def _sin_parametro(url: str, nombre: str) -> str:
    ruta, _, consulta = url.partition("?")
    quedan = [p for p in consulta.split("&") if p and not p.startswith(f"{nombre}=")]
    return f"{ruta}?{'&'.join(quedan)}" if quedan else ruta


def _con_modal(destino: str, photo_id: str) -> str:
    """La URL de vuelta, con el modal abierto sobre ella."""
    limpia = _sin_parametro(destino, "nueva")
    return f"{limpia}{'&' if '?' in limpia else '?'}nueva={photo_id}"


def _contexto_libreria(db, settings, user_id: str, role: str, **extra) -> dict:
    fotos = library.list_photos(db, user_id=user_id, role=role or None)
    return {
        "fotos": [_foto(p, library.resolve_media(db, settings, p)) for p in fotos],
        "role": role,
        "roles": ORDEN_ROLES,
        "etiquetas": ETIQUETAS,
        "ayudas": AYUDAS,
        "stats": library.stats(db, user_id=user_id),
        # Que roles admiten recorte lo decide `library`, no la plantilla: si la
        # lista se copiara aqui, el dia que cambie habria dos verdades.
        "roles_con_recorte": library.ROLES_CON_RECORTE,
        **extra,
    }


@dataclass(frozen=True, slots=True)
class Borrador:
    """Lo que llevo elegido: fotos, fondo y empujones.

    Vive entero en la barra de direcciones y no en el servidor: no hace falta
    una tabla de borradores, atrás y recargar funcionan solos, y no hay nada
    escondido. Son ids opacos del propio usuario sobre páginas `no-store`.

    Es un objeto y no tres argumentos sueltos porque ya son tres: cada vez que
    el borrador crece, un `_url_*` al que se le olvide uno pierde en silencio lo
    que la persona acababa de elegir.
    """

    seleccion: dict[str, list[str]] = field(default_factory=dict)
    degradado: str = episodes.DEGRADADO_POR_DEFECTO
    # Rol -> un ajuste por FIGURA, en el orden en que se eligieron sus fotos.
    ajustes: dict[str, list[episodes.Ajuste]] = field(default_factory=dict)

    def con(self, **cambios) -> "Borrador":
        return replace(self, **cambios)

    def ajuste(self, role: str, posicion: int = 0) -> episodes.Ajuste:
        figuras = self.ajustes.get(role, ())
        return figuras[posicion] if posicion < len(figuras) else episodes.SIN_AJUSTE

    def con_ajuste(self, role: str, posicion: int, ajuste: episodes.Ajuste) -> "Borrador":
        """El mismo borrador con ESA figura ajustada. Un ajuste nulo se borra.

        Las figuras anteriores que nadie tocó se rellenan con `SIN_AJUSTE`: la
        posición es lo que dice de quién es el ajuste, así que la lista no puede
        cerrarse antes de llegar a ella.
        """
        figuras = list(self.ajustes.get(role, ()))
        figuras.extend([episodes.SIN_AJUSTE] * (posicion + 1 - len(figuras)))
        figuras[posicion] = episodes.acotar(role, ajuste)
        while figuras and figuras[-1] == episodes.SIN_AJUSTE:
            figuras.pop()

        ajustes = {r: a for r, a in self.ajustes.items() if r != role}
        if figuras:
            ajustes[role] = figuras
        return replace(self, ajustes=ajustes)

    def pares(self) -> list[tuple[str, str]]:
        """Los campos de la URL: una foto por par, más uno por figura ajustada."""
        fotos = [(role, pid) for role, ids in self.seleccion.items() for pid in ids]
        ajustados = [
            (
                "ajuste",
                f"{role}.{posicion}:{a.dx},{a.dy},{a.capa},{int(a.voltear_x)},{int(a.voltear_y)}",
            )
            for role, figuras in sorted(self.ajustes.items())
            for posicion, a in enumerate(figuras)
            if a != episodes.SIN_AJUSTE
        ]
        return [*fotos, *ajustados]


def _seleccion(params) -> dict[str, list[str]]:
    """La selección en curso, leída de la URL."""
    elegido: dict[str, list[str]] = {}
    for role in ORDEN_ROLES:
        valores = [v for v in params.getlist(role) if v]
        if valores:
            elegido[role] = valores[: episodes.MAXIMOS.get(role, 1)]
    return elegido


def _lee_ajustes(valores) -> dict[str, episodes.Ajuste]:
    """`ajuste=invitado.1:40,-20,1,0,1`, uno por figura ajustada.

    Antes del punto va el rol y después la figura dentro de ese rol; los dos
    últimos números son los volteos. Se aceptan las dos formas viejas —sin
    posición, y con tres números— para que un enlace que alguien tenía abierto
    no pierda el ajuste entero por no traer un campo que aún no existía.

    Lo que no se entiende se ignora: esto viene de la barra de direcciones, que
    la escribe cualquiera, y un borrador ilegible no es un error — es un
    borrador sin ese ajuste. Quien sí rechaza un rol que no se puede mover o
    voltear es `episodes`, al crear el episodio.
    """
    leidos: dict[str, list[episodes.Ajuste]] = {}
    for texto in valores:
        figura, _, numeros = str(texto).partition(":")
        role, _, indice = figura.partition(".")
        if role not in episodes.ROLES_MOVIBLES and role not in episodes.ROLES_VOLTEABLES:
            continue
        partes = numeros.split(",")
        if len(partes) not in (3, 5):
            continue
        try:
            posicion = int(indice) if indice else 0
            dx, dy, capa, vx, vy = (int(p) for p in [*partes, "0", "0"][:5])
        except ValueError:
            continue
        if not 0 <= posicion < episodes.MAXIMOS.get(role, 1):
            continue
        acotado = episodes.acotar(
            role,
            episodes.Ajuste(dx=dx, dy=dy, capa=capa, voltear_x=bool(vx), voltear_y=bool(vy)),
        )
        if acotado == episodes.SIN_AJUSTE:
            continue
        figuras = leidos.setdefault(role, [])
        figuras.extend([episodes.SIN_AJUSTE] * (posicion + 1 - len(figuras)))
        figuras[posicion] = acotado
    return leidos


def _muestra(nombre: str) -> str:
    """El `background` del botón de un fondo, con los colores de la paleta.

    Salen del template y no de la hoja de estilos a propósito: escribirlos en el
    CSS sería una segunda verdad, y el día que el show cambie de degradado la
    muestra enseñaría el viejo sin que nada fallara.
    """
    desde, hasta = (f"rgb({r} {g} {b})" for r, g, b in episodes.DEGRADADOS[nombre])
    return f"linear-gradient({desde}, {hasta})"


def _degradado(params) -> str:
    """El fondo por defecto en curso, leído de la URL como el resto del borrador.

    Un nombre que no existe cae en el por defecto en vez de dar un error: esto
    es el borrador de una pantalla, y lo que llega por la barra de direcciones
    lo escribe cualquiera. Quien sí rechaza un nombre inválido es `episodes`,
    al crear el episodio.
    """
    pedido = params.get("degradado", "")
    return pedido if pedido in episodes.DEGRADADOS else episodes.DEGRADADO_POR_DEFECTO


def _borrador(params) -> Borrador:
    """Todo el borrador, leído de la URL de una vez."""
    return Borrador(
        seleccion=_seleccion(params),
        degradado=_degradado(params),
        ajustes=_lee_ajustes(params.getlist("ajuste")),
    )


# El pad, en dos filas. Las flechas mueven; la capa se dice con palabras.
# Con glifos para las dos cosas — ↑ para arriba y ⤒ para adelante — a un golpe
# de vista no se distingue mover de cambiar de capa, que son cosas distintas.
EMPUJONES = (
    ("mover", "←", "Izquierda", -1, 0, 0),
    ("mover", "→", "Derecha", 1, 0, 0),
    ("mover", "↑", "Arriba", 0, -1, 0),
    ("mover", "↓", "Abajo", 0, 1, 0),
    ("capa", "Atrás", "Atrás", 0, 0, -1),
    ("capa", "Adelante", "Adelante", 0, 0, 1),
)

# Los volteos, con palabras y no con glifos, por lo mismo que la capa: ⇄ y ⇅ no
# se distinguen de un golpe de vista, y menos al lado de cuatro flechas que
# significan otra cosa. Son interruptores: el enlace lleva al estado contrario.
VOLTEOS = (
    ("voltear_x", "Espejo", "Voltear de izquierda a derecha"),
    ("voltear_y", "Boca abajo", "Voltear de arriba a abajo"),
)


def _empujones(paso: int, borrador: Borrador, role: str, posicion: int) -> dict[str, list[dict]]:
    """El pad de UNA figura: enlaces al MISMO paso, más «como estaba».

    Una figura y no un rol: dos invitados comparten slot y no comparten sitio,
    así que cada uno trae el suyo. Con un solo invitado hay un solo pad, que es
    exactamente lo que había.

    En un tope el enlace desaparece en vez de quedarse sin hacer nada: `acotar`
    devuelve el mismo ajuste, así que el toque no cambiaría nada y un botón que
    no puede hacer nada es un botón que miente. Por eso mismo cada grupo se
    pregunta por separado: el `fondo` se voltea y no se mueve, así que su pad
    trae los volteos y ninguna flecha.
    """
    actual = borrador.ajuste(role, posicion)
    salto = episodes.AJUSTES.paso
    pad: dict[str, list[dict]] = {"mover": [], "capa": [], "voltear": [], "reponer": []}

    if role in episodes.ROLES_MOVIBLES:
        for grupo, etiqueta, titulo, mx, my, mc in EMPUJONES:
            pedido = replace(
                actual,
                dx=actual.dx + mx * salto,
                dy=actual.dy + my * salto,
                capa=actual.capa + mc,
            )
            movido = borrador.con_ajuste(role, posicion, pedido)
            if movido.ajuste(role, posicion) == actual:
                continue  # el tope: ese toque no movería nada
            pad[grupo].append(
                {"etiqueta": etiqueta, "titulo": titulo, "url": _url_flujo(paso, movido)}
            )

    if role in episodes.ROLES_VOLTEABLES:
        for campo, etiqueta, titulo in VOLTEOS:
            puesto = getattr(actual, campo)
            pad["voltear"].append(
                {
                    "etiqueta": etiqueta,
                    "titulo": titulo,
                    "puesto": puesto,
                    "url": _url_flujo(
                        paso,
                        borrador.con_ajuste(role, posicion, replace(actual, **{campo: not puesto})),
                    ),
                }
            )

    if actual != episodes.SIN_AJUSTE:
        pad["reponer"].append(
            {
                "etiqueta": "Como estaba",
                "titulo": "Como estaba",
                "url": _url_flujo(paso, borrador.con_ajuste(role, posicion, episodes.SIN_AJUSTE)),
            }
        )
    return pad


def _pads(paso: int, borrador: Borrador, role: str, rotulos: dict[str, str]) -> list[dict]:
    """Un pad por figura elegida de ese rol, en el orden en que se dibujan.

    El título es la etiqueta de la foto cuando hay más de una: con dos pads
    idénticos uno encima del otro, «invitado» e «invitado» no dicen cuál es
    cuál, y el de arriba movería al de abajo sin que nada avisara. `rotulos`
    trae la etiqueta que escribió la persona, no la de `_foto`, que cae al
    nombre del rol cuando no hay ninguna -- y eso volvería a dejar dos títulos
    iguales. Sin etiqueta se numera, que es feo pero distingue.
    """
    elegidas = borrador.seleccion.get(role, [])
    if len(elegidas) <= 1:
        titulos = [ETIQUETAS[role].lower()]
    else:
        figura = FIGURAS.get(role, ETIQUETAS[role].lower())
        titulos = [
            rotulos.get(photo_id) or f"{figura} {posicion + 1}"
            for posicion, photo_id in enumerate(elegidas)
        ]
    return [
        {
            "titulo": titulos[posicion],
            "ajuste": borrador.ajuste(role, posicion),
            "filas": _empujones(paso, borrador, role, posicion),
        }
        for posicion in range(len(elegidas))
    ]


def _url_flujo(paso: int, borrador: Borrador) -> str:
    return "/nueva?" + urlencode(
        [("paso", paso), *borrador.pares(), ("degradado", borrador.degradado)]
    )


def _url_preview(
    borrador: Borrador,
    title: str = "",
    titulo_ancho: int = 0,
    titulo_tamano: int = 0,
    titulo_alto: int = 0,
    titulo_apilado: bool = False,
) -> str:
    """El `<img src>` del paso. Lleva lo mismo que la página, más el título.

    Los campos del título van SIEMPRE al final y SIEMPRE todos, incluso en cero:
    la isla de JS corta la URL por `&titulo_ancho=` y pega los cuatro con lo que
    hay en el formulario. Si alguno faltara a veces, el corte dejaría un valor
    viejo delante del nuevo — y `preview` lee el primero.
    """
    return "/nueva/preview.jpg?" + urlencode(
        [
            *borrador.pares(),
            ("degradado", borrador.degradado),
            ("titulo_ancho", titulo_ancho),
            ("titulo_tamano", titulo_tamano),
            ("titulo_alto", titulo_alto),
            ("titulo_apilado", int(titulo_apilado)),
            ("title", title),
        ]
    )


def _rango_del_ancho() -> dict[str, int]:
    """Los topes y el paso del ancho del título, para el slider.

    Salen del template por la misma razón que las muestras de fondo: el HTML no
    puede tener su propia copia de un número de layout.
    """
    tipografia = episodes.TIPOGRAFIA
    return {
        "min": -tipografia.ancho_menos,
        "max": tipografia.ancho_mas,
        "paso": tipografia.ancho_paso,
    }


def _rango_del_tamano() -> dict[str, int]:
    """Lo mismo para el tamaño de la letra, que es el OTRO mando del título.

    En cero el slider deja el tamaño del template, que es lo que Portada hacía
    antes de que este mando existiera: el auto-ajuste elige el mayor que quepa.
    """
    tipografia = episodes.TIPOGRAFIA
    return {
        "min": -tipografia.tamano_menos,
        "max": tipografia.tamano_mas,
        "paso": tipografia.tamano_paso,
    }


def _rango_del_alto() -> dict[str, int]:
    """Y el tercero: hasta dónde puede crecer el título hacia arriba.

    Positivo es MÁS ALTO, no «más abajo»: los tres sliders dicen cuánto sitio
    hay. Que arriba sea una `y` más chica es cosa del lienzo, y la traducción la
    hace el template en `techo`, no la pantalla.
    """
    tipografia = episodes.TIPOGRAFIA
    return {
        "min": -tipografia.alto_menos,
        "max": tipografia.alto_mas,
        "paso": tipografia.alto_paso,
    }


def _tarjeta_episodio(episode) -> dict:
    """Un episodio listo para pintar en una grilla."""
    return {
        "id": episode.id,
        "titulo": episode.title,
        "creado": episode.created_at[:10],
        # El armado se sirve por la misma ruta de la API: es inmutable y con
        # ETag, asi que el navegador lo cachea de verdad entre pantallas.
        "url": f"/episodes/{episode.id}/assembly/file",
    }


def _recientes(db, user_id: str, tope: int = 3) -> list[dict]:
    """Los ultimos episodios ARMADOS.

    Uno sin armado no se ensena: su tarjeta seria un hueco. No deberia haberlos
    -- el flujo arma al confirmar -- pero un episodio creado por la API JSON si
    puede estar sin armar, y esta pantalla no es quien decide eso.
    """
    return [
        _tarjeta_episodio(episode)
        for episode in episodes.list_episodes(db, user_id=user_id)
        if _tiene_armado(db, user_id, episode.id)
    ][:tope]


def _tiene_armado(db, user_id: str, episode_id: str) -> bool:
    try:
        episodes.latest_assembly(db, user_id=user_id, episode_id=episode_id)
    except AppError:
        return False
    return True


def _marca(db, settings, user_id: str) -> dict[str, dict]:
    """El logo y el marco más recientes. `list_photos` ya ordena por fecha."""
    puesta = {}
    for role in MARCA:
        fotos = library.list_photos(db, user_id=user_id, role=role)
        if fotos:
            puesta[role] = _foto(fotos[0], library.resolve_media(db, settings, fotos[0]))
    return puesta


# --- entrar --------------------------------------------------------------


@router.get("/entrar")
def entrar(request: Request, user_id: OptionalUser, token: str = "") -> Response:
    """Una sola ruta para dos momentos: pedir el enlace, y abrirlo.

    El enlace del correo apunta aquí y no a `/auth/verify`, que solo acepta POST.
    Y esta página no inicia sesión: pinta el token en un campo y hace falta
    pulsar el botón, para que ningún GET cambie estado y un escáner de enlaces
    no gaste el token de un solo uso antes de que lo abras.
    """
    if token:
        return _pagina(request, "entrar_token.html", {"token": token})
    if user_id is not None:
        return RedirectResponse("/", status_code=303)
    return _pagina(request, "entrar.html", {})


@router.post("/entrar")
def pedir_enlace(
    request: Request, db: Db, settings: Config, email: Annotated[str, Form()] = ""
) -> Response:
    """Responde lo mismo exista o no la cuenta (IDENTITY-02).

    Un correo mal escrito acaba en la MISMA pantalla con el MISMO texto. Decirle
    a alguien que se equivocó al teclear estaría bien, pero aquí no cuesta nada
    mantenerlo indistinguible, y lo que cuesta distinguirlo es un oráculo.
    """
    from app.core.middleware import client_ip

    try:
        identity.request_magic_link(
            db, settings, request.app.state.mailer, raw_email=email, ip=client_ip(request)
        )
    except AppError as error:
        if error.code == "IDENTITY_RATE_LIMITED":
            return _pagina(request, "entrar.html", {"error": _mensaje(error)})
    return _pagina(request, "entrar.html", {"enviado": True})


@router.post("/entrar/verificar")
def verificar(
    request: Request, db: Db, settings: Config, token: Annotated[str, Form()] = ""
) -> Response:
    try:
        grant = identity.verify_magic_link(db, settings, token=token)
    except AppError as error:
        return _pagina(request, "entrar.html", {"error": _mensaje(error)})

    respuesta = RedirectResponse("/", status_code=303)
    # La cookie la pone identity: aquí no se sabe cómo se llama ni qué banderas
    # lleva, y eso es exactamente lo que se quiere.
    identity.set_session_cookie(respuesta, request, grant.token)
    return respuesta


@router.post("/salir")
def salir(request: Request, db: Db) -> Response:
    """Cierra la sesión y DEVUELVE UNA REDIRECCIÓN.

    `POST /auth/logout` contesta 204, que es correcto para un cliente y una
    trampa para un formulario: ante un 204 el navegador no navega, así que la
    sesión se cerraba y la pantalla se quedaba igual, como si el botón no
    hiciera nada.
    """
    identity.logout(db, request.cookies.get(identity.COOKIE_NAME))
    respuesta = RedirectResponse("/entrar", status_code=303)
    identity.clear_session_cookie(respuesta)
    return respuesta


# --- inicio y librería ---------------------------------------------------


@router.get("/")
def inicio(request: Request, db: Db, user_id: OptionalUser) -> Response:
    if user_id is None:
        return _a_entrar()
    return _pagina(
        request,
        "inicio.html",
        {
            "stats": library.stats(db, user_id=user_id),
            "roles": ORDEN_ROLES,
            "etiquetas": ETIQUETAS,
            "recientes": _recientes(db, user_id),
        },
    )


@router.get("/episodios")
def historial(request: Request, db: Db, user_id: OptionalUser) -> Response:
    if user_id is None:
        return _a_entrar()
    # `list_episodes` ya ordena del mas reciente al mas antiguo: el orden es del
    # repo, no de esta pantalla.
    episodios = [
        _tarjeta_episodio(e)
        for e in episodes.list_episodes(db, user_id=user_id)
        if _tiene_armado(db, user_id, e.id)
    ]
    return _pagina(request, "historial.html", {"episodios": episodios})


@router.get("/libreria")
def libreria(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    role: str = "",
    nueva: str = "",
) -> Response:
    if user_id is None:
        return _a_entrar()
    contexto = _contexto_libreria(db, settings, user_id, role)
    contexto |= _contexto_modal(request, db, settings, user_id, nueva)
    return _pagina(request, "libreria.html", contexto)


# `def` y no `async def`: dentro corre Pillow, y FastAPI manda las funciones
# síncronas al threadpool. Envolver Pillow en `async def` bloquea el event loop.
@router.post("/libreria/fotos")
def subir_foto(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    role: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    label: Annotated[str, Form()] = "",
    volver: Annotated[str, Form()] = "",
) -> Response:
    if user_id is None:
        return _a_entrar()
    destino = _vuelta_segura(volver, f"/libreria?role={role}")
    try:
        photo = library.add_photo(
            db,
            settings,
            request.app.state.cutout_provider,
            user_id=user_id,
            role=role,
            stream=file.file,
            filename=file.filename,
            declared_mime=file.content_type,
            label=label or None,
        )
    except AppError as error:
        # Se vuelve a pintar la página con el error dentro en vez de redirigir:
        # así el mensaje muere con la respuesta y no acaba pegado en una URL que
        # alguien comparte.
        return _pagina(
            request,
            "libreria.html",
            _contexto_libreria(db, settings, user_id, role, error=_mensaje(error)),
        )
    # Se vuelve a donde se estaba -- si la subida salió del flujo semanal, el
    # paso sigue donde estaba y con lo ya elegido puesto -- y con el modal de la
    # foto recién subida abierto encima.
    return RedirectResponse(_con_modal(destino, photo.id), status_code=303)


# `def` y no `async def`: aquí dentro corre el modelo de recorte.
@router.post("/libreria/fotos/{photo_id}/fondo")
def quitar_fondo(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    photo_id: str,
    volver: Annotated[str, Form()] = "",
) -> Response:
    if user_id is None:
        return _a_entrar()
    destino = _vuelta_segura(volver, "/libreria")
    try:
        library.quitar_fondo(
            db,
            settings,
            request.app.state.cutout_provider,
            user_id=user_id,
            photo_id=photo_id,
        )
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)
    return RedirectResponse(destino, status_code=303)


@router.post("/libreria/fotos/{photo_id}/fondo/deshacer")
def restaurar_fondo(
    request: Request,
    db: Db,
    user_id: OptionalUser,
    photo_id: str,
    volver: Annotated[str, Form()] = "",
) -> Response:
    if user_id is None:
        return _a_entrar()
    destino = _vuelta_segura(volver, "/libreria")
    try:
        library.restaurar_fondo(db, user_id=user_id, photo_id=photo_id)
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)
    return RedirectResponse(destino, status_code=303)


@router.get("/libreria/fotos/{photo_id}")
def detalle_foto(
    request: Request, db: Db, settings: Config, user_id: OptionalUser, photo_id: str
) -> Response:
    if user_id is None:
        return _a_entrar()
    try:
        photo = library.get_photo(db, user_id=user_id, photo_id=photo_id)
        media = library.resolve_media(db, settings, photo)
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)
    return _pagina(request, "foto.html", {"foto": _foto(photo, media), "etiquetas": ETIQUETAS})


# --- la miniatura --------------------------------------------------------


# `def` y no `async def`: aqui dentro corre Pillow.
@router.get("/nueva/preview.jpg")
def preview(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    title: str = "",
    titulo_ancho: int = 0,
    titulo_tamano: int = 0,
    titulo_alto: int = 0,
    titulo_apilado: int = 0,
) -> Response:
    """La miniatura de lo que llevo elegido (SPEC §8.4).

    Todo lo que necesita va en la URL, igual que el resto del flujo: así el
    `<img>` de cada paso apunta a la misma selección que la página, sin estado
    compartido entre los dos que se pueda desincronizar.

    No escribe nada. El episodio se crea al confirmar, no al mirar.

    Sin sesion contesta 401 y no redirige, que es la excepcion a WEB-01: esto no
    es una pantalla, es el `src` de un `<img>`. Mandar una redireccion a HTML
    dentro de una imagen solo consigue que el navegador se trague una pagina
    entera para no poder pintarla. Y ademas el 401 se distingue del 204 de "esa
    seleccion no resuelve", que es lo que permite comprobar que la sesion se
    pide de verdad.
    """
    if user_id is None:
        return Response(status_code=401, headers=SIN_CACHE)

    borrador = _borrador(request.query_params)
    seleccion = borrador.seleccion | {
        role: [foto["id"]] for role, foto in _marca(db, settings, user_id).items()
    }
    try:
        jpeg = episodes.preview(
            db,
            settings,
            user_id=user_id,
            selection=seleccion,
            title=title,
            degradado=borrador.degradado,
            ajustes=borrador.ajustes,
            titulo_ancho=titulo_ancho,
            titulo_tamano=titulo_tamano,
            titulo_alto=titulo_alto,
            titulo_apilado=bool(titulo_apilado),
        )
    except AppError:
        # SPEC §11.4 llevado a la UI: el preview es mejora, nunca dependencia.
        # Un 204 deja el `<img>` con lo último bueno en vez de romper la maqueta
        # con el icono de imagen partida.
        return Response(status_code=204, headers=SIN_CACHE)
    return Response(jpeg, media_type="image/jpeg", headers=SIN_CACHE)


@router.get("/nueva")
def flujo(
    request: Request, db: Db, settings: Config, user_id: OptionalUser, paso: int = 1
) -> Response:
    """Un paso del flujo semanal. El borrador viaja en la URL (ver `_seleccion`)."""
    if user_id is None:
        return _a_entrar()

    paso = max(1, min(paso, len(PASOS)))
    borrador = _borrador(request.query_params)
    seleccion = borrador.seleccion
    role = PASOS[paso - 1]
    marca = _marca(db, settings, user_id)
    con_marca = borrador.con(seleccion=seleccion | {r: [f["id"]] for r, f in marca.items()})

    contexto = {
        "paso": paso,
        "total": len(PASOS),
        "preview": _url_preview(con_marca),
        # El rango del ancho del título sale del template y no de la plantilla:
        # escribirlo en el HTML sería una segunda verdad, y el día que cambie el
        # bloque el slider seguiría ofreciendo el rango viejo.
        "titulo": "",
        "titulo_ancho": 0,
        "titulo_tamano": 0,
        "titulo_alto": 0,
        "titulo_apilado": False,
        "ancho_titulo": _rango_del_ancho(),
        "tamano_titulo": _rango_del_tamano(),
        "alto_titulo": _rango_del_alto(),
        "role": role,
        "etiquetas": ETIQUETAS,
        "ayudas": AYUDAS,
        "seleccion": seleccion,
        "marca": marca,
        "intensidades": episodes.STRENGTHS,
        "intensidad": episodes.DEFAULT_STRENGTH,
        "degradado": borrador.degradado,
        "ajustadas": sorted(borrador.ajustes),
        "atras": _url_flujo(paso - 1, borrador) if paso > 1 else "/",
        "campos": borrador.pares(),
    }

    if role == "titulo":
        return _pagina(request, "flujo_titulo.html", contexto)

    fotos = library.list_photos(db, user_id=user_id, role=role)
    elegidas = set(seleccion.get(role, []))
    tope = episodes.MAXIMOS.get(role, 1)
    tarjetas = []
    for photo in fotos:
        datos = _foto(photo, library.resolve_media(db, settings, photo))
        puesta = photo.id in elegidas
        # Tocar una foto la mete o la saca, y deja la URL en el mismo paso: se
        # ve lo que se acaba de elegir antes de avanzar.
        siguiente = dict(seleccion)
        if puesta:
            restantes = [p for p in siguiente.get(role, []) if p != photo.id]
            siguiente[role] = restantes
            if not restantes:
                siguiente.pop(role)
        else:
            siguiente[role] = ([*siguiente.get(role, []), photo.id])[-tope:]
        datos["puesta"] = puesta
        datos["toque"] = _url_flujo(paso, borrador.con(seleccion=siguiente))
        tarjetas.append(datos)

    contexto |= {
        "aqui": _url_flujo(paso, borrador),
        "fotos": tarjetas,
        "elegidas": len(elegidas),
        "obligatorio": role in episodes.MINIMOS,
        "siguiente": _url_flujo(paso + 1, borrador),
        "roles_con_recorte": library.ROLES_CON_RECORTE,
        # Un pad por figura elegida: dos invitados se ajustan por separado.
        # Sobre un paso vacío no hay ninguno, porque no habría qué mover.
        "pads": _pads(paso, borrador, role, {p.id: p.label or "" for p in fotos}),
        # Las dos opciones de fondo, como enlaces al MISMO paso: tocarlas no
        # avanza, repinta. Son enlaces y no radios porque el borrador vive en la
        # URL -- así elegir fondo se deshace con «atrás», como todo lo demás.
        "opciones_fondo": [
            {
                "nombre": nombre,
                "muestra": _muestra(nombre),
                "puesto": nombre == borrador.degradado,
                "url": _url_flujo(paso, borrador.con(degradado=nombre)),
            }
            for nombre in episodes.DEGRADADOS
        ]
        if role == "fondo"
        else [],
    }
    contexto |= _contexto_modal(
        request, db, settings, user_id, request.query_params.get("nueva", "")
    )
    return _pagina(request, "flujo_fotos.html", contexto)


# `def` y no `async def`: aquí dentro se arma la miniatura con Pillow.
@router.post("/nueva")
def crear(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    title: Annotated[str, Form()] = "",
    strength: Annotated[str, Form()] = episodes.DEFAULT_STRENGTH,
    degradado: Annotated[str, Form()] = episodes.DEGRADADO_POR_DEFECTO,
    titulo_ancho: Annotated[int, Form()] = 0,
    titulo_tamano: Annotated[int, Form()] = 0,
    titulo_alto: Annotated[int, Form()] = 0,
    # Una casilla sin marcar no manda «off»: no manda nada. Se lee la PRESENCIA
    # del campo, nunca su valor -- un `== "on"` funcionaría de casualidad hasta
    # el día que alguien le cambie el `value`.
    titulo_apilado: Annotated[str, Form()] = "",
    # Los empujones viajan como texto, uno por rol movido: `conductor:40,-20,1`.
    ajuste: Annotated[list[str], Form()] = [],  # noqa: B006
    # Los roles se declaran uno a uno en vez de leer el formulario entero: en una
    # ruta síncrona no se puede `await request.form()`, y además así la firma
    # dice exactamente qué acepta este endpoint. Lo que no está aquí no entra
    # -- que es la mitad de lo que WEB-18 comprueba.
    conductor: Annotated[list[str], Form()] = [],  # noqa: B006
    invitado: Annotated[list[str], Form()] = [],  # noqa: B006
    fondo: Annotated[list[str], Form()] = [],  # noqa: B006
    objeto: Annotated[list[str], Form()] = [],  # noqa: B006
) -> Response:
    """Crea el episodio y lo arma de una vez.

    De una vez porque no hay nada que esperar: con `NoopFinisher` el armado tarda
    ~300 ms, así que la pantalla «Generando» del prototipo no tendría nada que
    enseñar. Cuando exista la pasada de IA, ahí sí habrá dos momentos.
    """
    if user_id is None:
        return _a_entrar()

    formulario = {
        role: [v for v in valores if v][: episodes.MAXIMOS.get(role, 1)]
        for role, valores in (
            ("conductor", conductor),
            ("invitado", invitado),
            ("fondo", fondo),
            ("objeto", objeto),
        )
        if any(valores)
    }
    marca = _marca(db, settings, user_id)
    seleccion = dict(formulario) | {role: [foto["id"]] for role, foto in marca.items()}
    ajustes = _lee_ajustes(ajuste)

    try:
        episode = episodes.create_episode(
            db,
            user_id=user_id,
            title=title,
            selection=seleccion,
            strength=strength,
            degradado=degradado,
            ajustes=ajustes,
            titulo_ancho=titulo_ancho,
            titulo_tamano=titulo_tamano,
            titulo_alto=titulo_alto,
            titulo_apilado=bool(titulo_apilado),
        )
        episodes.build_assembly(
            db,
            settings,
            request.app.state.finisher,
            user_id=user_id,
            episode_id=episode.id,
        )
    except AppError as error:
        # Se vuelve al último paso con el error puesto, en vez de a una página de
        # fallo: lo elegido sigue ahí y solo falta corregir una cosa.
        fallido = Borrador(seleccion=formulario, degradado=degradado, ajustes=ajustes)
        return _pagina(
            request,
            "flujo_titulo.html",
            {
                "paso": len(PASOS),
                "total": len(PASOS),
                "role": "titulo",
                "etiquetas": ETIQUETAS,
                "ayudas": AYUDAS,
                "seleccion": formulario,
                "marca": marca,
                "intensidades": episodes.STRENGTHS,
                "intensidad": strength,
                "degradado": degradado,
                "ajustadas": sorted(ajustes),
                "titulo": title,
                # Lo elegido vuelve puesto: enterarte de que falta algo y perder
                # de paso cómo habías dejado el título sería dos castigos.
                "titulo_ancho": titulo_ancho,
                "titulo_tamano": titulo_tamano,
                "titulo_alto": titulo_alto,
                "titulo_apilado": bool(titulo_apilado),
                "ancho_titulo": _rango_del_ancho(),
                "tamano_titulo": _rango_del_tamano(),
                "alto_titulo": _rango_del_alto(),
                "atras": _url_flujo(len(PASOS) - 1, fallido),
                "campos": fallido.pares(),
                "preview": _url_preview(
                    fallido.con(
                        seleccion=fallido.seleccion | {r: [f["id"]] for r, f in marca.items()}
                    ),
                    title,
                    titulo_ancho,
                    titulo_tamano,
                    titulo_alto,
                    bool(titulo_apilado),
                ),
                "error": _mensaje(error),
            },
        )
    return RedirectResponse(f"/episodios/{episode.id}", status_code=303)


@router.get("/episodios/{episode_id}")
def resultado(
    request: Request, db: Db, settings: Config, user_id: OptionalUser, episode_id: str
) -> Response:
    if user_id is None:
        return _a_entrar()
    try:
        episode = episodes.get_episode(db, user_id=user_id, episode_id=episode_id)
        armado = episodes.latest_assembly(db, user_id=user_id, episode_id=episode_id)
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)

    usadas = []
    for role in ORDEN_ROLES:
        for photo_id in episode.slots.get(role, []):
            try:
                photo = library.get_photo(db, user_id=user_id, photo_id=photo_id)
            except AppError:
                continue  # borrada de la librería: el episodio sigue valiendo
            usadas.append((ETIQUETAS[role], photo.label or ETIQUETAS[role].lower()))

    armado_borrador = Borrador(
        seleccion=episode.slots, degradado=episode.degradado, ajustes=episode.ajustes
    )
    return _pagina(
        request,
        "resultado.html",
        {
            "episode": episode,
            "armado": armado,
            "usadas": usadas,
            "editar": _url_flujo(1, armado_borrador),
            "preview": _url_preview(armado_borrador, episode.title),
            # Se dice cuál fondo se usó, por lo mismo que se dice la marca: una
            # entrada invisible en el checksum del armado sería peor que un dato
            # de más. Solo cuando se ve, que es cuando no hay foto de fondo.
            "fondo_por_defecto": "" if episode.slots.get("fondo") else episode.degradado,
            "ajustadas": sorted(episode.ajustes),
        },
    )


# `def` y no `async def`: se vuelve a componer con Pillow.
@router.post("/episodios/{episode_id}/titulo")
def corregir_titulo(
    request: Request,
    db: Db,
    settings: Config,
    user_id: OptionalUser,
    episode_id: str,
    title: Annotated[str, Form()] = "",
) -> Response:
    """Corrige el título y vuelve a componer (SPEC §7③).

    Cuesta ~24 ms y no una regeneración, porque el título es *overlay*: se pega
    sobre la misma base, que sigue en la caché. Es la propiedad que hace que el
    producto tolere equivocarse, y `WEB-31` la vigila.
    """
    if user_id is None:
        return _a_entrar()
    try:
        episodes.set_title(db, user_id=user_id, episode_id=episode_id, title=title)
        episodes.build_assembly(
            db,
            settings,
            request.app.state.finisher,
            user_id=user_id,
            episode_id=episode_id,
        )
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)
    return RedirectResponse(f"/episodios/{episode_id}", status_code=303)


@router.post("/libreria/fotos/{photo_id}/borrar")
def borrar_foto(request: Request, db: Db, user_id: OptionalUser, photo_id: str) -> Response:
    """SPEC §11.11: borrar son dos pasos. Este es el segundo.

    El primero es entrar al detalle. La grilla no tiene este formulario, así que
    no hay forma de borrar de un toque desde una pantalla llena de miniaturas.
    """
    if user_id is None:
        return _a_entrar()
    try:
        library.delete_photo(db, user_id=user_id, photo_id=photo_id)
    except AppError as error:
        return _pagina(request, "vacio.html", {"mensaje": _mensaje(error)}, status=error.status)
    return RedirectResponse("/libreria", status_code=303)
