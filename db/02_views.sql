-- =====================================================================
-- Vistas analíticas optimizadas para agentes conversacionales
-- Reglas tomadas del Reglamento Estudiantil de Pregrado UNAB (2019):
--   Art. 24  Estados: NORMAL (PGA > 3.20), CONDICIONAL (3.00–3.20),
--            PRUEBA ACADÉMICA (2º periodo consecutivo 3.00–3.20 o PGA < 3.00)
--   Art. 38  Nota mínima aprobatoria 3.0
--   Art. 40  PGA = Σ(nota × créditos) / Σ créditos cursados
--   Art. 53  Si se repite un curso, cuenta la nota más alta
--   Art. 84  Condicional: máximo 3 cursos el siguiente periodo
--   Art. 85  Prueba académica: solo 2 cursos reprobados (Programa de Recuperación)
--   Art. 67  Grado: PGA ≥ 3.20, inglés B2, competencias digitales/informática, todo aprobado
-- =====================================================================
SET search_path TO academico, public, extensions;

-- Mejor intento por asignatura (Art. 53)
CREATE OR REPLACE VIEW v_mejor_nota AS
SELECT DISTINCT ON (h.id_estudiante, h.cod_asignatura)
       h.id_estudiante, h.cod_asignatura, a.nombre AS asignatura, a.creditos,
       a.semestre_sugerido, a.tipo, h.cod_periodo, h.nota_final, h.estado,
       COUNT(*) OVER (PARTITION BY h.id_estudiante, h.cod_asignatura) AS intentos
FROM historial_academico h
JOIN asignatura a USING (cod_asignatura)
WHERE h.estado IN ('APROBADA','REPROBADA','HOMOLOGADA')
ORDER BY h.id_estudiante, h.cod_asignatura,
         (h.estado IN ('APROBADA','HOMOLOGADA')) DESC, h.nota_final DESC NULLS LAST;

-- Resumen académico por estudiante
CREATE OR REPLACE VIEW v_resumen_estudiante AS
WITH notas AS (
  SELECT id_estudiante,
         SUM(creditos) FILTER (WHERE estado IN ('APROBADA','HOMOLOGADA'))            AS cred_aprobados,
         SUM(nota_final*creditos) FILTER (WHERE estado <> 'HOMOLOGADA' AND creditos>0) AS suma_pond,
         SUM(creditos) FILTER (WHERE estado <> 'HOMOLOGADA' AND creditos>0)            AS cred_cursados,
         COUNT(*) FILTER (WHERE estado = 'REPROBADA')                                 AS cursos_reprobados_vigentes,
         SUM(intentos-1)                                                               AS repeticiones
  FROM v_mejor_nota GROUP BY id_estudiante
), en_curso AS (
  SELECT h.id_estudiante, COUNT(*) AS cursos_en_curso, SUM(a.creditos) AS cred_en_curso
  FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
  WHERE h.estado = 'EN_CURSO' GROUP BY h.id_estudiante
)
SELECT e.id_estudiante, e.nombre_completo, e.email, p.nombre AS programa, e.cod_programa,
       e.condicion, e.semestre_actual, e.periodo_ingreso, e.nivel_ingles,
       p.creditos_totales,
       COALESCE(n.cred_aprobados,0)                                          AS creditos_aprobados,
       COALESCE(c.cred_en_curso,0)                                           AS creditos_en_curso,
       p.creditos_totales - COALESCE(n.cred_aprobados,0)                     AS creditos_pendientes,
       ROUND(100.0*COALESCE(n.cred_aprobados,0)/p.creditos_totales,1)        AS porcentaje_avance,
       ROUND(n.suma_pond / NULLIF(n.cred_cursados,0), 2)                     AS pga,
       COALESCE(n.cursos_reprobados_vigentes,0)                              AS cursos_reprobados_pendientes,
       COALESCE(n.repeticiones,0)                                            AS repeticiones,
       CASE
         WHEN n.cred_cursados IS NULL THEN 'SIN_NOTAS'
         WHEN ROUND(n.suma_pond/n.cred_cursados,2) > 3.20 THEN 'NORMAL'
         WHEN ROUND(n.suma_pond/n.cred_cursados,2) >= 3.00 THEN
              CASE WHEN m_prev.estado_academico = 'CONDICIONAL' THEN 'PRUEBA_ACADEMICA' ELSE 'CONDICIONAL' END
         ELSE 'PRUEBA_ACADEMICA'
       END                                                                   AS estado_academico
