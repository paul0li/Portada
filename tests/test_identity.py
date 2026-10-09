"""Criterios de `specs/identity.md`: magic link y sesiones.

Estos tests hablan solo por HTTP y por la base. Nunca llaman al `service`
directamente: si un comportamiento no se puede observar desde fuera, no es un
criterio de aceptacion.
"""

import re

import pytest

COOKIE = "portada_session"
EMAIL = "persona@ejemplo.cl"


def _link(mailer) -> str:
    """El enlace del ultimo correo enviado."""
    assert mailer.sent, "no se envio ningun correo"
    cuerpo = mailer.sent[-1].text
    match = re.search(r"https?://\S+", cuerpo)
    assert match, f"el correo no trae un enlace:\n{cuerpo}"
    return match.group(0)


def _token(mailer) -> str:
    return _link(mailer).rsplit("=", 1)[-1]


def _pedir(client, email=EMAIL, **kw):
    return client.post("/auth/magic-link", json={"email": email}, **kw)


def _entrar(client, mailer, email=EMAIL):
    """El flujo completo: pedir el enlace y canjearlo."""
    _pedir(client, email)
    return client.post("/auth/verify", json={"token": _token(mailer)})


# --- pedir el enlace -----------------------------------------------------


def test_identity_01_pedir_enlace_crea_el_usuario(client, db, mailer):
    assert _pedir(client).status_code == 202
    with db.connection() as conn:
        emails = [r[0] for r in conn.execute("SELECT email FROM identity_users")]
    assert emails == [EMAIL]
    assert len(mailer.sent) == 1


def test_identity_02_la_respuesta_no_revela_si_la_cuenta_existe(client, mailer):
    primera = _pedir(client)
    segunda = _pedir(client)
    assert primera.status_code == segunda.status_code == 202
    assert primera.json() == segunda.json()


@pytest.mark.parametrize("escrito", ["  Persona@Ejemplo.CL ", "PERSONA@ejemplo.cl", EMAIL])
def test_identity_03_el_email_se_normaliza(client, db, escrito):
    assert _pedir(client, escrito).status_code == 202
    with db.connection() as conn:
        filas = conn.execute("SELECT email FROM identity_users").fetchall()
    assert [r[0] for r in filas] == [EMAIL]


@pytest.mark.parametrize("malo", ["", "sin-arroba", "a@", "@b.cl", "a b@c.cl", "a@b"])
def test_identity_04_un_email_invalido_no_crea_nada(client, db, mailer, malo):
    assert _pedir(client, malo).status_code == 422
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM identity_users").fetchone()[0] == 0
    assert mailer.sent == []


def test_identity_05_el_correo_trae_el_enlace(client, mailer, settings):
    _pedir(client)
    enlace = _link(mailer)
    assert enlace.startswith(settings.public_url)
    assert len(_token(mailer)) >= 32
    assert mailer.sent[-1].to == EMAIL


def test_identity_06_el_token_no_se_guarda_en_claro(client, db, mailer):
    _pedir(client)
    token = _token(mailer)
    with db.connection() as conn:
        filas = conn.execute("SELECT * FROM identity_magic_tokens").fetchall()
    assert len(filas) == 1
    guardado = " ".join(str(v) for v in dict(filas[0]).values())
    assert token not in guardado, "el token esta en claro en la base"


def test_identity_07_pedir_otro_enlace_invalida_el_pendiente(client, mailer):
    _pedir(client)
    primer_token = _token(mailer)
    _pedir(client)

    rechazado = client.post("/auth/verify", json={"token": primer_token})
    assert rechazado.status_code == 401
    assert client.post("/auth/verify", json={"token": _token(mailer)}).status_code == 200


def test_identity_08_limite_por_email(client, settings, mailer):
    for _ in range(settings.magic_links_per_email):
        assert _pedir(client).status_code == 202
    excedido = _pedir(client)
    assert excedido.status_code == 429
    assert excedido.json()["error"]["code"] == "IDENTITY_RATE_LIMITED"
    assert len(mailer.sent) == settings.magic_links_per_email


def test_identity_09_limite_por_ip(client, settings, mailer):
    """Cada intento usa un email distinto: solo la IP los une."""
    for i in range(settings.magic_links_per_ip):
        assert _pedir(client, f"persona{i}@ejemplo.cl").status_code == 202
    assert _pedir(client, "otra@ejemplo.cl").status_code == 429


# --- canjear el enlace ---------------------------------------------------


def test_identity_10_verificar_crea_la_sesion(client, db, mailer):
    respuesta = _entrar(client, mailer)
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == EMAIL
    assert respuesta.cookies.get(COOKIE)
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM identity_sessions").fetchone()[0] == 1


def test_identity_11_un_token_no_se_puede_usar_dos_veces(client, db, mailer):
    _pedir(client)
    token = _token(mailer)
    assert client.post("/auth/verify", json={"token": token}).status_code == 200

    segunda = client.post("/auth/verify", json={"token": token})
    assert segunda.status_code == 401
    assert segunda.json()["error"]["code"] == "IDENTITY_TOKEN_USED"
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM identity_sessions").fetchone()[0] == 1


def test_identity_12_un_token_expirado_lo_dice(client, db, mailer):
    _pedir(client)
    with db.transaction() as conn:
        conn.execute("UPDATE identity_magic_tokens SET expires_at = '2020-01-01T00:00:00.000Z'")

    respuesta = client.post("/auth/verify", json={"token": _token(mailer)})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "IDENTITY_TOKEN_EXPIRED"


@pytest.mark.parametrize("falso", ["no-existe", "x" * 43, "../../etc/passwd"])
def test_identity_13_un_token_falso_no_sirve(client, falso):
    respuesta = client.post("/auth/verify", json={"token": falso})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "IDENTITY_TOKEN_INVALID"


