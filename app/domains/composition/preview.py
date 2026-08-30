"""Arma una miniatura desde una carpeta de fotos. Sin servidor, sin base de datos.

    make preview ARGS='fotos/ "LA VERDAD SOBRE EL CASO"'

Espera archivos nombrados por su rol: `conductor.png`, `invitado.png`,
`fondo.jpg`, `logo.png`, `objeto1.png`, `objeto2.png`.

Esto existe para responder la pregunta de SPEC 15.1 -- "¿el armado solo ya es
publicable?" -- con fotos reales y antes de que exista un endpoint. Si la
respuesta es no, este es el momento mas barato posible para saberlo.
"""

import sys
import time
from pathlib import Path

from app.domains.composition import fonts
from app.domains.composition.api import Brief, brief_checksum, compose
from app.domains.composition.template import SLOTS

EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp")


def collect(directory: Path) -> dict[str, list[Path]]:
    """Agrupa por rol segun el nombre del archivo."""
    encontradas: dict[str, list[Path]] = {}
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in EXTENSIONES:
            continue
        for role in SLOTS:
            if path.stem.lower().startswith(role):
                encontradas.setdefault(role, []).append(path)
                break
    return encontradas


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    directory = Path(argv[0])
    title = argv[1] if len(argv) > 1 else ""
    salida = Path(argv[2]) if len(argv) > 2 else directory / "miniatura.png"

    if not directory.is_dir():
        print(f"No es una carpeta: {directory}", file=sys.stderr)
        return 2

    photos = collect(directory)
    if not photos:
        print(f"No encontré fotos con nombre de rol en {directory}.", file=sys.stderr)
        print(f"Roles: {', '.join(SLOTS)}", file=sys.stderr)
        return 2

    brief = Brief(title=title, photos=photos)
    empezo = time.perf_counter()
    resultado = compose(brief)
    tardo = (time.perf_counter() - empezo) * 1000

    salida.write_bytes(resultado.final)
    base = salida.with_name(f"{salida.stem}-base{salida.suffix}")
    base.write_bytes(resultado.base)

    for role, rutas in sorted(photos.items()):
        print(f"  {role:<10} {', '.join(p.name for p in rutas)}")
    print()
    apretado = "" if resultado.title_fits else "  (apretado)"
    print(f"  título      {resultado.title_size}px{apretado}")
    print(f"  tipografía  {resultado.font}" + ("" if fonts.is_bundled() else "  (del sistema)"))
    print(f"  checksum    {brief_checksum(brief)[:16]}")
    print(f"  tiempo      {tardo:.0f} ms")
    print()
    print(f"  {salida}")
    print(f"  {base}   (lo que vería el modelo: sin logo ni título)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
