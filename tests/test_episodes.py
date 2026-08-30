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
    assert "immutable" in primera.headers["cache-control"]

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
