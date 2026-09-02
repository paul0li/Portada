-- El bloque del titulo deja de ser de un solo ancho.
--
-- `titulo_ancho` es cuanto se ensancha (o se angosta, en negativo) respecto del
-- bloque que dice el template, en pixeles. Es un DELTA y no un ancho absoluto
-- por lo mismo que la capa de un ajuste es relativa: el dia que el template
-- cambie el bloque, un episodio ensanchado se mueve con el en vez de quedarse
-- clavado en un numero que ya no significa lo mismo. Los topes los pone
-- `composition/template.py`, no un CHECK: son numeros de layout.
--
-- `titulo_apilado` es "una palabra por linea". Puede pedirse y no caber -- con
-- demasiadas palabras se vuelve al corte normal -- asi que esta columna guarda
-- lo que se PIDIO, y lo que se pudo lo dice el armado.
--
-- Los dos con DEFAULT 0: un episodio de antes de esto significa exactamente lo
-- mismo que antes, que es lo que tiene que significar.
ALTER TABLE episodes_jobs ADD COLUMN titulo_ancho   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE episodes_jobs ADD COLUMN titulo_apilado INTEGER NOT NULL DEFAULT 0;
