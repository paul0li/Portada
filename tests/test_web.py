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


def test_web_18_no_hay_perillas_que_no_hagan_nada(client, imagen):
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

    # Y la intensidad no se ofrece: con `NoopFinisher` no cambia nada, y un
    # botón que no hace nada es un botón que miente.
    ultimo = client.get("/nueva", params={"paso": 5, "conductor": ids["conductor"]}).text
    assert 'name="strength"' not in ultimo
    assert "Intensidad" not in ultimo


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


def _lienzo(client, **params):
    respuesta = client.get("/nueva/lienzo.json", params=params)
    assert respuesta.status_code == 200, respuesta.text[:300]
    return respuesta.json()


def test_web_43_el_preview_es_un_lienzo_de_capas(client, imagen):
    """El navegador apila; no compone. Lo que describe el JSON, apilado, es el
    preview, y cada figura dice qué se le puede hacer con los rangos del template.
    """
    from PIL import Image

    from app.domains.composition import api as composition

    assert client.get("/nueva/lienzo.json").status_code == 401

    _entrar(client)
    ids = _libreria_completa(client, imagen)
    borrador = {
        "conductor": ids["conductor"],
        "invitado": ids["invitado"],
        "fondo": ids["fondo"],
        "ajuste": "conductor.0:-100,20,0,0,0,70",
        "title": "LAS CAPAS NO MIENTEN",
    }
    lienzo = _lienzo(client, **borrador)

    assert lienzo["lienzo"] == list(composition.TEMPLATE.canvas)
    nombres = [c["nombre"] for c in lienzo["capas"]]
    # La marca se pone sola, como en el preview: el flujo la da por puesta.
    assert nombres == ["fondo", "invitado.0", "conductor.0", "logo", "titulo", "marco"]

    conductor = next(c for c in lienzo["capas"] if c["nombre"] == "conductor.0")
    assert conductor["ajuste"]["escala"] == 70 and conductor["ajuste"]["dx"] == -100
    assert conductor["mueve"] and conductor["voltea"]
    assert conductor["apoyo"] == "bottom-center"
    assert conductor["ancla"][1] == conductor["y"] + conductor["alto"]
    fondo = lienzo["capas"][0]
    assert not fondo["mueve"] and fondo["voltea"], "el fondo se voltea pero no se mueve"
    marco = lienzo["capas"][-1]
    assert not marco["mueve"] and not marco["voltea"], "el marco es marca: ni se mueve ni se voltea"
    assert lienzo["limites"]["escala"] == [
        composition.AJUSTES.escala_min,
        composition.AJUSTES.escala_max,
    ]

    # Apiladas donde dicen, las capas son el preview. Se comparan a la mitad de
    # lado, que es a lo que se sirven las dos cosas.
    apilado = Image.new("RGBA", (640, 360), (0, 0, 0, 255))
    for capa in lienzo["capas"]:
        servida = client.get(capa["src"])
        assert servida.status_code == 200, (capa["nombre"], servida.text[:200])
        img = Image.open(io.BytesIO(servida.content)).convert("RGBA")
        assert abs(img.width - capa["ancho"] / 2) <= 1 and abs(img.height - capa["alto"] / 2) <= 1
        apilado.alpha_composite(img, (round(capa["x"] / 2), round(capa["y"] / 2)))
    params = {k: v for k, v in borrador.items() if k != "title"}
    preview = client.get(
        "/nueva/preview.jpg", params={**params, "title": borrador["title"]}
    ).content
    esperado = Image.open(io.BytesIO(preview)).convert("RGB")
    diferencia = sum(
        abs(a - b)
        for pa, pb in zip(apilado.convert("RGB").getdata(), esperado.getdata(), strict=True)
        for a, b in zip(pa, pb, strict=True)
    ) / (640 * 360 * 3)
    assert diferencia < 4, f"las capas apiladas no son el preview ({diferencia:.1f} de media)"

    # Una figura se sirve con lo que la cambia y nada más: moverla no cambia su
    # URL, así que arrastrar no vuelve a bajar la imagen.
    movido = _lienzo(client, **{**borrador, "ajuste": "conductor.0:200,0,0,0,0,70"})
    otro = next(c for c in movido["capas"] if c["nombre"] == "conductor.0")
    assert otro["src"] == conductor["src"] and otro["x"] == conductor["x"] + 300

    # La capa de una foto ajena no se sirve.
    _entrar(client, email="otra@ejemplo.cl")
    assert client.get(conductor["src"]).status_code == 204
    client.post("/salir")
    assert client.get(conductor["src"]).status_code == 401


