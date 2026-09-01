# Portada — backend

Armado determinista de miniaturas 1280×720 para podcast. El producto y su
razón de ser están en `SPEC.md`; este archivo es **cómo se construye**.

## Outcome actual

**El frontend está terminado: Portada se usa de punta a punta.** Inicio con el
punto de entrada y los recientes, la librería, el flujo de cinco pasos con el
preview en vivo, el resultado descargable y el historial. Desde el teléfono, en
la LAN, sin nube. **197 tests.**

Corregir una errata cuesta **89 ms y no 287**: el título es *overlay*, así que se
pega sobre la misma base, que sigue en la caché (SPEC §7③). Eso valía para el
preview desde la fase 3, y ahora vale también para el armado final.

<details><summary>Fase 3 — el preview se actualiza en cada toque (SPEC §8.4)</summary>

La miniatura va fijada sobre cada paso y se repinta al elegir una foto y al
teclear el título. Armar deja de ser una revelación: para cuando se escribe el
título ya se vio el resultado.

Y la decisión de `CLAUDE.md` que decía que «el backend renderiza» se revertiría
si hiciera falta esto **se queda**, porque la pieza que lo abarata ya estaba
construida: la separación `base`/`final` de SPEC §7. Medido:

| Camino | p50 |
| --- | --- |
| repintar por el título (base en caché) | **24 ms** |
| primera vez, sin caché | 247 ms |
| peso: preview JPEG 640×360 vs PNG final | 71 KB vs 255 KB |

</details>

<details><summary>Fase 2 — hago una miniatura y la descargo</summary>

El flujo semanal entero desde el teléfono: elijo conductor, invitado, fondo y
objetos, escribo el título, y sale un PNG 1280×720 descargable.

El flujo son **cinco** pasos, no los seis del prototipo. Subir el logo y el marco
es *setup* y SPEC §8 ya lo cuenta como tal («el trabajo recurrente son los pasos
3–8»): la marca se pone una vez y el flujo la da por puesta, diciéndolo en el
resumen. Y el sexto paso del prototipo —«instrucciones personalizadas», con
presets tipo *colores saturados*— no está y no puede estar: es prosa dirigiendo a
un compositor, que es exactamente lo que SPEC §11.3 prohíbe. `WEB-18` lo vigila.

**El borrador del flujo vive en la URL**, no en el servidor: sin tabla de
borradores, atrás y recargar funcionan solos, y no hay nada escondido.

</details>

<details><summary>Fase 1 — entro con mi correo y gestiono mi librería</summary>

Desde el teléfono: pido el enlace, lo abro, subo una foto a su rol, la veo en la
grilla, entro a su detalle y la borro. HTML del servidor, cero Node.

El frontend es **Jinja2 + htmx servidos por el propio FastAPI**. La razón no es el
runtime: es que así un criterio de pantalla (`WEB-01…12`) es un test de
`TestClient` dentro de `make test`, en los mismos segundos y el mismo CI. Con una
SPA, probar «entro con mi correo y veo mi librería» pide un navegador — y
«criterio → test en rojo → implementación» se moriría justo en la capa nueva.

Se arreglaron dos bugs que lo bloqueaban: el marco no entraba por la API
(fase 0), y **el enlace del correo devolvía 405 al abrirlo** — apuntaba a
`/auth/verify`, que solo acepta POST. Nadie lo vio porque los tests extraen el
token y lo postean; ninguno abre el enlace, que es lo único que hace una persona.

</details>

El plan completo está en `/Users/paul0li/.claude/plans/glistening-stargazing-ritchie.md`.

<details><summary>Fase 0 — el marco entra por la API</summary>

La grilla de la fase 6 se armó pasando el marco como ruta local a
`composition.Brief`, saltándose la API: el resultado que valida el producto no se
reproducía por HTTP. `002_rol_marco.sql` reconstruye la tabla (SQLite no deja
alterar un `CHECK`) y `marco` pasa a ser el sexto rol de la librería.

</details>

<details><summary>Fase 6 — la grilla del canal pasa (SPEC §15.3)</summary>

Seis miniaturas de «El Club de las 3 de la Tarde» con fotos reales leen como un
mismo canal, también a 320 px (el tamaño al que se ven de verdad en un feed).

El template es **v2** y salió de mirar PNGs, no de leer el SPEC:

| Cambio | Por qué |
| --- | --- |
| Rol `marco` nuevo (z=6, sangre completa) | El show usa un PNG 16:9 con el nombre en una banda inferior. No es un logo |
| Título de y=604 a **y=500** | La banda del marco empieza en y=552 y se comía el título entero |
| Alturas 680/600 → **560/520** | SPEC §6 asumía fotos de torso. Con un busto real, 680 px de «figura» es una cabeza que tapa al invitado |
| Acento amarillo → **rojo del marco** `(233,40,39)` | Es el rojo de la marca, muestreado del propio marco |
| Degradado granate → **neutro frío** | Sobre fondo rojizo el acento rojo no se ve. Ahora el rojo es lo único rojo |
| Regla 9 px → **14 px** | A 320 px de feed, 9 px son 2 px y el acento desaparece |

