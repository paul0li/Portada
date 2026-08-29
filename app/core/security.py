"""Primitivas de secretos.

Regla que no se negocia: un secreto (magic link, cookie de sesion) se guarda
SIEMPRE como hash y nunca en claro, ni en la DB ni en un log. El hash es
SHA-256 crudo -- no bcrypt -- porque estos tokens son 256 bits de entropia real:
no hay diccionario que atacar, y necesitamos que la busqueda sea un lookup
indexado en vez de un escaneo comparando fila por fila.
"""

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    """Un secreto nuevo, apto para viajar en una URL o una cookie."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """El hash que se guarda. Determinista: sirve como clave de busqueda."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """Comparacion en tiempo constante, para los casos que no son lookup."""
    return hmac.compare_digest(a, b)
