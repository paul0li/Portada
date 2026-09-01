# library — criterios de aceptación

El catálogo de fotos por rol. Es el activo durable del producto (SPEC §11.7):
se etiqueta una vez y se reusa durante un año.

## Subir

- **LIBRARY-01** — subir una imagen con un rol la deja en mi librería con sus dimensiones.
- **LIBRARY-02** — los seis roles del template son válidos (`conductor`, `invitado`, `objeto`, `fondo`, `logo`, `marco`); cualquier otro se rechaza con 422.
- **LIBRARY-03** — se guardan `label` y `description` opcionales: son lo que un módulo futuro de selección por IA va a leer (SPEC §12.2).
- **LIBRARY-04** — subir sin sesión devuelve 401.
- **LIBRARY-05** — la misma imagen subida con dos roles distintos son dos fotos pero un solo archivo en disco.
- **LIBRARY-06** — el recorte se calcula al subir y nunca al armar, para que el camino semanal no lo espere (SPEC §6). Pedirlo o no es de `LIBRARY-18`; *cuándo* ocurre es esto.

## Consultar

- **LIBRARY-07** — listar devuelve solo mis fotos, nunca las de otro usuario.
- **LIBRARY-08** — filtrar por rol devuelve solo ese rol.
- **LIBRARY-09** — pedir la foto de otro usuario devuelve 404, no 403: un 403 confirmaría que existe.
- **LIBRARY-10** — descargar el archivo devuelve la imagen con `ETag`, y se revalida en vez de cachearse un año: esa URL es un puntero —sirve el recorte si está listo y si no el original— así que su contenido puede cambiar.
- **LIBRARY-11** — volver a pedirla con el mismo `ETag` devuelve 304 sin cuerpo.

## Borrar

- **LIBRARY-12** — borrar es soft delete: la foto desaparece de la librería pero la fila sigue, porque los episodios pasados la referencian (SPEC §11.11).
- **LIBRARY-13** — no puedo borrar la foto de otro usuario.
- **LIBRARY-14** — borrar dos veces la misma foto no es un error la segunda vez.

## El marco

- **LIBRARY-15** — un `marco` se sube por la API como cualquier otra foto: el resultado de SPEC §15.3 se reproduce por HTTP y no con rutas locales.
- **LIBRARY-16** — al `marco` no se le pide recorte: ya trae su transparencia, igual que el `logo`.
- **LIBRARY-17** — las fotos que ya estaban en la librería siguen ahí después de reconstruir la tabla para admitir el nuevo rol.

## Sacarle el fondo

- **LIBRARY-18** — subo una foto pidiendo que le saquen el fondo y queda con su recorte hecho.
- **LIBRARY-19** — si no lo pido, no se computa ningún recorte: la foto queda como la subí. El recorte es una elección, no un peaje que paga toda subida.
- **LIBRARY-20** — si el recorte falla, la subida termina bien igual y la foto queda con su original. Pedir el recorte no puede volver frágil el acto de subir una foto.

## Quitarle el fondo a una foto que ya está

- **LIBRARY-21** — puedo quitarle el fondo a una foto que ya está en mi librería, sin volver a subirla.
- **LIBRARY-22** — puedo deshacerlo, y la foto vuelve a servir su original. El recorte es una capa que se pone y se saca, no una decisión que se toma una vez.
- **LIBRARY-23** — no puedo tocarle el fondo a la foto de otra persona.