La tipografía ya vive en el repo (**Anton**, SIL OFL): el armado es determinista
entre máquinas, no solo dentro de la tuya. Lo verifica `COMPOSITION-20`, y el CI
corre en Ubuntu justo para que eso signifique algo.

**Pendiente:** una foto de Su de torso (la actual es busto).

</details>

<details><summary>Fases anteriores</summary>

**Fase 5 — el flujo completo funciona por API.** Entrar → subir la librería →
crear el episodio → armar → descargar. Armar es idempotente por checksum del
brief; corregir el título produce un armado nuevo sin regenerar nada; una foto
borrada degrada el armado en vez de romperlo. `finishing` existe con su contrato
y no hace nada, que es la configuración en la que el producto ya funciona.
**132 tests en 4 s.**

**Fase 4 — hay una miniatura.** El armado determinístico produce un PNG
1280×720 en ~170 ms, con los cinco roles de SPEC §6 en sus sitios, título
auto-ajustado y logo pegado sin deformar. Devuelve **dos** imágenes: la `base`
sin logo ni título (lo que vería el modelo) y el `final`. 115 tests.

Se prueba sin servidor: `make preview ARGS='carpeta/ "TÍTULO"'`.

**Fase 3 — la librería funciona.** Se entra con magic link, se suben fotos
etiquetadas con los cinco roles de SPEC §6, se listan, se descargan con `ETag`
y se borran. La misma imagen subida dos veces ocupa un archivo. El recorte se
calcula al subir (hoy passthrough). 98 tests en 1,5 s.

**Siguiente: Fase 4 — "tengo un PNG 1280×720 que publicaría"** (dominio
`composition`). Es la fase que decide si el producto existe (SPEC §15.1), y se
hace como script, sin HTTP.

| Fase | Outcome | Estado |
| - | --- | --- |
| 0 | El servidor arranca y los tests corren | hecho |
| 1 | Entro a Portada con mi correo | hecho |
| 2 | Subo una foto y persiste como archivo + fila | hecho |
| 3 | Mi librería tiene los 5 roles de §6 | hecho |
| 4 | Tengo un PNG 1280×720 que publicaría (§15.1) | hecho — falta tu juicio con fotos reales |
| 5 | El flujo completo por API: brief → armado → descarga | hecho |
| 6 | Seis episodios seguidos parecen el mismo show (§15.3) | hecho con fotos reales |

## Cómo se trabaja aquí

**Outcome-oriented.** Ninguna fase se define por una capa técnica. No existe la
tarea *"implementar el repo de fotos"*; existe *"subo una foto y la veo en mi
librería"*. Cada fase declara tres cosas antes de empezar:

- **Outcome** — qué puedes ver o hacer que antes no.
- **Prueba** — el comando o el archivo que lo demuestra.
- **Lo que NO construimos** para llegar ahí.

Un slice está listo cuando el outcome es demostrable, no cuando el código parece
completo.

**Spec-driven.** Criterio en `specs/<dominio>.md` → test en rojo → implementación.
En ese orden. `tests/test_spec_coverage.py` falla si un criterio no tiene test, y
también si un test dice cubrir un criterio que no existe.

## Invariantes

Romper una de estas es un bug, no una decisión de diseño.

**Arquitectura** (verificado por `tests/test_domain_boundaries.py`)
- Un dominio solo importa el `api.py` de otro. Nunca su `repo`, `service` o `router`.
- La tabla `ALLOWED` de ese test **es** la documentación de dependencias.
- `core` no importa ningún dominio: es infraestructura, no negocio.
- Ninguna `FOREIGN KEY` cruza dominios. La integridad entre dominios la garantiza
  el `api.py`. Es lo que permite mover un dominio a otro proceso sin desarmar el esquema.
- `composition` no toca la base de datos ni sabe qué es un usuario.

**Producto** (vienen de `SPEC.md`)
- El armado siempre es salida válida; la IA nunca es una dependencia (§11.4).
  Por eso `finishing.NoopFinisher` es la implementación por defecto, y es la que
  corre en todos los tests: el camino sin IA no es un fallback, es el camino normal.
- El logo y el título nunca pasan por un modelo (§11.5, §11.6).
- El layout vive en un solo archivo: `composition/template.py` (§6).
- El `marco` es mobiliario de marca: va en el *overlay* junto al logo y el
  título, nunca en la base, y por tanto nunca pasa por un modelo. Pero es un
  asset del show, no un número del template: vive en la librería, como el logo.
- Todo lo que compone una miniatura entra por la API. Si un resultado solo se
  reproduce con una ruta local, no es un resultado del producto — es lo que pasó
  con la grilla de la fase 6 y lo que arregla `EPISODES-15`.
- Los tamaños se eligen para **cómo se ve la miniatura** (320 px en un feed), no
  para cómo se ve el PNG a 1280. Es una regla distinta y da números distintos.
- Borrar es soft delete: nada destructivo sin revisión (§11.11).

