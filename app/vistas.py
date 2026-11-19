"""HTML de las pestañas de la app (Noticias, Historial, Eventos y Personal)."""
from collections import OrderedDict
from html import escape

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False}).enable("table")

ETIQUETAS = {"CURSOS": "Cursos", "CONVOCATORIA": "Convocatoria", "CERTIFICACION": "Certificación",
             "CCD": "Competencias digitales", "GENERAL": "General"}
SEMESTRES = {0: "Pendientes de semestres anteriores", 1: "Semestre 1", 2: "Semestre 2", 3: "Semestre 3",
             4: "Semestre 4", 5: "Semestre 5", 6: "Semestre 6", 7: "Semestre 7", 8: "Semestre 8"}

CSS_VISTAS = """
.vista { display:flex; flex-direction:column; gap:10px; }
.vista h3 { margin:6px 2px 0; font-size:1rem; color:var(--tinta); }
.vacio { color:var(--gris); text-align:center; padding:28px 12px; font-size:.9rem; }
.item { background:#fff; border:1px solid var(--borde); border-radius:14px; padding:12px 14px; }
.item .titulo { font-weight:700; color:var(--tinta); font-size:.93rem; line-height:1.3; }
.item .meta { color:var(--gris); font-size:.76rem; margin-top:4px; display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
.item .texto { color:#374151; font-size:.85rem; margin-top:6px; line-height:1.45; }
.item a { color:var(--morado); font-weight:600; font-size:.82rem; text-decoration:none; }
.etq { display:inline-block; border-radius:999px; padding:1px 8px; font-size:.7rem; font-weight:700;
       background:var(--morado-claro); color:var(--morado); }
.etq.ok { background:#E8F7EE; color:#137A3E; } .etq.mal { background:#FDECEC; color:#B42318; }
.etq.curso { background:#EEF2FF; color:#3730A3; } .etq.nar { background:var(--naranja-claro); color:#B45309; }
.fecha-box { flex:0 0 54px; text-align:center; border-radius:12px; background:var(--naranja-claro); padding:6px 0; }
.fecha-box .d { font-size:1.2rem; font-weight:800; color:#B45309; line-height:1; }
.fecha-box .m { font-size:.68rem; font-weight:700; color:#B45309; text-transform:uppercase; }
.evento { display:flex; gap:12px; align-items:flex-start; }
.evento.propio { border-color:#D9C4F7; background:linear-gradient(0deg, #FBF8FF, #FBF8FF); border-left:4px solid var(--morado); }
.evento.propio .fecha-box { background:var(--morado-claro); }
.evento.propio .fecha-box .d, .evento.propio .fecha-box .m { color:var(--morado); }
.leyenda { display:flex; gap:14px; font-size:.75rem; color:var(--gris); padding:0 4px; }
.leyenda i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:5px; vertical-align:-1px; }
details.grupo { background:#fff; border:1px solid var(--borde); border-radius:14px; padding:0; overflow:hidden; }
details.grupo > summary { cursor:pointer; list-style:none; padding:12px 14px; font-weight:700; color:var(--tinta);
                          display:flex; justify-content:space-between; align-items:center; font-size:.92rem; }
details.grupo > summary::-webkit-details-marker { display:none; }
details.grupo > summary .cnt { color:var(--gris); font-weight:600; font-size:.78rem; }
details.grupo[open] > summary { border-bottom:1px solid var(--borde); }
.tabla, .prose .tabla { width:100% !important; border-collapse:collapse !important; font-size:.8rem; border:none !important; margin:0 !important; }
.tabla th, .tabla td { border:none !important; border-top:1px solid #F1F2F4 !important; }
.etq { white-space:nowrap; }
.tabla th { text-align:left; color:var(--gris); font-weight:600; padding:8px 10px; background:#FAFAFB; }
.tabla td { padding:8px 10px; border-top:1px solid #F1F2F4; color:#374151; vertical-align:top; }
.tabla td.n { font-weight:700; text-align:center; }
.resumen { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.resumen .c { background:#fff; border:1px solid var(--borde); border-radius:14px; padding:10px; text-align:center; }
.resumen .v { font-size:1.15rem; font-weight:800; color:var(--tinta); }
.resumen .l { font-size:.7rem; color:var(--gris); }
.conv .p { font-weight:700; color:var(--tinta); font-size:.88rem; }
.conv .r { color:#374151; font-size:.84rem; margin-top:6px; border-left:3px solid var(--naranja); padding-left:10px; }
.conv .r p { margin:4px 0; } .conv .r ul { margin:4px 0 4px 18px; }
"""

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _vacio(txt):
    return f"<div class='vista'><div class='vacio'>{escape(txt)}</div></div>"