def test_web_44_lo_del_lienzo_viaja_en_la_url_y_llega_al_armado(client, imagen):
    """Escala y sitio del título viajan como el resto del borrador. Sin JS, los
    pads de siempre siguen ahí."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    escalado = "conductor.0:-100,20,0,0,0,70"
    pagina = client.get(
        "/nueva", params={"paso": 1, "conductor": ids["conductor"], "ajuste": escalado}
    )
    assert pagina.status_code == 200
    # El lienzo se describe con lo mismo que lleva la página.
    lienzo = re.search(r'data-lienzo="([^"]+)"', pagina.text)
    assert lienzo, "el paso no ofrece el lienzo"
    assert "ajuste=conductor.0" in lienzo.group(1).replace("%2C", ",")
    assert '<script src="/estatico/lienzo.js' in pagina.text
    # El paso siguiente se lleva la escala.
    siguiente = re.search(r'href="(/nueva\?paso=2[^"]*)"', pagina.text)
    assert siguiente and "70" in siguiente.group(1).split("ajuste=")[1], (
        "la escala no sobrevive al paso siguiente"
    )
    # Sin JS, los pads siguen.
    assert 'class="empujar"' in pagina.text

    # El paso del título lleva el sitio del título en el formulario.
    titulo = client.get("/nueva", params={"paso": 5, "conductor": ids["conductor"]})
    assert 'name="titulo_x"' in titulo.text and 'name="titulo_y"' in titulo.text

    creado = _armar(
        client,
        {"conductor": ids["conductor"]},
        ajuste=escalado,
        titulo_x=200,
        titulo_y=-60,
    )
    assert creado.status_code in (302, 303), creado.text[:400]
    episode_id = creado.headers["location"].rsplit("/", 1)[-1]
    guardado = client.get(f"/episodes/{episode_id}").json()
    assert guardado["ajustes"]["conductor"][0]["escala"] == 70
    assert (guardado["titulo_x"], guardado["titulo_y"]) == (200, -60)


def test_web_45_el_titulo_del_lienzo_describe_su_bloque(client, imagen):
    """Las asas del título manejan los tres mandos de siempre: el JSON dice dónde
    está el bloque, con qué tamaño salió la letra, y entre qué topes y de cuánto
    en cuánto se mueve cada mando -- todo del template."""
    from app.domains.episodes import api as episodes

    tipografia = episodes.TIPOGRAFIA
    _entrar(client)
    ids = _libreria_completa(client, imagen)

    def _titulo(**mandos):
        lienzo = _lienzo(client, conductor=ids["conductor"], title="NADIE LO VIO", **mandos)
        return next(c for c in lienzo["capas"] if c["nombre"] == "titulo")

    puesto = _titulo(titulo_ancho=80, titulo_alto=40, titulo_tamano=16, titulo_x=100, titulo_y=-50)
    techo = tipografia.top - 40 - 50
    regla = tipografia.bottom - 50 + tipografia.rule_gap + tipografia.rule_height
    assert puesto["bloque"] == {
        "x": tipografia.left + 100,
        "y": techo,
        "ancho": tipografia.block_width + 80,
        "alto": regla - techo,
    }
    assert puesto["tamano"] == tipografia.size_max + 16
    assert puesto["mandos"] == {"ancho": 80, "tamano": 16, "alto": 40}
    assert puesto["rangos"] == {
        "ancho": [-tipografia.ancho_menos, tipografia.ancho_mas, tipografia.ancho_paso],
        "tamano": [-tipografia.tamano_menos, tipografia.tamano_mas, tipografia.tamano_paso],
        "alto": [-tipografia.alto_menos, tipografia.alto_mas, tipografia.alto_paso],
    }

    # Con el tamaño en automático, dice el que eligió el auto-ajuste: es desde
    # donde la esquina empieza a agrandar.
    automatico = _titulo()
    assert tipografia.size_min <= automatico["tamano"] <= tipografia.size_max
    assert automatico["mandos"] == {"ancho": 0, "tamano": 0, "alto": 0}

    # Desmedido, se describe acotado: lo que se dibuja.
    acotado = _titulo(titulo_ancho=99999)
    assert acotado["mandos"]["ancho"] == tipografia.ancho_mas


def test_web_46_quito_el_fondo_desde_el_lienzo(client, imagen, app):
    """El botón está donde hace algo, y al quitar el fondo la capa cambia de URL."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    borrador = {"conductor": ids["conductor"], "fondo": ids["fondo"]}

    def _capas():
        return {c["nombre"]: c for c in _lienzo(client, **borrador)["capas"]}

    # Con un proveedor que no quita fondos no se ofrece: no haría nada (WEB-36).
    # Se pone a mano y no se confía en el de por defecto: un `.env` local con
    # `rembg` haría pasar este test por el motivo equivocado.
    class _NoRecorta:
        name = "passthrough"
        quita_fondo = False

    app.state.cutout_provider = _NoRecorta()
    assert _capas()["conductor.0"]["recorte"]["admite"] is False

    app.state.cutout_provider = _Recortador()
    antes = _capas()
    conductor = antes["conductor.0"]
    assert conductor["foto"] == ids["conductor"]
    assert conductor["recorte"] == {"admite": True, "puesto": False}
    assert "recorte" not in antes["fondo"], "al fondo no se le quita el fondo"

    aqui = "/nueva?paso=1&conductor=" + ids["conductor"]
    quitar = client.post(
        f"/libreria/fotos/{ids['conductor']}/fondo", data={"volver": aqui}, follow_redirects=False
    )
    assert quitar.status_code == 303
    despues = _capas()["conductor.0"]
    assert despues["recorte"]["puesto"] is True
    assert despues["src"] != conductor["src"], "la capa no cambió de URL: se vería la foto vieja"

    client.post(
        f"/libreria/fotos/{ids['conductor']}/fondo/deshacer",
        data={"volver": aqui},
        follow_redirects=False,
    )
    devuelta = _capas()["conductor.0"]
    assert devuelta["recorte"]["puesto"] is False and devuelta["src"] == conductor["src"]

    # Y la barra del lienzo trae el botón, que llama a esos mismos endpoints.
    script = client.get("/estatico/lienzo.js").text
    assert "Quitarle el fondo" in script and "/fondo" in script and "recorte.admite" in script


