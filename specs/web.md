# web — criterios de aceptación

Las pantallas. Es una capa de entrega, no un dominio de negocio: no tiene tablas,
no tiene reglas propias, y todo lo que sabe hacer lo hace llamando al `api.py` de
otro dominio. Por eso su tabla en `ALLOWED` es corta y se lee de un vistazo.

El web habla su propio dialecto — formularios y fragmentos de HTML — en vez de
consumir la API JSON. Son **dos transportes, no dos implementaciones**: los dos
routers llaman a las mismas funciones. El día que una regla exista en un router
y no en el otro, la regla estaba en el sitio equivocado.

Los criterios se prueban con el mismo `TestClient` síncrono que el resto. No
entra ningún navegador: si un comportamiento solo se puede comprobar con uno,
es que está en el cliente y no debería.

## Entrar

- **WEB-01** — sin sesión, una pantalla privada lleva a la de entrar; no devuelve un 401 en JSON.
- **WEB-02** — pedir el enlace responde lo mismo exista o no la cuenta, igual que la API.
- **WEB-03** — abrir el enlace del correo y pulsar «Entrar» deja la sesión iniciada.
- **WEB-04** — un enlace vencido o ya usado lo dice en la página y ofrece pedir otro, en vez de mostrar un error crudo.

## La librería

- **WEB-05** — subo una foto con su rol y aparece en la grilla de ese rol.
- **WEB-06** — la grilla muestra la foto misma, servida por su propia URL, no un marcador de posición.
- **WEB-07** — la librería de otra persona no se ve nunca.
- **WEB-08** — un archivo que no es una imagen da un error legible en la página, nunca un traceback ni un JSON crudo.
- **WEB-09** — borrar una foto son dos pasos: la grilla no borra, el detalle sí (SPEC §11.11).
- **WEB-12** — «Salir» cierra la sesión y deja al navegador en la pantalla de entrar, no en la misma página.

## La miniatura

El flujo semanal de SPEC §8, pasos 3–8. Son **cinco** pasos y no los seis del
prototipo: subir el logo y el marco es *setup*, y SPEC §8 ya lo cuenta como tal
(«el trabajo recurrente son los pasos 3–8»). La marca se pone una vez y el flujo
la da por puesta.

- **WEB-13** — recorro el flujo de punta a punta y al final tengo un PNG 1280×720 que puedo descargar.
- **WEB-14** — un paso opcional se omite y el armado sale igual: la ausencia es una entrada válida (SPEC §11.8).
- **WEB-15** — sin conductor no se puede avanzar, y la pantalla dice por qué en vez de fallar al final.
- **WEB-16** — la marca (logo y marco) va puesta sin pedirla cada semana, y el resumen del último paso dice cuál se va a usar.
- **WEB-17** — el título que escribo llega tal cual al armado, en mayúsculas y sobre la miniatura.
- **WEB-18** — la única perilla es la intensidad (*suave · medio · fuerte*): el flujo no acepta instrucciones libres, y un texto extra no cambia ni un píxel (SPEC §11.3).
- **WEB-19** — volver atrás en el flujo conserva lo ya elegido.
- **WEB-20** — puedo subir la foto del invitado sin salirme del flujo, y vuelvo al mismo paso con lo elegido intacto (SPEC §8, paso 3: el invitado se sube cada semana).
- **WEB-21** — la vuelta después de subir es siempre dentro de Portada: una dirección externa se ignora.
- **WEB-38** — puedo empujar al conductor, al invitado y a los objetos, y cambiar qué tapa a quién, desde el paso de ese rol y sin salir de él; el preview lo enseña y la elección llega al armado. En los topes el empujón deja de ofrecerse en vez de no hacer nada.
- **WEB-37** — en el paso del fondo puedo elegir el degradado claro o el oscuro sin salir del paso, la elección sobrevive hasta el final del flujo, y la miniatura sale con el fondo que elegí.

## El preview en vivo

SPEC §8.4 y §9: la miniatura se ve mientras se elige, fijada sobre el paso. Por
eso la generación deja de ser una revelación — para cuando se escribe el título
ya se ha visto el resultado.

- **WEB-22** — cada paso del flujo enseña el preview de lo elegido hasta ahí.
- **WEB-23** — el preview refleja el título que estoy escribiendo, sin recargar la página.
- **WEB-24** — el preview de una foto que no es mía no se puede pedir, ni con la sesión de otra persona ni sin sesión.
- **WEB-25** — si el preview falla, la pantalla no se queda en blanco ni enseña un error crudo (SPEC §11.4 llevado a la UI).

## Inicio e historial

La pantalla de inicio de SPEC §9: el punto de entrada al trabajo de la semana,
los episodios recientes y el tamaño de la librería.

- **WEB-26** — inicio ofrece empezar una miniatura nueva, y es lo primero que se ve.
- **WEB-27** — inicio muestra los episodios recientes con su miniatura, y el tamaño de la librería.
- **WEB-28** — el historial lista mis episodios del más reciente al más antiguo, y solo los míos.
- **WEB-29** — sin ningún episodio, inicio lo dice en vez de enseñar un hueco vacío.

## Corregir el título

SPEC §7③: el título se vuelve a componer sobre la misma base, así que corregir
una errata no cuesta una regeneración. Es la propiedad que hace que el producto
tolere equivocarse.

- **WEB-30** — puedo corregir el título de un episodio ya armado y la miniatura sale con el título nuevo.
- **WEB-31** — corregir el título reusa la base en vez de recomponerla: la errata sale gratis (SPEC §7③).
- **WEB-32** — no puedo tocar el episodio de otra persona.

## La forma de las páginas

- **WEB-10** — toda página privada se sirve con `Cache-Control: no-store`: nada de lo que hay dentro es de nadie más.
- **WEB-11** — ninguna página filtra el token del enlace ni la cookie en su HTML.

## Sacarle el fondo

- **WEB-33** — al subir una foto aparece un modal con la foto recién subida, y desde ahí se le puede quitar el fondo.
- **WEB-34** — quitarle el fondo desde el modal cambia lo que sirve la URL de la foto, y se puede deshacer: la decisión no es de una sola dirección.
- **WEB-35** — el modal no ofrece quitarle el fondo a un logo ni a un marco: son mobiliario de marca y ya vienen con su transparencia.
- **WEB-36** — si esta instancia no tiene recorte automático, el modal lo dice en vez de ofrecer un botón que no haría nada.