def noticias(datos):
    if not datos:
        return _vacio("No hay noticias para este tema. El scraper las actualiza cada 6 horas.")
    out = ["<div class='vista'>"]
    for n in datos:
        etq = ETIQUETAS.get((n.get("etiqueta") or "").upper(), n.get("etiqueta") or "")
        resumen = escape((n.get("resumen") or "")[:220]) + ("…" if len(n.get("resumen") or "") > 220 else "")
        fuente = n.get("fuente") or "unab.edu.co"
        tema = n.get("tema")
        hoy = "<span class='etq ok'>Hoy</span>" if n.get("hoy") else ""
        chips = hoy + (f"<span class='etq nar'>{escape(tema)}</span>" if tema else "") + \
            (f"<span class='etq'>{escape(etq)}</span>" if etq and etq != "General" else "")
        out.append(f"<div class='item'><div class='titulo'>{escape(n['titulo'])}</div>"
                   f"<div class='meta'>{chips}<b>{escape(fuente)}</b> · {escape(n.get('fecha') or '')}</div>"
                   f"<div class='texto'>{resumen}</div>"
                   f"<div class='meta'><a href='{escape(n['url'])}' target='_blank' rel='noopener'>Leer en {escape(fuente)}</a></div></div>")
    return "".join(out) + "</div>"


def eventos(datos):
    if not datos:
        return _vacio("No hay eventos próximos. Puedes agregar los tuyos con el botón de arriba.")
    out = ["<div class='vista'><div class='leyenda'><span><i style='background:var(--naranja)'></i>Calendario UNAB</span>"
           "<span><i style='background:var(--morado)'></i>Mis eventos</span></div>"]
    for e in datos:
        a, m, d = (e["inicio"] or "----------").split("-")
        dias = e.get("dias")
        if dias is not None and int(dias) > 0:
            cuando = f"en {int(dias)} día{'s' if int(dias) != 1 else ''}"
        elif dias is not None and int(dias) == 0:
            cuando = "hoy"
        else:
            cuando = "en curso"
        rango = e["inicio"] + (f" al {e['fin']}" if e.get("fin") and e["fin"] != e["inicio"] else "")
        propio = e.get("origen") == "personal"
        if propio:
            detalle = (f"<div class='texto'>{escape(e['descripcion'])}</div>" if e.get("descripcion") else "")
            etq = "<span class='etq'>Personal</span>"
        else:
            detalle = f"<div class='meta'>{escape(e.get('categoria') or '')} · {escape(e.get('dirigido_a') or '')}</div>"
            etq = ""
        out.append(f"<div class='item evento{' propio' if propio else ''}'><div class='fecha-box'><div class='d'>{int(d)}</div>"
                   f"<div class='m'>{_MESES[int(m) - 1]}</div></div><div>"
                   f"<div class='titulo'>{escape(e['actividad'])}</div>"
                   f"<div class='meta'>{etq}<span class='etq nar'>{escape(cuando)}</span>{escape(rango)}</div>"
                   f"{detalle}</div></div>")
    return "".join(out) + "</div>"


def historial(datos):
    if not datos:
        return _vacio("Aún no tienes conversaciones guardadas. Escríbele al asistente desde la pestaña Chat.")
    dias = OrderedDict()
    for c in datos:
        dias.setdefault(c["fecha"][:10], []).append(c)
    out = ["<div class='vista'>"]
    for i, (dia, convs) in enumerate(dias.items()):
        out.append(f"<details class='grupo' {'open' if i == 0 else ''}><summary>{dia}"
                   f"<span class='cnt'>{len(convs)} pregunta{'s' if len(convs) != 1 else ''}</span></summary>")
        for c in convs:
            out.append(f"<div class='item conv' style='border:none;border-top:1px solid #F1F2F4;border-radius:0'>"
                       f"<div class='meta'>{c['fecha'][11:]}</div><div class='p'>{escape(c['pregunta'])}</div>"
                       f"<div class='r'>{_md.render(c.get('respuesta') or '')}</div></div>")
        out.append("</details>")
    return "".join(out) + "</div>"


def _badge_estado(estado):
    return {"APROBADA": "<span class='etq ok'>Aprobada</span>", "REPROBADA": "<span class='etq mal'>Reprobada</span>",
            "EN_CURSO": "<span class='etq curso'>En curso</span>"}.get(estado, escape(estado or ""))


