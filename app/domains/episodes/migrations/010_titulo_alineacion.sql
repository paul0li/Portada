-- El episodio recuerda como se alinea su titulo: `izquierda`, `centro` o
-- `derecha` dentro del bloque (template v13).
--
-- Las filas que ya existen quedan en 'izquierda', que es como se armaron.
-- Sin CHECK, por lo mismo que `degradado`: los nombres validos los autora
-- `composition/template.py` y los valida `episodes/service.py`.
ALTER TABLE episodes_jobs ADD COLUMN titulo_alineacion TEXT NOT NULL DEFAULT 'izquierda';
