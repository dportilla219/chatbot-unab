-- =====================================================================================
-- Migración 06: profesores, certificados, contraseñas y sesiones guardadas
-- Se aplica UNA vez con:  bash deploy/migrar_06.sh
-- Es idempotente (se puede volver a correr sin duplicar datos).
-- La app y el servidor detectan solos si esta migración ya se aplicó.
-- =====================================================================================
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
SET search_path TO academico, public, extensions;

-- ---------------------------------------------------------------- 1. Profesores (sintéticos)
CREATE TABLE IF NOT EXISTS profesor (
    cod_profesor  VARCHAR(8) PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    area          VARCHAR(60)  NOT NULL
);

INSERT INTO profesor (cod_profesor, nombre, area) VALUES
 ('P001','Carlos Andrés Rueda Pinto','Ciencias básicas'),
 ('P002','Martha Lucía Ortiz Gómez','Ciencias básicas'),
 ('P003','Jorge Eliécer Sarmiento Díaz','Ciencias básicas'),
 ('P004','Diana Marcela Quintero Vega','Ciencias básicas'),
 ('P005','Hernán Darío Castellanos Ruiz','Sistemas'),
 ('P006','Paola Andrea Niño Serrano','Sistemas'),
 ('P007','Luis Fernando Arenas Mantilla','Sistemas'),
 ('P008','Claudia Patricia Rangel Silva','Sistemas'),
 ('P009','Óscar Javier Becerra León','Sistemas'),
 ('P010','Sandra Milena Prada Duarte','Datos'),
 ('P011','Ricardo Alfonso Jaimes Toloza','Datos'),
 ('P012','Natalia Carolina Vargas Pabón','Datos'),
 ('P013','Fabián Ernesto Gélvez Ardila','Ingeniería'),
 ('P014','Adriana Sofía Mendoza Cárdenas','Ingeniería'),
 ('P015','Germán Augusto Peña Rincón','Ingeniería'),
 ('P016','Liliana Rocío Suárez Barón','Formación humana'),
 ('P017','Mauricio José Villamizar Rojas','Formación humana'),
 ('P018','Ana María Pedraza Herrera','Formación humana'),
 ('P019','Felipe Santiago Moreno Galvis','Electivas'),
 ('P020','Juliana Isabel Cáceres Ortega','Electivas')
ON CONFLICT (cod_profesor) DO NOTHING;

ALTER TABLE historial_academico ADD COLUMN IF NOT EXISTS profesor VARCHAR(120);

-- Un profesor por (asignatura, periodo), elegido de forma determinista dentro del área del curso
-- (si el área no tiene profesores, se usa cualquier profesor).
WITH asign AS (
    SELECT DISTINCT h.cod_asignatura, h.cod_periodo, a.area
    FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
), elegido AS (
    SELECT s.cod_asignatura, s.cod_periodo,
           COALESCE(
             (SELECT p.nombre FROM profesor p WHERE p.area = s.area
               ORDER BY md5(s.cod_asignatura || s.cod_periodo || p.cod_profesor) LIMIT 1),
             (SELECT p.nombre FROM profesor p
               ORDER BY md5(s.cod_asignatura || s.cod_periodo || p.cod_profesor) LIMIT 1)) AS nombre
    FROM asign s
)
UPDATE historial_academico h SET profesor = e.nombre
FROM elegido e
WHERE h.cod_asignatura = e.cod_asignatura AND h.cod_periodo = e.cod_periodo AND h.profesor IS NULL;

-- ---------------------------------------------------------------- 2. Certificados (inglés y externos)
CREATE TABLE IF NOT EXISTS certificado (
    id             BIGSERIAL PRIMARY KEY,
    id_estudiante  VARCHAR(9) NOT NULL REFERENCES estudiante(id_estudiante),
    tipo           VARCHAR(20) NOT NULL CHECK (tipo IN ('Inglés','Externo')),
    nombre         VARCHAR(160) NOT NULL,
    entidad        VARCHAR(120) NOT NULL,
    fecha          DATE NOT NULL,
    detalle        VARCHAR(160),
    UNIQUE (id_estudiante, nombre)
);

