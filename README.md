# Portada

Miniaturas 1280×720 para un podcast semanal, armadas de forma determinista.
Desde el teléfono, en la LAN, sin nube.

Eliges quién va esta semana, escribes el título, y sale un PNG que publicarías.
Cada rol tiene un sitio fijo en el lienzo, así que seis episodios seguidos leen
como un mismo canal — que es lo que un feed reconoce antes de leer una palabra.

**El armado siempre es salida válida y la IA nunca es una dependencia.** El
camino sin modelo no es un plan B: es el camino normal, y es el que corre en
todos los tests.

## Empezar

```bash
make install
make dev       # http://localhost:8000
```

Las migraciones se aplican solas al arrancar; `make migrate` existe para
aplicarlas sin levantar el servidor.

Entras con tu correo: la app manda un enlace mágico, y en desarrollo lo imprime
en la consola del servidor en vez de mandarlo. No hay contraseñas.

## Comandos

| | |
| --- | --- |
| `make dev` | servidor con recarga en `:8000` |
| `make test` | unit + integración + golden + arquitectura + cobertura de spec |
| `make lint` / `make fmt` | ruff |
| `make migrate` | aplica migraciones sin levantar el servidor |
| `make preview ARGS='carpeta/ "TÍTULO"'` | arma una miniatura desde una carpeta de fotos, sin servidor ni base de datos |

### Recorte automático (opcional)

Quitarle el fondo a una foto usa [rembg](https://github.com/danielgatis/rembg)
con u2net, en local. Va aparte porque son ~546 MB y la app funciona sin ello:

```bash
make install-cutout                        # las librerías
make cutout-model                          # los 177 MB del modelo
PORTADA_CUTOUT_PROVIDER=rembg make dev
```

Sin esto, el proveedor por defecto es `passthrough` y la app lo dice en vez de
ofrecer un botón que no haría nada. Una foto que ya viene como PNG con
transparencia no lo necesita.

## Los documentos

Tres, y no se pisan:

- **[`SPEC.md`](SPEC.md)** — qué es Portada y por qué. El producto.
- **[`CLAUDE.md`](CLAUDE.md)** — cómo se construye: invariantes, decisiones
  tomadas con su condición de reversión, y las trampas que ya nos mordieron.
- **[`specs/`](specs/README.md)** — un archivo por dominio, un criterio de
  aceptación por línea.

El orden de trabajo es **criterio → test en rojo → implementación**, y no es una
intención: `tests/test_spec_coverage.py` falla si un criterio no tiene test, y
también si un test dice cubrir un criterio que no existe.

## El mapa

FastAPI + SQLite + Pillow. Cero Node: el frontend es Jinja2 servido por el mismo
proceso, de modo que un criterio de pantalla se prueba con el `TestClient` que ya
existe, dentro de `make test`.

```
app/domains/
  identity     magic link, sesiones
  intake       bytes que entran, direccionados por contenido
  processing   recorte (passthrough o rembg)
  library      el catálogo de fotos por rol
  composition  el armado. Puro: ni base de datos ni usuarios
  finishing    la pasada de IA. Hoy no hace nada, a propósito
  episodes     brief → armado → descarga
  web          las pantallas
```

Un dominio solo importa el `api.py` de otro, nunca su `repo`, `service` o
`router`, y ninguna `FOREIGN KEY` cruza dominios. La tabla `ALLOWED` de
`tests/test_domain_boundaries.py` **es** la documentación de dependencias, y el
test falla si alguien la contradice.

## Estado

El flujo está terminado y se usa de punta a punta: entrar, la librería, los
cinco pasos con preview en vivo, el resultado descargable y el historial.
197 tests. El detalle por fase está en `CLAUDE.md`.
