"""Criterios de `specs/web.md`: las pantallas.

Se prueban con el mismo `TestClient` sincrono que el resto del proyecto. Esa es
la razon entera de que el frontend sea HTML del servidor: un criterio de pantalla
es un test que corre en `make test`, en segundos, en el mismo CI. Con una SPA
esto pediria un navegador, y "criterio -> test en rojo -> implementacion" se
moriria justo en la capa nueva.
"""

import io
import re

from fastapi.testclient import TestClient

OTRO_EMAIL = "otra@ejemplo.cl"


def _pedir_enlace(client, email="paula@ejemplo.cl"):
    return client.post("/entrar", data={"email": email})


def _enlace(client) -> str:
    correo = client.app.state.mailer.sent[-1].text
    return re.search(r"https?://\S+", correo).group(0)


def _entrar(client, email="paula@ejemplo.cl"):
    """El recorrido real: pedir el enlace, abrirlo, pulsar el boton."""
    _pedir_enlace(client, email)
    token = _enlace(client).rsplit("=", 1)[-1]
    pagina = client.get("/entrar", params={"token": token})
    assert pagina.status_code == 200, pagina.text[:300]
    respuesta = client.post("/entrar/verificar", data={"token": token}, follow_redirects=False)
    assert respuesta.status_code in (302, 303), respuesta.text[:300]
    return respuesta


def _subir(client, imagen, *, role="conductor", nombre="foto.png", mime="image/png", **campos):
    return client.post(
        "/libreria/fotos",
        data={"role": role, **campos},
        files={"file": (nombre, imagen(), mime)},
        follow_redirects=False,
    )


# --- entrar --------------------------------------------------------------


def test_web_01_sin_sesion_lleva_a_entrar(client):
    respuesta = client.get("/libreria", follow_redirects=False)

    assert respuesta.status_code in (302, 303), "una pantalla no puede contestar 401 en JSON"
    assert respuesta.headers["location"].startswith("/entrar")
    assert "application/json" not in respuesta.headers.get("content-type", "")


def test_web_02_pedir_el_enlace_no_revela_si_la_cuenta_existe(client):
    """Misma respuesta byte a byte, exista o no el usuario (como IDENTITY-02)."""
    nueva = _pedir_enlace(client, "nadie@ejemplo.cl")
    existente = _pedir_enlace(client, "nadie@ejemplo.cl")

    assert nueva.status_code == existente.status_code == 200
    assert nueva.text == existente.text


def test_web_03_abrir_el_enlace_y_pulsar_entrar_inicia_sesion(client):
    respuesta = _entrar(client)

    assert respuesta.headers["location"] == "/"
    assert client.get("/auth/me").status_code == 200
    assert client.get("/libreria").status_code == 200


def test_web_04_un_enlace_gastado_lo_dice_la_pagina(client):
    _entrar(client)
    token = _enlace(client).rsplit("=", 1)[-1]

    # El mismo token otra vez: ya se uso.
    respuesta = client.post("/entrar/verificar", data={"token": token}, follow_redirects=False)

    assert respuesta.status_code == 200, "un enlace gastado no es una pagina de error crudo"
    assert "text/html" in respuesta.headers["content-type"]
    assert "Traceback" not in respuesta.text
    assert '"error"' not in respuesta.text, "salio el JSON de la API en vez de una pagina"
    assert "otro enlace" in respuesta.text.lower()


# --- la libreria ---------------------------------------------------------


def test_web_05_subo_una_foto_y_aparece_en_su_rol(client, imagen):
    _entrar(client)

    assert _subir(client, imagen, role="marco", label="marco del show").status_code in (302, 303)

    pagina = client.get("/libreria", params={"role": "marco"})
    assert pagina.status_code == 200
    assert "marco del show" in pagina.text


def test_web_06_la_grilla_muestra_la_foto(client, imagen):
    _entrar(client)
    _subir(client, imagen)

    pagina = client.get("/libreria").text
    urls = re.findall(r'src="(/photos/[^"]+/file)"', pagina)
    assert urls, "la grilla no enlaza el archivo de ninguna foto"

    archivo = client.get(urls[0])
    assert archivo.status_code == 200
    assert archivo.headers["content-type"] == "image/png"


