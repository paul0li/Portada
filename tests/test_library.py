"""Criterios de `specs/library.md`: el catalogo de fotos por rol."""

import pytest

from app.domains.library.service import ROLES

OTRO_EMAIL = "otra@ejemplo.cl"


def _subir(client, imagen, *, role="conductor", **campos):
    data = {"role": role, **{k: v for k, v in campos.items() if v is not None}}
    return client.post("/photos", data=data, files={"file": ("foto.png", imagen(), "image/png")})


def _entrar_como(client, email):
    import re

    client.post("/auth/logout")
    client.post("/auth/magic-link", json={"email": email})
    correo = client.app.state.mailer.sent[-1].text
    token = re.search(r"https?://\S+", correo).group(0).rsplit("=", 1)[-1]
    assert client.post("/auth/verify", json={"token": token}).status_code == 200


# --- subir ---------------------------------------------------------------


def test_library_01_subir_deja_la_foto_en_la_libreria(logged_in, imagen):
    respuesta = _subir(logged_in, imagen)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["role"] == "conductor"
    assert (cuerpo["width"], cuerpo["height"]) == (400, 300)
    assert logged_in.get("/photos").json()["stats"]["conductor"] == 1


@pytest.mark.parametrize("role", ROLES)
def test_library_02_los_seis_roles_del_template_son_validos(logged_in, imagen, role):
    assert _subir(logged_in, imagen, role=role).status_code == 201


def test_library_02_un_rol_inventado_se_rechaza(logged_in, imagen):
    respuesta = _subir(logged_in, imagen, role="protagonista")
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == "LIBRARY_ROLE_INVALID"


def test_library_03_se_guardan_label_y_descripcion(logged_in, imagen):
    respuesta = _subir(logged_in, imagen, label="Paula sonriendo", description="gesto de sorpresa")
    cuerpo = respuesta.json()
    assert cuerpo["label"] == "Paula sonriendo"
    assert cuerpo["description"] == "gesto de sorpresa"


def test_library_04_subir_sin_sesion_es_401(client, imagen):
    respuesta = _subir(client, imagen)
    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "IDENTITY_NO_SESSION"


def test_library_05_la_misma_imagen_en_dos_roles_es_un_solo_archivo(logged_in, imagen, settings):
    def misma():
        return imagen(size=(200, 200), color=(7, 7, 7))

    logged_in.post(
        "/photos", data={"role": "conductor"}, files={"file": ("a.png", misma(), "image/png")}
    )
    logged_in.post(
        "/photos", data={"role": "logo"}, files={"file": ("b.png", misma(), "image/png")}
    )

    assert len(logged_in.get("/photos").json()["photos"]) == 2
    archivos = [p for p in settings.media_dir.rglob("*") if p.is_file()]
    assert len(archivos) == 1, f"se duplico el archivo: {archivos}"


def test_library_06_al_subir_se_calcula_el_recorte(logged_in, imagen, db):
    _subir(logged_in, imagen, role="conductor")

    with db.connection() as conn:
        filas = conn.execute("SELECT status, kind FROM processing_derivatives").fetchall()
    assert [tuple(f) for f in filas] == [("ready", "cutout")]


def test_library_06_un_logo_no_pide_recorte(logged_in, imagen, db):
    """SPEC 11.5: el logo se pega tal cual. Recortarlo no tendria sentido."""
    _subir(logged_in, imagen, role="logo")

    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processing_derivatives").fetchone()[0]
    assert total == 0


# --- consultar -----------------------------------------------------------


def test_library_07_solo_veo_mis_fotos(logged_in, imagen):
    _subir(logged_in, imagen, role="conductor")
    _entrar_como(logged_in, OTRO_EMAIL)

    assert logged_in.get("/photos").json()["photos"] == []


def test_library_08_filtrar_por_rol(logged_in, imagen):
    _subir(logged_in, imagen, role="conductor")
    _subir(logged_in, imagen, role="invitado", label="distinta")

    solo_invitados = logged_in.get("/photos", params={"role": "invitado"}).json()["photos"]
    assert [p["role"] for p in solo_invitados] == ["invitado"]


def test_library_09_la_foto_de_otro_usuario_da_404_no_403(logged_in, imagen):
    photo_id = _subir(logged_in, imagen).json()["id"]
    _entrar_como(logged_in, OTRO_EMAIL)

    respuesta = logged_in.get(f"/photos/{photo_id}")
    # 403 confirmaria que ese id existe. 404 no distingue.
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "LIBRARY_PHOTO_NOT_FOUND"


def test_library_10_el_archivo_viene_con_etag_inmutable(logged_in, imagen):
    photo_id = _subir(logged_in, imagen).json()["id"]

    respuesta = logged_in.get(f"/photos/{photo_id}/file")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert respuesta.headers["etag"]
    assert "immutable" in respuesta.headers["cache-control"]
    assert len(respuesta.content) > 0


def test_library_11_con_el_mismo_etag_devuelve_304(logged_in, imagen):
    photo_id = _subir(logged_in, imagen).json()["id"]
    etag = logged_in.get(f"/photos/{photo_id}/file").headers["etag"]

    repetida = logged_in.get(f"/photos/{photo_id}/file", headers={"If-None-Match": etag})
    assert repetida.status_code == 304
    assert repetida.content == b""


