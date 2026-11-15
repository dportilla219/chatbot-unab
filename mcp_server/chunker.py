"""Fragmentación (chunking) de documentos institucionales para RAG.

- Reglamento: un fragmento por ARTÍCULO, con el título/capítulo como contexto.
- Markdown: por encabezados '##'.
- Artículos/noticias: por separador '====='.
Los fragmentos largos se dividen en ventanas de ~1200 caracteres con 150 de solapamiento.
"""
import re

MAX = 600       # el modelo MiniLM lee ~128 tokens: fragmentos cortos
OVERLAP = 120


def _window(text: str):
    text = text.strip()
    if len(text) <= MAX:
        return [text]
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + MAX)
        if j < len(text):
            k = text.rfind(". ", i + MAX // 2, j)
            j = k + 1 if k > 0 else j
        out.append(text[i:j].strip())
        if j >= len(text):
            break
        i = max(j - OVERLAP, i + 1)
    return out


def chunk_reglamento(text: str):
    chunks, titulo, capitulo = [], "", ""
    parts = re.split(r"(?=ARTÍCULO\s+\d+\.?)", text)
    for p in parts:
        for m in re.finditer(r"(TÍTULO\s+[A-ZÁÉÍÓÚ]+[^\n]*)", p):
            titulo = m.group(1).strip()
        for m in re.finditer(r"(CAPÍTULO\s+[A-ZÁÉÍÓÚ]+[^\n]*)", p):
            capitulo = m.group(1).strip()
        m = re.match(r"ARTÍCULO\s+(\d+)", p)
        if not m:
            continue
        body = re.sub(r"\s+", " ", p).strip()
        seccion = f"{titulo} > {capitulo} > Artículo {m.group(1)}".strip(" >")
        for w in _window(body):
            chunks.append({"seccion": seccion, "contenido": f"[Reglamento UNAB, Art. {m.group(1)}] {w}"})
    return chunks


def chunk_markdown(text: str, titulo_doc: str):
    chunks = []
    for sec in re.split(r"(?m)^(?=## )", text):
        head = sec.strip().splitlines()[0].lstrip("# ").strip() if sec.strip() else ""
        for w in _window(sec):
            chunks.append({"seccion": head, "contenido": f"[Plan de estudios - {head}] {w}"})
    return chunks


def chunk_articulos(text: str):
    chunks = []
    for art in text.split("====="):
        art = art.strip()
        if not art:
            continue
        m = re.search(r"TITULO:\s*(.+)", art)
        head = m.group(1).strip() if m else "Noticia UNAB"
        art = re.sub(r"IMAGENES:.*\n", "", art)
        for w in _window(art):
            chunks.append({"seccion": head, "contenido": w})
    return chunks


def chunk_documento(nombre: str, text: str):
    n = nombre.lower()
    if "reglamento" in n:
        return "reglamento", "Reglamento Estudiantil de Pregrado UNAB 2019", chunk_reglamento(text)
    if "frecuentes" in n:
        return "ccd", "Preguntas frecuentes CCD UNAB", chunk_markdown(text, "Preguntas frecuentes CCD")
    if n.endswith(".md"):
        return "plan_estudios", "Plan de estudios Ingeniería de Sistemas UNAB", chunk_markdown(text, "Plan de estudios Ingeniería de Sistemas UNAB")
    return "ccd", "Centro de Competencias Digitales y noticias UNAB", chunk_articulos(text)