**Bytes que entran**
- Manda el contenido, nunca lo que dice el cliente. El nombre del archivo, su
  extensión y su `content-type` son texto que cualquiera escribe: el formato se
  decide abriendo la imagen y la ruta se deriva del SHA-256. No hay nada que
  sanitizar porque nada de lo que mandó el cliente participa en una decisión.
- Los medios se direccionan por contenido (`<sha[:2]>/<sha>.<ext>`): deduplicación
  gratis, archivos inmutables, y `Cache-Control: immutable` seguro por construcción.
- Un archivo rechazado no deja basura: el temporal se borra en todos los caminos.

**Datos y rendimiento**
- Transacciones cortas por contrato. **Nunca** se procesa una imagen dentro de
  `db.transaction()`. Es la única disciplina que hace que el límite de un escritor
  de SQLite no se note.
- Endpoints con Pillow son `def`, **no** `async def`: así FastAPI los manda al
  threadpool. Envolver Pillow en `async def` bloquea el event loop.
- Las rutas en disco derivan de ids o de content-hash, **jamás** del nombre que
  subió el usuario. Eso cierra el path traversal por construcción, no por sanitizar.

**Secretos y logs**
- Un secreto (magic link, cookie) se guarda siempre como hash SHA-256, nunca en claro.
  El `id` de una sesión **es** el hash de su cookie: autenticar es un lookup por
  clave primaria y no existe ninguna columna con el secreto.
- Pedir un magic link responde igual exista o no la cuenta. El rate limit cuenta
  intentos, no aciertos: contar solo los que dieron con un usuario real
  convertiría el contador en un oráculo de qué cuentas existen.
- El correo se manda **fuera** de la transacción: SMTP puede tardar segundos y
  una transacción abierta bloquea al único escritor de SQLite.
- Nunca se loguea: token en claro, cookie, email completo (usar `mask_email`).
- Un error inesperado se loguea completo del lado servidor y sale como 500 genérico.
  El cliente nunca ve un traceback, un nombre de tabla ni una ruta del sistema.

## Comandos

```bash
make install   # uv sync
make dev       # uvicorn --reload en :8000
make test      # unit + integration + golden + arquitectura + cobertura de spec
make lint      # ruff check + format --check
make fmt       # arregla lo que se pueda
make migrate   # aplica migraciones sin levantar el servidor
```

## Decisiones tomadas