def test_web_47_guardo_la_miniatura_en_fotos(client, imagen):
    """En iPhone, un enlace de descarga manda a Archivos; la hoja de compartir
    manda a Fotos. Sin hoja de compartir (HTTP), mantener presionada la imagen."""
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    creado = _armar(client, {"conductor": ids["conductor"]})
    pagina = client.get(creado.headers["location"]).text
    episode_id = creado.headers["location"].rsplit("/", 1)[-1]
    archivo = f"/episodes/{episode_id}/assembly/file"

    boton = re.search(r'<button[^>]*id="guardar-fotos"[^>]*>', pagina)
    assert boton, "no hay botón para guardar en Fotos"
    assert f'data-src="{archivo}"' in boton.group(0)
    # Lo que se guarda manteniendo presionado es el PNG de verdad, no el preview.
    assert re.search(rf'<img[^>]*class="miniatura-final"[^>]*src="{archivo}"', pagina)
    assert "Agregar a Fotos" in pagina, "no dice qué hacer donde no hay hoja de compartir"
    # Sin JS, la descarga sigue ahí.
    assert f'href="{archivo}" download' in pagina
    script = client.get("/estatico/guardar.js").text
    assert "navigator.share" in script and "canShare" in script


def test_web_42_pongo_el_titulo_ancho_o_apilado(client, imagen):
    """Los tres mandos del título viajan con el formulario y llegan al armado.

    En pantalla los manejan las asas del lienzo (WEB-45): la página ya no trae
    sliders, ni la casilla de una palabra por línea, ni su explicación. Los
    campos siguen ahí, ocultos, porque el formulario es lo que crea el episodio.
    """
    from app.domains.episodes import api as episodes

    _entrar(client)
    ids = _libreria_completa(client, imagen)
    paso = f"/nueva?paso=5&conductor={ids['conductor']}"

    pagina = client.get(paso)
    assert pagina.status_code == 200
    for campo in ("titulo_ancho", "titulo_tamano", "titulo_alto"):
        assert re.search(rf'<input type="hidden"[^>]*name="{campo}"', pagina.text), campo
    assert 'type="range"' not in pagina.text, "quedó un slider en el paso del título"
    assert 'name="titulo_apilado"' not in pagina.text
    assert "Una palabra por línea" not in pagina.text
    assert 'name="strength"' not in pagina.text, "la intensidad se ofrece y no hace nada"

    def _png(**extra):
        creado = _armar(client, {"conductor": ids["conductor"]}, **extra)
        assert creado.status_code in (302, 303), creado.text[:400]
        resultado = client.get(creado.headers["location"])
        enlace = re.search(r'href="(/episodes/[^"]+/assembly/file)"', resultado.text)
        return client.get(enlace.group(1)).content

    normal = _png()
    assert _png(titulo_ancho=episodes.TIPOGRAFIA.ancho_mas) != normal
    assert _png(titulo_tamano=-episodes.TIPOGRAFIA.tamano_menos) != normal
    # El alto se ve con un título que tenga de qué crecer: apilado y largo.
    seis = {"title": "UNO DOS TRES CUATRO CINCO SEIS", "titulo_apilado": "on"}
    assert _png(**seis, titulo_alto=episodes.TIPOGRAFIA.alto_mas) != _png(**seis)
    # La casilla manda su presencia, no un valor: así se marca en un formulario.
    assert _png(titulo_apilado="on") != normal


