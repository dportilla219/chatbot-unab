-- =====================================================================================
-- Migración 09: calificación de respuestas del asistente (útil / no útil)
-- Se aplica con:  bash deploy/migrar_09.sh   (idempotente; solo crea una tabla nueva)
-- Sirve para medir la satisfacción por ruta (intención) y encontrar preguntas que el RAG responde mal.
-- =====================================================================================
SET search_path TO academico, public, extensions;

CREATE TABLE IF NOT EXISTS calificacion (
    id             BIGSERIAL PRIMARY KEY,
    id_estudiante  VARCHAR(9) NOT NULL REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    session_id     VARCHAR(40),
    chat_log_id    BIGINT REFERENCES chat_log(id) ON DELETE SET NULL,
    intencion      VARCHAR(30),
    pregunta       TEXT,
    respuesta      TEXT,
    huella         CHAR(32) NOT NULL,               -- md5(pregunta || respuesta): una calificación por respuesta
    valor          SMALLINT NOT NULL CHECK (valor IN (-1, 1)),
    creado         TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (id_estudiante, huella)
);
CREATE INDEX IF NOT EXISTS calificacion_intencion_idx ON calificacion (intencion);

-- Satisfacción por ruta del asistente
CREATE OR REPLACE VIEW v_satisfaccion AS
SELECT COALESCE(intencion, 'SIN_RUTA') AS intencion,
       COUNT(*)                                   AS calificaciones,
       COUNT(*) FILTER (WHERE valor = 1)          AS utiles,
       COUNT(*) FILTER (WHERE valor = -1)         AS no_utiles,
       ROUND(100.0 * COUNT(*) FILTER (WHERE valor = 1) / NULLIF(COUNT(*), 0), 1) AS porcentaje_util
FROM calificacion GROUP BY 1 ORDER BY 2 DESC;

SELECT COUNT(*) AS calificaciones FROM calificacion;