| Fecha | Decisión | Por qué | Qué la revertiría |
| --- | --- | --- | --- |
| 2026-08-28 | **FastAPI**, no Go | El trabajo real (Pillow, segmentación futura) es Python; en Go habría que llamar a Python igual | Que el backend quede siendo puro I/O — auth y CRUD — sin trabajo de imagen dentro |
| 2026-08-28 | **Magic link propio**, no better-auth | `better-auth` es TypeScript: usarla obligaba a un segundo runtime en Node para ~150 líneas | Necesitar OAuth con varios proveedores, o SSO |
| 2026-08-28 | **SQLite** | Un archivo, cero infra, backup = copiar; tests con DB nueva en milisegundos | Que los cutouts en background den `SQLITE_BUSY` seguido. Entonces: Postgres local (su `LISTEN/NOTIFY` además da la cola sin Redis) |
| 2026-08-28 | **Sin ORM**: `sqlite3` + SQL explícito | Más rápido, sin magia que depurar, y aísla el cambio a Postgres en `repo.py` | Que el esquema crezca a ~25 tablas con relaciones densas |
| 2026-08-28 | **El backend renderiza** | Una sola implementación del template, testeable a nivel de píxeles | Necesitar el preview en vivo de SPEC §7 — entonces el template se sirve como JSON y ambos lados lo interpretan |
| 2026-08-28 | **Cutouts fuera del MVP** | rembg son ~180MB y una cola; `processing` nace passthrough y se enchufa después | Que el armado se vea como un collage y eso baste para rechazar SPEC §15.1 |
| 2026-08-28 | **Fechas como texto ISO-8601 UTC** | Ordenan lexicográficamente, se leen en un log, y evitan los adaptadores de `datetime` obsoletos desde Python 3.12 | Necesitar aritmética de fechas en SQL más allá de comparar |
| 2026-08-28 | **`TestClient` síncrono**, no httpx async + pytest-asyncio | Una dependencia menos y tests que se leen de arriba a abajo | Tener que testear WebSockets o streaming de verdad |
| 2026-08-28 | **`core/auth.py` con la dependencia invertida**: `main.py` cuelga el autenticador en `app.state` | Ningún dominio importa `identity`. Un dominio no debe saber *cómo* se autenticó alguien, solo que hay un `UserId` | Nada previsible; es lo que hace barato meter OAuth o una API key para el cliente móvil |
| 2026-08-28 | **Validación de email por regex propia**, no `EmailStr` | Evita la dependencia `email-validator`, y deja la validación junto a la normalización para que sea la misma por HTTP o por script | Necesitar validación de dominios internacionalizados (IDN) |
| 2026-08-28 | **Sin `last_seen_at` en las sesiones** | Sería una escritura en *cada* request autenticado contra el único escritor de SQLite: justo el cuello de botella que no queremos construir | Necesitar de verdad “última actividad”. Entonces: escribirlo con granularidad de horas, no de request |
| 2026-08-28 | **`intake` no conoce `user_id`** | Es lo que permite deduplicar por contenido entre usuarios; de quién es una foto lo sabe `library` | Necesitar borrado real por usuario (GDPR): ahí hay que contar referencias antes de borrar el archivo |
| 2026-08-28 | **`processing` existe desde el día 1 aunque no recorte nada** | `PassthroughCutout` no es un stub: si la foto ya viene como PNG transparente, el recorte ya está hecho. La costura para rembg existe sin costo | Nada; es la costura barata que evita reescribir `library` y `composition` después |
| 2026-08-28 | **Un recorte fallido no es un error** | `cutout_or_source` devuelve el original. Es la regla de SPEC §11.4 a nivel de recorte: un recorte roto degrada el resultado, no lo impide | Nada |
| 2026-08-28 | **El armado devuelve `base` y `final`, no una imagen** | Es la tubería de SPEC §7 hecha estructura: el modelo recibe la `base` sin logo ni título, y `reapply` los vuelve a pegar. Por eso corregir un typo no cuesta una regeneración | Nada; es lo que hace que las reglas §11.5 y §11.6 se cumplan solas |
| 2026-08-28 | **La tipografía se resuelve en cadena** (repo → sistema → error) | Las fuentes del sistema sirven para trabajar pero no son redistribuibles. Fallar con la fuente de mapa de bits de Pillow sería peor que fallar | Ya no: hay una fuente libre en el repo. La cadena queda como red, no como camino |
| 2026-08-30 | **Anton en el repo**, no Impact | Impact es de Microsoft: no se puede redistribuir, y en Linux no existe. Anton es su equivalente libre (SIL OFL) | Comprar una licencia de la tipografía real del show |
| 2026-08-30 | **El título se ancla a la línea base**, no a la ascendente | La ascendente la elige cada tipografía a su gusto; anclar a ella hacía que `bottom=500` significara una altura distinta según la fuente | Nada: la línea base es lo que «se apoya en y=500» quiere decir |
| 2026-08-31 | **La URL del armado se revalida, no se cachea un año** | Es un PUNTERO al último armado, no un archivo: corregir el título produce otro. Con `immutable` el navegador hacía lo correcto —no volver a pedirla— y la miniatura vieja se quedaba en pantalla. `no-cache` + `ETag` cuesta un 304 (3,4 ms) y nunca miente. Lo mismo en `/photos/{id}/file`, que sirve el recorte si está listo y si no el original | Que las URLs pasen a llevar el hash del contenido. Entonces sí son inmutables y el año vuelve |
| 2026-08-31 | **El historial es una lista de una columna, no una rejilla de dos** | A 430 px, dos miniaturas 16:9 por línea son 96 px de ancho, y a ese tamaño no se reconoce cuál es cuál — que es lo único que un historial tiene que hacer | Una pantalla ancha de verdad, no un teléfono |
| 2026-08-31 | **El fondo por defecto es claro** (degradado `(238,240,245)→(188,194,208)`) | Es el fondo que se ve cuando el episodio no trae foto, o sea el caso normal. Sigue siendo neutro frío por lo mismo que en v2: el rojo del acento y el del marco tienen que ser lo único rojo. Cuesta algo: el título es blanco con contorno oscuro, así que sobre claro se lee por el contorno y no por el relleno — comprobado a 320 px, que es como se ve en un feed | Que el título deje de ser blanco. Un título oscuro se leería mejor sobre este degradado, pero peor sobre una foto de fondo, que ya va oscurecida |
| 2026-08-31 | **Fuera htmx: HTML del servidor y ~15 líneas de JS** | Se vendorizó en la fase 1 y al terminar la 3 no lo usaba ni un atributo: todo son formularios y enlaces. Lo único que una navegación no puede hacer es repintar mientras se teclea, y eso son 15 líneas. 50 KB de dependencia para eso es peor que no tenerla | Que aparezcan muchos intercambios parciales — el A/B del resultado, reordenar objetos. Con tres o cuatro, htmx vuelve y se nota |
| 2026-08-31 | **El preview no escribe nada**: ni fila, ni archivo | El episodio se crea al confirmar, no al mirar. Si el preview creara episodios, el historial se llenaría de borradores de gente que solo estaba probando | Nada |
| 2026-08-31 | **Una caché de bases en memoria, explícita y no un `@lru_cache`** | Dibujar la base cuesta ~215 ms y repintar el overlay ~21 ms; sin caché, teclear recompondría el fondo y los recortes en cada tecla. Explícita porque así se puede vaciar en un test y se puede MIRAR si hubo acierto — que es lo que hace comprobable a `COMPOSITION-22` en vez de una intención | Más de una instancia. Entonces la caché o se comparte o se acepta que cada proceso tenga la suya |
| 2026-08-30 | **Jinja2 servido por FastAPI**, cero Node | Es la única opción donde el método sobrevive: un criterio de pantalla se prueba con el `TestClient` que ya existe, dentro de `make test`. Con una SPA (Vite o HTML+`fetch`) haría falta un navegador — Playwright, segundo runtime, decenas de segundos — o no probar el frontend | Que el preview necesite estado de cliente que el servidor no puede tener (edición manual, arrastrar, canvas). Entonces: islas de JS, no una SPA |
| 2026-08-30 | **Mismo origen: el frontend lo sirve el propio proceso** | Sin dev server aparte no hay CORS y la cookie httponly+lax se queda intacta. Un Vite en `:5173` habría costado `CORSMiddleware` con `allow_credentials` en código de producción, existiendo solo para una comodidad de desarrollo (`samesite` no habría hecho falta aflojarlo: el puerto no cuenta para el *site*) | Un cliente móvil nativo o un frontend en otro host. Ahí CORS es real, no una comodidad |
| 2026-08-30 | **`web` habla su propio dialecto** (formularios y fragmentos), no consume la API JSON | Dos transportes, no dos implementaciones: los dos routers llaman a las mismas funciones de `library.api`. La API JSON queda intacta para el cliente que venga | Que los dos routers diverjan en reglas y no solo en formato. Sería la señal de que la regla se escribió en un router en vez de en el service |
| 2026-08-30 | **`web` es el único dominio que puede importar `identity`** | Es quien DIBUJA la pantalla de entrar: pedirle que no sepa que existe un magic link es pedirle que dibuje un formulario sin saber de qué es. Lo que protegía la regla —que `library`, `episodes` y compañía no dependan de cómo se autenticó nadie— sigue intacto y verificado | Que `web` empiece a usar `identity` para algo que no sea su pantalla |
| 2026-08-30 | **Archivo e IBM Plex Mono vendorizadas** (SIL OFL) | El mismo argumento que puso Anton en el repo: una instancia, sin nube. Con Portada abierta desde el teléfono en la LAN, una dependencia de `fonts.googleapis.com` es justo la que no se resuelve | Nada |
| 2026-08-30 | **El acento de la UI es el rojo del show `#E92827`**, no el `#FF4D2E` del prototipo | Es `template.Palette.accent`, muestreado del marco. La interfaz y la miniatura deben decir el mismo rojo | Que cambie el rojo de la marca: entonces cambian los dos, desde `template.py` |
| 2026-08-30 | **El borrador del flujo viaja en la URL**, no en una tabla ni en la sesión | Son ids opacos del propio usuario sobre páginas `no-store`. A cambio: atrás y recargar funcionan sin escribir una línea, no hay borradores que caducar, y no hay estado escondido que se desincronice de lo que se ve | Que el borrador crezca más allá de unos ids (recortes por episodio, orden manual). Ahí sí hace falta persistirlo |
| 2026-08-30 | **El flujo son 5 pasos y la marca no es uno** | SPEC §8 ya cuenta subir el logo como setup, no como trabajo semanal. El prototipo lo metía dentro porque era v1 | Que un show cambie de marco cada semana — pero entonces deja de ser una marca |
| 2026-08-30 | **Se arma al terminar el flujo, sin pantalla de «Generando»** | Con `NoopFinisher` el armado tarda ~300 ms: una pantalla de espera no tendría nada que enseñar, y el prototipo la llenaba con progreso falso | Que exista la pasada de IA. Ahí sí hay dos momentos y la espera es real |
| 2026-08-30 | **`marco` es un rol normal de `library`**, no parte del template | El precedente ya estaba tomado: el `logo` también es mobiliario de marca y vive en la librería. Lo que decide dónde va un asset no es si cambia cada semana, es de quién es — Anton está en el repo porque la elegimos nosotros; el marco es el PNG del show. Meterlo en `template.py` sería meter el PNG de un cliente en el código, y dejaría el armado de §15.3 sin reproducir por HTTP | Necesitar varios shows con marcos que gestionemos nosotros. Entonces el marco es del template y el template deja de ser único |
| 2026-08-30 | **La marca (logo + marco) no se autocompleta en el backend** | Si el backend rellenara la selección, subir un marco nuevo cambiaría en silencio el checksum de episodios que nadie tocó. El «se pone una vez» lo da la UI preseleccionando el último de cada uno, no el esquema | Nada previsible: es lo que mantiene el checksum honesto |
| 2026-08-30 | **CI en Ubuntu**, no en macOS | Es el único sitio donde `COMPOSITION-20` dice algo: en un Mac hay Impact, así que una fuente que falte se resuelve al sistema y el fallo no sale hasta producción | Que el proyecto deje de desplegarse en Linux |
| 2026-08-28 | **Los tests corren con `log_level=DEBUG`** | En `WARNING`, `log.info(...)` ni construye el `LogRecord`, y un `extra` inválido queda dormido hasta producción. Ver la trampa de abajo | Que el ruido de logs estorbe al depurar un test |
| 2026-08-31 | **El recorte automático es `rembg` local, no una API** | Canva no expone su background remover: bajé su OpenAPI y no hay un solo endpoint de edición de imagen — lo único que dice «background» es `transparent_background` al exportar. Y las de pago (remove.bg, Photoroom) mandarían las fotos de los invitados a un tercero para ahorrar 546 MB | Que el recorte pase a ser masivo, o que el disco importe más que el «sin nube» |
| 2026-08-31 | **`u2net` y no BiRefNet** | Medido sobre una foto cruda real: u2net 0,44 s, birefnet-lite 13,4 s. BiRefNet tiene el borde más nítido mirando el PNG a 1280 — y esa ventaja **no sobrevive a 320 px**, que es como se ve la miniatura. 30 veces el tiempo por algo invisible donde se mira | Que la miniatura se empiece a mirar a 1280. No pasa en un feed |
| 2026-08-31 | **El recorte se pide, no se hace de oficio** | Recortar cuesta ~0,45 s y ~730 MB de RSS. Muchas fotos ya vienen con transparencia y no lo necesitan; el marco y el logo no lo admiten. De oficio, toda subida pagaría por la minoría que lo usa | Que las fotos crudas pasen a ser la norma. Entonces el default se da vuelta |
| 2026-08-31 | **Se pide desde un modal DESPUÉS de subir**, no con una casilla antes | Un modal sobre la foto *que estás por subir* sería estado que solo vive en el navegador, y habría costado la isla de JS que la decisión de «fuera htmx» tenía como condición de reversión. Con la foto ya subida no hace falta nada de eso: tiene URL, el `photo_id` viaja en la URL, y el modal es HTML del servidor con **cero JS**. Además se puede deshacer, que con una casilla no se podía | Que el modal necesite actuar sobre la foto antes de que exista — recortar a mano, elegir encuadre. Ahí sí vuelve la isla de JS |
| 2026-08-31 | **El proveedor declara `quita_fondo`**, y la pantalla lo pregunta | Con `passthrough` puesto —que es el default— el botón llamaba al recorte, el recorte devolvía la misma imagen, y no pasaba nada: parecía que la app estaba rota. Ahora el modal dice que el recorte no está activo en vez de ofrecer un botón muerto | Nada; preguntar por capacidad y no por nombre es lo que deja meter otro proveedor sin tocar la pantalla |
| 2026-08-31 | **`import rembg` vive dentro del recorte** | Con la casilla, el import deja de ser una optimización y pasa a ser un requisito: son ~190 MB de RSS al importar y ~470 MB con la sesión cargada. Quien nunca marca la casilla no paga nada. El precio es que el primer recorte del proceso tarda 3,4 s en vez de 0,45 s | Precargar en el arranque, si el primer recorte llegara a molestar. Cuesta 470 MB siempre |
| 2026-08-31 | **rembg y su modelo se instalan aparte** (`make install-cutout`, `make cutout-model`) | Son 369 MB de librerías (`pymatting`→`numba`→`llvmlite` son dependencias duras, no extras) más 177 MB de modelo que no vive en el repo. `passthrough` sigue siendo el default y el que corre en todos los tests: CI no baja nada | Nada; es el mismo argumento que `NoopFinisher` |

