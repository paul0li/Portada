-- identity: usuarios, magic links y sesiones.
--
-- Las FOREIGN KEY de este archivo apuntan solo a tablas de identity. Esa es la
-- regla: dentro de un dominio la integridad la garantiza SQLite; entre dominios
-- la garantiza el api.py (ver CLAUDE.md).

CREATE TABLE identity_users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,   -- ya normalizado: minusculas, sin bordes
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

-- El token viaja en una URL y solo su hash se guarda. `token_hash` es UNIQUE
-- porque es la clave de busqueda: canjear un enlace es un lookup indexado, no
-- un escaneo comparando fila por fila.
CREATE TABLE identity_magic_tokens (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
    token_hash     TEXT NOT NULL UNIQUE,
    created_at     TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    used_at        TEXT,          -- canjeado
    invalidated_at TEXT           -- reemplazado por uno mas nuevo
);

CREATE INDEX idx_identity_magic_tokens_pendientes
    ON identity_magic_tokens (user_id)
    WHERE used_at IS NULL AND invalidated_at IS NULL;

-- El `id` de la sesion ES el hash de la cookie. Asi no existe una columna con
-- el secreto ni un indice aparte: autenticar es un lookup por clave primaria.
CREATE TABLE identity_sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE INDEX idx_identity_sessions_user ON identity_sessions (user_id);

-- Rate limiting. Se guarda el intento, no el resultado: pedir un enlace para un
-- email que no existe cuenta igual, porque si no, contar intentos fallidos
-- seria justamente la forma de averiguar que cuentas existen.
CREATE TABLE identity_link_requests (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    ip         TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_identity_link_requests_email ON identity_link_requests (email, created_at);
CREATE INDEX idx_identity_link_requests_ip    ON identity_link_requests (ip, created_at);