def test_web_41_cada_invitado_tiene_su_pad(client, imagen):
    """Dos invitados, dos pads: mover a uno no puede mover al otro.

    Y cada pad se titula con la etiqueta de SU foto: dos pads idénticos uno
    encima del otro no dirían cuál es cuál.
    """
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    client.post(
        "/libreria/fotos",
        data={"role": "invitado", "label": "la segunda invitada"},
        files={"file": ("segunda.png", imagen(color=(9, 200, 90)))},
        follow_redirects=False,
    )
    segunda = client.get("/photos", params={"role": "invitado"}).json()["photos"][0]["id"]

    paso = (
        f"/nueva?paso=2&conductor={ids['conductor']}&invitado={ids['invitado']}&invitado={segunda}"
    )
    pagina = client.get(paso)
    assert pagina.status_code == 200

    pads = pagina.text.split('class="empujar"')[1:]
    assert len(pads) == 2, "dos invitados elegidos y no hay un pad para cada uno"
    assert "la segunda invitada" in pads[1], "el pad no dice de qué invitada es"

    # El pad del segundo mueve al SEGUNDO: el ajuste lleva su posición.
    derecha = re.search(r'href="([^"]+)"[^>]*aria-label="Derecha"', pads[1])
    assert derecha
    movido = derecha.group(1).replace("&amp;", "&")
    assert "ajuste=invitado.1" in movido
    assert "ajuste=invitado.0" not in movido, "mover al segundo movió también al primero"

    # Y el del primero, al primero.
    primera = re.search(r'href="([^"]+)"[^>]*aria-label="Derecha"', pads[0])
    assert "ajuste=invitado.0" in primera.group(1).replace("&amp;", "&")


