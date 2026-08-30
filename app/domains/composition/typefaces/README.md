# Tipografías

**`Anton-Regular.ttf`** — la del título. SIL Open Font License 1.1 (`OFL.txt`),
que permite redistribuirla dentro del repo.

Se toma el primer `.ttf`/`.otf` por orden alfabético. Si algún día hay varias,
nómbralas `01-titulo.ttf`, `02-…`.

## Por qué está aquí y no se usa la del sistema

Impact y Arial Narrow Bold sirven para trabajar, pero son de Microsoft y su
licencia no permite dejar el `.ttf` suelto en un repo. Y no existen en Linux:
en un servidor la cadena caía a DejaVu Sans Bold, que no es condensada ni tiene
el peso que necesita un título de miniatura. El mismo brief daba píxeles
distintos según la máquina, y ahí «armado determinista» dejaba de ser cierto.

Anton es un rediseño libre de la misma grotesca condensada de la que sale
Impact. `COMPOSITION-20` falla si esta carpeta se queda sin tipografía.

## Al cambiarla, mira el PNG

Una tipografía no se elige por su nombre. Anton tiene la ascendente 18 px más
abajo que Impact a 104 px, y eso movió el título lo suficiente como para que se
comiera la regla de acento — el bug que obligó a anclar a la línea base en vez
de a la ascendente. `COMPOSITION-19` lo vigila, pero el juicio de si *se lee* a
320 px en un feed no lo da ningún test.