def test_identity_14_la_cookie_es_httponly_y_lax(client, mailer):
    respuesta = _entrar(client, mailer)
    cabecera = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cabecera
    assert "samesite=lax" in cabecera


# --- usar la sesion ------------------------------------------------------


def test_identity_15_sin_cookie_no_hay_sesion(client):
    respuesta = client.get("/auth/me")
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "IDENTITY_NO_SESSION"


def test_identity_16_con_cookie_devuelve_el_usuario(client, mailer):
    _entrar(client, mailer)
    respuesta = client.get("/auth/me")
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == EMAIL


def test_identity_17_logout_revoca_la_sesion(client, mailer):
    _entrar(client, mailer)
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_identity_18_una_sesion_expirada_no_autentica(client, db, mailer):
    _entrar(client, mailer)
    with db.transaction() as conn:
        conn.execute("UPDATE identity_sessions SET expires_at = '2020-01-01T00:00:00.000Z'")
    assert client.get("/auth/me").status_code == 401


def test_identity_19_una_cookie_falsificada_no_autentica(client, mailer):
    _entrar(client, mailer)
    client.cookies.set(COOKIE, "cookie-inventada")
    assert client.get("/auth/me").status_code == 401


# --- secretos ------------------------------------------------------------


def test_identity_20_los_secretos_no_llegan_a_los_logs(client, mailer, logs):
    _pedir(client)
    token = _token(mailer)
    client.post("/auth/verify", json={"token": token})
    cookie = client.cookies.get(COOKIE)

    escrito = logs.getvalue()
    assert token not in escrito, "el token del enlace quedo en los logs"
    assert cookie and cookie not in escrito, "la cookie de sesion quedo en los logs"


def test_identity_21_el_email_completo_no_llega_a_los_logs(client, mailer, logs):
    _pedir(client)
    client.post("/auth/verify", json={"token": _token(mailer)})

    escrito = logs.getvalue()
    assert EMAIL not in escrito, "el email completo quedo en los logs"
    assert "p***@ejemplo.cl" in escrito, "se esperaba el email enmascarado"


def test_identity_22_el_enlace_del_correo_se_puede_abrir(client, mailer):
    """El enlace apuntaba a `/auth/verify`, que solo acepta POST: abrirlo daba
    405. Nadie lo noto porque los tests extraen el token y lo postean -- ninguno
    abre el enlace, que es lo unico que hace una persona."""
    _pedir(client)

    respuesta = client.get(_link(mailer))

    assert respuesta.status_code == 200, f"abrir el enlace del correo da {respuesta.status_code}"
    assert "text/html" in respuesta.headers["content-type"]


def test_identity_23_abrir_el_enlace_no_inicia_sesion_por_si_solo(client, mailer):
    """Ningun GET cambia estado: es lo que hace que samesite=lax baste como
    defensa CSRF, y lo que evita que un escaner de enlaces queme el token."""
    _pedir(client)

    client.get(_link(mailer))

    assert client.get("/auth/me").status_code == 401, "un GET inicio sesion"
    # Y el token sigue sirviendo: abrirlo no lo gasto.
    assert client.post("/auth/verify", json={"token": _token(mailer)}).status_code == 200


# --- acceso por la red de Tailscale --------------------------------------


def test_identity_24_desde_tailscale_se_entra_sin_cookie(tailnet, db):
    respuesta = tailnet.get("/auth/me")

    assert respuesta.status_code == 200, "desde Tailscale hubo que iniciar sesion"
    assert respuesta.json()["email"] == "equipo@ejemplo.cl"
    assert COOKIE not in tailnet.cookies, "entrar por tailnet no deberia crear una sesion"


@pytest.mark.parametrize("ip", ["192.168.100.40", "10.0.0.7", "8.8.8.8"])
def test_identity_25_fuera_de_tailscale_no_se_entra(tailnet_app, ip):
    """El servidor puede estar escuchando en la red local: alguien en el mismo
    wifi llega sin pasar por Tailscale, y sin login nada lo pararia."""
    from fastapi.testclient import TestClient

    with TestClient(tailnet_app, client=(ip, 50000)) as cliente:
        assert cliente.get("/auth/me").status_code == 403
        assert cliente.get("/", follow_redirects=False).status_code == 403


def test_identity_25_el_propio_equipo_si_entra(tailnet_app):
    from fastapi.testclient import TestClient

    with TestClient(tailnet_app, client=("127.0.0.1", 50000)) as cliente:
        assert cliente.get("/auth/me").status_code == 200


def test_identity_25_con_magic_link_la_ip_no_importa(client):
    """La guarda es del acceso por tailnet: con login, la puerta es la cookie."""
    assert client.get("/entrar").status_code == 200


def test_identity_26_el_usuario_se_crea_al_primer_acceso(tailnet, db):
    with db.connection() as conn:
        antes = conn.execute("SELECT COUNT(*) FROM identity_users").fetchone()[0]

    tailnet.get("/auth/me")
    tailnet.get("/auth/me")

    with db.connection() as conn:
        filas = conn.execute("SELECT email FROM identity_users").fetchall()
    assert antes == 0
    assert [f[0] for f in filas] == ["equipo@ejemplo.cl"], "se esperaba un solo usuario"


def test_identity_27_por_tailnet_no_se_manda_ningun_enlace(tailnet, mailer):
    respuesta = tailnet.post("/auth/magic-link", json={"email": EMAIL})

    assert respuesta.status_code == 404
    assert not mailer.sent, "se mando un correo con el acceso por tailnet"
