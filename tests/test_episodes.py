"""Criterios de `specs/episodes.md`: el flujo completo por API."""

import io

from PIL import Image


def _foto(client, imagen, role, **kw):
    respuesta = client.post(
        "/photos",
        data={"role": role, **kw},
        files={"file": (f"{role}.png", imagen(color=(len(role) * 20 % 255, 60, 90)), "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _libreria(client, imagen, *roles):
    return {role: _foto(client, imagen, role) for role in roles}


def _crear(client, seleccion, title="LA VERDAD SOBRE EL CASO", **kw):
    return client.post("/episodes", json={"title": title, "selection": seleccion, **kw})


def _entrar_como(client, email):
    import re

    client.post("/auth/logout")
    client.post("/auth/magic-link", json={"email": email})
    correo = client.app.state.mailer.sent[-1].text
    token = re.search(r"https?://\S+", correo).group(0).rsplit("=", 1)[-1]
    assert client.post("/auth/verify", json={"token": token}).status_code == 200


# --- crear ---------------------------------------------------------------


def test_episodes_01_crear_devuelve_el_episodio(logged_in, imagen):
    fotos = _libreria(logged_in, imagen, "conductor", "invitado", "logo")

    respuesta = _crear(logged_in, fotos)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["title"] == "LA VERDAD SOBRE EL CASO"
    assert cuerpo["selection"]["conductor"] == [fotos["conductor"]]
    assert cuerpo["assembly"] is None, "crear no arma todavía"


def test_episodes_02_hace_falta_un_conductor(logged_in, imagen):
    fotos = _libreria(logged_in, imagen, "invitado", "logo")

    respuesta = _crear(logged_in, fotos)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == "EPISODES_CONDUCTOR_REQUIRED"


def test_episodes_03_no_puedo_usar_la_foto_de_otro(logged_in, imagen):
    ajena = _foto(logged_in, imagen, "conductor")
    _entrar_como(logged_in, "otra@ejemplo.cl")

    respuesta = _crear(logged_in, {"conductor": ajena})
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "LIBRARY_PHOTO_NOT_FOUND"


def test_episodes_04_fondo_y_objeto_son_opcionales(logged_in, imagen):
    """SPEC 11.8: la ausencia es una entrada válida."""
    conductor = _foto(logged_in, imagen, "conductor")

    respuesta = _crear(logged_in, {"conductor": conductor})
    assert respuesta.status_code == 201

    armado = logged_in.post(f"/episodes/{respuesta.json()['id']}/assembly")
    assert armado.status_code == 201


def test_episodes_05_sin_sesion_es_401(client):
    assert client.post("/episodes", json={"title": "x", "selection": {}}).status_code == 401


# --- armar ---------------------------------------------------------------


def test_episodes_06_armar_produce_un_png_de_1280x720(logged_in, imagen):
    fotos = _libreria(logged_in, imagen, "conductor", "invitado", "fondo", "logo")
    episode_id = _crear(logged_in, fotos).json()["id"]

    assert logged_in.post(f"/episodes/{episode_id}/assembly").status_code == 201
    archivo = logged_in.get(f"/episodes/{episode_id}/assembly/file")

    assert archivo.status_code == 200
    with Image.open(io.BytesIO(archivo.content)) as img:
        assert img.size == (1280, 720)
        assert img.format == "PNG"


def test_episodes_07_armar_dos_veces_no_recompone(logged_in, imagen):
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}).json()["id"]

    primero = logged_in.post(f"/episodes/{episode_id}/assembly").json()
    segundo = logged_in.post(f"/episodes/{episode_id}/assembly").json()

    assert primero["id"] == segundo["id"]


def test_episodes_08_cambiar_el_titulo_produce_un_armado_nuevo(logged_in, imagen):
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}, title="EL RIGN").json()["id"]
    primero = logged_in.post(f"/episodes/{episode_id}/assembly").json()

    logged_in.patch(f"/episodes/{episode_id}", json={"title": "EL RING"})
    segundo = logged_in.post(f"/episodes/{episode_id}/assembly").json()

    assert primero["id"] != segundo["id"]