def test_web_07_no_veo_la_libreria_de_otra_persona(client, imagen):
    _entrar(client)
    _subir(client, imagen, label="mi foto privada")
    client.post("/auth/logout")
    _entrar(client, OTRO_EMAIL)

    assert "mi foto privada" not in client.get("/libreria").text


def test_web_08_un_archivo_que_no_es_imagen_da_un_error_legible(client, imagen):
    _entrar(client)

    respuesta = client.post(
        "/libreria/fotos",
        data={"role": "conductor"},
        files={"file": ("notas.txt", b"esto no es una imagen", "text/plain")},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
    assert "Traceback" not in respuesta.text
    assert "INTAKE_NOT_AN_IMAGE" not in respuesta.text, "el codigo de error no es para leerlo"
    assert "imagen" in respuesta.text.lower()


def test_web_09_borrar_son_dos_pasos(client, imagen):
    """SPEC 11.11: nada destructivo sin revision. La grilla no borra."""
    _entrar(client)
    _subir(client, imagen)
    photo_id = client.get("/photos").json()["photos"][0]["id"]

    grilla = client.get("/libreria").text
    assert f'action="/libreria/fotos/{photo_id}/borrar"' not in grilla, (
        "la grilla borra de un toque: falta el paso de revision"
    )

    detalle = client.get(f"/libreria/fotos/{photo_id}")
    assert detalle.status_code == 200
    assert f"/libreria/fotos/{photo_id}/borrar" in detalle.text

    borrado = client.post(f"/libreria/fotos/{photo_id}/borrar", follow_redirects=True)
    assert borrado.status_code == 200
    assert client.get(f"/photos/{photo_id}").status_code == 404


# --- la forma de las paginas ---------------------------------------------


def test_web_10_las_paginas_privadas_no_se_cachean(client, imagen):
    _entrar(client)
    _subir(client, imagen)

    for ruta in ("/", "/libreria"):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 200, ruta
        assert "no-store" in respuesta.headers.get("cache-control", ""), ruta


def test_web_11_ninguna_pagina_filtra_el_token_ni_la_cookie(client):
    _pedir_enlace(client)
    token = _enlace(client).rsplit("=", 1)[-1]

    # La pagina del enlace necesita el token para poder postearlo, y va en un
    # campo del formulario. Lo que no puede es acabar en una URL que se
    # comparte, ni quedarse pegado despues de canjearlo.
    client.post("/entrar/verificar", data={"token": token})
    cookie = client.cookies.get("portada_session")
    assert cookie

    for ruta in ("/", "/libreria"):
        cuerpo = client.get(ruta).text
        assert token not in cuerpo, f"{ruta} filtra el token del enlace"
        assert cookie not in cuerpo, f"{ruta} filtra la cookie de sesion"


def test_web_12_salir_cierra_la_sesion_y_lleva_a_entrar(client, imagen):
    """`POST /auth/logout` devuelve 204, y un formulario HTML contra un 204 NO
    navega: la sesión se cerraba y la pantalla se quedaba igual, como si el
    botón no hiciera nada. Un 204 es correcto para un cliente y es una pantalla
    congelada para una persona."""
    _entrar(client)

    respuesta = client.post("/salir", follow_redirects=False)

    assert respuesta.status_code in (302, 303), "el navegador se queda donde estaba"
    assert respuesta.headers["location"] == "/entrar"
    assert client.get("/auth/me").status_code == 401, "la sesión sigue viva"
    assert client.get("/libreria", follow_redirects=False).status_code in (302, 303)


# --- la miniatura --------------------------------------------------------


def _marco_png():
    """Un marco DE VERDAD: borde y banda inferior, centro transparente.

    Con un rectangulo opaco -- que es lo que da el fixture `imagen` -- el marco
    se estira a sangre completa y tapa la miniatura entera: el PNG final sale
    siendo una mancha de un color, identica pase lo que pase debajo. Cualquier
    test que compare pixeles estaria comparando nada. Nos paso.
    """
    import io

    from PIL import Image, ImageDraw

    lienzo = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rectangle([0, 0, 1279, 719], outline=(233, 40, 39, 255), width=16)
    dibujo.rectangle([0, 552, 1279, 719], fill=(233, 40, 39, 255))
    buffer = io.BytesIO()
    lienzo.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _libreria_completa(client, imagen):
    """Una libreria con un asset de cada rol, como despues del setup."""
    ids = {}
    for role in ("conductor", "invitado", "fondo", "objeto", "logo", "marco"):
        archivo = _marco_png() if role == "marco" else imagen(color=(len(role) * 30 % 255, 70, 120))
        respuesta = client.post(
            "/libreria/fotos",
            data={"role": role, "label": f"{role} de prueba"},
            files={"file": (f"{role}.png", archivo)},
            follow_redirects=False,
        )
        assert respuesta.status_code in (302, 303), respuesta.text[:300]
        ids[role] = client.get("/photos", params={"role": role}).json()["photos"][0]["id"]
    return ids


def _armar(client, seleccion, title="LA VERDAD SOBRE EL CASO", **extra):
    datos = {"title": title, "strength": "medio", **extra}
    for role, valores in seleccion.items():
        datos[role] = valores
    return client.post("/nueva", data=datos, follow_redirects=False)


def test_web_13_el_flujo_entero_deja_un_png_descargable(client, imagen):
    from PIL import Image

    _entrar(client)
    ids = _libreria_completa(client, imagen)

    # Paso 1: la grilla del conductor, con sus fotos.
    paso1 = client.get("/nueva")
    assert paso1.status_code == 200
    assert ids["conductor"] in paso1.text

    creado = _armar(client, {"conductor": ids["conductor"], "invitado": ids["invitado"]})
    assert creado.status_code in (302, 303), creado.text[:400]
    destino = creado.headers["location"]

    resultado = client.get(destino)
    assert resultado.status_code == 200
    descarga = re.search(r'href="(/episodes/[^"]+/assembly/file)"', resultado.text)
    assert descarga, "el resultado no ofrece la descarga"

    png = client.get(descarga.group(1))
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(png.content)).size == (1280, 720)


