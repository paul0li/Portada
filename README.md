# Portada

Miniaturas 1280×720 para un podcast semanal, armadas de forma determinista.
Desde el teléfono, por tu red de Tailscale, sin nube.

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
en la consola del servidor en vez de mandarlo. No hay contraseñas. Desplegada
por Tailscale no hay ni eso: ver «Despliegue».

## Comandos

| | |
| --- | --- |
| `make dev` | servidor con recarga en `:8000` |
| `make serve` | el servidor como se usa desde el teléfono: sin recarga, solo en `127.0.0.1` |
| `make reiniciar` | reinicia el servidor del agente de `launchd`: **después de cada cambio de Python o del `.env`** |
| `make estado` | qué está arriba: el servidor, Tailscale y el `serve` |
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

## Despliegue

Portada corre **en el Mac** y se abre desde el teléfono por **Tailscale**. No
hay servidor en la nube: las fotos de los invitados no salen de tu equipo.

```
iPhone (app Tailscale) ──HTTPS──▶ tailscale serve ──▶ uvicorn 127.0.0.1:8000 ──▶ data/
                                   (en el Mac)         (make serve)               SQLite + fotos
```

- **`tailscale serve`** pone HTTPS con un certificado real en
  `https://<tu-mac>.<tu-tailnet>.ts.net` (hoy: `https://macbook-pro-2.taile1b659.ts.net`)
  y solo lo ven los dispositivos de tu red de Tailscale. HTTPS no es un lujo
  aquí: sin él Safari no ofrece la hoja de compartir, y «Guardar en Fotos» y
  «Mejorar en ChatGPT» no funcionan.
- **No hay login.** Con `PORTADA_ACCESO=tailnet`, quien llega por Tailscale entra
  directo como `PORTADA_ACCESO_COMO`. Lo que no viene de una IP de Tailscale ni
  del propio Mac recibe 403.
- **uvicorn escucha solo en `127.0.0.1`.** Así nadie en el mismo wifi llega al
  puerto sin pasar por Tailscale.
- **El Mac tiene que estar encendido y despierto.** Si duerme, Portada no
  responde.

### Después de cada cambio de código: reiniciar

El servidor lo mantiene un agente de `launchd` (ver «Que se levante solo», más
abajo), y corre **sin recarga automática**: lo que cambies en el código no se ve
en el teléfono hasta reiniciarlo.

```bash
make reiniciar
# es lo mismo que: launchctl kickstart -k gui/$(id -u)/com.portada.servidor
```

Tarda un par de segundos. `make estado` confirma que volvió.

Lo que **pide** reiniciar: el código Python, el `.env` y las migraciones nuevas,
que se aplican al arrancar. Las plantillas, el CSS y el JS se leen del disco en
cada página y se ven sin reiniciar; ante la duda, reiniciar no cuesta nada.

### Montarlo desde cero

1. **Dependencias**, incluido el recorte de fondo:
   ```bash
   make install
   make install-cutout
   make cutout-model
   ```