def test_episodes_09_el_armado_guarda_la_version_del_template(logged_in, imagen):
    from app.domains.composition import api as composition

    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}).json()["id"]

    armado = logged_in.post(f"/episodes/{episode_id}/assembly").json()
    assert armado["template_version"] == composition.TEMPLATE_VERSION


def test_episodes_10_un_acabado_roto_deja_el_armado_descargable(
    logged_in, imagen, app, db, settings
):
    """SPEC 7: la IA es mejora, nunca dependencia."""
    from app.domains.finishing import api as finishing

    class AcabadoRoto:
        name = "roto"

        def finish(self, base_png, *, strength):
            raise RuntimeError("el modelo se cayó")

    app.state.finisher = AcabadoRoto()
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}).json()["id"]

    armado = logged_in.post(f"/episodes/{episode_id}/assembly")
    assert armado.status_code == 201
    assert armado.json()["finish_applied"] is False

    archivo = logged_in.get(f"/episodes/{episode_id}/assembly/file")
    assert archivo.status_code == 200
    assert len(archivo.content) > 0
    assert finishing.DEFAULT_STRENGTH == "medio"


# --- consultar -----------------------------------------------------------


def test_episodes_11_listar_devuelve_los_mios_del_mas_reciente(logged_in, imagen):
    conductor = _foto(logged_in, imagen, "conductor")
    primero = _crear(logged_in, {"conductor": conductor}, title="UNO").json()["id"]
    segundo = _crear(logged_in, {"conductor": conductor}, title="DOS").json()["id"]

    listado = logged_in.get("/episodes").json()
    assert [e["id"] for e in listado] == [segundo, primero]


def test_episodes_12_el_episodio_de_otro_da_404(logged_in, imagen):
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}).json()["id"]
    _entrar_como(logged_in, "otra@ejemplo.cl")

    respuesta = logged_in.get(f"/episodes/{episode_id}")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "EPISODES_NOT_FOUND"


def test_episodes_13_el_armado_se_descarga_con_etag(logged_in, imagen):
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}).json()["id"]
    logged_in.post(f"/episodes/{episode_id}/assembly")

    primera = logged_in.get(f"/episodes/{episode_id}/assembly/file")
    etag = primera.headers["etag"]
    cache = primera.headers["cache-control"]
    # Esta URL sirve EL ULTIMO armado, y corregir el titulo produce otro.
    assert "immutable" not in cache, "promete que nunca cambia, y cambia"
    assert "no-cache" in cache
    assert "public" not in cache

    repetida = logged_in.get(
        f"/episodes/{episode_id}/assembly/file", headers={"If-None-Match": etag}
    )
    assert repetida.status_code == 304

    # La base es un archivo distinto del final: sin logo ni título.
    base = logged_in.get(f"/episodes/{episode_id}/assembly/file", params={"variant": "base"})
    assert base.status_code == 200
    assert base.content != primera.content


def test_episodes_14_una_foto_borrada_no_rompe_el_episodio(logged_in, imagen):
    """SPEC 11.11: el armado se degrada, no falla."""
    fotos = _libreria(logged_in, imagen, "conductor", "invitado")
    episode_id = _crear(logged_in, fotos).json()["id"]
    logged_in.post(f"/episodes/{episode_id}/assembly")

    assert logged_in.delete(f"/photos/{fotos['invitado']}").status_code == 204

    rearmado = logged_in.post(f"/episodes/{episode_id}/assembly")
    assert rearmado.status_code == 201
    assert logged_in.get(f"/episodes/{episode_id}/assembly/file").status_code == 200