def test_web_14_un_paso_opcional_se_omite(client, imagen):
    """SPEC 11.8: la ausencia es una entrada valida, no un error."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    creado = _armar(client, {"conductor": ids["conductor"]})

    assert creado.status_code in (302, 303), creado.text[:400]
    assert client.get(creado.headers["location"]).status_code == 200


def test_web_15_sin_conductor_no_se_avanza_y_se_dice_por_que(client, imagen):
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    creado = _armar(client, {"invitado": ids["invitado"]})

    assert creado.status_code == 200, "dejo crear un episodio sin conductor"
    assert "text/html" in creado.headers["content-type"]
    assert "conductor" in creado.text.lower()
    assert "EPISODES_CONDUCTOR_REQUIRED" not in creado.text


def test_web_16_la_marca_va_puesta_sin_pedirla(client, imagen):
    """SPEC 8: subir el logo es setup, no trabajo semanal. El flujo lo da puesto,
    pero lo DICE: una entrada invisible en el checksum seria peor que pedirla."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    ultimo = client.get("/nueva", params={"paso": 5, "conductor": ids["conductor"]})
    assert ultimo.status_code == 200
    assert "logo de prueba" in ultimo.text, "el resumen no dice que logo se usa"
    assert "marco de prueba" in ultimo.text, "el resumen no dice que marco se usa"

    creado = _armar(client, {"conductor": ids["conductor"]})
    episode_id = creado.headers["location"].rsplit("/", 1)[-1]
    seleccion = client.get(f"/episodes/{episode_id}").json()["selection"]
    assert seleccion["logo"] == [ids["logo"]]
    assert seleccion["marco"] == [ids["marco"]]


