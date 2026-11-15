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
import os
import re
import unicodedata

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

import db
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
    cand = pend["habilitadas"]
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
            "limite_aplicado": f"{max_cursos} cursos / {max_cred if max_cred < 99 else 'sin tope'} créditos por estado {estado}"},
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
    """Noticias UNAB obtenidas por el scraper: nuevos cursos, convocatorias, certificaciones, CCD.
    tema opcional: 'CURSOS' | 'CONVOCATORIA' | 'CERTIFICACION' | 'CCD' o una palabra clave."""
    sql = "SELECT titulo, fecha_pub, etiqueta, resumen, url FROM noticia"
    params: list = []
    if tema:
        if tema.upper() in ("CURSOS", "CONVOCATORIA", "CERTIFICACION", "CCD", "GENERAL"):
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
    v = to_pgvector(embed([pregunta])[0])
    rows = db.fetch_all("SELECT * FROM buscar_hibrido(%s::vector, %s, %s, %s)", (v, pregunta, min(k, 10), fuente))
    return [{**r, "similitud": round(r["similitud"], 3)} for r in rows]


def _authorized(request: Request) -> bool:
    return not API_TOKEN or request.headers.get("x-api-key") == API_TOKEN


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request):
    n = db.fetch_one("SELECT (SELECT COUNT(*) FROM estudiante) AS estudiantes, (SELECT COUNT(*) FROM documento_chunk) AS chunks, (SELECT COUNT(*) FROM noticia) AS noticias")
    return JSONResponse({"status": "ok", **n})


@mcp.custom_route("/auth", methods=["POST"])
async def auth_route(request: Request):
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    b = await request.json()
    return JSONResponse(autenticar(b.get("nombre_completo", ""), b.get("id_estudiante", ""), b.get("programa", "Ingeniería de Sistemas")))


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


@mcp.custom_route("/scrape", methods=["POST"])
async def scrape_route(request: Request):
    if not _authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(scraper.ejecutar())


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "9000")), path="/mcp")
