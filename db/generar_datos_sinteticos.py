"""
Generador de datos sintéticos que simula Banner/COSMOS para el chatbot UNAB.

Fuentes reales usadas como base (consultadas en noviembre de 2026):
  - Plan de estudios Ingeniería de Sistemas UNAB (MiPortalU, programa 1791): 134 créditos, 8 semestres.
  - Reglamento Estudiantil de Pregrado UNAB (2019): estados académicos, PGA, nota aprobatoria 3.0.
  - Centro de Competencias Digitales (CCD): 3 rutas, prueba diagnóstica >= 70 %, homologaciones.
Los ESTUDIANTES, NOTAS, PAGOS y PRERREQUISITOS son ficticios.

Uso:
    python generar_datos_sinteticos.py            # genera 03_seed.sql (300 estudiantes)
    python generar_datos_sinteticos.py --n 500
"""
import argparse
import math
import random
from datetime import date, timedelta

from faker import Faker

SEED = 2026
random.seed(SEED)
fake = Faker("es_CO")
Faker.seed(SEED)

PROGRAMA = dict(cod="ISIS", nombre="Ingeniería de Sistemas", facultad="Facultad de Ingeniería",
                snies="1643", creditos=134, semestres=8)

# (codigo, nombre, creditos, semestre, tipo, area, prerrequisitos, dificultad)
PLAN = [
    ("ISIS-1101", "Electiva EHLE (Escucha, Habla y Lectura)", 4, 1, "INSTITUCIONAL", "Formación institucional", [], 0.0),
    ("ISIS-1102", "Ideando la Ingeniería", 2, 1, "OBLIGATORIA", "Ingeniería", [], -0.2),
    ("ISIS-1103", "Pensamiento Sistémico", 2, 1, "OBLIGATORIA", "Sistemas", [], -0.1),
    ("ISIS-1104", "Razonamiento Algorítmico", 3, 1, "OBLIGATORIA", "Programación", [], 0.3),
    ("ISIS-1105", "Tecnologías para el Entorno de Desarrollo", 2, 1, "OBLIGATORIA", "Programación", [], -0.1),
    ("ISIS-1106", "Álgebra Lineal", 3, 1, "OBLIGATORIA", "Ciencias básicas", [], 0.4),
    ("ISIS-1201", "Análisis de Algoritmos", 3, 2, "OBLIGATORIA", "Programación", ["ISIS-1104"], 0.4),
    ("ISIS-1202", "Cálculo Diferencial", 4, 2, "OBLIGATORIA", "Ciencias básicas", [], 0.6),
    ("ISIS-1203", "Dinámica de la Ingeniería", 2, 2, "OBLIGATORIA", "Ingeniería", ["ISIS-1102"], 0.0),
    ("ISIS-1204", "Electiva Autonomía en Contexto", 3, 2, "ELECTIVA", "Formación institucional", [], -0.2),
    ("ISIS-1205", "Matemáticas Computacionales", 2, 2, "OBLIGATORIA", "Ciencias básicas", ["ISIS-1106"], 0.4),
    ("ISIS-1206", "Programación Orientada a Objetos", 3, 2, "OBLIGATORIA", "Programación", ["ISIS-1104"], 0.3),
    ("ISIS-2301", "Cálculo Integral", 3, 3, "OBLIGATORIA", "Ciencias básicas", ["ISIS-1202"], 0.6),
    ("ISIS-2302", "Diseño y Desarrollo Multimedia", 3, 3, "OBLIGATORIA", "Desarrollo", ["ISIS-1105"], -0.1),
    ("ISIS-2303", "Electiva Creatividad", 3, 3, "ELECTIVA", "Formación institucional", [], -0.2),
    ("ISIS-2304", "Estructura de Datos", 3, 3, "OBLIGATORIA", "Programación", ["ISIS-1206", "ISIS-1201"], 0.5),
    ("ISIS-2305", "Ingeniería del Entorno", 2, 3, "OBLIGATORIA", "Ingeniería", ["ISIS-1203"], 0.0),
    ("ISIS-2306", "Laboratorio de Mecánica", 0, 3, "LABORATORIO", "Ciencias básicas", [], 0.0),
    ("ISIS-2307", "Mecánica", 3, 3, "OBLIGATORIA", "Ciencias básicas", ["ISIS-1202"], 0.5),
    ("ISIS-2401", "Arquitectura de Software", 3, 4, "OBLIGATORIA", "Ingeniería de software", ["ISIS-2304"], 0.3),
    ("ISIS-2402", "Cálculo en Varias Variables", 3, 4, "OBLIGATORIA", "Ciencias básicas", ["ISIS-2301"], 0.6),
    ("ISIS-2403", "Desarrollo Frontend", 2, 4, "OBLIGATORIA", "Desarrollo", ["ISIS-2302"], 0.0),
    ("ISIS-2404", "Diseño de Bases de Datos", 3, 4, "OBLIGATORIA", "Datos", ["ISIS-2304"], 0.2),
    ("ISIS-2405", "Electiva Ética, Ciudadanía y Cultura", 3, 4, "ELECTIVA", "Formación institucional", [], -0.2),
    ("ISIS-2406", "Electromagnetismo", 3, 4, "OBLIGATORIA", "Ciencias básicas", ["ISIS-2307", "ISIS-2301"], 0.6),
    ("ISIS-2407", "Laboratorio de Electromagnetismo", 0, 4, "LABORATORIO", "Ciencias básicas", [], 0.0),
    ("ISIS-3501", "Curso Menor I - Ing. Sistemas", 3, 5, "CURSO_MENOR", "Curso menor", [], 0.0),
    ("ISIS-3502", "Desarrollo Backend", 3, 5, "OBLIGATORIA", "Desarrollo", ["ISIS-2404", "ISIS-2401"], 0.3),
    ("ISIS-3503", "Ecuaciones Diferenciales", 3, 5, "OBLIGATORIA", "Ciencias básicas", ["ISIS-2402"], 0.6),
    ("ISIS-3504", "Estadística Descriptiva", 3, 5, "OBLIGATORIA", "Ciencias básicas", ["ISIS-2301"], 0.2),
    ("ISIS-3505", "Gestión de Bases de Datos", 2, 5, "OBLIGATORIA", "Datos", ["ISIS-2404"], 0.2),
    ("ISIS-3506", "Ingeniería de Software", 3, 5, "OBLIGATORIA", "Ingeniería de software", ["ISIS-2401"], 0.2),
    ("ISIS-3601", "Ciencia de Datos e Inteligencia Artificial", 3, 6, "OBLIGATORIA", "Datos", ["ISIS-3504", "ISIS-3505"], 0.4),
    ("ISIS-3602", "Curso Menor II - Ing. Sistemas", 3, 6, "CURSO_MENOR", "Curso menor", [], 0.0),
    ("ISIS-3603", "Desarrollo de Aplicaciones Móviles", 3, 6, "OBLIGATORIA", "Desarrollo", ["ISIS-3502", "ISIS-2403"], 0.2),
    ("ISIS-3604", "Estadística Inferencial y Muestreo", 3, 6, "OBLIGATORIA", "Ciencias básicas", ["ISIS-3504"], 0.4),
    ("ISIS-3605", "Infraestructura Tecnológica", 3, 6, "OBLIGATORIA", "Infraestructura", ["ISIS-3502"], 0.2),
    ("ISIS-3606", "Ingeniería Basada en Evidencia", 2, 6, "OBLIGATORIA", "Investigación", ["ISIS-3506"], 0.0),
    ("ISIS-4701", "Calidad de Software", 2, 7, "OBLIGATORIA", "Ingeniería de software", ["ISIS-3506"], 0.1),
    ("ISIS-4702", "Ciberseguridad", 3, 7, "OBLIGATORIA", "Infraestructura", ["ISIS-3605"], 0.3),
    ("ISIS-4703", "Curso Menor III - Ing. Sistemas", 3, 7, "CURSO_MENOR", "Curso menor", [], 0.0),
    ("ISIS-4704", "Dinámica de Sistemas", 2, 7, "OBLIGATORIA", "Sistemas", ["ISIS-3503", "ISIS-1103"], 0.3),
    ("ISIS-4705", "Servicios Cloud e IoT", 3, 7, "OBLIGATORIA", "Infraestructura", ["ISIS-3605"], 0.2),
    ("ISIS-4706", "Sistemas Inteligentes", 3, 7, "OBLIGATORIA", "Datos", ["ISIS-3601"], 0.4),
    ("ISIS-4707", "Soluciones Innovadoras", 2, 7, "OBLIGATORIA", "Investigación", ["ISIS-3606"], -0.1),
    ("ISIS-4801", "Curso Menor IV - Ing. Sistemas", 3, 8, "CURSO_MENOR", "Curso menor", [], 0.0),
    ("ISIS-4802", "Práctica Profesional", 12, 8, "PRACTICA", "Práctica", ["ISIS-4701", "ISIS-4702", "ISIS-4707"], -0.4),
]
CORREQ = {"ISIS-2306": "ISIS-2307", "ISIS-2407": "ISIS-2406"}  # laboratorio -> teoría
assert sum(p[2] for p in PLAN) == 134
PLAN_BY = {p[0]: p for p in PLAN}

