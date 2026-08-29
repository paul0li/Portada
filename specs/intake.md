# intake — criterios de aceptación

Recibir, validar y persistir bytes. No sabe qué es un rol, un usuario ni un
episodio: solo sabe si esto es una imagen y dónde quedó guardada.

- **INTAKE-01** — guardar una imagen devuelve su id, formato, dimensiones y tamaño.
- **INTAKE-02** — el mismo contenido guardado dos veces ocupa un solo archivo y devuelve el mismo id: el logo del show no se duplica cada semana.
- **INTAKE-03** — la ruta en disco deriva del hash del contenido, nunca del nombre que subió el usuario.
- **INTAKE-04** — un nombre de archivo malicioso (`../../etc/passwd`) no puede escribir fuera del directorio de medios.
- **INTAKE-05** — un archivo que no es imagen se rechaza con 415.
- **INTAKE-06** — un archivo que excede el límite de tamaño se rechaza con 413 sin haberlo cargado entero en memoria.
- **INTAKE-07** — una imagen con demasiados píxeles se rechaza, aunque el archivo pese poco (bomba de descompresión).
- **INTAKE-08** — el formato se decide por el contenido, no por la extensión ni por el `content-type` que declara el cliente.
- **INTAKE-09** — se conserva el canal alfa de un PNG transparente: es lo que hace que un recorte siga siendo un recorte.
- **INTAKE-10** — pedir un media que no existe devuelve nada, no un error de base de datos.
- **INTAKE-11** — un archivo rechazado no deja basura en el directorio de medios.
