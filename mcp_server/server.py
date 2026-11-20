"""
Servidor MCP (FastMCP) del Chatbot Académico UNAB - Ingeniería de Sistemas.

Expone herramientas relacionales sobre PostgreSQL/Supabase (simulación Banner/COSMOS)
y búsqueda semántica (RAG) sobre documentos institucionales con pgvector.

Transporte: HTTP streamable en  http://<host>:9000/mcp   (lo consume el nodo "MCP Client" de n8n,
Claude Desktop u otros clientes MCP).

Rutas HTTP auxiliares (para n8n y la app Gradio):
  GET  /health            estado del servicio
  POST /auth              valida nombre completo + ID + carrera
  POST /embed             {"texts": [...]} -> embeddings 384d (ingesta RAG desde n8n)
  POST /rag/search        {"query": "...", "k": 5}
  POST /scrape            ejecuta el scraper de noticias
"""
import hashlib
import json
import os
import re
import secrets
import unicodedata

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

import db
import glosario
import scraper
from embeddings import embed, to_pgvector

API_TOKEN = os.getenv("API_TOKEN", "")  # si se define, /auth /embed /scrape exigen header X-API-Key

mcp = FastMCP(
    name="unab-academico",
    instructions=(
        "Herramientas del chatbot académico de la UNAB (Ingeniería de Sistemas). Datos de estudiantes "
        "SINTÉTICOS que simulan Banner/COSMOS. Usa siempre el id_estudiante de la sesión autenticada; "
        "nunca consultes datos de otro estudiante. Para normas usa buscar_reglamento_y_documentos y cita el artículo."
    ),
)