# --- borrar --------------------------------------------------------------


def test_library_12_borrar_es_soft_delete(logged_in, imagen, db):
    photo_id = _subir(logged_in, imagen).json()["id"]

    assert logged_in.delete(f"/photos/{photo_id}").status_code == 204
    assert logged_in.get("/photos").json()["photos"] == []
    assert logged_in.get(f"/photos/{photo_id}").status_code == 404

    # La fila sigue: los episodios pasados la referencian (SPEC 11.11).
    with db.connection() as conn:
        fila = conn.execute(
            "SELECT deleted_at FROM library_photos WHERE id = ?", (photo_id,)
        ).fetchone()
    assert fila is not None and fila[0] is not None


def test_library_13_no_puedo_borrar_la_foto_de_otro(logged_in, imagen, db):
    photo_id = _subir(logged_in, imagen).json()["id"]
    _entrar_como(logged_in, OTRO_EMAIL)

    assert logged_in.delete(f"/photos/{photo_id}").status_code == 404
    with db.connection() as conn:
        fila = conn.execute(
            "SELECT deleted_at FROM library_photos WHERE id = ?", (photo_id,)
        ).fetchone()
    assert fila[0] is None, "la foto ajena fue borrada"


def test_library_14_borrar_dos_veces_no_es_error(logged_in, imagen):
    photo_id = _subir(logged_in, imagen).json()["id"]

    assert logged_in.delete(f"/photos/{photo_id}").status_code == 204
    assert logged_in.delete(f"/photos/{photo_id}").status_code == 204


# --- el marco ------------------------------------------------------------


def test_library_15_el_marco_se_sube_por_la_api(logged_in, imagen):
    """La grilla de SPEC 15.3 se armo pasando el marco como ruta local, saltandose
    la API entera. Si no se puede subir, ese resultado no se reproduce por HTTP."""
    respuesta = _subir(logged_in, imagen, role="marco", label="marco del show")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["role"] == "marco"
    assert logged_in.get("/photos", params={"role": "marco"}).json()["photos"][0]["label"] == (
        "marco del show"
    )
    assert logged_in.get("/photos").json()["stats"]["marco"] == 1


def test_library_16_al_marco_no_se_le_pide_recorte(logged_in, imagen, db):
    """Un marco ya trae su transparencia: recortarlo no significa nada (como el logo)."""
    # Sin esta linea el test pasa por el motivo equivocado: si la subida falla,
    # no hay derivado que contar y el COUNT da 0 igual.
    assert _subir(logged_in, imagen, role="marco").status_code == 201

    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processing_derivatives").fetchone()[0]
    assert total == 0


def test_library_17_las_fotos_viejas_sobreviven_a_la_reconstruccion(settings, imagen):
    """SQLite no deja alterar un CHECK: hay que reconstruir la tabla. Este test
    monta el esquema ANTERIOR, mete una fila, y aplica lo que falte encima."""
    import sqlite3

    from app.core.db import Database
    from app.core.migrations import discover, migrate

    inicial = next(m for m in discover() if m.domain == "library" and m.version == 1)
    db = Database(settings.database_path)
    with db.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS core_schema_version ("
            " domain TEXT NOT NULL, version INTEGER NOT NULL, name TEXT NOT NULL,"
            " checksum TEXT NOT NULL, applied_at TEXT NOT NULL, PRIMARY KEY (domain, version))"
        )
        conn.executescript(inicial.sql)
        conn.execute(
            "INSERT INTO core_schema_version (domain, version, name, checksum, applied_at) "
            "VALUES ('library', 1, ?, ?, '2026-08-30T00:00:00Z')",
            (inicial.name, inicial.checksum),
        )
        conn.execute(
            "INSERT INTO library_photos "
            "(id, user_id, media_id, role, label, description, created_at, deleted_at) "
            "VALUES ('foto-vieja', 'u1', 'm1', 'conductor', 'Paula', 'sonriendo',"
            " '2026-08-01T00:00:00Z', NULL)"
        )
        conn.commit()

    migrate(db)

    with db.connection() as conn:
        fila = conn.execute("SELECT * FROM library_photos WHERE id = 'foto-vieja'").fetchone()
        assert fila is not None, "la reconstruccion se llevo por delante las filas"
        assert (fila["label"], fila["description"]) == ("Paula", "sonriendo")
        # Y el rol nuevo ya cabe donde antes el CHECK lo rechazaba.
        conn.execute(
            "INSERT INTO library_photos "
            "(id, user_id, media_id, role, label, description, created_at, deleted_at) "
            "VALUES ('m', 'u1', 'm2', 'marco', NULL, NULL, '2026-08-30T00:00:00Z', NULL)"
        )
        # El indice parcial tiene que seguir existiendo despues de renombrar.
        indices = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='library_photos'"
            )
        ]
        assert "idx_library_photos_vivas" in indices, indices
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO library_photos "
                "(id, user_id, media_id, role, label, description, created_at, deleted_at) "
                "VALUES ('x', 'u1', 'm3', 'protagonista', NULL, NULL, '2026-08-30T00:00:00Z', NULL)"
            )
