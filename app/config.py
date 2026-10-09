"""Configuracion del proceso.

Todo se lee del entorno con prefijo `PORTADA_`. Los valores por defecto son los
de desarrollo: `uv run make dev` funciona sin un solo `.env`. Lo que en produccion
seria inseguro (cookie sin `secure`, email a consola) esta desactivado por
`is_production`, no por confiar en que alguien recuerde ponerlo.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path("data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTADA_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_path: Path = DATA_DIR / "portada.db"
    media_dir: Path = DATA_DIR / "media"

    # La URL que el usuario abre. Es la base del magic link, asi que apuntar
    # esto al host equivocado manda tokens validos a un dominio ajeno.
    public_url: str = "http://localhost:8000"

    # Como se entra. `enlace` es el magic link. `tailnet` no tiene pantalla de
    # entrar: la puerta es Tailscale (`tailscale serve`), y todo el que llega
    # por ahi es `acceso_como`. Lo que no viene de Tailscale recibe 403, para
    # que escuchar en la red local no abra la app a quien comparta el wifi.
    acceso: Literal["enlace", "tailnet"] = "enlace"
    acceso_como: str = ""

    # El nombre que lleva el inicio. Es de la instalacion y no del codigo: el
    # repo no sabe para que canal se usa (WEB-53). Vacio, dice "Portada".
    programa: str = ""

    magic_link_ttl_minutes: int = 15
    session_ttl_days: int = 30
    magic_links_per_email: int = 3
    magic_links_per_ip: int = 10
    rate_limit_window_minutes: int = 10

    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 50_000_000  # techo anti decompression bomb

    # `passthrough` no recorta nada, y es correcto para el MVP: si la foto ya
    # viene como PNG con transparencia, el recorte ya esta hecho. Aca entrara
    # `rembg` sin tocar ningun otro dominio.
    cutout_provider: Literal["passthrough", "rembg"] = "passthrough"

    # `noop` no aplica ninguna pasada de IA. No es un stub pendiente: es la
    # configuracion en la que el producto ya funciona (SPEC 4.3, 11.4).
    finisher: Literal["noop"] = "noop"

    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Portada <no-reply@portada.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_starttls: bool = True

    @property
    def is_production(self) -> bool:
        return self.env == "prod"

    @property
    def cookie_secure(self) -> bool:
        """Solo HTTPS en produccion; en dev se trabaja sobre http://localhost."""
        return self.is_production

    @field_validator("public_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def _tailnet_dice_quien(self) -> "Settings":
        # Sin esto, `tailnet` arrancaria y fallaria en el primer request.
        if self.acceso == "tailnet" and not self.acceso_como.strip():
            raise ValueError("PORTADA_ACCESO=tailnet necesita PORTADA_ACCESO_COMO=<email>")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
