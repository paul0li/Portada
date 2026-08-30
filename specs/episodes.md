# episodes — criterios de aceptación

El trabajo: un brief (fotos + título) se convierte en una miniatura descargable.
Este dominio orquesta y no calcula: resuelve la selección con `library`, arma
con `composition`, guarda con `intake` y pasa por `finishing`.

## Crear

- **EPISODES-01** — crear un episodio con título y selección devuelve el episodio.
- **EPISODES-02** — hace falta al menos un `conductor` (SPEC §6, mínimo 1); sin él, 422.
- **EPISODES-03** — no puedo usar la foto de otro usuario en mi episodio.
- **EPISODES-04** — `fondo` y `objeto` son opcionales: la ausencia es una entrada válida (SPEC §11.8).
- **EPISODES-05** — sin sesión, 401.

## Armar

- **EPISODES-06** — armar produce un PNG 1280×720 descargable.
- **EPISODES-07** — armar dos veces el mismo brief devuelve el mismo armado sin recomponer (idempotencia por checksum).
- **EPISODES-08** — cambiar el título y volver a armar produce un armado nuevo.
- **EPISODES-09** — el armado guarda con qué versión de template se hizo.
- **EPISODES-10** — si el acabado falla, el episodio conserva su armado y sigue siendo descargable (SPEC §7).

## Consultar

- **EPISODES-11** — listar devuelve solo mis episodios, del más reciente al más antiguo.
- **EPISODES-12** — el episodio de otro usuario devuelve 404.
- **EPISODES-13** — descargar el armado devuelve el PNG con `ETag` inmutable.
- **EPISODES-14** — una foto borrada de la librería no rompe un episodio que ya la usó (SPEC §11.11).
- **EPISODES-15** — un episodio con `marco` lo lleva hasta los píxeles: el armado por HTTP produce lo mismo que el armado por script.
