-- =====================================================================================
-- Migración 07: eventos personales de cada estudiante (solo los ve su dueño)
-- Se aplica con:  bash deploy/migrar_07.sh   (idempotente; solo crea una tabla nueva)
-- =====================================================================================
SET search_path TO academico, public, extensions;

CREATE TABLE IF NOT EXISTS evento_personal (
    id             BIGSERIAL PRIMARY KEY,
    id_estudiante  VARCHAR(9) NOT NULL REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    nombre         VARCHAR(120) NOT NULL CHECK (length(trim(nombre)) > 0),
    fecha          DATE NOT NULL,
    descripcion    VARCHAR(500),
    creado         TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evento_personal_estudiante_idx ON evento_personal (id_estudiante, fecha);

SELECT COUNT(*) AS eventos_personales FROM evento_personal;
