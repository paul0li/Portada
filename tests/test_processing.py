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


class _ProveedorQueRecorta:
    """Produce un archivo NUEVO, que es lo que hace un recorte de verdad.
    Passthrough devuelve el mismo, y por eso no sirve para ver la diferencia."""

    name = "de-mentira"
    quita_fondo = True

    def cutout(self, source: Path) -> Path:
        import tempfile

        destino = Path(tempfile.mkdtemp()) / "recorte.png"
        with Image.open(source) as img:
            recortada = img.convert("RGBA")
            recortada.putalpha(128)
            recortada.save(destino, "PNG")
        return destino


class ProveedorRoto:
    name = "roto"
    quita_fondo = True

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


# --- el recorte de verdad ------------------------------------------------


class SesionFalsa:
    """Hace lo mismo que rembg sin rembg: devuelve la imagen con alfa a medias.

    Existe para que el CONTRATO del proveedor se pruebe en CI sin bajar 177 MB.
    Lo que rembg hace de verdad lo mira PROCESSING-05b, que se salta si el
    modelo no esta.
    """

    def __init__(self) -> None:
        self.llamadas = 0

    def __call__(self, img: Image.Image) -> Image.Image:
        self.llamadas += 1
        recortada = img.convert("RGBA")
        recortada.putalpha(Image.new("L", recortada.size, 0).point(lambda _: 128))
        return recortada


def test_processing_05_rembg_deja_un_png_con_transparencia(db, settings):
    media = intake.store(db, settings, _imagen())
    proveedor = processing.RembgCutout(quitar_fondo=SesionFalsa())

    derivada = processing.ensure_cutout(db, settings, proveedor, media_id=media.id)

    assert derivada.status == "ready"
    assert derivada.provider == "rembg"
    # No es la imagen original: es una derivada nueva, con su propio media.
    assert derivada.result_media_id != media.id
    resultado = intake.get(db, derivada.result_media_id)
    assert resultado is not None
    assert resultado.format == "PNG"
    assert resultado.has_alpha


def test_processing_06_construir_el_proveedor_no_importa_rembg():
    """Importar rembg cuesta ~190 MB de RSS. Quien no recorta no los paga."""
    import sys

    for modulo in [m for m in sys.modules if m == "rembg" or m.startswith("rembg.")]:
        del sys.modules[modulo]

    processing.build_provider("rembg")

    assert "rembg" not in sys.modules, (
        "build_provider importo rembg. El import va DENTRO del recorte: "
        "un proceso que nunca recorta no debe cargar la libreria."
    )


def test_processing_07_sin_modelo_el_recorte_falla_y_no_rompe_nada(db, settings):
    """Que falte el modelo no puede ser distinto de que el modelo se equivoque."""

    def sin_modelo(img):
        raise FileNotFoundError("u2net.onnx")

    media = intake.store(db, settings, _imagen())
    proveedor = processing.RembgCutout(quitar_fondo=sin_modelo)

    derivada = processing.ensure_cutout(db, settings, proveedor, media_id=media.id)

    assert derivada.status == "failed"
    assert processing.cutout_or_source(db, media.id) == media.id


def test_processing_08_borrar_la_derivada_devuelve_el_original(db, settings):
    """Lo que se quita es un puntero, no una foto: los medios son inmutables."""
    media = intake.store(db, settings, _imagen())
    processing.ensure_cutout(db, settings, _ProveedorQueRecorta(), media_id=media.id)
    assert processing.cutout_or_source(db, media.id) != media.id

    processing.clear_cutout(db, media_id=media.id)

    assert processing.get_cutout(db, media.id) is None
    assert processing.cutout_or_source(db, media.id) == media.id
    # Y borrar dos veces no es un error la segunda.
    processing.clear_cutout(db, media_id=media.id)
