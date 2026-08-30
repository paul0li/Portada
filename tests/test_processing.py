"""Criterios de `specs/processing.md`."""

import io
from pathlib import Path

from PIL import Image

from app.domains.intake import api as intake
from app.domains.processing import api as processing


def _imagen() -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGBA", (32, 32), (10, 20, 30, 255)).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class ProveedorRoto:
    name = "roto"

    def cutout(self, source: Path) -> Path:
        raise RuntimeError("el modelo no respondió")


def test_processing_01_pedir_un_recorte_deja_registro(db, settings):
    media = intake.store(db, settings, _imagen())
    derivada = processing.ensure_cutout(
        db, settings, processing.PassthroughCutout(), media_id=media.id
    )

    assert derivada.status == "ready"
    assert derivada.provider == "passthrough"
    assert processing.get_cutout(db, media.id) is not None


def test_processing_02_passthrough_devuelve_la_imagen_original(db, settings):
    media = intake.store(db, settings, _imagen())
    processing.ensure_cutout(db, settings, processing.PassthroughCutout(), media_id=media.id)

    assert processing.cutout_or_source(db, media.id) == media.id


def test_processing_03_no_se_recalcula(db, settings):
    media = intake.store(db, settings, _imagen())
    proveedor = processing.PassthroughCutout()

    primera = processing.ensure_cutout(db, settings, proveedor, media_id=media.id)
    segunda = processing.ensure_cutout(db, settings, proveedor, media_id=media.id)

    assert primera.id == segunda.id
    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processing_derivatives").fetchone()[0]
    assert total == 1


def test_processing_04_un_recorte_roto_no_impide_el_armado(db, settings):
    media = intake.store(db, settings, _imagen())
    derivada = processing.ensure_cutout(db, settings, ProveedorRoto(), media_id=media.id)

    assert derivada.status == "failed"
    assert "no respondió" in (derivada.error or "")
    # La regla del SPEC 11.4, a nivel de recorte: se sigue con el original.
    assert processing.cutout_or_source(db, media.id) == media.id
