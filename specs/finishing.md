# finishing — criterios de aceptación

La pasada de IA sobre el armado. **En el MVP no existe**: su implementación por
defecto no hace nada, y es la que corre en todos los tests.

Eso no es un stub, es la apuesta del producto hecha código. SPEC §11.4 dice que
el armado siempre es salida válida y que la IA nunca es una dependencia; aquí el
camino sin IA no es un *fallback*, es el camino normal.

- **FINISHING-01** — el acabado por defecto devuelve el armado sin tocarlo, y el episodio queda igual de publicable.
- **FINISHING-02** — si el acabado falla, el episodio conserva su armado y se puede descargar: la IA es mejora, nunca dependencia (SPEC §7).
- **FINISHING-03** — el acabado nunca ve el logo ni el título: recibe la `base` (SPEC §7②).
