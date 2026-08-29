"""Errores de intake."""

from app.core.errors import PayloadTooLarge, UnsupportedMedia


class ArchivoDemasiadoGrande(PayloadTooLarge):
    code = "INTAKE_FILE_TOO_LARGE"


class NoEsImagen(UnsupportedMedia):
    code = "INTAKE_NOT_AN_IMAGE"


class ImagenDemasiadoGrande(UnsupportedMedia):
    code = "INTAKE_IMAGE_TOO_LARGE"


class FormatoNoSoportado(UnsupportedMedia):
    code = "INTAKE_FORMAT_UNSUPPORTED"