FROM estudiante e
JOIN programa p USING (cod_programa)
LEFT JOIN notas n USING (id_estudiante)
LEFT JOIN en_curso c USING (id_estudiante)
LEFT JOIN LATERAL (
   SELECT m.estado_academico FROM matricula m
   WHERE m.id_estudiante = e.id_estudiante AND m.pga IS NOT NULL
   ORDER BY m.cod_periodo DESC OFFSET 1 LIMIT 1) m_prev ON TRUE;

-- Asignaturas pendientes con validación de prerrequisitos
CREATE OR REPLACE VIEW v_asignaturas_pendientes AS
SELECT e.id_estudiante, a.cod_asignatura, a.nombre AS asignatura, a.creditos,
       a.semestre_sugerido, a.tipo,
       EXISTS (SELECT 1 FROM historial_academico h WHERE h.id_estudiante=e.id_estudiante
               AND h.cod_asignatura=a.cod_asignatura AND h.estado='EN_CURSO')        AS en_curso,
       EXISTS (SELECT 1 FROM historial_academico h WHERE h.id_estudiante=e.id_estudiante
               AND h.cod_asignatura=a.cod_asignatura AND h.estado='REPROBADA')       AS reprobada_antes,
       COALESCE((SELECT string_agg(pa.nombre, ', ')
                 FROM prerrequisito pr JOIN asignatura pa ON pa.cod_asignatura = pr.cod_prerrequisito
                 WHERE pr.cod_asignatura = a.cod_asignatura
                   AND NOT EXISTS (SELECT 1 FROM v_mejor_nota mn WHERE mn.id_estudiante=e.id_estudiante
                                   AND mn.cod_asignatura=pr.cod_prerrequisito
                                   AND mn.estado IN ('APROBADA','HOMOLOGADA'))), '')       AS prerrequisitos_faltantes
FROM estudiante e
JOIN asignatura a ON a.cod_programa = e.cod_programa
WHERE NOT EXISTS (SELECT 1 FROM v_mejor_nota mn WHERE mn.id_estudiante=e.id_estudiante
                  AND mn.cod_asignatura=a.cod_asignatura AND mn.estado IN ('APROBADA','HOMOLOGADA'));

-- Estado de la ruta de Competencias Digitales (CCD)
CREATE OR REPLACE VIEW v_ccd_estado AS
SELECT e.id_estudiante, e.nombre_completo,
       r.ruta, r.nombre_ruta,
       (SELECT c.nombre || ' (' || h.via || ', ' || h.estado || COALESCE(', nota '||h.nota,'')
               || COALESCE(', origen: '||h.curso_origen,'') || ')'
        FROM ccd_historial h JOIN ccd_curso c USING (cod_ccd)
        WHERE h.id_estudiante=e.id_estudiante AND c.ruta=r.ruta
        ORDER BY (h.estado IN ('APROBADA','HOMOLOGADA')) DESC, h.id DESC LIMIT 1)          AS detalle,
       EXISTS (SELECT 1 FROM ccd_historial h JOIN ccd_curso c USING (cod_ccd)
               WHERE h.id_estudiante=e.id_estudiante AND c.ruta=r.ruta
                 AND h.estado IN ('APROBADA','HOMOLOGADA'))                               AS cumplida,
       EXISTS (SELECT 1 FROM ccd_historial h JOIN ccd_curso c USING (cod_ccd)
               WHERE h.id_estudiante=e.id_estudiante AND c.ruta=r.ruta AND h.estado='EN_CURSO') AS en_curso
FROM estudiante e
CROSS JOIN (SELECT DISTINCT ruta, nombre_ruta FROM ccd_curso) r;

