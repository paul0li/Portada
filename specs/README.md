# Criterios de aceptación

Un archivo por dominio. Cada criterio es una línea:

```
- **DOMINIO-NN** — lo que debe pasar, en una frase, observable desde fuera.
```

Reglas:

1. El criterio describe **comportamiento observable**, nunca implementación.
   Bien: *"un token usado dos veces devuelve 401 y no crea sesión"*.
   Mal: *"el service llama a `repo.mark_used`"*.
2. Cada criterio necesita un test cuyo nombre empiece por `test_dominio_nn_`.
   `tests/test_spec_coverage.py` falla si falta alguno.
3. El orden de trabajo es: escribir el criterio → escribir el test en rojo →
   implementar. No al revés.
4. Un criterio no se borra cuando se cumple. Se borra cuando deja de ser cierto
   que lo queremos.