ID_RX = re.compile(r"^U\d{8}$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _check_id(id_estudiante: str) -> str:
    sid = (id_estudiante or "").strip().upper()
    if not ID_RX.match(sid):
        raise ValueError("ID inválido. Formato esperado: U seguido de 8 dígitos, p. ej. U00174957")
    if not db.fetch_one("SELECT 1 AS x FROM estudiante WHERE id_estudiante=%s", (sid,)):
        raise ValueError(f"No existe un estudiante con ID {sid}")
    return sid


# ----------------------------------------------------------------- herramientas MCP
@mcp.tool
def identificar_estudiante(nombre_completo: str, id_estudiante: str, programa: str = "Ingeniería de Sistemas") -> dict:
    """Valida la identidad del estudiante con su nombre completo, ID (U00xxxxxx) y carrera."""
    return autenticar(nombre_completo, id_estudiante, programa)


@mcp.tool
def estado_academico(id_estudiante: str) -> dict:
    """Estado de matrícula del periodo actual y avance del plan: créditos aprobados, % de avance,
    PGA, estado académico según el Reglamento (Normal/Condicional/Prueba académica)."""
    sid = _check_id(id_estudiante)
    resumen = db.fetch_one("SELECT * FROM v_resumen_estudiante WHERE id_estudiante=%s", (sid,))
    mat = db.fetch_one("""SELECT cod_periodo, periodo, creditos_inscritos, valor_matricula, estado_financiero,
                                 fecha_pago, medio_pago FROM v_matricula_actual WHERE id_estudiante=%s""", (sid,))
    en_curso = db.fetch_all("""SELECT a.nombre AS asignatura, a.creditos FROM historial_academico h
                               JOIN asignatura a USING (cod_asignatura)
                               WHERE h.id_estudiante=%s AND h.estado='EN_CURSO' ORDER BY a.semestre_sugerido""", (sid,))
    hist = db.fetch_all("""SELECT cod_periodo, creditos_inscritos, ppa, pga, estado_academico FROM matricula
                           WHERE id_estudiante=%s ORDER BY cod_periodo""", (sid,))
    return {"resumen": resumen, "matricula_periodo_actual": mat, "cursos_en_curso": en_curso,
            "evolucion_por_periodo": hist,
            "nota": "Estados según Art. 24 del Reglamento: Normal PGA>3.20; Condicional 3.00-3.20; "
                    "Prueba académica: segundo periodo consecutivo 3.00-3.20 o PGA<3.00."}


@mcp.tool
def historial_cursos(id_estudiante: str, periodo: str | None = None) -> list[dict]:
    """Historial de asignaturas cursadas (nota, estado, intento, % fallas). periodo opcional: '202610'."""
    sid = _check_id(id_estudiante)
    sql = """SELECT h.cod_periodo, a.semestre_sugerido AS semestre_plan, a.nombre AS asignatura, a.creditos,
                    h.nota_final, h.estado, h.intento, h.fallas_pct
             FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
             WHERE h.id_estudiante=%s"""
    params = [sid]
    if periodo:
        sql += " AND h.cod_periodo=%s"
        params.append(periodo)
    return db.fetch_all(sql + " ORDER BY h.cod_periodo, a.semestre_sugerido", params)


@mcp.tool
def asignaturas_pendientes(id_estudiante: str) -> dict:
    """Asignaturas del plan que faltan, indicando cuáles ya puede inscribir (prerrequisitos cumplidos)."""
    return _pendientes(_check_id(id_estudiante))


def _pendientes(sid: str) -> dict:
    rows = db.fetch_all("""SELECT * FROM v_asignaturas_pendientes WHERE id_estudiante=%s
                           ORDER BY semestre_sugerido, asignatura""", (sid,))
    return {"habilitadas": [r for r in rows if not r["prerrequisitos_faltantes"] and not r["en_curso"]],
            "en_curso": [r for r in rows if r["en_curso"]],
            "bloqueadas_por_prerrequisito": [r for r in rows if r["prerrequisitos_faltantes"] and not r["en_curso"]]}


@mcp.tool
def proyeccion_y_recomendaciones(id_estudiante: str) -> dict:
    """Proyección de semestres restantes, alertas de requisitos pendientes (inglés B2, competencias
    digitales, PGA de grado, estado académico), propuesta de cursos para el próximo periodo y
    recomendaciones para el éxito académico en tres ejes: investigación, autoaprendizaje y educación de precisión."""
    sid = _check_id(id_estudiante)
    proy = db.fetch_one("SELECT * FROM v_proyeccion_grado WHERE id_estudiante=%s", (sid,))
    pend = _pendientes(sid)
    estado = proy["estado_academico"]
    max_cred = {"CONDICIONAL": 9, "PRUEBA_ACADEMICA": 99}.get(estado, 18)
    max_cursos = {"CONDICIONAL": 3, "PRUEBA_ACADEMICA": 2}.get(estado, 9)
    # El próximo periodo empieza cuando termine el actual: se asume que aprueba los cursos que está viendo.
    viendo = {c["asignatura"] for c in pend["en_curso"]}
    cand = pend["habilitadas"] + [c for c in pend["bloqueadas_por_prerrequisito"]
                                  if not {x.strip() for x in c["prerrequisitos_faltantes"].split(",")} - viendo]
    if estado == "PRUEBA_ACADEMICA":
        cand = [c for c in cand if c["reprobada_antes"]]
    cand = sorted(cand, key=lambda c: (not c["reprobada_antes"], c["semestre_sugerido"]))
    plan, cred = [], 0
    for c in cand:
        if cred + c["creditos"] <= max_cred and len(plan) < max_cursos:
            plan.append({"asignatura": c["asignatura"], "creditos": c["creditos"],
                         "motivo": "repetir curso reprobado" if c["reprobada_antes"] else f"semestre {c['semestre_sugerido']} del plan"})
            cred += c["creditos"]
    dificiles = db.fetch_all("""SELECT a.area, COUNT(*) AS reprobadas FROM historial_academico h
                                JOIN asignatura a USING (cod_asignatura)
                                WHERE h.id_estudiante=%s AND h.estado='REPROBADA'
                                GROUP BY a.area ORDER BY 2 DESC""", (sid,))
    fallas = db.fetch_one("""SELECT COUNT(*) FILTER (WHERE fallas_pct>=15) AS cursos_fallas_altas
                             FROM historial_academico WHERE id_estudiante=%s""", (sid,))
    recs = []
    if estado == "CONDICIONAL":
        recs.append("Inscríbete en una estrategia de acompañamiento de Bienestar Universitario y acuerda con tu director los 3 cursos a matricular (Art. 84).")
    if estado == "PRUEBA_ACADEMICA":
        recs.append("Solicita por escrito al Consejo de Facultad el ingreso al Programa de Recuperación Académica (Art. 86); solo podrás matricular 2 cursos reprobados.")
    if dificiles:
        recs.append(f"Tu área con más dificultad es '{dificiles[0]['area']}': usa la asesoría académica de los profesores (Art. 82) y monitorías.")
    if fallas and fallas["cursos_fallas_altas"]:
        recs.append("Tienes cursos con inasistencia ≥15 %. Recuerda que con 20 % o más de fallas el curso se pierde (Art. 46).")
    if proy["ccd_rutas_pendientes"]:
        recs.append("Completa las rutas de Competencias Digitales pendientes (se recomienda en los tres primeros semestres; hay cursos vacacionales e intensivos).")
    if not proy["ingles_cumplido"]:
        recs.append(f"Planea tu inglés: estás en {proy['nivel_ingles']} y necesitas B2 para grado.")
    if proy["pga"] and proy["pga"] >= 4.25:
        recs.append("Vas en camino a una distinción de grado (Cum Laude desde PGA 4.25, sin cursos reprobados ni repetidos, Art. 89).")
    return {"proyeccion": proy, "propuesta_proximo_periodo": {"creditos": cred, "cursos": plan,
            "limite_aplicado": f"{max_cursos} cursos / {max_cred if max_cred < 99 else 'sin tope'} créditos por estado {estado}",
            "supuesto": "Se asume que apruebas los cursos que estás viendo este periodo." if pend["en_curso"] else ""},
            "recomendaciones_personalizadas": recs, "areas_con_dificultad": dificiles,
            "recomendaciones_exito": _recomendaciones_exito(sid, proy, dificiles, plan)}


def _recomendaciones_exito(sid: str, proy: dict, dificiles: list, plan: list) -> dict:
    """Recomendaciones en los tres ejes del objetivo del proyecto: investigación, autoaprendizaje y
    educación de precisión (decisiones basadas en los datos del propio estudiante)."""
    areas = db.fetch_all("""SELECT a.area, ROUND(AVG(m.nota_final)::numeric, 2) AS promedio, COUNT(*) AS cursos
                            FROM v_mejor_nota m JOIN asignatura a USING (cod_asignatura)
                            WHERE m.id_estudiante=%s AND m.nota_final IS NOT NULL
                            GROUP BY a.area ORDER BY promedio DESC""", (sid,))
    pga = float(proy["pga"] or 0); sem = proy["semestre_actual"] or 1
    fuerte = areas[0] if areas else None
    debil = areas[-1] if len(areas) > 1 else None
    inv = []
    if pga >= 3.8 and sem >= 3:
        inv.append("Tu rendimiento te permite postularte a un semillero de investigación de la Facultad de Ingeniería; pregunta a tu director por los grupos activos y sus convocatorias.")
    elif sem >= 3:
        inv.append("Antes de entrar a un semillero, estabiliza tu PGA por encima de 3.5; mientras tanto asiste a charlas y eventos de investigación de la facultad.")
    else:
        inv.append("En los primeros semestres explora líneas de investigación del programa (eventos, ferias de proyectos) para elegir un tema con tiempo.")
    if fuerte:
        inv.append(f"Tu área más fuerte es '{fuerte['area']}' (promedio {fuerte['promedio']}): es una buena candidata para tu proyecto de grado o un trabajo de investigación.")
    if sem >= 6:
        inv.append("Ya puedes perfilar tu opción de grado: un proyecto aplicado o de investigación se planea mejor uno o dos semestres antes de la práctica.")
    auto = []
    if proy["ccd_rutas_pendientes"]:
        auto.append(f"Tienes {proy['ccd_rutas_pendientes']} ruta(s) de Competencias Digitales pendientes: los cursos del CCD son virtuales y se pueden avanzar a tu ritmo, incluso en vacaciones.")
    if not proy["ingles_cumplido"]:
        auto.append(f"Inglés {proy['nivel_ingles']} → B2: dedica de 3 a 5 horas semanales de práctica autónoma (lectura técnica, escucha, plataformas de la biblioteca) además de los cursos.")
    if debil:
        auto.append(f"Refuerza '{debil['area']}' (tu promedio más bajo, {debil['promedio']}) con ejercicios y cursos abiertos antes de los cursos que la necesitan.")
    auto.append("Lleva un registro semanal de tus horas de estudio por materia; la regla de oro es 2 horas autónomas por cada crédito presencial.")
    prec = []
    if debil and fuerte:
        prec.append(f"Diferencia entre tu mejor área ({fuerte['area']}, {fuerte['promedio']}) y la más baja ({debil['area']}, {debil['promedio']}): prioriza asesorías en la segunda (Art. 82).")
    if dificiles:
        prec.append(f"Concentraste {dificiles[0]['reprobadas']} reprobación(es) en '{dificiles[0]['area']}'; no matricules juntos dos cursos de esa área en el mismo periodo.")
    if plan:
        prec.append("Cursos recomendados para tu próximo periodo según prerrequisitos y límite de carga: " + ", ".join(c["asignatura"] for c in plan) + ".")
    falta = 3.20 - pga
    if 0 < falta:
        prec.append(f"Te faltan {falta:.2f} puntos de PGA para el mínimo de grado (3.20, Art. 67).")
    return {"investigacion": inv, "autoaprendizaje": auto, "educacion_de_precision": prec, "promedio_por_area": areas}


# ----------------------------------------------------------------- simulador de notas
_CARGA = {"NORMAL": "hasta 18 créditos", "CONDICIONAL": "máximo 3 cursos y acompañamiento de Bienestar (Art. 84)",
          "PRUEBA_ACADEMICA": "solo 2 cursos reprobados dentro del Programa de Recuperación Académica (Art. 85-86)"}


def _estado_por_pga(pga: float | None, estado_actual: str) -> str:
    """Art. 24: Normal PGA > 3.20; Condicional 3.00-3.20; Prueba si es el segundo periodo consecutivo
    en 3.00-3.20 o si el PGA es inferior a 3.00."""
    if pga is None:
        return estado_actual or "NORMAL"
    if pga > 3.20:
        return "NORMAL"
    if pga >= 3.00:
        return "PRUEBA_ACADEMICA" if estado_actual in ("CONDICIONAL", "PRUEBA_ACADEMICA") else "CONDICIONAL"
    return "PRUEBA_ACADEMICA"


def _base_simulacion(sid: str) -> dict:
    mejores = db.fetch_all("""SELECT cod_asignatura AS codigo, asignatura, creditos, nota_final AS nota, estado
                              FROM v_mejor_nota WHERE id_estudiante=%s""", (sid,))
    en_curso = db.fetch_all("""SELECT h.cod_asignatura AS codigo, a.nombre AS asignatura, a.creditos,
                                      EXISTS (SELECT 1 FROM historial_academico r WHERE r.id_estudiante=h.id_estudiante
                                              AND r.cod_asignatura=h.cod_asignatura AND r.estado='REPROBADA') AS repite
                               FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
                               WHERE h.id_estudiante=%s AND h.estado='EN_CURSO'
                               ORDER BY a.semestre_sugerido, a.nombre""", (sid,))
    res = db.fetch_one("""SELECT pga, estado_academico, creditos_aprobados, creditos_totales, porcentaje_avance
                          FROM v_resumen_estudiante WHERE id_estudiante=%s""", (sid,))
    return {"mejores": mejores, "en_curso": en_curso, "resumen": res}


def _calcular(base: dict, notas: dict) -> dict:
    """Recalcula PGA y créditos como v_resumen_estudiante: cuenta la mejor nota de cada asignatura
    (si apruebas un curso que habías reprobado, la nota reprobada deja de contar)."""
    rango = lambda r: (r["estado"] in ("APROBADA", "HOMOLOGADA"), float(r["nota"] or 0))
    mejor = {r["codigo"]: r for r in base["mejores"]}
    for c in base["en_curso"]:
        if c["codigo"] not in notas:
            continue
        n = float(notas[c["codigo"]])
        nuevo = {"codigo": c["codigo"], "creditos": c["creditos"], "nota": n,
                 "estado": "APROBADA" if n >= 3.0 else "REPROBADA"}
        if c["codigo"] not in mejor or rango(nuevo) > rango(mejor[c["codigo"]]):
            mejor[c["codigo"]] = nuevo
    cursadas = [r for r in mejor.values() if r["estado"] != "HOMOLOGADA" and (r["creditos"] or 0) > 0 and r["nota"] is not None]
    cred = sum(r["creditos"] for r in cursadas)
    pga = round(sum(float(r["nota"]) * r["creditos"] for r in cursadas) / cred, 2) if cred else None
    aprob = sum(r["creditos"] for r in mejor.values() if r["estado"] in ("APROBADA", "HOMOLOGADA"))
    return {"pga": pga, "creditos_aprobados": aprob}


def _nota_minima(base: dict, cods: list, objetivo) -> float | None:
    """Menor nota igual en todos los cursos actuales con la que se cumple `objetivo(resultado)`."""
    if not cods:
        return None
    if not objetivo(_calcular(base, {c: 5.0 for c in cods})):
        return None
    lo, hi = 0.0, 5.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if objetivo(_calcular(base, {c: mid for c in cods})):
            hi = mid
        else:
            lo = mid
    return round(min(5.0, (int(hi * 10 + 0.999)) / 10), 1)


def _simular(sid: str, notas: dict | None = None, nota_uniforme: float | None = None) -> dict:
    base = _base_simulacion(sid)
    res = base["resumen"] or {}
    actual = res.get("estado_academico") or "NORMAL"
    cods = [c["codigo"] for c in base["en_curso"]]
    por_nombre = {_norm(c["asignatura"]): c["codigo"] for c in base["en_curso"]}
    elegidas: dict = {}
    for k, v in (notas or {}).items():
        if v is None or v == "":
            continue
        cod = k if k in cods else por_nombre.get(_norm(str(k))) or next(
            (c for n, c in por_nombre.items() if _norm(str(k)) and _norm(str(k)) in n), None)
        if cod:
            elegidas[cod] = max(0.0, min(5.0, round(float(v), 1)))
    if nota_uniforme is not None:
        for c in cods:
            elegidas.setdefault(c, max(0.0, min(5.0, round(float(nota_uniforme), 1))))
    calc = _calcular(base, elegidas)
    nuevo = _estado_por_pga(calc["pga"], actual) if elegidas else actual
    cursos = []
    for c in base["en_curso"]:
        n = elegidas.get(c["codigo"])
        cursos.append({"codigo": c["codigo"], "asignatura": c["asignatura"], "creditos": c["creditos"], "nota": n,
                       "resultado": None if n is None else ("aprobada" if n >= 3.0 else "reprobada"), "repite": c["repite"]})
    con_nota = [c for c in cursos if c["nota"] is not None]
    cred_sim = sum(c["creditos"] for c in con_nota)
    ppa = round(sum(c["nota"] * c["creditos"] for c in con_nota) / cred_sim, 2) if cred_sim else None
    tot = res.get("creditos_totales") or 0
    min_normal = _nota_minima(base, cods, lambda r: _estado_por_pga(r["pga"], actual) == "NORMAL")
    min_no_prueba = _nota_minima(base, cods, lambda r: _estado_por_pga(r["pga"], actual) != "PRUEBA_ACADEMICA")
    avisos = [] if elegidas else ["Escribe la nota que esperas en al menos uno de tus cursos actuales."]
    reprob = [c["asignatura"] for c in con_nota if c["resultado"] == "reprobada"]
    if reprob:
        uno = len(reprob) == 1
        avisos.append("Con esas notas reprobarías " + ", ".join(reprob) + ("; tendrías que repetirla y esa nota sigue contando en tu PGA hasta que la apruebes."
                      if uno else "; tendrías que repetirlas y esas notas siguen contando en tu PGA hasta que las apruebes."))
    if not elegidas:
        pass
    elif nuevo == "PRUEBA_ACADEMICA":
        avisos.append("Quedarías en prueba académica: debes solicitar el ingreso al Programa de Recuperación Académica (Art. 86). "
                      "Si no lo apruebas, pierdes el derecho de renovar matrícula (Art. 12 y 87).")
    elif nuevo == "CONDICIONAL":
        avisos.append("Quedarías en estado condicional: el próximo periodo podrás matricular máximo 3 cursos (Art. 84). "
                      "Si repites ese rango otro periodo, pasarías a prueba académica (Art. 24).")
    if elegidas and calc["pga"] is not None and calc["pga"] < 3.20:
        avisos.append("Para graduarte necesitas un PGA mínimo de 3.20 (Art. 67).")
    if calc["pga"] is not None and calc["pga"] >= 4.25 and not res.get("cursos_reprobados_pendientes"):
        avisos.append("Con un PGA desde 4.25, sin cursos reprobados ni repetidos, podrías aspirar a una distinción de grado (Art. 89).")
    return {
        "actual": {"pga": res.get("pga"), "estado": actual, "creditos_aprobados": res.get("creditos_aprobados"),
                   "porcentaje_avance": res.get("porcentaje_avance")},
        "simulado": {"ppa_periodo": ppa, "pga": calc["pga"], "estado": nuevo, "creditos_aprobados": calc["creditos_aprobados"],
                     "porcentaje_avance": round(100 * calc["creditos_aprobados"] / tot, 1) if tot else None,
                     "carga_proximo_periodo": _CARGA.get(nuevo, "")},
        "cursos": cursos,
        "nota_minima_para_normal": min_normal, "nota_minima_para_evitar_prueba": min_no_prueba,
        "avisos": avisos,
        "nota": "Estimación con la mejor nota de cada asignatura y el Art. 24 del Reglamento; el estado oficial lo define la universidad al cierre del periodo.",
    }


@mcp.tool
def simular_notas(id_estudiante: str, notas: dict[str, float] | None = None, nota_uniforme: float | None = None) -> dict:
    """Simulador "¿qué pasa si...?": recalcula el PGA, el estado académico (Art. 24) y la carga permitida del
    próximo periodo según las notas que el estudiante espera sacar en los cursos que está viendo.
    notas: {código o nombre de la asignatura: nota 0-5}. nota_uniforme: misma nota para todos los cursos sin nota.
    Devuelve además la nota mínima promedio para quedar en estado Normal y para evitar la prueba académica."""
    return _simular(_check_id(id_estudiante), notas, nota_uniforme)


@mcp.tool
def competencias_digitales(id_estudiante: str) -> dict:
    """Cursos de Competencias Digitales (CCD) tomados por el estudiante, rutas cumplidas/pendientes
    e insignia digital; incluye la oferta de cursos por ruta."""
    sid = _check_id(id_estudiante)
    return {
        "estado_por_ruta": db.fetch_all("SELECT ruta, nombre_ruta, cumplida, en_curso, detalle FROM v_ccd_estado WHERE id_estudiante=%s ORDER BY ruta", (sid,)),
        "resumen": db.fetch_one("SELECT * FROM v_ccd_resumen WHERE id_estudiante=%s", (sid,)),
        "prueba_diagnostica": db.fetch_one("SELECT fecha, puntaje_pct, puntaje_pct>=70 AS valido_ruta1 FROM ccd_prueba_diagnostica WHERE id_estudiante=%s", (sid,)),
        "oferta": db.fetch_all("SELECT ruta, nombre_ruta, nombre AS curso, obligatorio FROM ccd_curso ORDER BY ruta, nombre"),
        "reglas": "Un curso por ruta (3 rutas). Ruta 1 obligatoria: Interacción Digital. Se recomienda terminarlas en los "
                  "tres primeros semestres. Al graduarse se otorga la insignia digital. Prueba diagnóstica (estudiantes de "
                  "primer ingreso): con más del 70 % se valida el curso Interacción Digital (Ruta 1) y se continúa con las rutas 2 y 3; "
                  "si no se alcanza, se recomienda cursar Interacción Digital en el primer semestre. Las pruebas de suficiencia ya no "
                  "aplican para estudiantes continuos. Homologación: Ruta 1 con Cultura Digital y Vida en Línea; Ruta 2 con MS Word "
                  "o MS PowerPoint; Ruta 3 con MS Excel. Contacto: ccdigital@unab.edu.co · (607) 643 6111 ext. 1807/1644",
    }


@mcp.tool
def plan_de_estudios(semestre: int | None = None) -> list[dict]:
    """Plan de estudios de Ingeniería de Sistemas (134 créditos, 8 semestres) con prerrequisitos."""
    sql = """SELECT a.semestre_sugerido AS semestre, a.cod_asignatura, a.nombre, a.creditos, a.tipo,
                    COALESCE(string_agg(p.nombre, ', '), '') AS prerrequisitos
             FROM asignatura a LEFT JOIN prerrequisito pr ON pr.cod_asignatura=a.cod_asignatura AND pr.tipo='PRE'
             LEFT JOIN asignatura p ON p.cod_asignatura=pr.cod_prerrequisito"""
    params = []
    if semestre:
        sql += " WHERE a.semestre_sugerido=%s"
        params.append(semestre)
    return db.fetch_all(sql + " GROUP BY 1,2,3,4,5 ORDER BY 1,2", params)


@mcp.tool
def buscar_reglamento_y_documentos(pregunta: str, k: int = 5, fuente: str | None = None) -> list[dict]:
    """Búsqueda semántica (RAG) en el Reglamento Estudiantil, el plan de estudios, documentos del CCD y
    noticias. fuente opcional: 'reglamento' | 'plan_estudios' | 'ccd' | 'noticia'."""
    return rag_search(pregunta, k, fuente)


@mcp.tool
def calendario_academico(texto: str | None = None, desde: str | None = None) -> list[dict]:
    """Fechas del calendario académico (respaldo en BD del Google Sheet): inscripciones, pruebas
    diagnósticas, inicio de clases, pagos, competencias digitales. texto filtra por palabra; desde='2026-11-14'."""
    sql = "SELECT actividad, categoria, fecha_inicio, fecha_fin, dirigido_a, fuente FROM calendario_academico WHERE 1=1"
    params = []
    if texto:
        sql += " AND (unaccent_lower(actividad) LIKE %s OR unaccent_lower(categoria) LIKE %s)"
        params += [f"%{_norm(texto)}%"] * 2
    if desde:
        sql += " AND COALESCE(fecha_fin, fecha_inicio) >= %s"
        params.append(desde)
    return db.fetch_all(sql + " ORDER BY fecha_inicio", params)


@mcp.tool
def noticias_recientes(tema: str | None = None, limite: int = 5) -> list[dict]:
    """Noticias obtenidas por el scraper (UNAB y noticias del día de educación, tecnología e ingeniería de
    sistemas), con fuente y fecha. tema opcional: 'Educación' | 'Tecnología' | 'Ingeniería de Sistemas' |
    'Institucional' | 'CURSOS' | 'CONVOCATORIA' | 'CERTIFICACION' | 'CCD' o una palabra clave."""
    extra = ", fuente, tema" if _existe("noticia", "fuente") else ""
    sql = f"SELECT titulo, fecha_pub, etiqueta, resumen, url{extra} FROM noticia"
    params: list = []
    if tema:
        temas = {"educacion": "Educación", "tecnologia": "Tecnología", "ingenieria de sistemas": "Ingeniería de Sistemas",
                 "institucional": "Institucional"}
        if extra and _norm(tema) in temas:
            sql += " WHERE tema=%s"
            params.append(temas[_norm(tema)])
        elif tema.upper() in ("CURSOS", "CONVOCATORIA", "CERTIFICACION", "CCD", "GENERAL"):
            sql += " WHERE etiqueta=%s"
            params.append(tema.upper())
        else:
            sql += " WHERE titulo ILIKE %s OR contenido ILIKE %s"
            params += [f"%{tema}%"] * 2
    return db.fetch_all(sql + " ORDER BY fecha_pub DESC NULLS LAST LIMIT %s", params + [min(limite, 15)])


# ----------------------------------------------------------------- lógica compartida
def autenticar(nombre_completo: str, id_estudiante: str, programa: str) -> dict:
    sid = (id_estudiante or "").strip().upper()
    if not ID_RX.match(sid):
        return {"ok": False, "mensaje": "El ID debe tener el formato U00XXXXXX (U + 8 dígitos)."}
    e = db.fetch_one("""SELECT e.id_estudiante, e.nombre_completo, e.semestre_actual, e.condicion, p.nombre AS programa
                        FROM estudiante e JOIN programa p USING (cod_programa) WHERE e.id_estudiante=%s""", (sid,))
    if not e:
        return {"ok": False, "mensaje": "No encontramos ese ID en el sistema."}
    if _norm(e["nombre_completo"]) != _norm(nombre_completo):
        return {"ok": False, "mensaje": "El nombre no coincide con el registrado para ese ID."}
    if _norm(programa) not in _norm(e["programa"]):
        return {"ok": False, "mensaje": f"El estudiante no pertenece a {programa}."}
    return {"ok": True, "estudiante": e}


def rag_search(pregunta: str, k: int = 5, fuente: str | None = None) -> list[dict]:
    pregunta = glosario.expandir(pregunta)  # jerga estudiantil -> términos del Reglamento
    v = to_pgvector(embed([pregunta])[0])
    rows = db.fetch_all("SELECT * FROM buscar_hibrido(%s::vector, %s, %s, %s)", (v, pregunta, min(k, 10), fuente))
    return [{**r, "similitud": round(r["similitud"], 3)} for r in rows]


def _authorized(request: Request) -> bool:
    return not API_TOKEN or request.headers.get("x-api-key") == API_TOKEN


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request):
    n = db.fetch_one("SELECT (SELECT COUNT(*) FROM estudiante) AS estudiantes, (SELECT COUNT(*) FROM documento_chunk) AS chunks, (SELECT COUNT(*) FROM noticia) AS noticias")
    return JSONResponse({"status": "ok", **n})