def test_web_17_el_titulo_llega_al_armado(client, imagen):
    """Llega a los PIXELES, no solo a la pantalla.

    La primera version de este test buscaba el titulo en mayusculas dentro del
    HTML del resultado, y eso solo probaba que la UI lo repetia -- se rompio al
    dejar de repetirlo, sin que nada del producto cambiara. Lo que hay que
    comprobar es que dos titulos distintos dan dos miniaturas distintas.
    """
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    def _armado(title):
        creado = _armar(client, {"conductor": ids["conductor"]}, title=title)
        episode_id = creado.headers["location"].rsplit("/", 1)[-1]
        return (
            client.get(f"/episodes/{episode_id}").json()["title"],
            client.get(f"/episodes/{episode_id}/assembly/file").content,
            client.get(creado.headers["location"]).text,
        )

    guardado, png, pagina = _armado("nadie esperaba esta respuesta")
    _, otro_png, _ = _armado("otra cosa completamente distinta")

    assert guardado == "nadie esperaba esta respuesta", "el titulo se transformo por el camino"
    assert png != otro_png, "el titulo no llega a la miniatura"
    # Y la pantalla lo ensena tal cual se escribio, para poder corregirlo.
    assert "nadie esperaba esta respuesta" in pagina


def test_web_18_la_intensidad_es_la_unica_perilla(client, imagen):
    """SPEC 11.3: un modelo devuelve un parametro validado, nunca prosa que se
    pega en algun sitio. El paso 6 del prototipo -- "instrucciones
    personalizadas", con presets tipo "colores saturados" -- es justo lo que la
    regla prohibe. Si algun dia vuelve, este test lo dice."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    limpio = _armar(client, {"conductor": ids["conductor"]})
    con_instrucciones = _armar(
        client,
        {"conductor": ids["conductor"]},
        instructions="conductor a la izquierda, colores saturados, flecha senalando",
    )

    def _episodio(respuesta):
        episode_id = respuesta.headers["location"].rsplit("/", 1)[-1]
        return (
            client.get(f"/episodes/{episode_id}").json()["title"],
            client.get(f"/episodes/{episode_id}/assembly/file").content,
        )

    titulo_limpio, png_limpio = _episodio(limpio)
    titulo_sucio, png_sucio = _episodio(con_instrucciones)

    # El titulo es lo primero que cambiaria si el texto libre entrara por algun
    # sitio, y se comprueba aparte de los pixeles: comparar solo PNG deja pasar
    # cualquier bug que no llegue a dibujarse.
    assert titulo_limpio == titulo_sucio, "el texto libre se coló en el título"
    assert png_limpio == png_sucio, "un texto libre cambió la miniatura"

    ultimo = client.get("/nueva", params={"paso": 5, "conductor": ids["conductor"]}).text
    for perilla in ("suave", "medio", "fuerte"):
        assert perilla in ultimo.lower()


def test_web_19_volver_atras_conserva_lo_elegido(client, imagen):
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    paso3 = client.get(
        "/nueva",
        params={"paso": 3, "conductor": ids["conductor"], "invitado": ids["invitado"]},
    )

    assert paso3.status_code == 200
    # Volver al paso 1 tiene que llevarse la seleccion consigo.
    atras = re.search(r'href="(/nueva\?[^"]*paso=2[^"]*)"', paso3.text)
    assert atras, "no hay forma de volver al paso anterior"
    assert ids["conductor"] in atras.group(1)


def test_web_20_subo_al_invitado_sin_salirme_del_flujo(client, imagen):
    """SPEC 8 paso 3: el invitado se sube CADA SEMANA. Si para eso hay que salir
    a la librería, se pierde lo ya elegido y el flujo de seis pasos se convierte
    en un viaje de ida y vuelta."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    paso = f"/nueva?paso=2&conductor={ids['conductor']}"

    pagina = client.get(paso)
    assert 'name="volver"' in pagina.text, "el paso no ofrece subir sin salirse"

    subida = client.post(
        "/libreria/fotos",
        data={"role": "invitado", "label": "invitada nueva", "volver": paso},
        files={"file": ("nueva.png", imagen(color=(9, 200, 90)))},
        follow_redirects=False,
    )

    assert subida.status_code in (302, 303)
    destino = subida.headers["location"]
    # La vuelta trae `&nueva=` para abrir el modal ENCIMA del paso. Eso no es
    # salirse del flujo: el paso y el borrador siguen intactos, y es lo que se
    # compara. Comparar la URL entera haria fallar este test cada vez que el
    # modal agregue algo, sin que nada del flujo haya cambiado.
    sin_modal = "&".join(p for p in destino.split("&") if not p.startswith("nueva="))
    assert sin_modal == paso, "me sacó del flujo"
    assert "nueva=" in destino, "subir no abrió el modal de la foto recién subida"
    vuelta = client.get(destino)
    assert "invitada nueva" in vuelta.text
    assert ids["conductor"] in vuelta.text, "se perdió lo ya elegido"


