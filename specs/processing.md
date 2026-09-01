# processing — criterios de aceptación

Transformaciones sobre una imagen. Es el único dominio que algún día sabrá qué
es un modelo de segmentación; hoy su proveedor por defecto no hace nada.

- **PROCESSING-01** — pedir el recorte de una imagen deja un registro con su resultado.
- **PROCESSING-02** — con el proveedor `passthrough`, el recorte *es* la imagen original: el armado funciona igual sin ML, que es justamente lo que el MVP apuesta.
- **PROCESSING-03** — pedir dos veces el mismo recorte no lo recalcula: se computa una vez por imagen y se cachea (SPEC §6).
- **PROCESSING-04** — si el proveedor falla, queda registrado como fallido y `cutout_or_source` devuelve el original: un recorte roto no puede impedir un armado.

## El recorte de verdad (`rembg`)

- **PROCESSING-05** — el proveedor `rembg` devuelve un PNG con transparencia y deja la derivada `ready` a su nombre: el recorte automático es un proveedor más, no un camino aparte.
- **PROCESSING-06** — construir el proveedor `rembg` no importa `rembg`: la librería se carga en el primer recorte. Son ~190 MB de RSS, y un proceso que nunca recorta no tiene por qué pagarlos.
- **PROCESSING-07** — sin el modelo en disco el recorte falla como cualquier otro fallo: derivada `failed` y `cutout_or_source` devuelve el original. Que falte un archivo de 177 MB no puede ser distinto de que el modelo se equivoque.
- **PROCESSING-08** — borrar la derivada de una imagen la quita del registro y `cutout_or_source` vuelve a devolver el original. No se borra ningún archivo: los medios son inmutables y se direccionan por contenido, así que lo que se quita es un puntero, no una foto (SPEC §11.11).
