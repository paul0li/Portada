"""Envio del magic link.

Dos implementaciones tras la misma interfaz, elegidas por `PORTADA_EMAIL_BACKEND`:
consola en desarrollo, SMTP en produccion. Sin SDK de terceros y sin cuenta que
crear para poder trabajar.

El mensaje es texto plano a proposito: un correo de un solo enlace no gana nada
con HTML, y el texto plano no cae en filtros de spam por imagenes remotas.
"""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.config import Settings
from app.core.logging import get_logger, mask_email

log = get_logger("portada.identity.email")


@dataclass(frozen=True, slots=True)
class Message:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    def send(self, message: Message) -> None: ...


class ConsoleSender:
    """Desarrollo: el enlace queda en la salida del servidor.

    Es el unico lugar del sistema donde un token aparece en claro en un log, y
    es intencional: sin esto no se puede entrar en local. Por eso ConsoleSender
    no se puede usar en produccion (lo impide `build_sender`).
    """

    def send(self, message: Message) -> None:
        print(f"\n--- correo para {message.to} ---\n{message.text}\n", flush=True)


class SMTPSender:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def send(self, message: Message) -> None:
        msg = EmailMessage()
        msg["From"] = self._s.email_from
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.text)

        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port, timeout=10) as smtp:
            if self._s.smtp_starttls:
                smtp.starttls()
            if self._s.smtp_user:
                smtp.login(self._s.smtp_user, self._s.smtp_password)
            smtp.send_message(msg)

        log.info("identity.email.sent", extra={"to": mask_email(message.to)})


def build_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SMTPSender(settings)
    if settings.is_production:
        raise RuntimeError(
            "email_backend='console' en produccion imprimiria magic links validos "
            "en los logs. Configura PORTADA_EMAIL_BACKEND=smtp."
        )
    return ConsoleSender()


def magic_link_message(*, to: str, link: str, ttl_minutes: int) -> Message:
    return Message(
        to=to,
        subject="Tu enlace para entrar a Portada",
        text=(
            "Hola:\n\n"
            "Abre este enlace para entrar a Portada:\n\n"
            f"{link}\n\n"
            f"Vence en {ttl_minutes} minutos y sirve una sola vez.\n"
            "Si no lo pediste tu, puedes ignorar este correo.\n"
        ),
    )
