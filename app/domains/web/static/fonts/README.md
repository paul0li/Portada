# Tipografías de la interfaz

**Archivo** (variable, 400–700) e **IBM Plex Mono** (400 y 500). Ambas SIL Open
Font License 1.1: `OFL-Archivo.txt` y `OFL-IBMPlexMono.txt`.

Vienen del prototipo, y el emparejamiento es la personalidad de la app: una
grotesca cálida para leer, una mono para las micro-etiquetas en mayúsculas.

## Por qué están aquí y no se enlazan a Google Fonts

El mismo argumento que puso Anton en el repo (`composition/typefaces`): una sola
instancia, sin nube. Enlazar a `fonts.googleapis.com` mete una dependencia de red
en cada carga, y con Portada abierta desde el teléfono en la misma LAN —que es
como se usa— esa dependencia es justo la que no se puede resolver.

Son subconjuntos `latin` y `latin-ext`: lo que necesita el español, y nada más.
Los seis archivos suman ~99 KB.

## Al actualizarlas

`fonts.css` está generado: cada `@font-face` lleva su `unicode-range` original,
que es lo que hace que el navegador baje `latin-ext` solo si la página lo pide.
Regenerarlo a mano es fácil de estropear — mejor volver a bajar el CSS de Google
Fonts y quedarse con los bloques `latin` y `latin-ext`.
