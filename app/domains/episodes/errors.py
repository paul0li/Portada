"""Errores de episodes."""

from app.core.errors import NotFound, ValidationError


class EpisodioNoEncontrado(NotFound):
    """404 tambien si es de otra persona: un 403 confirmaria que existe."""

    code = "EPISODES_NOT_FOUND"


class SeleccionInvalida(ValidationError):
    code = "EPISODES_SELECTION_INVALID"


class FaltaConductor(ValidationError):
    code = "EPISODES_CONDUCTOR_REQUIRED"


class SinArmado(NotFound):
    code = "EPISODES_NO_ASSEMBLY"
