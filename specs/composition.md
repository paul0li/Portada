# composition — criterios de aceptación

El armado determinístico. Es el dominio que decide si el producto existe
(SPEC §15.1) y el único que no toca la base de datos: entra un `Brief` con rutas
y un título, sale un PNG.

## El armado

- **COMPOSITION-01** — el mismo brief produce exactamente los mismos bytes. Es la garantía de consistencia de SPEC §4, y sin ella nada del resto importa.
- **COMPOSITION-02** — la salida es un PNG de 1280×720 (SPEC §10).
- **COMPOSITION-03** — sin `fondo` se usa el degradado de la paleta: la ausencia es una entrada válida, no un error (SPEC §11.8).
- **COMPOSITION-26** — el brief elige cuál de los degradados de la paleta responde a «no hay fondo», claro u oscuro, y elegirlo cambia los píxeles y el checksum de la base. Un nombre que no existe cae en el por defecto en vez de romper el armado (SPEC §11.4).
- **COMPOSITION-04** — un brief vacío produce igual un PNG válido: el armado siempre es salida válida (SPEC §11.4).
- **COMPOSITION-05** — el `conductor` va delante del `invitado`: el z-order de SPEC §6 se respeta.

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
- **COMPOSITION-20** — la tipografía viene del repo, no del sistema: si no, el mismo brief da píxeles distintos en dos máquinas y el armado deja de ser determinista.

## El preview

Lo que hace posible el preview en vivo de SPEC §8.4 no es un motor aparte: es la
separación `base`/`final` que ya existía para la pasada de IA. Cambiar el título
no toca la base, y la base es lo caro.

- **COMPOSITION-21** — el checksum de la base ignora el logo, el marco y el título: son *overlay*, y cambiarlos no invalida lo que hay debajo.
- **COMPOSITION-22** — cambiar solo el título reusa la base ya dibujada en vez de volver a componerla.
- **COMPOSITION-23** — el preview sale de la misma composición: mismo template y mismo layout, solo más pequeño y en JPEG. Si fuera otra implementación, dejaría de ser cierto que el layout vive en un archivo.
- **COMPOSITION-24** — repintar el preview por un cambio de título tarda menos de 60 ms.

## Identidad del armado

- **COMPOSITION-13** — el checksum del brief cambia si cambia el título, las fotos o la versión del template, y no cambia si no cambia nada.
- **COMPOSITION-14** — editar el template obliga a subir `TEMPLATE_VERSION`: cambiar el layout es declarar que las miniaturas nuevas no coinciden con las viejas.
- **COMPOSITION-15** — armar tarda menos de 400 ms.

## El encuadre de un recorte automático

- **COMPOSITION-25** — el encuadre ignora el alfa residual: un recorte con píxeles casi transparentes desperdigados se mide por la persona y no por el lienzo. Sin esto, la figura sale más chica y descentrada, en silencio.
