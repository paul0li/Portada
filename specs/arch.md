# arquitectura — criterios de aceptación

Las reglas estructurales del plan, verificadas por `tests/test_domain_boundaries.py`.
No describen comportamiento del producto, sino la forma del código que lo sostiene.

- **ARCH-01** — cada carpeta en `app/domains/` declara sus dependencias en la tabla `ALLOWED`, y no sobra ninguna entrada.
- **ARCH-02** — un dominio solo importa el `api.py` de otro, y solo de los que tiene permitidos.
- **ARCH-03** — `core` no importa ningún dominio: es infraestructura, no negocio.
- **ARCH-04** — `composition` no toca la base de datos, para poder responder SPEC §15.1 con un script.