def test_web_21_la_vuelta_despues_de_subir_no_sale_de_portada(client, imagen):
    """`volver` viene del cliente, así que es una redirección abierta esperando
    a que alguien la use: basta un enlace a Portada con `volver=https://…`."""
    _entrar(client)

    for fuera in ("https://ejemplo.cl/robo", "//ejemplo.cl/robo", "http://ejemplo.cl"):
        subida = client.post(
            "/libreria/fotos",
            data={"role": "conductor", "volver": fuera},
            files={"file": ("f.png", imagen())},
            follow_redirects=False,
        )
        destino = subida.headers["location"]
        assert destino.startswith("/") and not destino.startswith("//"), (
            f"redirección abierta con volver={fuera!r} -> {destino!r}"
        )


def test_web_37_el_fondo_por_defecto_se_elige_en_su_paso(client, imagen):
    """Claro u oscuro, sin salir del paso y sin perder lo elegido.

    Es la misma mecanica que elegir una foto: un enlace al MISMO paso con el
    borrador entero puesto. Por eso se comprueba que la eleccion sigue viva tres
    pantallas mas adelante, que es donde se arma.
    """
    from PIL import Image

    _entrar(client)
    ids = _libreria_completa(client, imagen)

    paso_fondo = client.get(
        "/nueva", params={"paso": 3, "conductor": ids["conductor"], "degradado": "claro"}
    )
    assert paso_fondo.status_code == 200
    enlace = re.search(r'href="(/nueva\?[^"]*degradado=oscuro[^"]*)"', paso_fondo.text)
    assert enlace, "el paso del fondo no ofrece el degradado oscuro"

    # `&amp;` es lo correcto en un atributo HTML, y no es lo que se pide por HTTP.
    oscuro = client.get(enlace.group(1).replace("&amp;", "&"))
    assert oscuro.status_code == 200
    assert ids["conductor"] in oscuro.text, "elegir el fondo se llevo por delante lo elegido"
    assert "paso=4" in oscuro.text, "elegir el fondo saco del paso en vez de repintarlo"
    # El preview de esa pantalla pide el fondo elegido: es lo que hace que la
    # eleccion se VEA antes de armar.
    assert re.search(r'id="preview" src="[^"]*degradado=oscuro', oscuro.text)

    # Y sobrevive hasta el ultimo paso, que es quien manda el formulario.
    ultimo = client.get(
        "/nueva", params={"paso": 5, "conductor": ids["conductor"], "degradado": "oscuro"}
    )
    assert 'name="degradado" value="oscuro"' in ultimo.text

    def _esquina(degradado):
        creado = _armar(client, {"conductor": ids["conductor"]}, degradado=degradado)
        assert creado.status_code in (302, 303), creado.text[:400]
        episode_id = creado.headers["location"].rsplit("/", 1)[-1]
        png = client.get(f"/episodes/{episode_id}/assembly/file").content
        # (400, 30) y no una esquina: el flujo pone el marco a sangre completa,
        # y sus 16px de borde son lo que se mide en la esquina, pase lo que pase
        # debajo. Ahi arriba no llegan ni el logo, ni el titulo, ni las figuras:
        # es degradado puro.
        return Image.open(io.BytesIO(png)).convert("RGB").getpixel((400, 30))

    assert sum(_esquina("claro")) > sum(_esquina("oscuro")) + 200, (
        "el fondo elegido no llego a la miniatura"
    )


# --- el preview en vivo --------------------------------------------------