CCD = [
    ("CCD-R1-ID", "Interacción Digital", 1, "Competencias Digitales Básicas", True,
     "Enseña a moverse con seguridad en internet, verificar fuentes y proteger la información."),
    ("CCD-R2-HAD", "Habilidades de Analítica Digital", 2, "Analítica y Contenido Digital", False, None),
    ("CCD-R2-MPD", "Marca Personal Digital", 2, "Analítica y Contenido Digital", False, None),
    ("CCD-R2-CCD", "Creación de Contenidos Digitales", 2, "Analítica y Contenido Digital", False, None),
    ("CCD-R3-IAG", "IA Generativa", 3, "Tecnología Transformativa", False, None),
    ("CCD-R3-MLD", "Marco Legal Digital", 3, "Tecnología Transformativa", False, None),
    ("CCD-R3-CBD", "Cuidado y Bienestar Digital", 3, "Tecnología Transformativa", False, None),
]
HOMOLOGA = {1: ["Cultura Digital y Vida en Línea", "Internet Básico"],
            2: ["MS Word", "MS PowerPoint"], 3: ["MS Excel", "Hoja Electrónica Básica"]}

PERIODOS = []
for y in range(2021, 2028):
    PERIODOS.append((f"{y}10", f"{y}-1", date(y, 1, 26), date(y, 5, 30)))
    PERIODOS.append((f"{y}20", f"{y}-2", date(y, 7, 27), date(y, 11, 28)))
