"""Formas de salida HTTP de library."""

from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: str
    role: str
    label: str | None
    description: str | None
    width: int
    height: int
    has_alpha: bool
    created_at: str


class PhotoListOut(BaseModel):
    photos: list[PhotoOut]
    stats: dict[str, int]