DEMO_HABILITADO = os.getenv("DEMO_HABILITADO", "1") == "1"
DEMO_ID = os.getenv("DEMO_ID", "U00174957")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _crear_sesion(sid: str, dispositivo: str) -> str | None:
    if not _existe("sesion"):
        return None
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sesion (token_hash, id_estudiante, dispositivo) VALUES (%s, %s, %s)",
               (_hash_token(token), sid, (dispositivo or "Dispositivo")[:120]))
    return token


def _sesion_de_token(token: str) -> dict | None:
    if not token or not _existe("sesion"):
        return None
    th = _hash_token(token)
    r = db.fetch_one("SELECT id_estudiante FROM sesion WHERE token_hash=%s AND NOT revocada", (th,))
    if r:
        db.execute("UPDATE sesion SET ultimo_uso=now() WHERE token_hash=%s", (th,))
        r["token_hash"] = th
    return r


def _estudiante(sid: str) -> dict | None:
    return db.fetch_one("""SELECT e.id_estudiante, e.nombre_completo, e.semestre_actual, e.condicion, p.nombre AS programa
                           FROM estudiante e JOIN programa p USING (cod_programa) WHERE e.id_estudiante=%s""", (sid,))


async def _json(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:  # noqa: BLE001
        return {}


@mcp.custom_route("/auth/config", methods=["GET"])
async def auth_config(request: Request):
    """Qué funciones de acceso están activas (dependen de la migración 06)."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"password": _existe("acceso"), "sesiones": _existe("sesion"),
                         "eventos_personales": _existe("evento_personal"),
                         "demo": DEMO_HABILITADO})


@mcp.custom_route("/auth", methods=["POST"])
async def auth_route(request: Request):
    """Inicio de sesión: nombre + ID + carrera (+ contraseña si la migración 06 está aplicada).
    Con demo=true entra al perfil de prueba sin datos. Si hay sesiones guardadas, devuelve un token."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await _json(request)
    debe_cambiar = False
    if b.get("demo"):
        if not DEMO_HABILITADO:
            return JSONResponse({"ok": False, "mensaje": "El perfil de prueba está desactivado."})
        e = _estudiante(DEMO_ID)
        if not e:
            return JSONResponse({"ok": False, "mensaje": "No existe el estudiante de prueba."})
        r = {"ok": True, "estudiante": e, "demo": True}
    else:
        r = autenticar(b.get("nombre_completo", ""), b.get("id_estudiante", ""), b.get("programa", "Ingeniería de Sistemas"))
        if not r.get("ok"):
            return JSONResponse(r)
        sid = r["estudiante"]["id_estudiante"]
        if _existe("acceso"):
            a = db.fetch_one("""SELECT debe_cambiar, password_hash = extensions.crypt(%s, password_hash) AS valida
                                FROM acceso WHERE id_estudiante=%s""", (b.get("password") or "", sid))
            if not a or not a["valida"]:
                return JSONResponse({"ok": False, "mensaje": "La contraseña no es correcta."})
            debe_cambiar = bool(a["debe_cambiar"])
    r["debe_cambiar"] = debe_cambiar
    if b.get("recordar", True):
        r["token"] = _crear_sesion(r["estudiante"]["id_estudiante"], b.get("dispositivo", ""))
    return JSONResponse(json.loads(json.dumps(r, default=str)))


@mcp.custom_route("/auth/token", methods=["POST"])
async def auth_token(request: Request):
    """Reabre una sesión guardada en el dispositivo (sin volver a escribir los datos)."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    ses = _sesion_de_token((await _json(request)).get("token", ""))
    if not ses:
        return JSONResponse({"ok": False, "mensaje": "La sesión guardada ya no es válida."})
    debe = False
    if _existe("acceso"):
        a = db.fetch_one("SELECT debe_cambiar FROM acceso WHERE id_estudiante=%s", (ses["id_estudiante"],))
        debe = bool(a and a["debe_cambiar"]) and ses["id_estudiante"] != DEMO_ID
    return JSONResponse(json.loads(json.dumps({"ok": True, "estudiante": _estudiante(ses["id_estudiante"]),
                                                "debe_cambiar": debe}, default=str)))


@mcp.custom_route("/auth/password", methods=["POST"])
async def auth_password(request: Request):
    """Cambio de contraseña. Exige la sesión (token) y la contraseña actual."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not _existe("acceso"):
        return JSONResponse({"ok": False, "mensaje": "Las contraseñas todavía no están activadas en el servidor."})
    b = await _json(request)
    ses = _sesion_de_token(b.get("token", ""))
    if not ses:
        return JSONResponse({"ok": False, "mensaje": "Tu sesión expiró. Vuelve a iniciar sesión."})
    sid = ses["id_estudiante"]
    nueva = b.get("nueva") or ""
    if len(nueva) < 8 or nueva.upper() == sid or not re.search(r"[A-Za-z]", nueva) or not re.search(r"\d", nueva):
        return JSONResponse({"ok": False, "mensaje": "La contraseña nueva debe tener al menos 8 caracteres, "
                                                     "letras y números, y no puede ser tu ID."})
    ok = db.fetch_one("SELECT password_hash = extensions.crypt(%s, password_hash) AS valida FROM acceso WHERE id_estudiante=%s",
                      (b.get("actual") or "", sid))
    if not ok or not ok["valida"]:
        return JSONResponse({"ok": False, "mensaje": "La contraseña actual no es correcta."})
    db.execute("""UPDATE acceso SET password_hash = extensions.crypt(%s, extensions.gen_salt('bf', 8)),
                  debe_cambiar = FALSE, actualizado = now() WHERE id_estudiante=%s""", (nueva, sid))
    if b.get("cerrar_otras", True):
        db.execute("UPDATE sesion SET revocada=TRUE WHERE id_estudiante=%s AND token_hash<>%s", (sid, ses["token_hash"]))
    return JSONResponse({"ok": True, "mensaje": "Contraseña actualizada."})


@mcp.custom_route("/auth/sesiones", methods=["POST"])
async def auth_sesiones(request: Request):
    """Lista las sesiones abiertas del estudiante, o cierra una, todas las demás, o la actual."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await _json(request)
    ses = _sesion_de_token(b.get("token", ""))
    if not ses:
        return JSONResponse({"ok": False, "sesiones": []})
    sid, th = ses["id_estudiante"], ses["token_hash"]
    cerrar = b.get("cerrar")
    if cerrar == "esta":
        db.execute("UPDATE sesion SET revocada=TRUE WHERE token_hash=%s", (th,))
    elif cerrar == "otras":
        db.execute("UPDATE sesion SET revocada=TRUE WHERE id_estudiante=%s AND token_hash<>%s", (sid, th))
    elif cerrar:
        db.execute("UPDATE sesion SET revocada=TRUE WHERE id_estudiante=%s AND left(token_hash, 12)=%s", (sid, cerrar))
    filas = db.fetch_all("""SELECT left(token_hash, 12) AS id, dispositivo, token_hash=%s AS actual,
               to_char((creada AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota','YYYY-MM-DD HH24:MI') AS creada,
               to_char((ultimo_uso AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota','YYYY-MM-DD HH24:MI') AS ultimo_uso
           FROM sesion WHERE id_estudiante=%s AND NOT revocada ORDER BY ultimo_uso DESC LIMIT 20""", (th, sid))
    return JSONResponse({"ok": True, "sesiones": filas})


@mcp.custom_route("/historial", methods=["POST"])
async def historial_route(request: Request):
    """Últimos intercambios del estudiante (para restaurar el chat al volver a iniciar sesión).
    Exige el mismo nombre + ID que el login, además de la API key."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await request.json()
    a = autenticar(b.get("nombre_completo", ""), b.get("id_estudiante", ""), b.get("programa", "Ingeniería de Sistemas"))
    if not a.get("ok"):
        return JSONResponse({"ok": False, "mensajes": []})
    n = max(1, min(int(b.get("limite", 10)), 30))
    rows = db.fetch_all("""SELECT pregunta, respuesta, intencion, to_char((creado AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota', 'YYYY-MM-DD HH24:MI') AS fecha
                           FROM chat_log WHERE id_estudiante = %s AND respuesta IS NOT NULL
                           ORDER BY id DESC LIMIT %s""", (a["estudiante"]["id_estudiante"], n))
    return JSONResponse({"ok": True, "mensajes": list(reversed(rows))})


# ----------------------------------------------------------------- datos para las pestañas de la app
_COLS_CACHE: dict = {}


def _existe(tabla: str, columna: str | None = None) -> bool:
    """Detecta si la migración 06 (profesores, certificados, contraseñas, sesiones) ya se aplicó."""
    k = (tabla, columna)
    if k not in _COLS_CACHE:
        if columna:
            r = db.fetch_one("""SELECT 1 AS ok FROM information_schema.columns
                                WHERE table_schema='academico' AND table_name=%s AND column_name=%s""", (tabla, columna))
        else:
            r = db.fetch_one("""SELECT 1 AS ok FROM information_schema.tables
                                WHERE table_schema='academico' AND table_name=%s""", (tabla,))
        _COLS_CACHE[k] = bool(r)
    return _COLS_CACHE[k]


def _app_noticias(tema: str = ""):
    extra = "fuente, tema" if _existe("noticia", "fuente") else "'unab.edu.co' AS fuente, NULL AS tema"
    sql = f"""SELECT titulo, to_char(fecha_pub,'YYYY-MM-DD') AS fecha, ((fecha_pub AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota')::date = (now() AT TIME ZONE 'America/Bogota')::date AS hoy,
                     etiqueta, resumen, url, {extra} FROM noticia"""
    params: list = []
    if tema and _existe("noticia", "tema"):
        sql += " WHERE tema = %s"
        params.append(tema)
    return db.fetch_all(sql + " ORDER BY fecha_pub DESC NULLS LAST LIMIT 40", params)


def _app_eventos(sid: str = ""):
    unab = db.fetch_all("""SELECT 'unab' AS origen, NULL::bigint AS id, actividad, categoria, dirigido_a, fuente,
                                  NULL AS descripcion,
                                  to_char(fecha_inicio,'YYYY-MM-DD') AS inicio, to_char(fecha_fin,'YYYY-MM-DD') AS fin,
                                  (fecha_inicio - CURRENT_DATE) AS dias
                           FROM calendario_academico
                           WHERE COALESCE(fecha_fin, fecha_inicio) >= CURRENT_DATE
                           ORDER BY fecha_inicio LIMIT 25""")
    propios = []
    if sid and ID_RX.match(sid) and _existe("evento_personal"):
        propios = db.fetch_all("""SELECT 'personal' AS origen, id, nombre AS actividad, 'Personal' AS categoria,
                                         NULL AS dirigido_a, NULL AS fuente, descripcion,
                                         to_char(fecha,'YYYY-MM-DD') AS inicio, NULL AS fin, (fecha - CURRENT_DATE) AS dias
                                  FROM evento_personal WHERE id_estudiante=%s AND fecha >= CURRENT_DATE
                                  ORDER BY fecha LIMIT 50""", (sid,))
    return sorted(unab + propios, key=lambda e: (e["inicio"] or "", e["origen"] != "personal"))


@mcp.custom_route("/app/eventos", methods=["POST"])
async def app_eventos_personales(request: Request):
    """Crea o elimina un evento personal. Solo el dueño (id_estudiante) puede verlo o borrarlo."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not _existe("evento_personal"):
        return JSONResponse({"ok": False, "mensaje": "Los eventos personales todavía no están activados en el servidor."})
    b = await _json(request)
    sid = (b.get("id_estudiante") or "").strip().upper()
    if not ID_RX.match(sid):
        return JSONResponse({"ok": False, "mensaje": "ID inválido."}, status_code=400)
    if b.get("accion") == "eliminar":
        n = db.execute("DELETE FROM evento_personal WHERE id=%s AND id_estudiante=%s", (int(b.get("id") or 0), sid))
        return JSONResponse({"ok": n > 0, "mensaje": "Evento eliminado." if n else "No se encontró el evento."})
    nombre = " ".join(str(b.get("nombre") or "").split())[:120]
    desc = str(b.get("descripcion") or "").strip()[:500]
    fecha = str(b.get("fecha") or "")[:10]
    if not nombre:
        return JSONResponse({"ok": False, "mensaje": "Escribe un nombre para el evento."})
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
        return JSONResponse({"ok": False, "mensaje": "Elige una fecha válida."})
    try:
        db.execute("INSERT INTO evento_personal (id_estudiante, nombre, fecha, descripcion) VALUES (%s, %s, %s, %s)",
                   (sid, nombre, fecha, desc or None))
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "mensaje": "La fecha no es válida."})
    return JSONResponse({"ok": True, "mensaje": "Evento agregado."})


def _limpiar_respuesta(t: str) -> str:
    """Quita la marca de ruta que la app agrega al final (<sub>Ruta: ...</sub>)."""
    return re.sub(r"\s*<sub>Ruta:[^<]*</sub>\s*$", "", t or "").strip()


@mcp.custom_route("/app/calificar", methods=["POST"])
async def app_calificar(request: Request):
    """Guarda si una respuesta del asistente fue útil (1) o no (-1). Volver a calificar la misma respuesta la
    actualiza; valor 0 borra la calificación."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not _existe("calificacion"):
        return JSONResponse({"ok": False, "mensaje": "La calificación de respuestas todavía no está activada en el servidor."})
    b = await _json(request)
    sid = (b.get("id_estudiante") or "").strip().upper()
    if not ID_RX.match(sid):
        return JSONResponse({"ok": False, "mensaje": "ID inválido."}, status_code=400)
    try:
        valor = int(b.get("valor"))
    except (TypeError, ValueError):
        valor = 99
    if valor not in (-1, 0, 1):
        return JSONResponse({"ok": False, "mensaje": "Valor inválido."}, status_code=400)
    pregunta = str(b.get("pregunta") or "")[:4000]
    respuesta = _limpiar_respuesta(str(b.get("respuesta") or ""))[:12000]
    conv = str(b.get("session_id") or "")[:40] or None
    huella = hashlib.md5((pregunta + "\n" + respuesta).encode()).hexdigest()
    if valor == 0:
        db.execute("DELETE FROM calificacion WHERE id_estudiante=%s AND huella=%s", (sid, huella))
        return JSONResponse({"ok": True})
    log = db.fetch_one("""SELECT id, intencion FROM chat_log WHERE id_estudiante=%s AND pregunta=%s
                          AND (%s::text IS NULL OR session_id=%s) ORDER BY id DESC LIMIT 1""", (sid, pregunta, conv, conv)) or {}
    db.execute("""INSERT INTO calificacion (id_estudiante, session_id, chat_log_id, intencion, pregunta, respuesta, huella, valor)
                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                  ON CONFLICT (id_estudiante, huella) DO UPDATE SET valor=EXCLUDED.valor, creado=now()""",
               (sid, conv, log.get("id"), log.get("intencion") or b.get("intencion"), pregunta, respuesta, huella, valor))
    return JSONResponse({"ok": True})


@mcp.custom_route("/app/simular", methods=["POST"])
async def app_simular(request: Request):
    """Simulador de notas de la pestaña Personal (misma lógica que la herramienta MCP simular_notas)."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await _json(request)
    sid = (b.get("id_estudiante") or "").strip().upper()
    if not ID_RX.match(sid):
        return JSONResponse({"ok": False, "mensaje": "ID inválido."}, status_code=400)
    notas = b.get("notas") if isinstance(b.get("notas"), dict) else {}
    try:
        data = _simular(sid, notas)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "mensaje": str(e)}, status_code=500)
    return JSONResponse(json.loads(json.dumps({"ok": True, "datos": data}, default=str)))


def _app_historial_chat(sid: str):
    return db.fetch_all("""SELECT pregunta, respuesta, intencion,
                                  to_char((creado AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota','YYYY-MM-DD HH24:MI') AS fecha
                           FROM chat_log WHERE id_estudiante=%s AND respuesta IS NOT NULL
                           ORDER BY id DESC LIMIT 60""", (sid,))


def _app_conversaciones(sid: str, q: str = ""):
    """Conversaciones del estudiante (una por session_id), la más reciente primero. Con `q` solo devuelve
    las que contienen esas palabras en alguna pregunta o respuesta (sin importar tildes ni mayúsculas)."""
    filtro, params = "", [sid]
    palabras = [w for w in re.findall(r"\w+", q or "") if len(w) > 1][:6]
    for w in palabras:
        filtro += """ AND session_id IN (SELECT session_id FROM chat_log WHERE id_estudiante=%s
                      AND unaccent_lower(coalesce(pregunta,'') || ' ' || coalesce(respuesta,'')) LIKE unaccent_lower(%s))"""
        params += [sid, f"%{w}%"]
    return db.fetch_all(f"""
        SELECT session_id AS id, COUNT(*) AS mensajes,
               (array_agg(pregunta ORDER BY id))[1] AS primera,
               to_char((MAX(creado) AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota','YYYY-MM-DD HH24:MI') AS ultima
        FROM chat_log WHERE id_estudiante=%s AND respuesta IS NOT NULL {filtro}
        GROUP BY session_id ORDER BY MAX(creado) DESC LIMIT 50""", params)


def _app_conversacion(sid: str, conv: str):
    return db.fetch_all("""SELECT pregunta, respuesta, intencion,
                                  to_char((creado AT TIME ZONE 'UTC') AT TIME ZONE 'America/Bogota','YYYY-MM-DD HH24:MI') AS fecha
                           FROM chat_log WHERE id_estudiante=%s AND session_id=%s AND respuesta IS NOT NULL
                           ORDER BY id LIMIT 200""", (sid, conv))


def _app_alertas(sid: str):
    """Avisos para el estudiante: fechas del calendario y eventos propios cercanos, riesgos académicos y
    requisitos de grado pendientes. Ordenados de más a menos urgente."""
    av = []
    res = db.fetch_one("SELECT * FROM v_proyeccion_grado WHERE id_estudiante=%s", (sid,)) or {}
    estado, pga, sem = res.get("estado_academico"), res.get("pga"), res.get("semestre_actual") or 1
    if estado == "PRUEBA_ACADEMICA":
        av.append(("alta", "Estás en prueba académica", "Solicita el ingreso al Programa de Recuperación Académica (Art. 86) y matricula solo los cursos que te autoricen."))
    elif estado == "CONDICIONAL":
        av.append(("alta", "Estás en estado condicional", "Puedes matricular máximo 3 cursos y debes inscribirte en acompañamiento de Bienestar (Art. 84). Usa el simulador de la pestaña Personal para ver qué notas necesitas."))
    elif pga is not None and float(pga) <= 3.35:
        av.append(("media", f"Tu PGA ({pga}) está cerca del límite", "Por debajo de 3.20 pasarías a estado condicional (Art. 24). Revisa el simulador de notas en la pestaña Personal."))
    fallas = db.fetch_all("""SELECT a.nombre, h.fallas_pct FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
                             WHERE h.id_estudiante=%s AND h.estado='EN_CURSO' AND h.fallas_pct >= 10
                             ORDER BY h.fallas_pct DESC""", (sid,))
    for f in [f for f in fallas if float(f["fallas_pct"]) >= 15]:
        av.append(("alta", f"Fallas en {f['nombre']}: {f['fallas_pct']} %", "Con 20 % o más de inasistencia el curso se pierde (Art. 46)."))
    leves = [f for f in fallas if float(f["fallas_pct"]) < 15]
    if leves:
        av.append(("info", "Inasistencia por encima del 10 %", ", ".join(f"{f['nombre']} ({f['fallas_pct']} %)" for f in leves)
                   + ". Con 20 % o más el curso se pierde (Art. 46)."))
    for e in db.fetch_all("""SELECT actividad, to_char(fecha_inicio,'YYYY-MM-DD') AS inicio, (fecha_inicio - CURRENT_DATE) AS dias,
                                    to_char(fecha_fin,'YYYY-MM-DD') AS fin, (fecha_fin - CURRENT_DATE) AS dias_fin
                             FROM calendario_academico
                             WHERE fecha_inicio BETWEEN CURRENT_DATE AND CURRENT_DATE + 14
                                OR (fecha_inicio < CURRENT_DATE AND fecha_fin BETWEEN CURRENT_DATE AND CURRENT_DATE + 7)
                             ORDER BY fecha_inicio LIMIT 3"""):
        if e["dias"] >= 0:
            cuando = "hoy" if e["dias"] == 0 else f"en {e['dias']} día{'s' if e['dias'] != 1 else ''}"
            av.append(("media" if e["dias"] <= 3 else "info", e["actividad"], f"Empieza {cuando} ({e['inicio']})."))
        else:
            cuando = "hoy" if e["dias_fin"] == 0 else f"en {e['dias_fin']} día{'s' if e['dias_fin'] != 1 else ''}"
            av.append(("media", e["actividad"], f"Termina {cuando} ({e['fin']})."))
    if _existe("evento_personal"):
        for e in db.fetch_all("""SELECT nombre, to_char(fecha,'YYYY-MM-DD') AS fecha, (fecha - CURRENT_DATE) AS dias
                                 FROM evento_personal WHERE id_estudiante=%s AND fecha BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
                                 ORDER BY fecha""", (sid,)):
            cuando = "hoy" if e["dias"] == 0 else ("mañana" if e["dias"] == 1 else f"en {e['dias']} días")
            av.append(("personal", e["nombre"], f"Tu evento es {cuando} ({e['fecha']})."))
    if not res.get("ingles_cumplido") and sem >= 5:
        av.append(("info", f"Inglés: estás en {res.get('nivel_ingles')}", "Necesitas B2 para graduarte (Art. 67). Planea tus cursos o la certificación desde ya."))
    if res.get("ccd_rutas_pendientes") and sem >= 3:
        av.append(("info", f"Competencias digitales: {res['ccd_rutas_pendientes']} ruta(s) pendiente(s)",
                   "Se recomienda terminarlas en los primeros semestres; hay cursos vacacionales e intensivos."))
    orden = {"alta": 0, "personal": 1, "media": 2, "info": 3}
    return [{"nivel": n, "titulo": t, "detalle": d} for n, t, d in sorted(av, key=lambda a: orden[a[0]])]


def _app_personal(sid: str):
    prof = "h.profesor" if _existe("historial_academico", "profesor") else "NULL"
    cursos = db.fetch_all(f"""SELECT h.cod_periodo AS periodo, p.descripcion AS periodo_txt, a.cod_asignatura AS codigo,
                                     a.nombre AS asignatura, a.creditos, h.nota_final AS nota, h.estado, h.intento,
                                     {prof} AS profesor
                              FROM historial_academico h JOIN asignatura a USING (cod_asignatura)
                              LEFT JOIN periodo p USING (cod_periodo)
                              WHERE h.id_estudiante=%s ORDER BY h.cod_periodo, a.nombre""", (sid,))
    certificados = db.fetch_all("""SELECT 'Competencias digitales' AS tipo, c.nombre, 'CCD UNAB' AS entidad,
                                          ch.cod_periodo AS fecha, ch.via AS detalle, ch.nota
                                   FROM ccd_historial ch JOIN ccd_curso c USING (cod_ccd)
                                   WHERE ch.id_estudiante=%s AND ch.estado IN ('APROBADA','HOMOLOGADA')
                                   ORDER BY ch.cod_periodo""", (sid,))
    if _existe("certificado"):
        certificados += db.fetch_all("""SELECT tipo, nombre, entidad, to_char(fecha,'YYYY-MM-DD') AS fecha, detalle, NULL AS nota
                                        FROM certificado WHERE id_estudiante=%s ORDER BY fecha DESC""", (sid,))
    est = db.fetch_one("SELECT semestre_actual, nivel_ingles FROM estudiante WHERE id_estudiante=%s", (sid,)) or {}
    pend = db.fetch_all("""SELECT * FROM v_asignaturas_pendientes WHERE id_estudiante=%s
                           ORDER BY semestre_sugerido, asignatura""", (sid,))
    en_curso = [a for a in pend if a.get("en_curso")]
    pend = [a for a in pend if not a.get("en_curso")]
    por_sem: dict = {}
    for a in pend:
        sem = a.get("semestre_sugerido") or 0
        clave = sem if sem >= (est.get("semestre_actual") or 1) else 0  # 0 = atrasadas
        por_sem.setdefault(clave, []).append(a)
    proy = db.fetch_one("SELECT * FROM v_proyeccion_grado WHERE id_estudiante=%s", (sid,)) or {}
    res = db.fetch_one("SELECT * FROM v_resumen_estudiante WHERE id_estudiante=%s", (sid,)) or {}
    areas = db.fetch_all("""SELECT a.area, SUM(a.creditos) AS total,
                                   COALESCE(SUM(a.creditos) FILTER (WHERE m.estado IN ('APROBADA','HOMOLOGADA')), 0) AS aprobados
                            FROM asignatura a JOIN estudiante e ON e.cod_programa=a.cod_programa AND e.id_estudiante=%s
                            LEFT JOIN v_mejor_nota m ON m.id_estudiante=e.id_estudiante AND m.cod_asignatura=a.cod_asignatura
                            WHERE a.creditos > 0 GROUP BY a.area ORDER BY SUM(a.creditos) DESC""", (sid,))
    progreso = {"porcentaje_avance": res.get("porcentaje_avance"), "creditos_aprobados": res.get("creditos_aprobados"),
                "creditos_totales": res.get("creditos_totales"), "creditos_en_curso": res.get("creditos_en_curso"),
                "pga": res.get("pga"), "estado_academico": res.get("estado_academico"),
                "semestres_restantes": proy.get("semestres_restantes_estimados"), "areas": areas}
    try:
        propuesta = proyeccion_y_recomendaciones(sid)["propuesta_proximo_periodo"]
    except Exception:  # noqa: BLE001
        propuesta = None
    return {"progreso": progreso, "propuesta": propuesta,
            "simulador": [{"codigo": c["codigo"], "asignatura": c["asignatura"], "creditos": c["creditos"]}
                          for c in _base_simulacion(sid)["en_curso"]],
            "cursos": cursos, "certificados": certificados, "nivel_ingles": est.get("nivel_ingles"),
            "semestre_actual": est.get("semestre_actual"),
            "en_curso": en_curso,
            "pendientes_por_semestre": [{"semestre": k, "asignaturas": v} for k, v in sorted(por_sem.items())],
            "tiene_profesores": prof != "NULL"}


@mcp.custom_route("/app/datos", methods=["POST"])
async def app_datos(request: Request):
    """Datos de las pestañas de la app: noticias, eventos, historial (chat) y personal."""
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await request.json()
    seccion = b.get("seccion"); sid = (b.get("id_estudiante") or "").strip().upper()
    try:
        if seccion == "noticias":
            data = _app_noticias(str(b.get("tema") or ""))
        elif seccion == "eventos":
            data = _app_eventos(sid)
        elif seccion in ("historial", "personal", "conversaciones", "conversacion", "alertas"):
            if not ID_RX.match(sid):
                return JSONResponse({"error": "id inválido"}, status_code=400)
            if seccion == "historial":
                data = _app_historial_chat(sid)
            elif seccion == "conversaciones":
                data = _app_conversaciones(sid, str(b.get("q") or ""))
            elif seccion == "alertas":
                data = _app_alertas(sid)
            elif seccion == "conversacion":
                data = _app_conversacion(sid, str(b.get("conversacion") or ""))
            else:
                data = _app_personal(sid)
        else:
            return JSONResponse({"error": "sección desconocida"}, status_code=400)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse(json.loads(json.dumps({"ok": True, "datos": data}, default=str)))


@mcp.custom_route("/embed", methods=["POST"])
async def embed_route(request: Request):
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await request.json()
    texts = b.get("texts") or [b.get("text", "")]
    vecs = embed(texts)
    return JSONResponse({"dim": len(vecs[0]) if vecs else 0, "embeddings": vecs,
                         "pgvector": [to_pgvector(v) for v in vecs]})


@mcp.custom_route("/rag/search", methods=["POST"])
async def rag_route(request: Request):
    b = await request.json()
    return JSONResponse({"resultados": rag_search(b.get("query", ""), int(b.get("k", 5)), b.get("fuente"))})


# ----------------------------------------------------------------- evidencias públicas (sin costo de LLM)
_EVID_CACHE: dict = {}
CONSULTAS_RAG_DEMO = [
    "¿Qué pasa si quedo en prueba académica?",
    "¿Cuántas fallas puedo tener antes de perder una materia?",
    "requisitos para graduarse de ingeniería de sistemas",
    "¿Qué es la insignia de competencias digitales?",
    "que formas hay de quedar PFU",
]


@mcp.custom_route("/evidencias", methods=["GET"])
async def evidencias(_: Request):
    """Evidencia de funcionamiento para la documentación: tablas con datos, herramientas MCP, una llamada de
    ejemplo al estudiante de prueba (datos sintéticos) y recuperación RAG de consultas fijas. Sin LLM; caché 10 min."""
    import time
    if _EVID_CACHE.get("t", 0) > time.time() - 600:
        return JSONResponse(_EVID_CACHE["data"])
    nombres = [r["t"] for r in db.fetch_all("""SELECT table_name AS t FROM information_schema.tables
                                                WHERE table_schema='academico' AND table_type='BASE TABLE' ORDER BY 1""")]
    tablas = [{"tabla": n, "filas": db.fetch_one(f'SELECT COUNT(*) AS c FROM academico."{n}"')["c"]} for n in nombres]
    vistas_bd = [r["t"] for r in db.fetch_all("""SELECT table_name AS t FROM information_schema.views
                                                 WHERE table_schema='academico' ORDER BY 1""")]
    herramientas = []
    for t in await mcp.list_tools():
        herramientas.append({"nombre": t.name, "descripcion": (t.description or "").split("\n")[0]})
    rag = []
    for q in CONSULTAS_RAG_DEMO:
        res = rag_search(q, 3)
        rag.append({"consulta": q, "consulta_expandida": glosario.expandir(q), "resultados": [{"fuente": r.get("fuente"), "titulo": r.get("titulo"),
                                                   "similitud": r.get("similitud"),
                                                   "fragmento": (r.get("contenido") or "")[:220]} for r in res]})
    chunks = db.fetch_all("""SELECT fuente, COUNT(*) AS fragmentos, ROUND(AVG(length(contenido))) AS caracteres_promedio,
                                    MAX(length(contenido)) AS caracteres_max
                             FROM documento_chunk GROUP BY fuente ORDER BY 2 DESC""")
    satisfaccion = None
    if _existe("calificacion"):
        satisfaccion = {"por_ruta": db.fetch_all("SELECT * FROM v_satisfaccion"),
                        "total": db.fetch_one("""SELECT COUNT(*) AS calificaciones, COUNT(*) FILTER (WHERE valor=1) AS utiles,
                                                        ROUND(100.0*COUNT(*) FILTER (WHERE valor=1)/NULLIF(COUNT(*),0),1) AS porcentaje_util
                                                 FROM calificacion""")}
    data = json.loads(json.dumps({
        "generado": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "satisfaccion": satisfaccion,
        "tablas": tablas, "vistas": vistas_bd, "herramientas_mcp": herramientas,
        "ejemplo_herramienta": {"llamada": f"estado_academico('{DEMO_ID}')", "respuesta": estado_academico(DEMO_ID)},
        "rag": {"modelo": "paraphrase-multilingual-MiniLM-L12-v2 (384 dimensiones)", "chunk_max": 600, "overlap": 120,
                "puntaje": "fusión RRF: suma de 1/(60 + posición) en la lista vectorial y en la de texto completo",
                "fragmentos_por_fuente": chunks, "consultas": rag},
    }, default=str))
    _EVID_CACHE.update(t=time.time(), data=data)
    return JSONResponse(data)


@mcp.custom_route("/scrape", methods=["POST"])
async def scrape_route(request: Request):
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(scraper.ejecutar())


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "9000")), path="/mcp")
