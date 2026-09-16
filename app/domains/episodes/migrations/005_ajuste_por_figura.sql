-- Un ajuste deja de ser del ROL y pasa a ser de la FIGURA.
--
-- El motivo lo trajo el segundo invitado: dos figuras comparten slot pero no
-- comparten sitio, y con una fila por rol moverlas juntas era lo unico posible.
--
-- Hay que reconstruir la tabla y no basta un ADD COLUMN: cambia la PRIMARY KEY,
-- que pasa a incluir la posicion. Es la receta oficial de SQLite. Dos avisos de
-- CLAUDE.md que aqui SI se tuvieron en cuenta:
--
--   * el `PRAGMA foreign_keys = OFF` de esa receta seria inerte: cada migracion
--     corre dentro de un BEGIN IMMEDIATE. Aqui no hace falta igualmente --
--     ninguna otra tabla apunta a esta, asi que soltarla no deja nada colgando.
--   * renombrar una tabla NO se lleva sus indices de vuelta. Esta no tiene
--     ninguno aparte de su PK, que se declara entera abajo.
--
-- `posicion` es el indice de la foto dentro de su rol, el mismo de
-- `episodes_slots`. Los ajustes que ya existian son todos de la primera figura,
-- que es la unica que habia: por eso entran con posicion 0 y siguen
-- significando exactamente lo mismo.
CREATE TABLE episodes_ajustes_nueva (
    episode_id TEXT    NOT NULL REFERENCES episodes_jobs(id) ON DELETE CASCADE,
    role       TEXT    NOT NULL,
    posicion   INTEGER NOT NULL DEFAULT 0,
    dx         INTEGER NOT NULL DEFAULT 0,
    dy         INTEGER NOT NULL DEFAULT 0,
    capa       INTEGER NOT NULL DEFAULT 0,
    voltear_x  INTEGER NOT NULL DEFAULT 0,
    voltear_y  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (episode_id, role, posicion)
);

INSERT INTO episodes_ajustes_nueva
    (episode_id, role, posicion, dx, dy, capa, voltear_x, voltear_y)
SELECT episode_id, role, 0, dx, dy, capa, voltear_x, voltear_y FROM episodes_ajustes;

DROP TABLE episodes_ajustes;
ALTER TABLE episodes_ajustes_nueva RENAME TO episodes_ajustes;
