"""Criterios de `specs/intake.md`: la puerta por la que entran los bytes.

Estos tests llaman al `api` del dominio en vez de a HTTP: intake no expone
rutas propias -- `library` es quien recibe la subida. Lo que se prueba aca es el
contrato que `library` va a usar.
"""

import io

import pytest
from PIL import Image

from app.core.errors import PayloadTooLarge, UnsupportedMedia
from app.domains.intake import api as intake


def _imagen(fmt="PNG", size=(64, 48), color=(200, 30, 30), alpha=False) -> io.BytesIO:
    modo = "RGBA" if alpha else "RGB"
    relleno = (*color, 128) if alpha else color
    buffer = io.BytesIO()
    Image.new(modo, size, relleno).save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def test_intake_01_guardar_devuelve_los_metadatos(db, settings):
    media = intake.store(db, settings, _imagen(size=(320, 180)))

    assert media.format == "PNG"
    assert (media.width, media.height) == (320, 180)
    assert media.bytes > 0
    assert intake.path(settings, media).exists()


def test_intake_02_el_mismo_contenido_no_se_duplica(db, settings):
    primero = intake.store(db, settings, _imagen())
    segundo = intake.store(db, settings, _imagen())

    assert primero.id == segundo.id
    archivos = list(settings.media_dir.rglob("*.*"))
    assert len(archivos) == 1, f"se guardo dos veces: {archivos}"


def test_intake_03_la_ruta_deriva_del_hash(db, settings):
    media = intake.store(db, settings, _imagen(), filename="mi foto de perfil.png")
    ruta = intake.path(settings, media)

    assert media.sha256 in ruta.name
    assert "mi foto" not in str(ruta)


@pytest.mark.parametrize(
    "malicioso",
    ["../../etc/passwd", "/etc/passwd", "..\\..\\windows\\system32", "a/../../b.png"],
)
def test_intake_04_un_nombre_malicioso_no_escapa_del_directorio(db, settings, malicioso):
    media = intake.store(db, settings, _imagen(), filename=malicioso)
    ruta = intake.path(settings, media).resolve()

    assert ruta.is_relative_to(settings.media_dir.resolve())


def test_intake_05_lo_que_no_es_imagen_se_rechaza(db, settings):
    with pytest.raises(UnsupportedMedia):
        intake.store(db, settings, io.BytesIO(b"esto es un pdf, o casi"))


def test_intake_06_un_archivo_demasiado_grande_se_rechaza(db, settings):
    settings = settings.model_copy(update={"max_upload_bytes": 1024})
    grande = _imagen(size=(2000, 2000), color=(1, 2, 3))
    assert len(grande.getvalue()) > 1024

    with pytest.raises(PayloadTooLarge):
        intake.store(db, settings, grande)


def test_intake_07_una_bomba_de_descompresion_se_rechaza(db, settings):
    """Un PNG de un color plano comprime muchisimo: pocos KB, millones de pixeles."""
    settings = settings.model_copy(update={"max_image_pixels": 100_000})
    bomba = _imagen(size=(4000, 4000), color=(0, 0, 0))
    assert len(bomba.getvalue()) < settings.max_upload_bytes

    with pytest.raises(UnsupportedMedia):
        intake.store(db, settings, bomba)


def test_intake_08_manda_el_contenido_no_la_extension(db, settings):
    """Un JPEG llamado .png con content-type mentido sigue siendo un JPEG."""
    media = intake.store(
        db, settings, _imagen(fmt="JPEG"), filename="trampa.png", declared_mime="image/gif"
    )

    assert media.format == "JPEG"
    assert media.mime == "image/jpeg"


def test_intake_09_se_conserva_la_transparencia(db, settings):
    media = intake.store(db, settings, _imagen(alpha=True))

    assert media.has_alpha
    with Image.open(intake.path(settings, media)) as guardada:
        assert guardada.mode == "RGBA"
        assert guardada.getpixel((0, 0))[3] == 128


def test_intake_10_un_media_inexistente_devuelve_nada(db):
    assert intake.get(db, "01MNOEXISTE0000000000000000") is None


def test_intake_11_un_archivo_rechazado_no_deja_basura(db, settings):
    with pytest.raises(UnsupportedMedia):
        intake.store(db, settings, io.BytesIO(b"no soy una imagen"))

    restos = [p for p in settings.media_dir.rglob("*") if p.is_file()]
    assert restos == [], f"quedaron archivos huerfanos: {restos}"
