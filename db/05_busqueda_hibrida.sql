-- Búsqueda híbrida para RAG: similitud vectorial (pgvector) + texto completo en español (tsvector),
-- combinadas con Reciprocal Rank Fusion (RRF).
SET search_path TO academico, public, extensions;
ALTER TABLE documento_chunk ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('spanish', contenido)) STORED;
CREATE INDEX IF NOT EXISTS ix_chunk_tsv ON documento_chunk USING gin (tsv);

CREATE OR REPLACE FUNCTION buscar_hibrido(q vector(384), qtext TEXT, k INT DEFAULT 6, filtro_fuente TEXT DEFAULT NULL)
RETURNS TABLE (id BIGINT, fuente VARCHAR, titulo TEXT, seccion TEXT, contenido TEXT, similitud FLOAT)
LANGUAGE sql STABLE AS $$
  WITH vec AS (
    SELECT d.id, ROW_NUMBER() OVER (ORDER BY d.embedding <=> q) AS r, 1 - (d.embedding <=> q) AS sim
    FROM academico.documento_chunk d
    WHERE filtro_fuente IS NULL OR d.fuente = filtro_fuente
    ORDER BY d.embedding <=> q LIMIT 40
  ), txt AS (
    SELECT d.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(d.tsv, websearch_to_tsquery('spanish', qtext)) DESC) AS r
    FROM academico.documento_chunk d
    WHERE (filtro_fuente IS NULL OR d.fuente = filtro_fuente)
      AND d.tsv @@ plainto_tsquery('spanish', regexp_replace(qtext, '[¿?¡!]', '', 'g'))
    LIMIT 40
  ), txt_or AS (   -- si ninguna fila contiene todas las palabras, usa coincidencia parcial (OR)
    SELECT d.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(d.tsv, q2.qq) DESC) AS r
    FROM academico.documento_chunk d,
         (SELECT to_tsquery('spanish', array_to_string(array_agg(lexeme), ' | ')) AS qq
            FROM unnest(to_tsvector('spanish', qtext))) q2
    WHERE (filtro_fuente IS NULL OR d.fuente = filtro_fuente) AND q2.qq IS NOT NULL AND d.tsv @@ q2.qq
    LIMIT 40
  ), fus AS (
    SELECT id, SUM(score) AS score FROM (
      SELECT id, 1.0/(60 + r) AS score FROM vec
      UNION ALL SELECT id, 1.0/(60 + r) FROM txt
      UNION ALL SELECT id, 0.8/(60 + r) FROM txt_or
    ) u GROUP BY id
  )
  SELECT d.id, d.fuente, d.titulo, d.seccion, d.contenido, ROUND(f.score::numeric, 4)::float AS similitud
  FROM fus f JOIN academico.documento_chunk d USING (id)
  ORDER BY f.score DESC LIMIT k;
$$;
