-- Entra el rol `marco`: el PNG 16:9 que enmarca la miniatura y trae el nombre
-- del show en una banda inferior. El template lo tiene desde v2 (SPEC 15.3),
-- pero el CHECK de 001 solo conocia cinco roles, asi que la unica forma de
-- armar con marco era pasar una ruta local a composition.Brief, saltandose la
-- API. Es decir: el resultado que valida el producto no se reproducia por HTTP.
--
-- SQLite no permite ALTER de un CHECK. Hay que reconstruir la tabla.
--
-- TRAMPA: la receta oficial de SQLite empieza con `PRAGMA foreign_keys=OFF`, y
-- aqui eso NO HACE NADA: el pragma es inerte dentro de una transaccion, y
-- core/migrations.py envuelve cada migracion en BEGIN IMMEDIATE. Esta
-- reconstruccion es segura por otro motivo -- ninguna FOREIGN KEY apunta a
-- library_photos, porque ninguna FK cruza dominios (ver CLAUDE.md). Si algun
-- dia una la apuntara, este script la romperia en silencio.

CREATE TABLE library_photos_nueva (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    media_id    TEXT NOT NULL,

    -- Los seis roles del template. `marco` es mobiliario de marca igual que
    -- `logo`, y como el logo vive en la libreria: es un asset del show que sube
    -- su dueno, no un numero del template. Que se ponga una sola vez es una
    -- decision del flujo, no del esquema.
    role        TEXT NOT NULL CHECK (
                    role IN ('conductor', 'invitado', 'objeto', 'fondo', 'logo', 'marco')
                ),

    label       TEXT,
    description TEXT,
    created_at  TEXT NOT NULL,
    deleted_at  TEXT
);

INSERT INTO library_photos_nueva
    (id, user_id, media_id, role, label, description, created_at, deleted_at)
SELECT id, user_id, media_id, role, label, description, created_at, deleted_at
FROM library_photos;

DROP TABLE library_photos;

ALTER TABLE library_photos_nueva RENAME TO library_photos;

-- El indice se va con la tabla vieja: renombrar no lo trae de vuelta.
CREATE INDEX idx_library_photos_vivas
    ON library_photos (user_id, role, created_at DESC)
    WHERE deleted_at IS NULL;