def test_web_22_cada_paso_ensena_el_preview(client, imagen):
    """SPEC 8.4 y 9: la miniatura se ve mientras se elige, fijada sobre el paso.
    Por eso armar deja de ser una revelacion."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    from PIL import Image

    for paso, params in (
        (1, {}),
        (2, {"conductor": ids["conductor"]}),
        (5, {"conductor": ids["conductor"], "invitado": ids["invitado"]}),
    ):
        pagina = client.get("/nueva", params={"paso": paso, **params})
        assert pagina.status_code == 200, paso
        src = re.search(r'id="preview" src="([^"]+)"', pagina.text)
        assert src, f"el paso {paso} no ensena preview"

        imagen_preview = client.get(src.group(1).replace("&amp;", "&"))
        assert imagen_preview.status_code == 200, paso
        assert imagen_preview.headers["content-type"] == "image/jpeg"
        abierta = Image.open(io.BytesIO(imagen_preview.content))
        assert abierta.size == (640, 360), paso
        # Y lleva puesto lo elegido: la marca va siempre, sin pedirla.
        for photo_id in params.values():
            assert photo_id in src.group(1)


def test_web_23_el_preview_refleja_el_titulo(client, imagen):
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    base = {"conductor": ids["conductor"]}

    sin_titulo = client.get("/nueva/preview.jpg", params={**base, "title": ""})
    con_titulo = client.get("/nueva/preview.jpg", params={**base, "title": "UN TITULO LARGO"})

    assert sin_titulo.status_code == con_titulo.status_code == 200
    assert sin_titulo.content != con_titulo.content, "el titulo no llega al preview"

    # Y el paso del titulo trae con que repintar sin recargar la pagina.
    paso = client.get("/nueva", params={"paso": 5, **base}).text
    assert 'id="titulo"' in paso and "addEventListener" in paso


def test_web_24_no_puedo_pedir_el_preview_con_la_foto_de_otro(client, imagen):
    """Dos formas de que la foto no sea tuya, y las dos cuentan.

    La primera -- sesion de otra persona -- es dificil de romper aqui: no existe
    ninguna funcion que busque una foto solo por su id (ver `library/repo.py`),
    asi que `get_photo` filtra por usuario siempre. La segunda -- sin sesion --
    depende de que la ruta se acuerde de pedirla, y esa SI se puede olvidar.
    """
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    parametros = {"conductor": ids["conductor"]}

    sin_sesion = TestClient(client.app).get(
        "/nueva/preview.jpg", params=parametros, follow_redirects=False
    )
    assert sin_sesion.status_code == 401, "sirvio un preview sin sesion"
    assert sin_sesion.content[:2] != b"\xff\xd8"

    client.post("/salir")
    _entrar(client, OTRO_EMAIL)
    de_otra = client.get("/nueva/preview.jpg", params=parametros)

    assert de_otra.status_code != 200, "me dio un preview con la foto de otra persona"
    assert de_otra.content[:2] != b"\xff\xd8", "devolvio un JPEG igualmente"


def test_web_25_si_el_preview_falla_la_pantalla_no_se_rompe(client, imagen):
    """SPEC 11.4 llevado a la UI: el preview es mejora, nunca dependencia."""
    _entrar(client)

    # Un id inventado: la seleccion no resuelve.
    respuesta = client.get("/nueva/preview.jpg", params={"conductor": "no-existe"})

    assert respuesta.status_code in (204, 404)
    assert "text/html" not in respuesta.headers.get("content-type", "")
    assert b"Traceback" not in respuesta.content

    # Y el paso sigue pintandose: el preview que falla no se lleva la pagina.
    paso = client.get("/nueva", params={"conductor": "no-existe"})
    assert paso.status_code == 200
    assert 'id="preview"' in paso.text
    assert "onerror" in paso.text, "un preview roto dejaria el icono de imagen partida"


# --- inicio e historial --------------------------------------------------


def _un_episodio(client, imagen, title="LA VERDAD SOBRE EL CASO"):
    ids = _libreria_completa(client, imagen)
    creado = _armar(client, {"conductor": ids["conductor"]}, title=title)
    assert creado.status_code in (302, 303), creado.text[:300]
    return creado.headers["location"].rsplit("/", 1)[-1], ids


def test_web_26_inicio_ofrece_empezar_una_miniatura(client, imagen):
    _entrar(client)

    inicio = client.get("/")

    assert inicio.status_code == 200
    assert 'href="/nueva"' in inicio.text, "no hay por donde empezar el trabajo de la semana"


def test_web_27_inicio_muestra_los_recientes_y_la_libreria(client, imagen):
    _entrar(client)
    episode_id, _ = _un_episodio(client, imagen, title="SE FUE DE LA ENTREVISTA")

    inicio = client.get("/").text

    assert "SE FUE DE LA ENTREVISTA" in inicio
    assert f"/episodios/{episode_id}" in inicio
    # Con su miniatura, no solo el titulo: un historial sin imagenes no sirve
    # para encontrar nada.
    assert f"/episodes/{episode_id}/assembly/file" in inicio
    assert "Librería" in inicio


def test_web_28_el_historial_va_del_mas_reciente_al_mas_antiguo(client, imagen):
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    for title in ("EL PRIMERO", "EL SEGUNDO", "EL TERCERO"):
        _armar(client, {"conductor": ids["conductor"]}, title=title)

    historial = client.get("/episodios").text
    posiciones = [historial.index(t) for t in ("EL TERCERO", "EL SEGUNDO", "EL PRIMERO")]
    assert posiciones == sorted(posiciones), "el historial no esta del mas reciente al mas antiguo"

    # Y solo los mios.
    client.post("/salir")
    _entrar(client, OTRO_EMAIL)
    for title in ("EL PRIMERO", "EL SEGUNDO", "EL TERCERO"):
        assert title not in client.get("/episodios").text


def test_web_29_sin_episodios_inicio_lo_dice(client, imagen):
    _entrar(client)

    inicio = client.get("/")

    assert inicio.status_code == 200
    # Se comprueba el bloque, no la frase: un test que fija la redaccion se
    # rompe al corregir una tilde y no dice nada del comportamiento.
    assert 'class="vacio"' in inicio.text, (
        "una pantalla vacia sin explicacion parece una pantalla rota"
    )
    assert "/episodios/" not in inicio.text, "listo un episodio que no existe"


# --- corregir el titulo --------------------------------------------------


def test_web_30_puedo_corregir_el_titulo(client, imagen):
    _entrar(client)
    episode_id, _ = _un_episodio(client, imagen, title="LA VERDAD SOBER EL CASO")

    corregido = client.post(
        f"/episodios/{episode_id}/titulo",
        data={"title": "LA VERDAD SOBRE EL CASO"},
        follow_redirects=False,
    )

    assert corregido.status_code in (302, 303), corregido.text[:300]
    resultado = client.get(f"/episodios/{episode_id}")
    assert "LA VERDAD SOBRE EL CASO" in resultado.text
    assert "SOBER" not in resultado.text
    assert client.get(f"/episodes/{episode_id}").json()["title"] == "LA VERDAD SOBRE EL CASO"


def test_web_31_corregir_el_titulo_reusa_la_base(client, imagen):
    """SPEC 7 paso 3: el titulo se vuelve a componer sobre la MISMA base, asi que
    una errata no cuesta una regeneracion. Es la propiedad que hace que el
    producto tolere equivocarse, y sin este test es solo una intencion."""
    from app.domains.composition import api as composition

    _entrar(client)
    episode_id, _ = _un_episodio(client, imagen, title="CON ERRATA")

    composition.BASES.clear()
    client.post(f"/episodios/{episode_id}/titulo", data={"title": "SIN ERRATA"})
    dibujadas = composition.BASES.dibujadas

    client.post(f"/episodios/{episode_id}/titulo", data={"title": "OTRA VEZ DISTINTO"})

    assert composition.BASES.dibujadas == dibujadas, "recompuso la base por un titulo"
    assert "OTRA VEZ DISTINTO" in client.get(f"/episodios/{episode_id}").text


def test_web_32_no_puedo_tocar_el_episodio_de_otro(client, imagen):
    _entrar(client)
    episode_id, _ = _un_episodio(client, imagen, title="MI EPISODIO")
    client.post("/salir")
    _entrar(client, OTRO_EMAIL)

    ajeno = client.post(
        f"/episodios/{episode_id}/titulo",
        data={"title": "SECUESTRADO"},
        follow_redirects=False,
    )

    assert ajeno.status_code not in (302, 303), "dejo cambiar el titulo de otra persona"
    assert client.get(f"/episodios/{episode_id}", follow_redirects=False).status_code == 404


# --- sacarle el fondo ----------------------------------------------------


class _Recortador:
    """Produce un archivo NUEVO: es lo que distingue un recorte de no hacer nada."""

    name = "de-mentira"
    quita_fondo = True

    def cutout(self, source):
        import tempfile
        from pathlib import Path as P

        from PIL import Image

        destino = P(tempfile.mkdtemp()) / "recorte.png"
        with Image.open(source) as img:
            recortada = img.convert("RGBA")
            recortada.putalpha(128)
            recortada.save(destino, "PNG")
        return destino


def _subir_y_abrir_modal(client, imagen, role="conductor"):
    """Sube y devuelve (photo_id, html del modal). El modal vive en la URL."""
    respuesta = _subir(client, imagen, role=role)
    destino = respuesta.headers["location"]
    assert "nueva=" in destino, (
        "subir no abrio el modal: la URL de vuelta no trae la foto recien subida"
    )
    photo_id = destino.split("nueva=")[1].split("&")[0]
    return photo_id, client.get(destino).text


def test_web_33_al_subir_aparece_un_modal_con_la_foto(client, imagen, app):
    _entrar(client)
    app.state.cutout_provider = _Recortador()

    photo_id, modal = _subir_y_abrir_modal(client, imagen)

    assert f"/photos/{photo_id}/file" in modal, "el modal no muestra la foto recien subida"
    assert f"/libreria/fotos/{photo_id}/fondo" in modal, "el modal no ofrece quitarle el fondo"


def test_web_34_quitar_el_fondo_desde_el_modal_y_deshacerlo(client, imagen, app):
    _entrar(client)
    app.state.cutout_provider = _Recortador()
    photo_id, _ = _subir_y_abrir_modal(client, imagen)

    original = client.get(f"/photos/{photo_id}/file").content

    quitar = client.post(
        f"/libreria/fotos/{photo_id}/fondo",
        data={"volver": f"/libreria?nueva={photo_id}"},
        follow_redirects=False,
    )
    assert quitar.status_code in (302, 303)
    assert client.get(f"/photos/{photo_id}/file").content != original, (
        "la URL de la foto sigue sirviendo el original"
    )
    # Y el modal, todavia abierto, lo dice.
    assert "Deshacer" in client.get(quitar.headers["location"]).text

    deshacer = client.post(
        f"/libreria/fotos/{photo_id}/fondo/deshacer",
        data={"volver": f"/libreria?nueva={photo_id}"},
        follow_redirects=False,
    )
    assert deshacer.status_code in (302, 303)
    assert client.get(f"/photos/{photo_id}/file").content == original, (
        "deshacer no devolvio el original"
    )


def test_web_35_a_un_logo_no_se_le_ofrece_quitarle_el_fondo(client, imagen, app):
    """Es mobiliario de marca: ya viene con su transparencia (SPEC 11.5)."""
    _entrar(client)

    _, modal = _subir_y_abrir_modal(client, imagen, role="logo")

    assert "/fondo" not in modal, "ofrece quitarle el fondo a un logo"


def test_web_36_sin_recorte_activo_el_modal_lo_dice(client, imagen, app):
    """Con `passthrough` el botón llamaría al recorte, el recorte devolvería la
    misma imagen, y no pasaría nada. Un botón que no hace nada y no lo dice es
    peor que no tenerlo: es lo que hace que alguien crea que la app está rota."""
    _entrar(client)
    # `passthrough` es el proveedor por defecto, y es el que corre aquí.
    assert app.state.cutout_provider.quita_fondo is False

    _, modal = _subir_y_abrir_modal(client, imagen)

    assert "/fondo" not in modal, "ofrece un botón que no puede hacer nada"
    assert "no está activo" in modal, "no dice por qué no está el botón"
