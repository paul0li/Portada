# composition — criterios de aceptación

El armado determinístico. Es el dominio que decide si el producto existe
(SPEC §15.1) y el único que no toca la base de datos: entra un `Brief` con rutas
y un título, sale un PNG.

## El armado

- **COMPOSITION-01** — el mismo brief produce exactamente los mismos bytes. Es la garantía de consistencia de SPEC §4, y sin ella nada del resto importa.
- **COMPOSITION-02** — la salida es un PNG de 1280×720 (SPEC §10).
- **COMPOSITION-03** — sin `fondo` se usa el degradado de la paleta: la ausencia es una entrada válida, no un error (SPEC §11.8).
- **COMPOSITION-26** — el brief elige cuál de los degradados de la paleta responde a «no hay fondo», claro u oscuro, y elegirlo cambia los píxeles y el checksum de la base. Un nombre que no existe cae en el por defecto en vez de romper el armado (SPEC §11.4).
- **COMPOSITION-44** — una foto de fondo se ve con sus colores: va a sangre completa sin desaturar, oscurecer, desenfocar ni viñeta (v14). Quien sube una foto de fondo la sube para que se vea.
- **COMPOSITION-04** — un brief vacío produce igual un PNG válido: el armado siempre es salida válida (SPEC §11.4).
- **COMPOSITION-05** — el `conductor` va delante del `invitado`: el z-order de SPEC §6 se respeta.

## Empujar una figura (SPEC §6)

El template decide la posición **y el tamaño de partida**, no los finales. Un
episodio puede mover `conductor`, `invitado` y `objeto` a donde quiera, escalarlos
y reordenarlos entre ellos (v11: «como en Canva»). Lo que no puede: sacar una
figura del cuadro, meterla debajo del fondo ni taparle el título. Cuánto se puede
escalar y qué cuenta como «fuera del cuadro» lo sigue diciendo el template.

- **COMPOSITION-27** — un ajuste desplaza al rol respecto de su slot y su capa decide quién tapa a quién; con los ajustes en cero sale exactamente la misma imagen que sin ellos.
- **COMPOSITION-28** — un ajuste desmedido se acota en vez de sacar la figura del cuadro: el **centro** de la figura se queda dentro del lienzo, sea cual sea su escala y su sitio en el grupo. No hay pasos ni otros topes. Y una capa no puede esconder una figura bajo el fondo ni ponerla sobre el título.
- **COMPOSITION-40** — un ajuste puede escalar la figura, en porcentaje del tamaño que le da el template y dentro del rango que el template autora. En 100 no cambia ni un píxel; la figura escalada sigue apoyada en su mismo punto (por la base el conductor, por el centro un objeto), y la escala va en el checksum de la **base**.
- **COMPOSITION-29** — los ajustes van en el checksum de la **base**: mover una figura invalida lo de abajo, al revés que el título. Y un ajuste que no mueve nada no produce un checksum distinto.

## Voltear una figura (SPEC §6)

Del mismo tipo que el empujón: arregla **una** miniatura —el invitado mira hacia
afuera, el motivo del fondo cae justo detrás del título— en vez de cambiar el
canal entero. Y el template sigue decidiendo lo suyo: **qué** se puede voltear.

- **COMPOSITION-33** — un ajuste puede voltear la figura de izquierda a derecha o de arriba a abajo, y se ve en qué dirección se volteó, no solo que algo cambió. Sin volteo no cambia ni un píxel, y el volteo va en el checksum de la **base**: la figura está debajo del título.
- **COMPOSITION-34** — el `logo` y el `marco` no se voltean: los dos llevan el nombre del show escrito, y un texto en espejo es reinterpretar la marca (SPEC §11.5). El `fondo` sí, aunque no se pueda mover — son dos permisos distintos y se preguntan por separado.

## Cuando el invitado no es uno (SPEC §6)

El `invitado` deja de ser uno: en la semana en que vienen dos, vienen dos. El
reparto —cuánto se separan y dónde cae el centro del grupo— lo autora el
template, como todo lo demás del layout.

- **COMPOSITION-30** — un slot que admite varias figuras las reparte por las que **trae**, no por las que admite: con una sola, la figura cae donde el slot dice y no a media separación, dejando el hueco de la foto que no vino.
- **COMPOSITION-31** — dos invitados se dibujan los dos, separados por lo que dice el template y dentro del cuadro; con uno solo, la miniatura no cambia ni un píxel respecto de cuando el slot admitía uno.
- **COMPOSITION-35** — cada figura lleva su propio ajuste: mover al segundo invitado deja al primero donde estaba, y su capa puede ponerlo delante del otro. Un rol con menos ajustes que figuras deja las demás donde dice el template.
- **COMPOSITION-32** — dentro de un rol, el orden de las fotos es parte del brief: intercambiar dos invitados cambia los píxeles, así que tiene que cambiar el checksum. Ordenar los nombres antes de hashear daba el mismo checksum a dos miniaturas distintas, y con eso armar devolvía la vieja sin recomponer.

## Cómo se pone el título (SPEC §6)

El bloque termina en x=620 porque ahí empieza el invitado, y con eso las
palabras se apilan enseguida. Pero el título se dibuja **encima** de las
figuras, así que invadirlas es una decisión de la semana y no un error. El
template autora el rango y el paso; el episodio elige dentro.

