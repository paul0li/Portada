-- library: el catalogo de fotos por rol.
--
-- `user_id` y `media_id` no llevan FOREIGN KEY: apuntan a identity e intake, y
-- ninguna FK cruza dominios (ver CLAUDE.md).

CREATE TABLE library_photos (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    media_id    TEXT NOT NULL,

    -- Los cinco roles de SPEC 6. El CHECK deja la regla en el esquema y no solo
    -- en Python: una fila con un rol inventado no puede existir, la escriba quien
    -- la escriba.
    role        TEXT NOT NULL CHECK (role IN ('conductor', 'invitado', 'objeto', 'fondo', 'logo')),

    label       TEXT,
    description TEXT,   -- "gesto de sorpresa": lo que leera el modulo de seleccion (SPEC 12.2)
    created_at  TEXT NOT NULL,
    deleted_at  TEXT    -- soft delete: los episodios pasados siguen apuntando aca
);

-- El indice parcial cubre la consulta que se hace en cada paso del flujo
-- semanal: "mis fotos vivas de este rol".
CREATE INDEX idx_library_photos_vivas
    ON library_photos (user_id, role, created_at DESC)
    WHERE deleted_at IS NULL;
