# processing — criterios de aceptación

Transformaciones sobre una imagen. Es el único dominio que algún día sabrá qué
es un modelo de segmentación; hoy su proveedor por defecto no hace nada.

- **PROCESSING-01** — pedir el recorte de una imagen deja un registro con su resultado.
- **PROCESSING-02** — con el proveedor `passthrough`, el recorte *es* la imagen original: el armado funciona igual sin ML, que es justamente lo que el MVP apuesta.
- **PROCESSING-03** — pedir dos veces el mismo recorte no lo recalcula: se computa una vez por imagen y se cachea (SPEC §6).
- **PROCESSING-04** — si el proveedor falla, queda registrado como fallido y `cutout_or_source` devuelve el original: un recorte roto no puede impedir un armado.