## Trampas conocidas

Cosas que ya nos mordieron. Están resueltas en el código; están acá para que no
vuelvan a morder en la próxima.

- **`executescript` hace COMMIT de la transacción pendiente antes de empezar.**
  Una transacción abierta por fuera no sobrevive. Por eso el `BEGIN IMMEDIATE` de
  una migración va **dentro** del script (`core/migrations.py`). Como el DDL de
  SQLite es transaccional, así una migración a medias no existe.
- **`PRAGMA foreign_keys = OFF` es inerte dentro de una transacción.** La receta
  oficial de SQLite para reconstruir una tabla (la única forma de cambiar un
  `CHECK`) empieza apagando las FK — y aquí ese `PRAGMA` **no hace nada**, porque
  `core/migrations.py` envuelve cada migración en `BEGIN IMMEDIATE`. No avisa: no
  es un error, es una sentencia que se ignora. `002_rol_marco.sql` es segura por
  otro motivo, no por el pragma: ninguna FK apunta a `library_photos` porque
  ninguna FK cruza dominios. El día que una lo haga, ese script la rompe callado.
- **Renombrar una tabla no se lleva sus índices de vuelta.** Al reconstruir,
  el índice vivía en la tabla vieja y se fue con el `DROP`. Hay que recrearlo
  explícitamente, y comprobarlo: `LIBRARY-17` mira `sqlite_master`, porque un
  índice que falta no rompe ningún test — solo hace lento lo que se consulta en
  cada paso del flujo semanal.
