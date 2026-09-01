-- Los empujones de un episodio: cuanto se movio cada figura y en que capa quedo.
--
-- Tabla aparte y no columnas en `episodes_slots` porque el ajuste es del ROL y
-- no de la foto: `objeto` admite dos fotos y comparten un solo empujon, igual
-- que comparten un solo slot.
--
-- Una fila por rol AJUSTADO. Lo normal es no tener ninguna: el ajuste es la
-- excepcion de una semana, y "sin fila" significa "donde diga el template".
--
-- `capa` es RELATIVA al z del template (+1 = un paso adelante), no absoluta.
-- Asi el dia que el template cambie el z de un slot, un episodio ajustado se
-- mueve con el en vez de quedarse clavado en un numero que ya no significa lo
-- mismo. Los limites los pone `composition/template.py`, no un CHECK: son
-- numeros de layout, y aqui serian una segunda verdad.
CREATE TABLE episodes_ajustes (
    episode_id TEXT NOT NULL REFERENCES episodes_jobs(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    dx         INTEGER NOT NULL DEFAULT 0,
    dy         INTEGER NOT NULL DEFAULT 0,
    capa       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (episode_id, role)
);