ACTUAL = "202620"
PER_IDX = {p[0]: i for i, p in enumerate(PERIODOS)}
INGLES = ["A1", "A2", "B1", "B1", "B2", "B2", "C1"]
VALOR_CREDITO = 615_000  # COP sintético


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def estado_por_pga(pga, prev_estado):
    if pga > 3.20:
        return "NORMAL"
    if pga >= 3.00:
        return "PRUEBA_ACADEMICA" if prev_estado in ("CONDICIONAL", "PRUEBA_ACADEMICA") else "CONDICIONAL"
    return "PRUEBA_ACADEMICA"


def nota(habilidad, dificultad):
    return round(min(5.0, max(0.5, random.gauss(habilidad - dificultad * 0.6, 0.45))), 1)


def simular_estudiante(sid, nombres, apellidos, ingreso, habilidad, perfil=None):
    """Recorre periodos desde el ingreso hasta el actual cursando el plan."""
    hist, mats, ccd, diag = [], [], [], None
    aprobadas, reprobadas = set(), {}
    mejor = {}
    prev_estado = "NORMAL"
    estado = "NORMAL"
    i0, i1 = PER_IDX[ingreso], PER_IDX[ACTUAL]
    condicion = "ACTIVO"
    deserta_en = None
    if perfil is None and random.random() < 0.05 and i1 - i0 >= 2:
        deserta_en = random.randint(i0 + 1, i1)
    sem_cursados = 0
    ruta_pend = {1, 2, 3}
    nuevo_ccd = ingreso >= "202610"
    if nuevo_ccd:
        diag = round(random.uniform(45, 95), 1)
        if diag >= 70:
            ruta_pend.discard(1)
            ccd.append(("CCD-R1-ID", ingreso, "PRUEBA_DIAGNOSTICA", "APROBADA", None, None))
    else:  # estudiantes antiguos: homologación del plan de informática anterior
        for r in (1, 2, 3):
            if random.random() < 0.55:
                ruta_pend.discard(r)
                cod = [c[0] for c in CCD if c[2] == r][0]
                ccd.append((cod, "202610", "HOMOLOGACION", "HOMOLOGADA", None, random.choice(HOMOLOGA[r])))

    for ip in range(i0, i1 + 1):
        per = PERIODOS[ip][0]
        if deserta_en is not None and ip >= deserta_en:
            condicion = "DESERTOR"
            break
        if len(aprobadas) == len(PLAN):
            condicion = "EGRESADO"
            break
        en_curso = (per == ACTUAL)
        max_cred = {"NORMAL": 18, "CONDICIONAL": 9, "PRUEBA_ACADEMICA": 6}[estado]
        max_cursos = {"NORMAL": 9, "CONDICIONAL": 3, "PRUEBA_ACADEMICA": 2}[estado]
        candidatos = []
        for c in PLAN:
            cod = c[0]
            if cod in aprobadas:
                continue
            if estado == "PRUEBA_ACADEMICA" and cod not in reprobadas:
                continue
            if all(p in aprobadas for p in c[6]):
                candidatos.append(c)
        candidatos.sort(key=lambda c: (c[0] not in reprobadas, c[3]))
        tomados, cred = [], 0
        for c in candidatos:
            if c[0] in CORREQ:
                continue
            if cred + c[2] <= max_cred and len(tomados) < max_cursos:
                tomados.append(c)
                cred += c[2]
                lab = [k for k, v in CORREQ.items() if v == c[0]]
                if lab and lab[0] not in aprobadas:
                    tomados.append(PLAN_BY[lab[0]])
        if not tomados:
            continue
        sem_cursados += 1
        suma, credp = 0, 0
        for c in tomados:
            intento = 1 + (1 if c[0] in reprobadas else 0)
            if en_curso:
                hist.append((c[0], per, None, "EN_CURSO", intento, round(random.uniform(0, 12), 1)))
                continue
            n = nota(habilidad + (0.25 if intento > 1 else 0), c[7])
            fallas = round(random.choice([0, 0, 0, 2.5, 5, 7.5, 10, 12.5, 15, 22.5]), 1)
            if fallas >= 20:  # Art. 46: inasistencia >= 20 % reprueba
                n = min(n, 2.0)
            st = "APROBADA" if n >= 3.0 else "REPROBADA"
            hist.append((c[0], per, n, st, intento, fallas))
            if c[2] > 0:
                suma += n * c[2]
                credp += c[2]
            if st == "APROBADA":
                aprobadas.add(c[0])
                reprobadas.pop(c[0], None)
            else:
                reprobadas[c[0]] = reprobadas.get(c[0], 0) + 1
            prev = mejor.get(c[0])
            if prev is None or n > prev:
                mejor[c[0]] = n
        # CCD: un curso por periodo en los primeros semestres
        if ruta_pend and (sem_cursados <= 4 or random.random() < 0.35):
            r = min(ruta_pend)
            opciones = [x for x in CCD if x[2] == r]
            cc = random.choice(opciones)
            via = random.choice(["CURSO", "CURSO", "CURSO", "VACACIONAL", "INTENSIVO"])
            if en_curso:
                ccd.append((cc[0], per, "CURSO", "EN_CURSO", None, None))
                ruta_pend.discard(r)
            else:
                nn = nota(habilidad + 0.4, 0)
                stt = "APROBADA" if nn >= 3.0 else "REPROBADA"
                ccd.append((cc[0], per, via, stt, nn, None))
                if stt == "APROBADA":
                    ruta_pend.discard(r)
        valor = cred * VALOR_CREDITO
        if en_curso:
            ef = random.choices(["PAGADA", "PENDIENTE", "FINANCIADA", "VENCIDA"], [70, 12, 15, 3])[0]
            mats.append((per, cred, valor, ef, date(2026, 7, random.randint(1, 24)) if ef in ("PAGADA", "FINANCIADA") else None,
                         random.choice(["PSE", "Tarjeta de crédito", "ICETEX", "Flexi30", "Plan Horizontes"]) if ef != "PENDIENTE" else None,
                         estado, None, None))
        else:
            ppa = round(suma / credp, 2) if credp else None
            cred_tot = sum(PLAN_BY[k][2] for k in mejor if PLAN_BY[k][2] > 0)
            pga = round(sum(mejor[k] * PLAN_BY[k][2] for k in mejor if PLAN_BY[k][2] > 0) / cred_tot, 2) if cred_tot else None
            prev_estado = estado
            estado = estado_por_pga(pga, prev_estado) if pga else "NORMAL"
            fecha = PERIODOS[ip][2] - timedelta(days=random.randint(3, 25))
            mats.append((per, cred, valor, random.choice(["PAGADA"] * 8 + ["FINANCIADA"] * 2), fecha,
                         random.choice(["PSE", "Tarjeta de crédito", "ICETEX", "Flexi30", "Efectivo banco"]),
                         estado, ppa, pga))
            if perfil is None and estado == "PRUEBA_ACADEMICA" and prev_estado == "PRUEBA_ACADEMICA" and pga < 3.0:
                condicion = "INACTIVO"  # pierde derecho de renovación (Art. 85 par. 2)
                break
    sem_actual = min(8, max(1, 1 + len([m for m in mats if m[7] is not None]) if condicion == "ACTIVO" else len(mats)))
    if perfil and perfil.get("semestre"):
        sem_actual = perfil["semestre"]
    nivel_ing = INGLES[min(len(INGLES) - 1, int(sem_cursados * random.uniform(0.5, 0.9)))]
    if perfil and perfil.get("ingles"):
        nivel_ing = perfil["ingles"]
    if condicion == "EGRESADO" and nivel_ing in ("B2", "C1") and random.random() < 0.6:
        condicion = "GRADUADO"
    return dict(id=sid, nombres=nombres, apellidos=apellidos, ingreso=ingreso, condicion=condicion,
                semestre=sem_actual, ingles=nivel_ing, hist=hist, mats=mats, ccd=ccd, diag=diag)