def test_web_40_volteo_una_figura_desde_su_paso(client, imagen, asimetrica):
    """El volteo es un INTERRUPTOR: el mismo toque pone y quita.

    Por eso no basta con comprobar que el enlace existe y cambia el preview: se
    toca dos veces y tiene que quedar como estaba. Un botón que solo sabe poner
    es medio botón, y se nota al segundo toque, no al primero.
    """
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    client.post(
        "/libreria/fotos",
        data={"role": "conductor", "label": "conductor asimétrico"},
        files={"file": ("asimetrica.png", asimetrica())},
        follow_redirects=False,
    )
    conductor = client.get("/photos", params={"role": "conductor"}).json()["photos"][0]["id"]
    paso1 = f"/nueva?paso=1&conductor={conductor}"

    pagina = client.get(paso1)
    espejo = re.search(
        r'href="([^"]+)"[^>]*aria-label="Voltear de izquierda a derecha"', pagina.text
    )
    assert espejo, "el paso del conductor no ofrece voltearlo"

    puesto = client.get(espejo.group(1).replace("&amp;", "&"))
    assert puesto.status_code == 200
    assert "paso=1" in puesto.text, "voltear me sacó del paso en vez de repintarlo"
    assert re.search(r'id="preview" src="[^"]*ajuste=conductor[^"]*1', puesto.text), (
        "el preview no enseña el volteo"
    )
    assert re.search(
        r'<a[^>]*aria-label="Voltear de izquierda a derecha"[^>]*aria-pressed="true"',
        puesto.text,
        re.S,
    ), "el volteo puesto no se ve puesto"

    # El segundo toque lo quita: mismo botón, estado contrario.
    otra_vez = re.search(
        r'href="([^"]+)"[^>]*aria-label="Voltear de izquierda a derecha"', puesto.text
    )
    quitado = client.get(otra_vez.group(1).replace("&amp;", "&"))
    # Se mira el PREVIEW y no la página entera: los botones de mover siguen
    # proponiendo `ajuste=conductor` en sus enlaces, que es lo que tienen que
    # hacer. Lo que importa es lo que se está dibujando ahora.
    assert not re.search(r'id="preview" src="[^"]*ajuste=conductor', quitado.text), (
        "el volteo no se puede quitar"
    )

    # El paso del fondo ofrece voltear y NO ofrece mover: son dos permisos.
    paso_fondo = client.get(f"/nueva?paso=3&conductor={conductor}&fondo={ids['fondo']}")
    assert 'aria-label="Voltear de arriba a abajo"' in paso_fondo.text
    assert 'aria-label="Izquierda"' not in paso_fondo.text, (
        "ofrece mover un fondo a sangre completa"
    )

    # Y llega al armado.
    def _png(**extra):
        creado = _armar(client, {"conductor": conductor}, **extra)
        assert creado.status_code in (302, 303), creado.text[:400]
        resultado = client.get(creado.headers["location"])
        enlace = re.search(r'href="(/episodes/[^"]+/assembly/file)"', resultado.text)
        return client.get(enlace.group(1)).content

    assert _png(ajuste="conductor:0,0,0,1,0") != _png(), "el volteo no llegó a la miniatura"