CREATE OR REPLACE VIEW v_ccd_resumen AS
SELECT id_estudiante, nombre_completo,
       COUNT(*) FILTER (WHERE cumplida) AS rutas_cumplidas,
       3 - COUNT(*) FILTER (WHERE cumplida) AS rutas_pendientes,
       COUNT(*) FILTER (WHERE cumplida) = 3 AS insignia_digital_habilitada,
       string_agg(CASE WHEN NOT cumplida THEN 'Ruta '||ruta||' - '||nombre_ruta END, '; ') AS rutas_faltantes
FROM v_ccd_estado GROUP BY id_estudiante, nombre_completo;

-- Proyección de semestres restantes y alertas de requisitos (Art. 67, 84, 85)
CREATE OR REPLACE VIEW v_proyeccion_grado AS
SELECT r.id_estudiante, r.nombre_completo, r.semestre_actual, r.creditos_aprobados,
       r.creditos_pendientes, r.pga, r.estado_academico, r.nivel_ingles,
       CASE r.estado_academico WHEN 'CONDICIONAL' THEN 9          -- ~3 cursos (Art. 84)
                               WHEN 'PRUEBA_ACADEMICA' THEN 6     -- 2 cursos (Art. 85)
                               ELSE 17 END                                        AS carga_max_estimada,
       CEIL(GREATEST(r.creditos_pendientes - r.creditos_en_curso,0)::numeric /
            CASE r.estado_academico WHEN 'CONDICIONAL' THEN 9 WHEN 'PRUEBA_ACADEMICA' THEN 6 ELSE 17 END)
            + CASE WHEN r.creditos_en_curso > 0 THEN 1 ELSE 0 END                 AS semestres_restantes_estimados,
       c.rutas_pendientes AS ccd_rutas_pendientes,
       (r.nivel_ingles IN ('B2','C1','C2'))                                       AS ingles_cumplido,
       (r.pga >= 3.20)                                                            AS pga_grado_cumplido,
       concat_ws(' | ',
         CASE WHEN r.estado_academico='CONDICIONAL' THEN 'Estado CONDICIONAL: solo puede matricular hasta 3 cursos y debe inscribirse en acompañamiento de Bienestar (Art. 84)' END,
         CASE WHEN r.estado_academico='PRUEBA_ACADEMICA' THEN 'PRUEBA ACADÉMICA: debe solicitar el Programa de Recuperación Académica; solo 2 cursos reprobados (Art. 85-86)' END,
         CASE WHEN c.rutas_pendientes > 0 THEN 'Competencias Digitales pendientes: ' || c.rutas_faltantes END,
         CASE WHEN r.nivel_ingles NOT IN ('B2','C1','C2') THEN 'Inglés: nivel actual ' || r.nivel_ingles || ', requiere B2 para grado (Art. 7 y 67)' END,
         CASE WHEN r.pga < 3.20 THEN 'PGA ' || r.pga || ' inferior a 3.20 exigido para grado (Art. 67)' END,
         CASE WHEN r.cursos_reprobados_pendientes > 0 THEN r.cursos_reprobados_pendientes || ' curso(s) reprobado(s) por recuperar' END
       )                                                                          AS alertas
FROM v_resumen_estudiante r
LEFT JOIN v_ccd_resumen c USING (id_estudiante);

-- Matrícula del periodo actual
CREATE OR REPLACE VIEW v_matricula_actual AS
SELECT m.*, p.descripcion AS periodo, e.nombre_completo
FROM matricula m JOIN periodo p USING (cod_periodo) JOIN estudiante e USING (id_estudiante)
WHERE p.es_actual;

-- Búsqueda semántica (RAG) como función reutilizable
CREATE OR REPLACE FUNCTION buscar_chunks(q vector(384), k INT DEFAULT 5, filtro_fuente TEXT DEFAULT NULL)
RETURNS TABLE (id BIGINT, fuente VARCHAR, titulo TEXT, seccion TEXT, contenido TEXT, similitud FLOAT)
LANGUAGE sql STABLE AS $$
  SELECT d.id, d.fuente, d.titulo, d.seccion, d.contenido, 1 - (d.embedding <=> q) AS similitud
  FROM academico.documento_chunk d
  WHERE filtro_fuente IS NULL OR d.fuente = filtro_fuente
  ORDER BY d.embedding <=> q
  LIMIT k;
$$;