- **`ROLLBACK` sobre una transacción ya cerrada lanza, y su error tapa el error
  real.** De ahí la guarda `if conn.in_transaction` en `db.transaction()`. Un
  fallo en la limpieza nunca debe enmascarar el fallo que veníamos a propagar.
- **Los ids son ordenables entre milisegundos, no dentro de uno.** Dos ids creados
  en el mismo ms tienen sufijo aleatorio y no ordenan entre sí. No sirven como
  número de secuencia estricto.
- **`X-Forwarded-For` solo se cree con un proxy delante** (`app.state.trust_proxy`).
  Sin eso, el rate limit por IP es inútil: el cliente elige su propia identidad.
- **`extra={"name": ...}` revienta con `KeyError` en ejecución.** `name`, `module`,
  `filename`, `args`, `process` y compañía son atributos reservados de `LogRecord`;
  stdlib rechaza pisarlos. No avisa al escribirlo, y con el nivel de log alto el
  record ni se construye, así que el error **queda dormido hasta producción** —
  nos tumbó el arranque del servidor con los tests en verde. Dos defensas: los
  tests corren en DEBUG, y `CORE-13` lo caza estáticamente en todo `app/`.
- **Un `ETag` correcto no salva a un `Cache-Control` que miente.** La URL del
  armado llevaba `immutable, max-age=1 año` siendo un puntero al *último*
  armado. Al corregir una errata el backend hacía todo bien —nuevo armado, nuevo
  ETag— y el navegador seguía enseñando la miniatura vieja, porque `immutable`
  le dice justamente que no pregunte. **Ningún test de la API podía verlo:**
  `TestClient` no implementa una caché HTTP. Salió de corregir un título en un
  navegador de verdad. Corolario: una cabecera de caché es una promesa sobre el
  futuro, y hay que comprobar que la URL puede cumplirla.
