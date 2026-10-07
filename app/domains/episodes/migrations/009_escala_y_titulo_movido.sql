-- Lo que se hace en el lienzo (template v11): escalar una figura y mover el
-- bloque del titulo.
--
-- `escala` es un porcentaje del tamano que el slot le da a la figura. DEFAULT
-- 100 y no 0, a diferencia de los demas: 100 es "como dice el template", que es
-- lo que tiene que significar una fila de antes de esto. Entero y no REAL por
-- lo mismo que en `composition.Ajuste`: 1.0 y 1.0000001 serian dos escalas que
-- dibujan lo mismo con checksums distintos.
--
-- `titulo_x` y `titulo_y` son cuanto se movio el bloque entero del titulo
-- respecto de donde lo pone el template, en pixeles del lienzo. Delta y no
-- valor absoluto, como los otros mandos del titulo: el dia que el template
-- mueva el bloque, un episodio con el titulo movido se mueve con el.
--
-- Los topes los pone `composition/template.py`, no un CHECK: son numeros de
-- layout. Y es `ADD COLUMN`: no hay CHECK que cambiar ni tabla que reconstruir.
ALTER TABLE episodes_ajustes ADD COLUMN escala INTEGER NOT NULL DEFAULT 100;
ALTER TABLE episodes_jobs ADD COLUMN titulo_x INTEGER NOT NULL DEFAULT 0;
ALTER TABLE episodes_jobs ADD COLUMN titulo_y INTEGER NOT NULL DEFAULT 0;