def test_web_39_puedo_elegir_dos_invitados(client, imagen):
    """La semana en que vienen dos: el segundo toque SUMA en vez de reemplazar.

    La pantalla no sabe cuantos caben -- lo lee de `episodes.MAXIMOS`, que a su
    vez lo lee del template. Este test hace lo mismo, para que subir o bajar el
    tope no deje un test afirmando el numero viejo.
    """
    from app.domains.episodes import api as episodes

    tope = episodes.MAXIMOS["invitado"]
    assert tope >= 2, "el template ya no admite mas de un invitado"

    _entrar(client)
    ids = _libreria_completa(client, imagen)
    otros = []
    for n in range(tope):
        client.post(
            "/libreria/fotos",
            data={"role": "invitado", "label": f"invitado extra {n}"},
            files={"file": (f"extra{n}.png", imagen(color=(10 + n * 60, 200, 90)))},
            follow_redirects=False,
        )
        otros.append(client.get("/photos", params={"role": "invitado"}).json()["photos"][0]["id"])

    paso = f"/nueva?paso=2&conductor={ids['conductor']}&invitado={ids['invitado']}"
    pagina = client.get(paso)
    assert pagina.status_code == 200

    # El toque de otra foto deja las DOS puestas, sin salir del paso.
    suma = re.search(
        rf'href="(/nueva\?[^"]*invitado={ids["invitado"]}[^"]*invitado={otros[0]}[^"]*)"',
        pagina.text,
    )
    assert suma, "elegir un segundo invitado reemplaza al primero en vez de sumarlo"

    con_dos = client.get(suma.group(1).replace("&amp;", "&"))
    assert con_dos.status_code == 200
    assert "paso=2" in con_dos.text, "elegir el segundo me sacó del paso"
    assert "2 elegida" in con_dos.text
    src = re.search(r'id="preview" src="([^"]+)"', con_dos.text)
    assert src and src.group(1).count("invitado=") == 2, "el preview no enseña a los dos"

    # Y los dos llegan al armado, que es lo unico que cuenta.
    def _png(invitados):
        creado = _armar(client, {"conductor": ids["conductor"], "invitado": invitados})
        assert creado.status_code in (302, 303), creado.text[:400]
        resultado = client.get(creado.headers["location"])
        enlace = re.search(r'href="(/episodes/[^"]+/assembly/file)"', resultado.text)
        return client.get(enlace.group(1)).content

    assert _png([ids["invitado"], otros[0]]) != _png([ids["invitado"]])

    # Uno mas de los que caben desplaza al mas viejo en vez de dar un error: en
    # una grilla de fotos, tocar la siguiente es elegirla, no equivocarse.
    lleno = "".join(f"&invitado={i}" for i in [ids["invitado"], *otros[: tope - 1]])
    pagina = client.get(f"/nueva?paso=2&conductor={ids['conductor']}{lleno}")
    desplaza = re.search(rf'href="(/nueva\?[^"]*invitado={otros[tope - 1]}[^"]*)"', pagina.text)
    assert desplaza, "la foto de mas no se puede elegir"
    destino = desplaza.group(1).replace("&amp;", "&")
    assert destino.count("invitado=") == tope, "elegir una de mas se lleva por delante el tope"
    assert f"invitado={ids['invitado']}" not in destino, "desplazó a otra que a la más vieja"


