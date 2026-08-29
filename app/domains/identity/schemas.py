"""Formas de entrada y salida HTTP de identity."""

from pydantic import BaseModel, Field


class MagicLinkRequest(BaseModel):
    # `str` y no `EmailStr`: la validacion real vive en el service (junto a la
    # normalizacion) para que sea la misma se entre por HTTP o por un script, y
    # para no arrastrar la dependencia `email-validator`.
    email: str = Field(max_length=320)


class VerifyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: str
