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
- **EPISODES-19** — un episodio puede llevar dos invitados, y el armado los lleva los dos hasta los píxeles. El tercero es 422, y cuántos caben lo dice el template: aquí no hay una segunda lista de topes que se pueda quedar vieja.

## Armar

- **EPISODES-06** — armar produce un PNG 1280×720 descargable.
- **EPISODES-07** — armar dos veces el mismo brief devuelve el mismo armado sin recomponer (idempotencia por checksum).
- **EPISODES-08** — cambiar el título y volver a armar produce un armado nuevo.
- **EPISODES-09** — el armado guarda con qué versión de template se hizo.
- **EPISODES-10** — si el acabado falla, el episodio conserva su armado y sigue siendo descargable (SPEC §7).

## Consultar

- **EPISODES-11** — listar devuelve solo mis episodios, del más reciente al más antiguo.
- **EPISODES-12** — el episodio de otro usuario devuelve 404.
- **EPISODES-13** — descargar el armado devuelve el PNG con `ETag`, y se revalida en vez de cachearse un año: esa URL sirve *el último* armado, y corregir el título produce otro.
- **EPISODES-14** — una foto borrada de la librería no rompe un episodio que ya la usó (SPEC §11.11).
- **EPISODES-15** — un episodio con `marco` lo lleva hasta los píxeles: el armado por HTTP produce lo mismo que el armado por script.
- **EPISODES-16** — corregir el título cambia lo que sirve la URL del armado, y un cliente que la había pedido antes se entera.
- **EPISODES-18** — el episodio recuerda los ajustes de cada rol y el armado los respeta; ajustar un rol que no se puede mover es 422, no un ajuste ignorado en silencio.
- **EPISODES-20** — el episodio recuerda los volteos de cada rol y el armado los respeta. Voltear un rol que no se voltea es 422; mover uno que solo se puede voltear, también — el `fondo` acepta el volteo y rechaza el empujón, en la misma petición.
- **EPISODES-21** — el episodio guarda un ajuste por figura y los devuelve en orden. Ajustar más figuras de las que el rol admite es 422; el ajuste de una figura que no se llegó a elegir simplemente no se guarda, porque no dibujaría nada.
- **EPISODES-22** — el episodio recuerda cómo se puso el título —cuánto se ensanchó el bloque y si va a una palabra por línea— y el armado lo respeta. Un ensanche desmedido se guarda acotado, no se rechaza.
- **EPISODES-17** — el episodio recuerda qué fondo por defecto se eligió, el armado lo respeta, y un nombre que no existe es un 422 y no un armado con el fondo equivocado.