- **COMPOSITION-36** — el episodio puede ensanchar o angostar el bloque del título dentro de los topes del template, y con más ancho el mismo título entra en menos líneas. Angostarlo hasta el tope **no pierde una palabra**: el título crece por encima del bloque antes que quedarse a medias. Un ensanche desmedido se acota en vez de romper nada. Es *overlay*: no invalida la base, así que cuesta lo mismo que corregir una errata.
- **COMPOSITION-37** — el título puede ir a una palabra por línea. Si no caben tantas, se vuelve al corte normal y se dice cuál se usó: apilar es un look, y ningún look justifica perder media frase.
- **COMPOSITION-38** — tocar el tamaño le pasa el mando al episodio: ese **es** el tamaño, y deja de regir el máximo de tres líneas. Con el tamaño en cero manda el template, como siempre. Es la diferencia entre repartir el texto y reinterpretarlo: con el auto-ajuste al mando, ensanchar el bloque no cambiaba el corte —subía el tamaño y el título se partía en las mismas líneas, más grande— y angostarlo no apilaba las palabras, las achicaba. Con el tamaño puesto, el ancho reparte y el alto dice hasta dónde pueden crecer. Lo único que sigue cediendo es lo físico: si no entra en el bloque, baja el tamaño hasta que entre. También es *overlay*.
- **COMPOSITION-39** — el episodio puede subir o bajar el **techo** del bloque del título dentro de los topes del template. El título sigue apoyado donde dice el template y crece hacia arriba, así que subir el techo es dejar entrar más líneas antes de que el auto-ajuste achique la letra —y es lo que hace que «una palabra por línea» quepa con más palabras—. Bajarlo aprieta el bloque y el auto-ajuste responde. También es *overlay*.
- **COMPOSITION-41** — el bloque del título se puede **mover** entero —texto, techo y regla de acento juntos—, sin cambiar cómo se corta ni de qué tamaño sale. Un desplazamiento desmedido se acota para que el bloque no salga del lienzo. Es *overlay*: no invalida la base.

## La separación base / final (SPEC §7)

- **COMPOSITION-06** — `base` no lleva logo ni título; `final` sí. Es lo que el modelo recibiría.
- **COMPOSITION-07** — cambiar solo el título cambia `final` pero deja `base` idéntica: por eso corregir un typo es gratis y no cuesta una regeneración.
- **COMPOSITION-08** — `reapply` vuelve a pegar logo y título sobre una base ya terminada, sin recomponer nada más.

## El marco

- **COMPOSITION-16** — el `marco` se dibuja a sangre completa y por encima de todo, incluido el título: es la ventana por la que se ve el resto.
- **COMPOSITION-17** — el marco va en el *overlay*, no en la base: como el logo y el título, nunca pasa por el modelo (SPEC §11.5).

## Recortes

- **COMPOSITION-18** — un recorte con margen transparente se escala por el **sujeto**, no por el lienzo: el slot dice «680 px de alto» y eso es alto de persona.

## Logo y título

- **COMPOSITION-09** — el logo se escala de forma uniforme y nunca se deforma (SPEC §11.5).
- **COMPOSITION-10** — el título se compone en mayúsculas (SPEC §6).
- **COMPOSITION-11** — un título largo se achica en vez de desbordarse, y nunca baja del mínimo legible.
- **COMPOSITION-12** — el corte de línea nunca parte una palabra.
- **COMPOSITION-19** — el título nunca se pisa con la regla de acento, sea cual sea la tipografía: el bloque se ancla a la línea base, no a la ascendente, que cada fuente elige a su gusto.
- **COMPOSITION-43** — el título se puede alinear a la izquierda, al centro o a la derecha de su bloque, y la regla de acento va con él. El bloque no se mueve por alinear. A la izquierda —la de siempre— no cambia ni un píxel ni el checksum de un armado de antes.
- **COMPOSITION-20** — la tipografía viene del repo, no del sistema: si no, el mismo brief da píxeles distintos en dos máquinas y el armado deja de ser determinista.

## El preview

Lo que hace posible el preview en vivo de SPEC §8.4 no es un motor aparte: es la
separación `base`/`final` que ya existía para la pasada de IA. Cambiar el título
no toca la base, y la base es lo caro.

- **COMPOSITION-21** — el checksum de la base ignora el logo, el marco y el título: son *overlay*, y cambiarlos no invalida lo que hay debajo.
- **COMPOSITION-22** — cambiar solo el título reusa la base ya dibujada en vez de volver a componerla.
- **COMPOSITION-23** — el preview sale de la misma composición: mismo template y mismo layout, solo más pequeño y en JPEG. Si fuera otra implementación, dejaría de ser cierto que el layout vive en un archivo.
- **COMPOSITION-24** — repintar el preview por un cambio de título tarda menos de 60 ms.
- **COMPOSITION-42** — el armado se puede pedir **por capas** —fondo, cada figura, logo, título y marco, en orden de dibujo y cada una con su sitio— y apilarlas donde dicen da **exactamente** la miniatura final. Es lo que deja al navegador mover una figura bajo el dedo sin una segunda implementación del template: el navegador apila, no compone. Si las capas y el armado pudieran diferir, el editor enseñaría una miniatura que no es la que se descarga.

## Identidad del armado

- **COMPOSITION-13** — el checksum del brief cambia si cambia el título, las fotos o la versión del template, y no cambia si no cambia nada.
- **COMPOSITION-14** — editar el template obliga a subir `TEMPLATE_VERSION`: cambiar el layout es declarar que las miniaturas nuevas no coinciden con las viejas.
- **COMPOSITION-15** — armar tarda menos de 400 ms.

## El encuadre de un recorte automático

- **COMPOSITION-25** — el encuadre ignora el alfa residual: un recorte con píxeles casi transparentes desperdigados se mide por la persona y no por el lienzo. Sin esto, la figura sale más chica y descentrada, en silencio.
