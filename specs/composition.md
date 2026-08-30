# composition — criterios de aceptación

El armado determinístico. Es el dominio que decide si el producto existe
(SPEC §15.1) y el único que no toca la base de datos: entra un `Brief` con rutas
y un título, sale un PNG.

## El armado

- **COMPOSITION-01** — el mismo brief produce exactamente los mismos bytes. Es la garantía de consistencia de SPEC §4, y sin ella nada del resto importa.
- **COMPOSITION-02** — la salida es un PNG de 1280×720 (SPEC §10).
- **COMPOSITION-03** — sin `fondo` se usa el degradado de la paleta: la ausencia es una entrada válida, no un error (SPEC §11.8).
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

## Identidad del armado

- **COMPOSITION-13** — el checksum del brief cambia si cambia el título, las fotos o la versión del template, y no cambia si no cambia nada.
- **COMPOSITION-14** — editar el template obliga a subir `TEMPLATE_VERSION`: cambiar el layout es declarar que las miniaturas nuevas no coinciden con las viejas.
- **COMPOSITION-15** — armar tarda menos de 400 ms.
