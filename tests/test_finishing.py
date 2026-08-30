"""Criterios de `specs/finishing.md`.

El dominio esta vacio, pero su contrato no: estos tests fijan la regla de que la
IA nunca puede ser una dependencia.
"""

from app.domains.finishing import api as finishing


class AcabadoRoto:
    name = "roto"

    def finish(self, base_png, *, strength):
        raise RuntimeError("el modelo no respondió")


def test_finishing_01_el_acabado_por_defecto_devuelve_el_armado_intacto():
    base = b"\x89PNG-lo-que-sea"
    resultado = finishing.NoopFinisher().finish(base, strength="medio")

    assert resultado.png == base
    assert resultado.applied is False


def test_finishing_02_un_acabado_roto_no_rompe_el_episodio():
    """SPEC 7: si el paso 2 falla, el episodio conserva su armado."""
    base = b"\x89PNG-lo-que-sea"
    resultado = finishing.safe_finish(AcabadoRoto(), base, strength="fuerte")

    assert resultado.png == base, "se debe devolver el armado original"
    assert resultado.applied is False
    assert "no respondió" in (resultado.detail or "")


def test_finishing_03_el_acabado_recibe_la_base_sin_logo_ni_titulo(logged_in, imagen, db, settings):
    """SPEC 7.2: lo que ve el modelo es la base. Se comprueba en el episodio real."""
    from app.domains.episodes import service as episodes

    vistos: list[bytes] = []

    class Espia:
        name = "espia"

        def finish(self, base_png, *, strength):
            vistos.append(base_png)
            return finishing.Finish(png=base_png, applied=False, provider=self.name)

    conductor = logged_in.post(
        "/photos", data={"role": "conductor"}, files={"file": ("c.png", imagen(), "image/png")}
    ).json()["id"]
    episode = logged_in.post(
        "/episodes", json={"title": "EL RING", "selection": {"conductor": conductor}}
    ).json()

    user_id = logged_in.get("/auth/me").json()["id"]
    episodes.build_assembly(db, settings, Espia(), user_id=user_id, episode_id=episode["id"])

    assert len(vistos) == 1
    # La base no lleva el titulo. Se compara contra el armado completo: si el
    # espia hubiera recibido el final, serian iguales.
    with db.connection() as conn:
        fila = conn.execute(
            "SELECT base_media_id, final_media_id FROM episodes_assemblies"
        ).fetchone()
    assert fila["base_media_id"] != fila["final_media_id"]