- **Un contador que se resetea no sirve para vigilar nada.** `CacheDeBases.clear()`
  ponía `dibujadas = 0`, así que un `clear()` escondido dentro de una ruta era
  invisible: el test comparaba dos ceros. Ahora el contador solo sube y quien
  mide, mide diferencias. Lo mismo de siempre: si dos situaciones distintas dan
  el mismo número, un test no puede distinguirlas.
- **Un guardia de propiedad puede no poder fallar.** `WEB-24` comprobaba que el
  preview de una foto ajena no se sirve, y pasaba aunque se quitara la
  comprobación de sesión: sin sesión y con la foto de otro **daban la misma
  respuesta**, así que el test no podía distinguirlos. Se arregló haciendo que
  «sin sesión» conteste 401 y «esa selección no resuelve» conteste 204. Regla:
  si dos caminos distintos producen la misma respuesta, un test no puede vigilar
  uno de los dos. (Lo otro que aprendimos ahí: el guardia es difícil de romper de
  verdad porque `library/repo.py` no tiene ninguna función que busque una foto
  solo por su id. El invariante hace su trabajo.)
- **Un fixture puede tapar justo lo que el test mira.** El marco de los tests de
  `web` era un rectángulo opaco, y a sangre completa tapaba la miniatura entera:
  el PNG final salía siendo una mancha de un color, idéntica pasara lo que
  pasara debajo. `WEB-18` comparaba dos PNG para probar que un texto libre no
  cambia nada, y comparaba dos manchas iguales — pasaba con el bug puesto. El
  fixture ahora dibuja un marco de verdad, con el centro transparente. Corolario:
  cuando un test compara píxeles, hay que comprobar que los píxeles enseñan algo.
- **Un `204` congela un formulario HTML.** `POST /auth/logout` contesta 204, que
  es correcto para un cliente; ante un 204 el navegador **no navega**, así que
  «Salir» cerraba la sesión y dejaba la pantalla igual, como si el botón no
  hiciera nada. Por eso `web` tiene su propio `/salir` que redirige. Regla
  general: un endpoint pensado para un cliente no sirve tal cual para un
  formulario, y la diferencia no la enseña ningún test de la API.
- **`Image.verify()` deja el objeto inutilizable.** Hay que abrir la imagen dos
  veces: una para validar la estructura y otra para leer sus metadatos.
- **El límite de píxeles se comprueba después del encabezado y antes de decodificar.**
  Un PNG de un color plano pesa unos KB y puede declarar 40.000 × 40.000: el
  límite de bytes no protege de una bomba de descompresión.
- **`executescript` no es el único con reglas raras de transacción**; ver también
  la trampa de arriba. Regla general: si una sentencia puede tocar la transacción,
  compruébalo con un test antes de confiar.
- **`ruff` marca `B008` en `file: UploadFile = File(...)`.** La forma correcta no
  es silenciar la regla sino usar `Annotated[UploadFile, File()]`, que además es
  el estilo recomendado por FastAPI.
- **El `.pyc` guarda el mtime del fuente en SEGUNDOS.** Dos ediciones del mismo
  tamaño dentro del mismo segundo — un script que cambia un valor, corre los
  tests y lo revierte — dejan bytecode obsoleto que Python considera válido: el
  disco dice 48 y el proceso lee 56. `make test` va con
  `PYTHONDONTWRITEBYTECODE=1`; si algo parece imposible, `find . -name __pycache__
  -exec rm -rf {} +` antes de dudar de tu código.
- **Un recorte real trae padding transparente arbitrario.** Una de las fotos venía
  con 372 px vacíos a la izquierda. Sin recortar al alfa antes de escalar, el slot
  mide el *lienzo* en vez de la *persona* y la figura sale pequeña y descentrada.
  `_trim_alpha` lo arregla; `COMPOSITION-18` lo fija.
