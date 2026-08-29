"""Errores de library."""

from app.core.errors import NotFound, ValidationError


class RolInvalido(ValidationError):
    code = "LIBRARY_ROLE_INVALID"


class FotoNoEncontrada(NotFound):
    """404 tambien cuando la foto existe pero es de otra persona.

    Un 403 seria una confirmacion de que ese id existe. El 404 no distingue
    entre "no existe" y "no es tuya", que es exactamente lo que queremos.
    """

    code = "LIBRARY_PHOTO_NOT_FOUND"


class ArchivoNoEncontrado(NotFound):
    code = "LIBRARY_FILE_NOT_FOUND"