def test_episodes_15_un_episodio_con_marco_lo_lleva_hasta_los_pixeles(
    logged_in, imagen, settings, db
):
    """SPEC 15.3: la grilla que valida el producto se armo con rutas locales.
    Este test exige el mismo resultado, pero entrando por HTTP."""
    from app.domains.composition import api as composition
    from app.domains.intake import api as intake
    from app.domains.library import api as library

    fotos = _libreria(logged_in, imagen, "conductor", "invitado")
    marco = logged_in.post(
        "/photos",
        data={"role": "marco"},
        # Un marco opaco entero: si llego hasta el final, no se ve nada mas.
        files={"file": ("marco.png", imagen(size=(1280, 720), color=(233, 40, 39)), "image/png")},
    )
    assert marco.status_code == 201, marco.text
    fotos["marco"] = marco.json()["id"]

    episode_id = _crear(logged_in, fotos).json()["id"]
    assert logged_in.post(f"/episodes/{episode_id}/assembly").status_code == 201

    final = logged_in.get(f"/episodes/{episode_id}/assembly/file")
    assert final.status_code == 200
    imagen_final = Image.open(io.BytesIO(final.content))
    for punto in [(4, 4), (1276, 716), (640, 360)]:
        assert imagen_final.getpixel(punto) == (233, 40, 39), (
            f"en {punto} se ve {imagen_final.getpixel(punto)}: el marco no llego al armado"
        )

    # Y el marco esta en el overlay, no en la base: nunca pasaria por un modelo.
    base = logged_in.get(f"/episodes/{episode_id}/assembly/file", params={"variant": "base"})
    assert Image.open(io.BytesIO(base.content)).getpixel((4, 4)) != (233, 40, 39)

    # Lo mismo por script: el armado por HTTP no es otro armado.
    rutas = {}
    for role, photo_id in fotos.items():
        photo = library.get_photo(db, user_id=_mi_id(logged_in), photo_id=photo_id)
        rutas[role] = [intake.path(settings, library.resolve_media(db, settings, photo))]
    brief = composition.Brief(title="LA VERDAD SOBRE EL CASO", photos=rutas)
    por_script = composition.compose(brief)
    assert final.content == por_script.final, "el armado por HTTP difiere del armado por script"


def _mi_id(client) -> str:
    return client.get("/auth/me").json()["id"]


def test_episodes_16_corregir_el_titulo_cambia_lo_que_sirve_esa_url(logged_in, imagen):
    """El bug que solo se ve en un navegador.

    La URL del armado llevaba `immutable, max-age=1 ano`, pero su contenido
    cambia al corregir el titulo. El navegador hacia lo correcto -- no volver a
    pedirla -- y la persona veia la miniatura vieja despues de arreglar la
    errata. `TestClient` no implementa una cache HTTP, asi que esto se comprueba
    por el ETag: si el ETag viejo sigue validando, un cliente se queda con la
    imagen vieja para siempre.
    """
    conductor = _foto(logged_in, imagen, "conductor")
    episode_id = _crear(logged_in, {"conductor": conductor}, title="CON ERRATA").json()["id"]
    logged_in.post(f"/episodes/{episode_id}/assembly")

    antes = logged_in.get(f"/episodes/{episode_id}/assembly/file")
    etag_viejo = antes.headers["etag"]

    logged_in.patch(f"/episodes/{episode_id}", json={"title": "SIN ERRATA"})
    logged_in.post(f"/episodes/{episode_id}/assembly")

    despues = logged_in.get(f"/episodes/{episode_id}/assembly/file")
    assert despues.content != antes.content, "sirvio el armado viejo"
    assert despues.headers["etag"] != etag_viejo

    # Y el ETag viejo ya no vale: un cliente que preguntara con el recibe la
    # imagen nueva, no un 304.
    con_etag_viejo = logged_in.get(
        f"/episodes/{episode_id}/assembly/file", headers={"If-None-Match": etag_viejo}
    )
    assert con_etag_viejo.status_code == 200, "el ETag viejo sigue validando"


