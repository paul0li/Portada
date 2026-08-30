"""Formas de entrada y salida HTTP de episodes."""

from pydantic import BaseModel, Field


class CreateEpisode(BaseModel):
    title: str = Field(default="", max_length=200)
    # rol -> ids de foto. Se acepta un id suelto o una lista.
    selection: dict[str, list[str] | str] = Field(default_factory=dict)
    strength: str = "medio"

    def normalized_selection(self) -> dict[str, list[str]]:
        return {
            role: ([value] if isinstance(value, str) else list(value))
            for role, value in self.selection.items()
        }


class UpdateTitle(BaseModel):
    title: str = Field(max_length=200)


class AssemblyOut(BaseModel):
    id: str
    template_version: int
    finish_applied: bool
    finish_provider: str | None
    created_at: str


class EpisodeOut(BaseModel):
    id: str
    title: str
    strength: str
    selection: dict[str, list[str]]
    created_at: str
    assembly: AssemblyOut | None = None