-- Inglés: un certificado con el nivel actual para quien ya superó A1
INSERT INTO certificado (id_estudiante, tipo, nombre, entidad, fecha, detalle)
SELECT e.id_estudiante, 'Inglés', 'Certificado de nivel de inglés ' || e.nivel_ingles,
       CASE WHEN ('x' || substr(md5(e.id_estudiante), 1, 2))::bit(8)::int % 2 = 0
            THEN 'Instituto de Lenguas UNAB' ELSE 'Cambridge English (examen de ubicación)' END,
       DATE '2024-06-01' + (('x' || substr(md5(e.id_estudiante), 3, 3))::bit(12)::int % 700),
       'Nivel ' || e.nivel_ingles || ' del Marco Común Europeo'
FROM estudiante e
WHERE e.nivel_ingles IN ('A2','B1','B2','C1')
ON CONFLICT (id_estudiante, nombre) DO NOTHING;

-- Externos: de 0 a 3 cursos por estudiante, elegidos de forma determinista
WITH cat(n, nombre, entidad, horas) AS (VALUES
  (0,'Fundamentos de Python','Coursera · Universidad de Michigan', 40),
  (1,'CCNA: Introducción a las redes','Cisco Networking Academy', 70),
  (2,'AWS Cloud Foundations','AWS Academy', 20),
  (3,'Fundamentos de bases de datos con SQL','Platzi', 25),
  (4,'Git y GitHub','Platzi', 12),
  (5,'Introducción a la ciberseguridad','Cisco Networking Academy', 15),
  (6,'Google Data Analytics','Coursera · Google', 180),
  (7,'Scrum Fundamentals Certified','SCRUMstudy', 16),
  (8,'Desarrollo web con JavaScript','freeCodeCamp', 300),
  (9,'Machine Learning','Coursera · Stanford Online', 60)
), est AS (
  SELECT id_estudiante, ('x' || substr(md5(id_estudiante || 'ext'), 1, 4))::bit(16)::int AS h
  FROM estudiante
)
INSERT INTO certificado (id_estudiante, tipo, nombre, entidad, fecha, detalle)
SELECT e.id_estudiante, 'Externo', c.nombre, c.entidad,
       DATE '2023-03-01' + ((e.h * (k + 3)) % 1000), c.horas || ' horas'
FROM est e
CROSS JOIN generate_series(0, 2) AS k
JOIN cat c ON c.n = (e.h / (k + 1) + k * 3) % 10
WHERE k < (e.h % 4)
ON CONFLICT (id_estudiante, nombre) DO NOTHING;

-- ---------------------------------------------------------------- 3. Contraseñas (cifradas con bcrypt)
CREATE TABLE IF NOT EXISTS acceso (
    id_estudiante  VARCHAR(9) PRIMARY KEY REFERENCES estudiante(id_estudiante),
    password_hash  TEXT NOT NULL,
    debe_cambiar   BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado    TIMESTAMP NOT NULL DEFAULT now()
);

-- Contraseña inicial = el mismo ID del estudiante; se pide cambiarla al primer ingreso.
INSERT INTO acceso (id_estudiante, password_hash, debe_cambiar)
SELECT id_estudiante, extensions.crypt(id_estudiante, extensions.gen_salt('bf', 8)), TRUE
FROM estudiante
ON CONFLICT (id_estudiante) DO NOTHING;

-- ---------------------------------------------------------------- 4. Sesiones guardadas por dispositivo
CREATE TABLE IF NOT EXISTS sesion (
    token_hash     CHAR(64) PRIMARY KEY,            -- sha256 del token; el token solo lo tiene el dispositivo
    id_estudiante  VARCHAR(9) NOT NULL REFERENCES estudiante(id_estudiante),
    dispositivo    VARCHAR(120),
    creada         TIMESTAMP NOT NULL DEFAULT now(),
    ultimo_uso     TIMESTAMP NOT NULL DEFAULT now(),
    revocada       BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS sesion_estudiante_idx ON sesion (id_estudiante) WHERE NOT revocada;

-- Verificación rápida
SELECT (SELECT COUNT(*) FROM historial_academico WHERE profesor IS NOT NULL) AS cursos_con_profesor,
       (SELECT COUNT(*) FROM certificado) AS certificados,
       (SELECT COUNT(*) FROM acceso) AS contrasenas;
