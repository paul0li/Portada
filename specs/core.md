# core — criterios de aceptación

Infraestructura compartida: no es un dominio, pero tiene contrato.

- **CORE-01** — `GET /health` responde 200 con `status: ok`.
- **CORE-02** — toda respuesta lleva la cabecera `X-Request-Id`.
- **CORE-03** — un `X-Request-Id` entrante y con forma válida se conserva en la respuesta, para poder correlacionar a través de un proxy.
- **CORE-04** — un `X-Request-Id` entrante con forma inválida se descarta y se genera uno nuevo: es una cabecera que cualquiera puede escribir y termina en nuestros logs.
- **CORE-05** — una ruta inexistente devuelve 404 con el formato de error estándar, no con el de FastAPI.
- **CORE-06** — un `AppError` se traduce a su status y su `code` estable, y el `request_id` del cuerpo coincide con el de la cabecera.
- **CORE-07** — una excepción no controlada devuelve 500 genérico sin filtrar el traceback, el tipo de la excepción ni su mensaje.
- **CORE-08** — un cuerpo que no valida devuelve 422 nombrando los campos, sin incluir el valor que el usuario envió.
- **CORE-09** — las migraciones se aplican solas al arrancar y correrlas dos veces no cambia nada.
- **CORE-10** — editar una migración ya aplicada falla ruidosamente en vez de divergir en silencio.
- **CORE-11** — una migración que falla a mitad no deja tablas a medias ni queda registrada.
- **CORE-12** — un id es ordenable por tiempo de creación y no puede contener separadores de ruta.
- **CORE-13** — ninguna llamada a log usa en `extra` un nombre reservado de `LogRecord`: stdlib lanza `KeyError` en tiempo de ejecución, no al escribirlo.
