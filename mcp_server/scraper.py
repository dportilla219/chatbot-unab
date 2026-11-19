"""Scraper de noticias: UNAB + noticias del día de educación, tecnología e ingeniería de sistemas.

Fuente principal: API REST pública de WordPress de unab.edu.co (categoría 232 'Estudiantes'
y 556 'Ingeniería de Sistemas'). Si la API falla, hace scraping HTML de /category/estudiantes/.
Clasifica cada noticia (CURSOS | CONVOCATORIA | CERTIFICACION | CCD | GENERAL), la guarda en
academico.noticia y la vectoriza en academico.documento_chunk (fuente='noticia').
"""
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

import db
from chunker import _window
from embeddings import embed, to_pgvector

BASE = "https://unab.edu.co"
CATEGORIAS = {232: "Estudiantes", 556: "Ingeniería de Sistemas", 134: "Facultad de Ingeniería"}
HEADERS = {"User-Agent": "ChatbotAcademicoUNAB/1.0 (proyecto academico)"}

REGLAS = [
    ("CCD", r"competencias digitales|\bccd\b|insignia|interacci[oó]n digital"),
    ("CERTIFICACION", r"certificaci[oó]n|certificado|examen|celpe|toefl|ielts|prueba de"),
    ("CONVOCATORIA", r"convocatoria|inscripci|elecciones|beca|postula|abiertas"),
    ("CURSOS", r"curso|diplomado|taller|vacacional|intensivo|capacitaci"),
]


TEMAS = [
    ("Ingeniería de Sistemas", r"ingenier[ií]a de sistemas|software|programaci|desarrollador|inteligencia artificial|\bia\b|"
                               r"ciberseguridad|\bdatos\b|algoritm|computaci|\bnube\b|cloud"),
    ("Tecnología", r"tecnolog|digital|internet|\bapp\b|innovaci|\b5g\b|startup|robot"),
    ("Educación", r"educaci|universidad|estudiant|beca|icetex|acad[eé]mic|docente|pregrado|posgrado"),
]


def _gn(q: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(q + ' when:2d')}&hl=es-419&gl=CO&ceid=CO:es-419"


# Noticias del día por tema (Google News, últimos 2 días) + un medio de tecnología colombiano
FEEDS = [
    (_gn("educación superior Colombia universidades"), "Educación"),
    (_gn("tecnología Colombia"), "Tecnología"),
    (_gn('"ingeniería de sistemas" OR "desarrollo de software" OR "inteligencia artificial" Colombia'), "Ingeniería de Sistemas"),
    ("https://www.enter.co/feed/", "Tecnología"),
]


def tema_de(texto: str, por_defecto: str = "Institucional") -> str:
    for tema, rx in TEMAS:
        if re.search(rx, texto, re.I):
            return tema
    return por_defecto


def _id_externo(url: str) -> int:
    """Id negativo y estable para noticias que no vienen de WordPress UNAB (no choca con sus ids)."""
    return -int(hashlib.sha1(url.encode()).hexdigest()[:13], 16)


def via_rss(por_feed: int = 8, dias: int = 3) -> list[dict]:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    out, vistos = [], set()
    for url, tema_feed in FEEDS:
        try:
            raiz = ET.fromstring(requests.get(url, headers=HEADERS, timeout=20).content)
        except Exception:  # noqa: BLE001  (si una fuente falla, se sigue con las demás)
            continue
        for item in raiz.iter("item"):
            if len([o for o in out if o["_feed"] == url]) >= por_feed:
                break
            titulo = limpiar(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            try:
                fecha = parsedate_to_datetime(item.findtext("pubDate") or "")
            except Exception:  # noqa: BLE001
                continue
            if not titulo or not link or link in vistos or fecha < desde:
                continue
            vistos.add(link)
            fuente = (item.findtext("source") or urlparse(link).hostname or "RSS").replace("www.", "")
            if titulo.endswith(f" - {fuente}"):
                titulo = titulo[: -len(fuente) - 3]
            resumen = limpiar(item.findtext("description") or "").replace(titulo, "").replace(fuente, "").strip()[:400]
            resumen = resumen if len(resumen) >= 25 else titulo
            tema = tema_de(f"{titulo} {resumen}", tema_feed)
            out.append({"_feed": url, "id_wp": _id_externo(link), "url": link, "fecha_pub": fecha.isoformat(),
                        "titulo": titulo, "resumen": resumen, "contenido": resumen, "categorias": "RSS",
                        "fuente": fuente[:80], "tema": tema})
    return out


def limpiar(h: str) -> str:
    soup = BeautifulSoup(h or "", "html.parser")
    for br in soup.find_all(["br", "p", "li", "h2", "h3", "tr"]):
        br.append("\n")
    t = html.unescape(soup.get_text(" "))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()


def etiquetar(titulo: str, texto: str) -> str:
    base = f"{titulo} {texto[:600]}".lower()
    for et, rx in REGLAS:
        if re.search(rx, base):
            return et
    return "GENERAL"


def via_api(por_categoria: int = 10) -> list[dict]:
    items = {}
    for cat, nombre in CATEGORIAS.items():
        r = requests.get(f"{BASE}/wp-json/wp/v2/posts", headers=HEADERS, timeout=20,
                         params={"categories": cat, "per_page": por_categoria, "orderby": "date",
                                 "_fields": "id,date,link,title,excerpt,content,categories"})
        r.raise_for_status()
        for p in r.json():
            items[p["id"]] = {
                "id_wp": p["id"], "url": p["link"], "fecha_pub": p["date"],
                "titulo": limpiar(p["title"]["rendered"]),
                "resumen": limpiar(p["excerpt"]["rendered"])[:500],
                "contenido": limpiar(p["content"]["rendered"]),
                "categorias": ",".join(CATEGORIAS.get(c, str(c)) for c in p["categories"]),
            }
    return list(items.values())


def via_html(paginas: int = 2) -> list[dict]:
    out = []
    for n in range(1, paginas + 1):
        url = f"{BASE}/category/estudiantes/" + (f"page/{n}/" if n > 1 else "")
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=20).text, "html.parser")
        for a in soup.select("h2 a, h3 a, .entry-title a"):
            href = a.get("href", "")
            if not href.startswith(BASE):
                continue
            art = BeautifulSoup(requests.get(href, headers=HEADERS, timeout=20).text, "html.parser")
            body = art.select_one(".entry-content, article, main")
            texto = limpiar(str(body)) if body else ""
            out.append({"id_wp": abs(hash(href)) % 10**12, "url": href, "fecha_pub": None,
                        "titulo": a.get_text(strip=True), "resumen": texto[:500], "contenido": texto,
                        "categorias": "Estudiantes"})
    return out