def test_episodes_17_el_episodio_recuerda_su_fondo_por_defecto(logged_in, imagen):
    """El fondo claro u oscuro viaja con el episodio hasta los pixeles.

    Y un nombre que no existe es un 422 aqui, no un armado silencioso con el
    fondo equivocado: `composition` cae en el por defecto para no fallar a mitad
    de dibujar (SPEC 11.4), asi que el sitio donde eso ES un error es la puerta.
    """
    conductor = _foto(logged_in, imagen, "conductor")

    def _armar(degradado):
        creado = _crear(logged_in, {"conductor": conductor}, degradado=degradado)
        assert creado.status_code == 201, creado.text
        episode_id = creado.json()["id"]
        logged_in.post(f"/episodes/{episode_id}/assembly")
        return (
            logged_in.get(f"/episodes/{episode_id}").json()["degradado"],
            logged_in.get(f"/episodes/{episode_id}/assembly/file").content,
        )

    guardado_claro, png_claro = _armar("claro")
    guardado_oscuro, png_oscuro = _armar("oscuro")

    assert (guardado_claro, guardado_oscuro) == ("claro", "oscuro"), "no lo recordo"

    # Hasta los pixeles: la esquina de arriba a la izquierda es degradado puro,
    # sin conductor ni titulo encima.
    esquina_clara = Image.open(io.BytesIO(png_claro)).convert("RGB").getpixel((20, 8))
    esquina_oscura = Image.open(io.BytesIO(png_oscuro)).convert("RGB").getpixel((20, 8))
    assert sum(esquina_clara) > sum(esquina_oscura) + 200, "el armado ignoro el fondo elegido"

    # Sin pedir nada se sigue armando con el claro: el por defecto no cambio.
    por_defecto = _crear(logged_in, {"conductor": conductor})
    assert por_defecto.json()["degradado"] == "claro"

    invalido = _crear(logged_in, {"conductor": conductor}, degradado="fucsia")
    assert invalido.status_code == 422, "acepto un fondo que no existe"
    assert invalido.json()["error"]["code"] == "EPISODES_SELECTION_INVALID"


def test_episodes_18_el_episodio_recuerda_los_ajustes(logged_in, imagen):
    """El empujon viaja con el episodio hasta los pixeles, y se guarda acotado.

    Y pedir mover un rol que no se mueve es 422: un ajuste que se ignora en
    silencio es peor que uno rechazado, porque parece que funciono.
    """
    fotos = _libreria(logged_in, imagen, "conductor", "invitado")

    quieto = _crear(logged_in, fotos)
    movido = _crear(logged_in, fotos, ajustes={"conductor": {"dx": -120, "capa": -1}})
    assert movido.status_code == 201, movido.text

    guardado = movido.json()["ajustes"]
    assert guardado["conductor"]["dx"] == -120
    assert guardado["conductor"]["capa"] == -1
    assert "invitado" not in guardado, "guardo un rol que nadie movio"

    def _png(respuesta):
        episode_id = respuesta.json()["id"]
        logged_in.post(f"/episodes/{episode_id}/assembly")
        return logged_in.get(f"/episodes/{episode_id}/assembly/file").content

    assert _png(movido) != _png(quieto), "el ajuste no llego a la miniatura"

    # Se guarda ACOTADO: la fila dice lo que se va a dibujar, no lo que se pidio.
    from app.domains.composition import api as composition

    desmedido = _crear(logged_in, fotos, ajustes={"conductor": {"dx": 99999}})
    assert desmedido.json()["ajustes"]["conductor"]["dx"] == composition.AJUSTES.max_x

    # Un ajuste que no mueve nada no deja rastro: pedirlo en cero es no pedirlo.
    en_cero = _crear(logged_in, fotos, ajustes={"conductor": {"dx": 0}})
    assert en_cero.json()["ajustes"] == {}

    ajeno = _crear(logged_in, fotos, ajustes={"marco": {"dx": 40}})
    assert ajeno.status_code == 422, "dejo mover un rol que no se mueve"
    assert ajeno.json()["error"]["code"] == "EPISODES_SELECTION_INVALID"
