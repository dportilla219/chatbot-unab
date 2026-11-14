-- =====================================================================
-- Chatbot de apoyo académico UNAB - Ingeniería de Sistemas
-- Esquema relacional que SIMULA Banner / COSMOS (datos sintéticos)
-- Motor: PostgreSQL 15+ (Supabase) con extensión pgvector
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE SCHEMA IF NOT EXISTS academico;
SET search_path TO academico, public, extensions;

-- ---------- Catálogos ----------
CREATE TABLE IF NOT EXISTS programa (
    cod_programa      VARCHAR(10) PRIMARY KEY,         -- p.ej. 'ISIS' (código interno), 1791 en MiPortalU
    nombre            VARCHAR(120) NOT NULL,
    facultad          VARCHAR(120) NOT NULL,
    snies             VARCHAR(10),
    creditos_totales  INT NOT NULL,
    semestres         INT NOT NULL,
    nivel_ingles_req  VARCHAR(5) DEFAULT 'B2',
    pga_minimo_grado  NUMERIC(3,2) DEFAULT 3.20
);

CREATE TABLE IF NOT EXISTS periodo (              -- STVTERM
    cod_periodo   VARCHAR(6) PRIMARY KEY,           -- formato Banner: 202610 = 2026-1, 202620 = 2026-2
    descripcion   VARCHAR(40) NOT NULL,
    fecha_inicio  DATE NOT NULL,
    fecha_fin     DATE NOT NULL,
    es_actual     BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS asignatura (           -- SCACRSE
    cod_asignatura    VARCHAR(12) PRIMARY KEY,
    nombre            VARCHAR(120) NOT NULL,
    creditos          INT NOT NULL,
    semestre_sugerido INT,
    cod_programa      VARCHAR(10) REFERENCES programa(cod_programa),
    tipo              VARCHAR(20) NOT NULL CHECK (tipo IN
                      ('OBLIGATORIA','ELECTIVA','CURSO_MENOR','PRACTICA','LABORATORIO','INSTITUCIONAL')),
    area              VARCHAR(60)
);

CREATE TABLE IF NOT EXISTS prerrequisito (        -- SCRRTST
    cod_asignatura    VARCHAR(12) REFERENCES asignatura(cod_asignatura),
    cod_prerrequisito VARCHAR(12) REFERENCES asignatura(cod_asignatura),
    tipo              VARCHAR(12) DEFAULT 'PRE' CHECK (tipo IN ('PRE','CO')),
    PRIMARY KEY (cod_asignatura, cod_prerrequisito)
);

-- ---------- Estudiantes ----------
CREATE TABLE IF NOT EXISTS estudiante (           -- SPRIDEN + SGBSTDN
    id_estudiante     VARCHAR(9) PRIMARY KEY CHECK (id_estudiante ~ '^U[0-9]{8}$'),
    nombres           VARCHAR(80) NOT NULL,
    apellidos         VARCHAR(80) NOT NULL,
    nombre_completo   VARCHAR(160) GENERATED ALWAYS AS (nombres || ' ' || apellidos) STORED,
    email             VARCHAR(120) UNIQUE,
    cod_programa      VARCHAR(10) REFERENCES programa(cod_programa),
    periodo_ingreso   VARCHAR(6) REFERENCES periodo(cod_periodo),
    condicion         VARCHAR(20) NOT NULL DEFAULT 'ACTIVO' CHECK (condicion IN
                      ('ACTIVO','RESERVA_CUPO','REINTEGRO','DESERTOR','INACTIVO','EGRESADO','GRADUADO','RETIRADO')),
    semestre_actual   INT,
    nivel_ingles      VARCHAR(5) DEFAULT 'A1',
    fecha_creacion    TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS historial_academico (  -- SHRTCKN / SHATERM
    id               BIGSERIAL PRIMARY KEY,
    id_estudiante    VARCHAR(9) REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    cod_asignatura   VARCHAR(12) REFERENCES asignatura(cod_asignatura),
    cod_periodo      VARCHAR(6) REFERENCES periodo(cod_periodo),
    nota_final       NUMERIC(2,1) CHECK (nota_final BETWEEN 0 AND 5),
    estado           VARCHAR(12) NOT NULL CHECK (estado IN ('APROBADA','REPROBADA','EN_CURSO','HOMOLOGADA','CANCELADA')),
    intento          INT DEFAULT 1,
    fallas_pct       NUMERIC(4,1) DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_hist_est ON historial_academico(id_estudiante);

CREATE TABLE IF NOT EXISTS matricula (            -- SFRSTCR + TBRACCD resumido
    id_estudiante      VARCHAR(9) REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    cod_periodo        VARCHAR(6) REFERENCES periodo(cod_periodo),
    creditos_inscritos INT NOT NULL,
    valor_matricula    NUMERIC(12,0),
    estado_financiero  VARCHAR(12) CHECK (estado_financiero IN ('PAGADA','PENDIENTE','FINANCIADA','VENCIDA')),
    fecha_pago         DATE,
    medio_pago         VARCHAR(30),
    estado_academico   VARCHAR(20) CHECK (estado_academico IN ('NORMAL','CONDICIONAL','PRUEBA_ACADEMICA','FUERA_PROGRAMA')),
    ppa                NUMERIC(3,2),                 -- promedio del periodo
    pga                NUMERIC(3,2),                 -- promedio general acumulado al cierre
    PRIMARY KEY (id_estudiante, cod_periodo)
);

-- ---------- Centro de Competencias Digitales (CCD) ----------
CREATE TABLE IF NOT EXISTS ccd_curso (
    cod_ccd      VARCHAR(10) PRIMARY KEY,
    nombre       VARCHAR(80) NOT NULL,
    ruta         INT NOT NULL CHECK (ruta IN (1,2,3)),
    nombre_ruta  VARCHAR(60) NOT NULL,
    obligatorio  BOOLEAN DEFAULT FALSE,
    descripcion  TEXT
);

CREATE TABLE IF NOT EXISTS ccd_historial (
    id              BIGSERIAL PRIMARY KEY,
    id_estudiante   VARCHAR(9) REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    cod_ccd         VARCHAR(10) REFERENCES ccd_curso(cod_ccd),
    cod_periodo     VARCHAR(6) REFERENCES periodo(cod_periodo),
    via             VARCHAR(20) NOT NULL CHECK (via IN ('CURSO','PRUEBA_DIAGNOSTICA','HOMOLOGACION','VACACIONAL','INTENSIVO')),
    estado          VARCHAR(12) NOT NULL CHECK (estado IN ('APROBADA','REPROBADA','EN_CURSO','HOMOLOGADA')),
    nota            NUMERIC(2,1),
    curso_origen    VARCHAR(60)                       -- si fue homologación (p.ej. 'MS Excel')
);

CREATE TABLE IF NOT EXISTS ccd_prueba_diagnostica (
    id_estudiante  VARCHAR(9) REFERENCES estudiante(id_estudiante) ON DELETE CASCADE,
    fecha          DATE,
    puntaje_pct    NUMERIC(5,2),
    PRIMARY KEY (id_estudiante)
);

-- ---------- Calendario (respaldo del Google Sheet) ----------
CREATE TABLE IF NOT EXISTS calendario_academico (
    id            SERIAL PRIMARY KEY,
    cod_periodo   VARCHAR(6),
    actividad     VARCHAR(160) NOT NULL,
    categoria     VARCHAR(40),
    fecha_inicio  DATE NOT NULL,
    fecha_fin     DATE,
    dirigido_a    VARCHAR(80),
    fuente        VARCHAR(200)
);

-- ---------- Noticias (alimentada por el scraper) ----------
CREATE TABLE IF NOT EXISTS noticia (
    id_wp        BIGINT PRIMARY KEY,
    titulo       TEXT NOT NULL,
    url          TEXT UNIQUE NOT NULL,
    fecha_pub    TIMESTAMP,
    resumen      TEXT,
    contenido    TEXT,
    categorias   TEXT,
    etiqueta     VARCHAR(40),                         -- CURSOS | CONVOCATORIA | CERTIFICACION | CCD | GENERAL
    scraped_at   TIMESTAMP DEFAULT now()
);

-- ---------- RAG: documentos institucionales vectorizados ----------
CREATE TABLE IF NOT EXISTS documento_chunk (
    id           BIGSERIAL PRIMARY KEY,
    fuente       VARCHAR(80) NOT NULL,               -- reglamento | plan_estudios | ccd | noticia
    titulo       TEXT,
    seccion      TEXT,
    chunk_index  INT,
    contenido    TEXT NOT NULL,
    metadata     JSONB DEFAULT '{}'::jsonb,
    embedding    vector(384),
    creado       TIMESTAMP DEFAULT now(),
    UNIQUE (fuente, titulo, chunk_index)
);
CREATE INDEX IF NOT EXISTS ix_chunk_emb ON documento_chunk USING hnsw (embedding vector_cosine_ops);

-- ---------- Auditoría del chatbot (guardrails / analítica) ----------
CREATE TABLE IF NOT EXISTS chat_log (
    id            BIGSERIAL PRIMARY KEY,
    session_id    VARCHAR(40),
    id_estudiante VARCHAR(9),
    intencion     VARCHAR(30),
    pregunta      TEXT,
    respuesta     TEXT,
    bloqueado     BOOLEAN DEFAULT FALSE,
    motivo        TEXT,
    creado        TIMESTAMP DEFAULT now()
);

-- Normalización de texto para búsquedas sin tildes
CREATE OR REPLACE FUNCTION unaccent_lower(t text) RETURNS text
LANGUAGE sql STABLE SET search_path = public, extensions, pg_catalog AS $$ SELECT lower(unaccent(t)) $$;
