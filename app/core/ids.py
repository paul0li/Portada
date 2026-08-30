"""Identificadores ordenables por tiempo (ULID-like, sin dependencias).

26 caracteres en Crockford base32: 48 bits de milisegundos + 80 bits de azar.
Ordenables lexicograficamente, lo que hace que `ORDER BY id` sea `ORDER BY fecha`
y que un indice B-tree sobre la PK no se fragmente al insertar.
"""

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford: sin I, L, O, U


def _encode(value: int, length: int) -> str:
    out = [""] * length
    for i in range(length - 1, -1, -1):
        out[i] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(out)


def new_id() -> str:
    """Un identificador nuevo, ordenable por tiempo de creacion."""
    millis = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(millis, 10) + _encode(randomness, 16)


def is_id(value: str) -> bool:
    """True si `value` tiene la forma de un id nuestro.

    Sirve para rechazar entrada basura antes de que llegue al SQL, y sobre todo
    para que un id nunca pueda contener `/` o `..` cuando se usa en una ruta.
    """
    return len(value) == 26 and all(c in _ALPHABET for c in value)
