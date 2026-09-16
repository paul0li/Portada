-- Voltear una figura: izquierda por derecha, arriba por abajo.
--
-- Dos columnas y no una tabla nueva porque es el mismo concepto que ya vive
-- aqui: lo que un episodio le hace a un ROL. Un episodio que no voltea nada
-- sigue sin tener fila, y uno que ya la tenia sigue significando lo mismo --
-- por eso los dos DEFAULT son 0 y no hay nada que rellenar.
--
-- `ALTER TABLE ... ADD COLUMN` y no la receta de reconstruir la tabla: no hay
-- ningun CHECK que cambiar. Ver la trampa de `002_rol_marco.sql` en CLAUDE.md
-- para cuando si lo hay.
ALTER TABLE episodes_ajustes ADD COLUMN voltear_x INTEGER NOT NULL DEFAULT 0;
ALTER TABLE episodes_ajustes ADD COLUMN voltear_y INTEGER NOT NULL DEFAULT 0;