- **Cambiar de tipografía mueve el título, aunque el tamaño sea el mismo.** Anton
  tiene la ascendente 18 px más abajo que Impact a 104 px. Con el título anclado
  a la ascendente (`anchor="la"`), `bottom=500` no significaba «el título termina
  en y=500» sino «la ascendente de la última línea cae en 500 − line_height», que
  es otra cosa y la decide la fuente: la última línea se comía la regla de acento.
  Impact se salvaba por 7 px de casualidad. Ahora se ancla a la línea base
  (`anchor="ls"`), que es la misma idea en cualquier tipografía.
- **Un test de píxeles puede comprobar lo contrario de lo que crees.** El primer
  intento de `COMPOSITION-19` miraba los píxeles de la regla y pasaba con el bug
  puesto: la regla se dibuja **después** del título, así que lo tapa y sus píxeles
  siempre son del acento. Lo que delata la invasión es el bloque del título
  (572 px) siendo más ancho que la regla (200 px): lo que se cuela por fuera no lo
  tapa nada. Un test de guardia no vale hasta verlo fallar con el bug reintroducido.
- **Un acento del color de la marca puede desaparecer.** El rojo del show sobre un
  degradado granate, pegado a una banda roja, no se ve. Elegir bien el color no
  basta: hay que mirar contra qué cae.
- **Desaturar, oscurecer y aplicar viñeta se multiplican.** Tres efectos suaves
  dan uno brutal: un fondo de estudio (ya oscuro) quedaba negro con 0.55 × 0.75.
  Los valores del tratamiento de fondo salen de mirar el PNG, no de razonarlos.
- **`getbbox()` cuenta cualquier alfa distinto de cero, y un recorte automático
  no deja ceros duros.** rembg deja ~15.000 píxeles con alfa entre 1 y 8
  desperdigados: medido sobre una foto real, con `isnet` llegaban a las esquinas
  y el bbox saltaba de 912 a **1200 px** de ancho — el lienzo entero. `_trim_alpha`
  pasaba a encuadrar por el lienzo en vez de por la persona, así que la figura
  salía más chica y descentrada, sin romper nada y sin avisar. Es la trampa del
  padding transparente (`COMPOSITION-18`) con la causa al revés, y la vigila
  `COMPOSITION-25`. Corolario: el umbral no es cosmético; sin él, cambiar de
  modelo de segmentación cambia el encuadre.
- **`PYTHONDONTWRITEBYTECODE=1` es carísimo con 369 MB de dependencias.** El
  primer recorte por HTTP medía **47 s**, y no era rembg: sin `.pyc`, cada
  arranque reparsea scipy, scikit-image, numba y llvmlite desde el fuente. Con
  la caché de bytecode puesta —que es como corre `make dev`— son **3,4 s**. La
  variable está en `make test` por la trampa del mtime, y ahí no molesta porque
  los tests corren con `passthrough`. Pero cualquier medición de tiempo hecha
  con ella puesta miente por un orden de magnitud.
- **Una casilla HTML sin marcar no viaja.** No manda `off`: no manda nada. Por
  eso `web` lee la *presencia* del campo (`bool(recortar)`) y no su valor. Un
  `== "on"` funcionaría por casualidad hoy y se rompería el día que alguien le
  cambie el `value`.
- **Una casilla que no hace nada es un botón que miente.** «Sacarle el fondo»
  aparecía también en `logo` y `marco`, donde el recorte no existe: se marcaba y
  no pasaba nada. La lista de roles que admiten recorte la exporta `library` y la
  plantilla la lee; copiarla en el HTML habría dejado dos verdades. `WEB-33`
  vigila las dos direcciones — que esté donde debe y que no esté donde no.
- **Un botón que no puede fallar es un botón que miente, y vuelve por otra
  puerta.** Pasó dos veces con lo mismo en una tarde: primero la casilla
  «sacarle el fondo» aparecía en `logo` y `marco`, donde el recorte no existe;
  y después, ya arreglado eso, el botón del modal seguía apareciendo con
  `passthrough` configurado —el default— llamando a un recorte que devuelve la
  misma imagen. Ninguna de las dos rompía nada: las dos hacían creer que la app
  estaba rota. La diferencia entre «no ofrezco esto» y «esto no hace nada» tiene
  que estar en la pantalla, y quien la decide es la capacidad (`quita_fondo`),
  no el nombre del proveedor. Lo vigilan `WEB-35` y `WEB-36`.
- **Un test que compara la URL de vuelta entera se rompe con cada cosa que se le
  agregue.** `WEB-20` afirmaba `location == paso`, y abrir el modal le sumó
  `&nueva=<id>`: el test falló diciendo «me sacó del flujo» cuando el flujo
  estaba intacto. Ahora compara el paso sin los parámetros del modal, que es lo
  que el criterio dice de verdad. Regla: un test afirma lo que le importa, no
  todo lo que pasa por delante.
- **`StarletteDeprecationWarning: install httpx2`** al importar `TestClient`. Es
  ruido conocido de starlette 1.6 con httpx 0.28; no afecta nada. Se resuelve solo
  cuando starlette estabilice el soporte de httpx2.