def nuevo_id(usados):
    while True:
        n = random.randint(140000, 199999)
        sid = f"U00{n}"
        if sid not in usados:
            usados.add(sid)
            return sid


def main(n_est: int, salida: str):
    out = ["-- Datos SINTÉTICOS generados por generar_datos_sinteticos.py (semilla %d)" % SEED,
           "SET search_path TO academico, public, extensions;", "BEGIN;",
           "TRUNCATE chat_log, ccd_prueba_diagnostica, ccd_historial, matricula, historial_academico, estudiante, "
           "prerrequisito, asignatura, ccd_curso, periodo, programa RESTART IDENTITY CASCADE;"]
    p = PROGRAMA
    out.append(f"INSERT INTO programa VALUES ({q(p['cod'])},{q(p['nombre'])},{q(p['facultad'])},{q(p['snies'])},{p['creditos']},{p['semestres']},'B2',3.20);")
    for cod, desc, ini, fin in PERIODOS:
        out.append(f"INSERT INTO periodo VALUES ({q(cod)},{q(desc)},{q(ini.isoformat())},{q(fin.isoformat())},{q(cod == ACTUAL)});")
    for c in PLAN:
        out.append(f"INSERT INTO asignatura VALUES ({q(c[0])},{q(c[1])},{c[2]},{c[3]},'ISIS',{q(c[4])},{q(c[5])});")
    for c in PLAN:
        for pre in c[6]:
            out.append(f"INSERT INTO prerrequisito VALUES ({q(c[0])},{q(pre)},'PRE');")
    for lab, teo in CORREQ.items():
        out.append(f"INSERT INTO prerrequisito VALUES ({q(lab)},{q(teo)},'CO');")
    for c in CCD:
        out.append(f"INSERT INTO ccd_curso VALUES ({q(c[0])},{q(c[1])},{c[2]},{q(c[3])},{q(c[4])},{q(c[5])});")

    usados = set()
    estudiantes = []
    # Perfiles demo con IDs fijos para el video de demostración
    demos = [
        ("U00174957", "Valentina", "Rojas Méndez", "202410", 4.3, {"semestre": 6, "ingles": "B1"}),
        ("U00160001", "Andrés Felipe", "Gómez Pardo", "202510", 3.15, {"semestre": 4, "ingles": "A2"}),
        ("U00160002", "Laura Camila", "Suárez Díaz", "202420", 3.05, {"semestre": 5, "ingles": "A2"}),
        ("U00160003", "Santiago", "Pérez Villamizar", "202620", 3.9, {"semestre": 1, "ingles": "A2"}),
        ("U00160004", "María José", "Ardila Castro", "202310", 4.6, {"semestre": 8, "ingles": "B2"}),
    ]
    for sid, nom, ape, ing, hab, perf in demos:
        usados.add(sid)
        estudiantes.append(simular_estudiante(sid, nom, ape, ing, hab, perf))
    ingresos = [pp[0] for pp in PERIODOS if "202210" <= pp[0] <= ACTUAL]
    for _ in range(n_est - len(demos)):
        sex = random.random() < 0.3
        nom = (fake.first_name_female() if sex else fake.first_name_male())
        if random.random() < 0.35:
            nom += " " + (fake.first_name_female() if sex else fake.first_name_male())
        ape = f"{fake.last_name()} {fake.last_name()}"
        estudiantes.append(simular_estudiante(nuevo_id(usados), nom, ape, random.choice(ingresos),
                                              random.gauss(3.8, 0.45)))

    for e in estudiantes:
        email = (e["nombres"].split()[0][0] + e["apellidos"].split()[0]).lower()
        email = email.translate(str.maketrans("áéíóúñü", "aeiounu")) + e["id"][-3:] + "@unab.edu.co"
        out.append(f"INSERT INTO estudiante (id_estudiante,nombres,apellidos,email,cod_programa,periodo_ingreso,condicion,semestre_actual,nivel_ingles) VALUES "
                   f"({q(e['id'])},{q(e['nombres'])},{q(e['apellidos'])},{q(email)},'ISIS',{q(e['ingreso'])},{q(e['condicion'])},{e['semestre']},{q(e['ingles'])});")
        for cod, per, n, st, it, fa in e["hist"]:
            out.append(f"INSERT INTO historial_academico (id_estudiante,cod_asignatura,cod_periodo,nota_final,estado,intento,fallas_pct) VALUES "
                       f"({q(e['id'])},{q(cod)},{q(per)},{q(n)},{q(st)},{it},{fa});")
        for m in e["mats"]:
            out.append("INSERT INTO matricula VALUES (" + ",".join(q(x.isoformat() if isinstance(x, date) else x)
                                                                    for x in (e["id"], *m)) + ");")
        for cod, per, via, st, nn, orig in e["ccd"]:
            out.append(f"INSERT INTO ccd_historial (id_estudiante,cod_ccd,cod_periodo,via,estado,nota,curso_origen) VALUES "
                       f"({q(e['id'])},{q(cod)},{q(per)},{q(via)},{q(st)},{q(nn)},{q(orig)});")
        if e["diag"] is not None:
            out.append(f"INSERT INTO ccd_prueba_diagnostica VALUES ({q(e['id'])},{q(PERIODOS[PER_IDX[e['ingreso']]][2].isoformat())},{e['diag']});")
    out.append("COMMIT;")
    with open(salida, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{len(estudiantes)} estudiantes -> {salida} ({len(out)} sentencias)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="03_seed.sql")
    a = ap.parse_args()
    main(a.n, a.out)