def personal(datos):
    if not datos:
        return _vacio("No se pudieron cargar tus datos.")
    cursos = datos.get("cursos") or []
    aprob = [c for c in cursos if c["estado"] == "APROBADA"]
    reprob = [c for c in cursos if c["estado"] == "REPROBADA"]
    con_prof = datos.get("tiene_profesores")
    out = ["<div class='vista'><div class='resumen'>",
           f"<div class='c'><div class='v'>{datos.get('semestre_actual') or '-'}</div><div class='l'>Semestre actual</div></div>",
           f"<div class='c'><div class='v'>{len(aprob)}</div><div class='l'>Cursos aprobados</div></div>",
           f"<div class='c'><div class='v'>{escape(datos.get('nivel_ingles') or '-')}</div><div class='l'>Nivel de inglés</div></div>",
           "</div>"]

    # Cursos por periodo
    out.append(f"<h3>Cursos de la carrera</h3>")
    periodos = OrderedDict()
    for c in cursos:
        periodos.setdefault(c.get("periodo_txt") or c["periodo"], []).append(c)
    for i, (per, cs) in enumerate(reversed(list(periodos.items()))):
        filas = "".join(
            f"<tr><td>{escape(c['asignatura'])}<div class='meta'>{c['creditos']} créditos"
            f"{' · intento ' + str(c['intento']) if (c.get('intento') or 1) > 1 else ''}</div></td>"
            f"<td class='n'>{'' if c.get('nota') is None else c['nota']}</td><td>{_badge_estado(c['estado'])}</td>"
            + (f"<td>{escape(c.get('profesor') or '')}</td>" if con_prof else "") + "</tr>" for c in cs)
        cab = "<tr><th>Asignatura</th><th>Nota</th><th>Estado</th>" + ("<th>Profesor</th>" if con_prof else "") + "</tr>"
        out.append(f"<details class='grupo' {'open' if i == 0 else ''}><summary>Periodo {escape(per)}"
                   f"<span class='cnt'>{len(cs)} cursos</span></summary><table class='tabla'>{cab}{filas}</table></details>")
    if reprob:
        out.append(f"<div class='meta' style='padding:0 4px'>Has reprobado {len(reprob)} curso(s) en total; "
                   "las notas reprobadas siguen contando en tu PGA hasta que repitas el curso.</div>")

    # Certificados
    certs = datos.get("certificados") or []
    out.append("<h3>Certificados</h3>")
    if certs:
        for c in certs:
            nota = f" · nota {c['nota']}" if c.get("nota") is not None else ""
            out.append(f"<div class='item'><div class='titulo'>{escape(c['nombre'])}</div>"
                       f"<div class='meta'><span class='etq'>{escape(c['tipo'])}</span>{escape(c.get('entidad') or '')}"
                       f" · {escape(str(c.get('fecha') or ''))} · {escape((c.get('detalle') or '').replace('_', ' ').lower())}{nota}</div></div>")
    else:
        out.append("<div class='vacio'>Todavía no tienes certificados registrados.</div>")

    # Materias pendientes
    out.append("<h3>Materias que te faltan</h3>")
    en_curso = datos.get("en_curso") or []
    if en_curso:
        out.append(f"<details class='grupo'><summary>Cursando ahora<span class='cnt'>{len(en_curso)} cursos</span></summary>"
                   "<table class='tabla'><tr><th>Asignatura</th><th>Créditos</th></tr>"
                   + "".join(f"<tr><td>{escape(a['asignatura'])}</td><td class='n'>{a['creditos']}</td></tr>" for a in en_curso)
                   + "</table></details>")
    for g in datos.get("pendientes_por_semestre") or []:
        filas = "".join(
            f"<tr><td>{escape(a['asignatura'])}<div class='meta'>{escape((a.get('tipo') or '').capitalize())}"
            f"{' · ya la reprobaste antes' if a.get('reprobada_antes') else ''}</div></td>"
            f"<td class='n'>{a['creditos']}</td><td>"
            + ("<span class='etq ok'>Disponible</span>" if not a.get("prerrequisitos_faltantes")
               else f"<span class='etq mal'>Requiere</span><div class='meta'>{escape(a['prerrequisitos_faltantes'])}</div>")
            + "</td></tr>" for a in g["asignaturas"])
        total = sum(a["creditos"] for a in g["asignaturas"])
        out.append(f"<details class='grupo'><summary>{SEMESTRES.get(g['semestre'], 'Semestre ' + str(g['semestre']))}"
                   f"<span class='cnt'>{len(g['asignaturas'])} materias · {total} créditos</span></summary>"
                   f"<table class='tabla'><tr><th>Asignatura</th><th>Créd.</th><th>Prerrequisitos</th></tr>{filas}</table></details>")
    return "".join(out) + "</div>"
