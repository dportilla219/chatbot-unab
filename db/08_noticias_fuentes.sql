-- =====================================================================================
-- Migración 08: noticias de varias fuentes, con fuente y tema
-- (educación, tecnología, ingeniería de sistemas e institucional UNAB)
-- Se aplica con:  bash deploy/migrar_08.sh   (idempotente; solo agrega columnas)
-- =====================================================================================
SET search_path TO academico, public, extensions;

ALTER TABLE noticia ADD COLUMN IF NOT EXISTS fuente VARCHAR(80) NOT NULL DEFAULT 'unab.edu.co';
ALTER TABLE noticia ADD COLUMN IF NOT EXISTS tema   VARCHAR(30);
CREATE INDEX IF NOT EXISTS noticia_fecha_idx ON noticia (fecha_pub DESC);

-- Clasifica las noticias que ya existían
UPDATE noticia SET tema = CASE
    WHEN (titulo || ' ' || coalesce(resumen, '')) ~* '(ingenier[ií]a de sistemas|software|programaci|desarrollador|inteligencia artificial|\mia\M|ciberseguridad|datos|algoritm|computaci|nube|cloud)'
         THEN 'Ingeniería de Sistemas'
    WHEN (titulo || ' ' || coalesce(resumen, '')) ~* '(tecnolog|digital|internet|\mapp\M|innovaci|5g|startup|robot)'
         THEN 'Tecnología'
    WHEN (titulo || ' ' || coalesce(resumen, '')) ~* '(educaci|universidad|estudiant|beca|icetex|acad[eé]mic|docente|pregrado|posgrado)'
         THEN 'Educación'
    ELSE 'Institucional' END
WHERE tema IS NULL;

-- Noticias RSS guardadas sin nombre de medio: se usa el dominio del enlace
UPDATE noticia SET fuente = substring(url from '^https?://(?:www\.)?([^/:?#]+)')
WHERE fuente = 'RSS' AND url ~ '^https?://';

SELECT fuente, tema, COUNT(*) FROM noticia GROUP BY 1, 2 ORDER BY 1, 2;