def _tiene_fuente() -> bool:
    return bool(db.fetch_one("""SELECT 1 AS x FROM information_schema.columns WHERE table_schema='academico'
                                AND table_name='noticia' AND column_name='fuente'"""))


def ejecutar(por_categoria: int = 10) -> dict:
    try:
        items, metodo = via_api(por_categoria), "wp-json"
    except Exception as e:  # noqa: BLE001
        items, metodo = via_html(), f"html (api falló: {e.__class__.__name__})"
    for it in items:
        it["fuente"] = "unab.edu.co"
        it["tema"] = tema_de(f"{it['titulo']} {it['contenido'][:600]}", "Institucional")
    con_fuente = _tiene_fuente()
    if con_fuente:  # las fuentes externas necesitan la migración 08 (columnas fuente y tema)
        externas = via_rss()
        items += externas
        metodo += f" + rss ({len(externas)} noticias del día)"
    nuevos = []
    for it in items:
        it["etiqueta"] = etiquetar(it["titulo"], it["contenido"])
        existe = db.fetch_one("SELECT 1 AS x FROM noticia WHERE id_wp=%s OR url=%s", (it["id_wp"], it["url"]))
        if con_fuente:
            db.execute("""
                INSERT INTO noticia (id_wp,titulo,url,fecha_pub,resumen,contenido,categorias,etiqueta,fuente,tema,scraped_at)
                VALUES (%(id_wp)s,%(titulo)s,%(url)s,%(fecha_pub)s,%(resumen)s,%(contenido)s,%(categorias)s,%(etiqueta)s,
                        %(fuente)s,%(tema)s,now())
                ON CONFLICT (id_wp) DO UPDATE SET titulo=EXCLUDED.titulo, resumen=EXCLUDED.resumen, contenido=EXCLUDED.contenido,
                    etiqueta=EXCLUDED.etiqueta, fuente=EXCLUDED.fuente, tema=EXCLUDED.tema, scraped_at=now()""", it)
        else:
            db.execute("""
                INSERT INTO noticia (id_wp,titulo,url,fecha_pub,resumen,contenido,categorias,etiqueta,scraped_at)
                VALUES (%(id_wp)s,%(titulo)s,%(url)s,%(fecha_pub)s,%(resumen)s,%(contenido)s,%(categorias)s,%(etiqueta)s,now())
                ON CONFLICT (id_wp) DO UPDATE SET titulo=EXCLUDED.titulo, resumen=EXCLUDED.resumen,
                    contenido=EXCLUDED.contenido, etiqueta=EXCLUDED.etiqueta, scraped_at=now()""", it)
        if not existe:
            nuevos.append(it)
            textos = [f"[Noticia {it['fuente']} {str(it['fecha_pub'])[:10]} - {it['titulo']}] {w}"
                      for w in _window(it["contenido"] or it["resumen"])]
            for i, (t, v) in enumerate(zip(textos, embed(textos))):
                db.execute("""INSERT INTO documento_chunk (fuente,titulo,seccion,chunk_index,contenido,metadata,embedding)
                              VALUES ('noticia',%s,%s,%s,%s,%s::jsonb,%s::vector)
                              ON CONFLICT (fuente,titulo,chunk_index) DO NOTHING""",
                           (it["titulo"], it["etiqueta"], i, t,
                            json.dumps({"url": it["url"], "fecha": str(it["fecha_pub"]), "fuente": it["fuente"]}), to_pgvector(v)))
    return {"metodo": metodo, "procesadas": len(items), "nuevas": len(nuevos),
            "titulos_nuevos": [n["titulo"] for n in nuevos], "ejecutado": datetime.now().isoformat(timespec="seconds")}


if __name__ == "__main__":
    print(ejecutar())
