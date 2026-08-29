-- intake: los bytes y sus metadatos.
--
-- No hay `user_id` aca a proposito. intake no sabe de quien es un archivo; eso
-- lo sabe `library`, que guarda la asociacion. Esa ignorancia es lo que permite
-- deduplicar por contenido: si dos personas suben el mismo logo, es un archivo.

CREATE TABLE intake_media_files (
    id         TEXT PRIMARY KEY,
    sha256     TEXT NOT NULL UNIQUE,   -- identidad del contenido, y su ruta en disco
    path       TEXT NOT NULL,          -- relativa a media_dir
    mime       TEXT NOT NULL,
    format     TEXT NOT NULL,          -- PNG / JPEG / WEBP, segun el contenido
    width      INTEGER NOT NULL,
    height     INTEGER NOT NULL,
    bytes      INTEGER NOT NULL,
    has_alpha  INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