2. **Tailscale en el Mac y en el iPhone**, con la misma cuenta. En el Mac, la app
   de [tailscale.com/download](https://tailscale.com/download) trae el comando
   `tailscale`; en el iPhone, la app de la App Store.
3. **Publicar Portada en la red de Tailscale:**
   ```bash
   tailscale serve --bg 8000
   ```
   La primera vez contesta con un enlace para habilitar HTTPS en tu red: ábrelo,
   acepta, y el comando termina solo. Queda guardado en Tailscale: sobrevive a
   reinicios y no hay que volver a correrlo.
4. **`.env`** en la raíz del repo (no se versiona):
   ```bash
   PORTADA_CUTOUT_PROVIDER=rembg
   PORTADA_PUBLIC_URL=https://<tu-mac>.<tu-tailnet>.ts.net
   PORTADA_ACCESO=tailnet
   PORTADA_ACCESO_COMO=<tu correo>
   ```
   `PORTADA_ACCESO_COMO` es la cuenta con la que se entra. Si ya existe, se
   conservan su librería y su historial; si no, se crea sola. El nombre del Mac
   en la red sale de `tailscale status`.
5. **Levantar el servidor:**
   ```bash
   make serve
   ```
6. **Abrir** `https://<tu-mac>.<tu-tailnet>.ts.net` en el iPhone, con la app de
   Tailscale conectada. Desde Compartir → «Agregar a inicio» queda como una app.

Para sumar a alguien del equipo: invítalo a tu red de Tailscale, o compártele
solo el Mac desde el panel de Tailscale. Entra como `PORTADA_ACCESO_COMO`, con la
misma librería.

### Si se cae

Primero, `make estado`. Dice cuál de las tres piezas falta:

```
servidor   arriba                               ← uvicorn responde
tailscale  100.x.x.x  macbook-pro-2  …  macOS   ← Tailscale conectado
serve
  https://macbook-pro-2.….ts.net (tailnet only)
  |-- / proxy http://127.0.0.1:8000             ← el serve apunta al servidor
```

| Síntoma | Qué pasa | Cómo se arregla |
| --- | --- | --- |
| `servidor  no responde` | El proceso murió, o el Mac se reinició | Con el agente de `launchd` (abajo) vuelve solo en segundos; si no, mirar `data/servidor.log`. Sin agente: `make serve` |
| `make serve` dice *address already in use* | Quedó otro proceso en el 8000 | `lsof -iTCP:8000 -sTCP:LISTEN` para ver cuál, `kill <PID>`, y otra vez `make serve` |
| `tailscale` dice *stopped* o *Logged out* | La app de Tailscale está cerrada o cerró la sesión | Abrir Tailscale en el Mac (`open -a Tailscale`) y entrar |
| `serve` vacío o *No serve config* | Se borró la configuración del `serve` | `tailscale serve --bg 8000` |
| El iPhone no carga la página | La app de Tailscale del iPhone está desconectada, o el Mac duerme | Conectar Tailscale en el iPhone; despertar el Mac |
| *Portada solo se abre por Tailscale.* (403) | Se entró por la IP de la red local, no por Tailscale | Usar la dirección `https://….ts.net` |
| Pide correo para entrar | El servidor arrancó sin `PORTADA_ACCESO=tailnet` | Revisar `.env` y reiniciar con `make serve` |
| ChatGPT no sale en la hoja de compartir | Está escondida en la lista de apps | En la fila de apps de la hoja: deslizar al final → «Más» → activar ChatGPT |

**Que el Mac no se duerma.** Con el Mac enchufado, en Ajustes del Sistema →
Batería → Opciones, activa «Evitar el reposo automático cuando la pantalla está
apagada». O, mientras haga falta, `caffeinate -s` en una terminal.

**Que se levante solo.** `make serve` muere con la terminal que lo lanzó. Para
que arranque al iniciar sesión y vuelva si se cae, un agente de `launchd`. Se
crea desde la raíz del repo, porque `$(pwd)` fija ahí las rutas:

```bash
cat > ~/Library/LaunchAgents/com.portada.servidor.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.portada.servidor</string>
  <key>WorkingDirectory</key><string>$(pwd)</string>
  <key>ProgramArguments</key><array>
    <string>$(whence -p uv)</string><string>run</string><string>uvicorn</string>
    <string>app.main:app</string><string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8000</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$(pwd)/data/servidor.log</string>
  <key>StandardErrorPath</key><string>$(pwd)/data/servidor.log</string>
</dict></plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.portada.servidor.plist
```

`whence -p` y no `which`: si `uv` es un alias en tu shell, `which` devuelve el
texto del alias y `launchd` falla sin dejar log (`launchctl list` muestra un 78).
Con el agente puesto, `make serve` sobra: el 8000 ya está ocupado.

- Comprobar que está corriendo: `launchctl list | grep portada` (la primera columna es el PID; un `-` con un número al lado es el código con que murió)

- Reiniciarlo después de un cambio de código: `make reiniciar`
- Quitarlo: `launchctl unload ~/Library/LaunchAgents/com.portada.servidor.plist`
- El log queda en `data/servidor.log`.

### Respaldo

Todo el estado vive en `data/`: la base SQLite y las fotos, direccionadas por
contenido. Respaldar es copiar esa carpeta con el servidor detenido.

### Volver al enlace mágico

Quitar `PORTADA_ACCESO` y `PORTADA_ACCESO_COMO` del `.env` y reiniciar. El
magic link es el modo por defecto; para que el correo salga de verdad hacen falta
`PORTADA_EMAIL_BACKEND=smtp` y las `PORTADA_SMTP_*` (ver `app/config.py`).

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
242 tests. El detalle por fase está en `CLAUDE.md`.