def test_web_38_empujo_una_figura_desde_su_paso(client, imagen):
    """Mover sin salir del paso, con el preview delante y sin una línea de JS.

    Se comprueban las tres cosas del criterio: que el toque no me saca del paso,
    que la elección sobrevive hasta el armado, y que en el tope el empujón deja
    de ofrecerse en vez de quedarse sin hacer nada.
    """
    from PIL import Image

    _entrar(client)
    ids = _libreria_completa(client, imagen)
    paso1 = f"/nueva?paso=1&conductor={ids['conductor']}"

    pagina = client.get(paso1)
    assert pagina.status_code == 200
    toque = re.search(r'href="(/nueva\?[^"]*ajuste=conductor[^"]*)"', pagina.text)
    assert toque, "el paso del conductor no ofrece empujarlo"

    movido = client.get(toque.group(1).replace("&amp;", "&"))
    assert movido.status_code == 200
    assert "paso=2" in movido.text, "empujar me sacó del paso en vez de repintarlo"
    assert ids["conductor"] in movido.text, "empujar se llevó por delante lo elegido"
    assert re.search(r'id="preview" src="[^"]*ajuste=conductor', movido.text), (
        "el preview no enseña el empujón"
    )

    # En el tope, ese empujón deja de ofrecerse: un botón que no puede mover
    # nada es un botón que miente.
    from app.domains.composition import api as composition

    en_el_tope = client.get(
        "/nueva",
        params={
            "paso": 1,
            "conductor": ids["conductor"],
            "ajuste": "conductor:{},0,0".format(
                composition.acotar("conductor", composition.Ajuste(dx=99999)).dx
            ),
        },
    )
    derechas = re.findall(r'aria-label="Derecha"', en_el_tope.text)
    izquierdas = re.findall(r'aria-label="Izquierda"', en_el_tope.text)
    assert not derechas, "ofrece seguir empujando más allá del tope"
    assert izquierdas, "en el tope se quedó sin forma de volver"

    # Y llega al armado, que es lo único que cuenta.
    def _png(**extra):
        creado = _armar(client, {"conductor": ids["conductor"]}, **extra)
        assert creado.status_code in (302, 303), creado.text[:400]
        episode_id = creado.headers["location"].rsplit("/", 1)[-1]
        return client.get(f"/episodes/{episode_id}/assembly/file").content

    quieto = _png()
    empujado = _png(ajuste="conductor:-120,0,0")
    assert Image.open(io.BytesIO(empujado)).size == (1280, 720)
    assert empujado != quieto, "el empujón no llegó a la miniatura"


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

    # Y el paso del titulo trae con que repintar sin recargar la pagina. Desde
    # v11 lo hace el lienzo, que repinta la capa del titulo -- o el <img> de
    # siempre, si el lienzo no cargo.
    paso = client.get("/nueva", params={"paso": 5, **base}).text
    assert 'id="titulo"' in paso and '<script src="/estatico/lienzo.js' in paso
    script = client.get("/estatico/lienzo.js").text
    assert 'campo("titulo")' in script and 'addEventListener("input"' in script


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


def test_web_48_por_tailnet_se_entra_directo_al_inicio(tailnet):
    inicio = tailnet.get("/", follow_redirects=False)
    assert inicio.status_code == 200, "por tailnet no deberia haber pantalla de entrar"
    assert 'action="/salir"' not in inicio.text, "no hay sesion que cerrar"

    entrar = tailnet.get("/entrar", follow_redirects=False)
    assert entrar.status_code == 303
    assert entrar.headers["location"] == "/"

    assert tailnet.get("/libreria").status_code == 200


def test_web_49_mejoro_la_miniatura_en_chatgpt(client, imagen):
    _entrar(client)
    ids = _libreria_completa(client, imagen)
    creado = _armar(client, {"conductor": ids["conductor"]})
    pagina = client.get(creado.headers["location"]).text
    episode_id = creado.headers["location"].rsplit("/", 1)[-1]

    boton = re.search(r'<button[^>]*id="mejorar-chatgpt"[^>]*>', pagina)
    assert boton, "no hay botón para mejorar en ChatGPT"
    assert f'data-src="/episodes/{episode_id}/assembly/file"' in boton.group(0)
    assert 'data-instruccion="Mejora esta miniatura de YouTube."' in boton.group(0)

    # Debajo de «Guardar en Fotos» y «Volver atrás», que van lado a lado.
    acciones = pagina.index('id="guardar-fotos"')
    assert pagina.index("Volver atrás") > acciones
    assert pagina.index('id="mejorar-chatgpt"') > pagina.index("Volver atrás")
    assert "Cambiar fotos" not in pagina

    # `?q=` envía el mensaje al instante, sin la imagen.
    assert "chatgpt.com/?q=" not in pagina

    script = client.get("/estatico/guardar.js").text
    assert "mejorar-chatgpt" in script
    assert "clipboard" in script, "la instrucción tiene que quedar copiada"
    assert "chatgpt.com/?q=" not in script
