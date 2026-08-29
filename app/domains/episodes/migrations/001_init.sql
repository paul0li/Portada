-- episodes: el trabajo semanal.
--
-- Ninguna columna que apunta a otro dominio (user_id, photo_id, media_id) lleva
-- FOREIGN KEY: ninguna FK cruza dominios (ver CLAUDE.md).

CREATE TABLE episodes_jobs (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL,
    strength   TEXT NOT NULL DEFAULT 'medio',
    created_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX idx_episodes_jobs_usuario
    ON episodes_jobs (user_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- La seleccion del brief: que foto ocupa que rol en este episodio.
-- `position` ordena cuando un rol admite varias (objeto: hasta 2).
CREATE TABLE episodes_slots (
    episode_id TEXT NOT NULL REFERENCES episodes_jobs(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    photo_id   TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (episode_id, role, position)
);

-- Un armado por checksum de brief. Rearmar sin cambiar nada devuelve este mismo
-- registro en vez de recomponer: la idempotencia sale de la clave, no de un if.
CREATE TABLE episodes_assemblies (
    id               TEXT PRIMARY KEY,
    episode_id       TEXT NOT NULL REFERENCES episodes_jobs(id) ON DELETE CASCADE,
    brief_checksum   TEXT NOT NULL,
    template_version INTEGER NOT NULL,

    base_media_id    TEXT NOT NULL,   -- sin logo ni titulo: lo que veria el modelo
    final_media_id   TEXT NOT NULL,   -- publicable

    finish_applied   INTEGER NOT NULL DEFAULT 0,
    finish_provider  TEXT,
    finish_detail    TEXT,
    created_at       TEXT NOT NULL,

    UNIQUE (episode_id, brief_checksum)
);

CREATE INDEX idx_episodes_assemblies_episodio
    ON episodes_assemblies (episode_id, created_at DESC);
