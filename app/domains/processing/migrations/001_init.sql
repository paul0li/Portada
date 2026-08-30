-- processing: derivadas de una imagen.
--
-- `source_media_id` y `result_media_id` apuntan a intake_media_files pero NO
-- llevan FOREIGN KEY: ninguna FK cruza dominios (ver CLAUDE.md). Quien garantiza
-- que existan es intake.api, no SQLite.

CREATE TABLE processing_derivatives (
    id              TEXT PRIMARY KEY,
    source_media_id TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('cutout')),
    result_media_id TEXT,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'ready', 'failed')),
    provider        TEXT NOT NULL,   -- que lo produjo: passthrough hoy, rembg manana
    error           TEXT,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,

    -- Una derivada por (imagen, tipo). Es lo que hace que pedirla dos veces
    -- no la recalcule, y lo que la convierte en cache sin escribir un cache.
    UNIQUE (source_media_id, kind)
);
