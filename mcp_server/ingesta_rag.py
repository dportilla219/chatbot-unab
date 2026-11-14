"""Ingesta RAG por línea de comandos (alternativa al workflow n8n 'RAG - Ingesta').

    python ingesta_rag.py ../rag_docs
Lee cada documento, lo fragmenta, genera embeddings locales y los guarda en academico.documento_chunk.
"""
import json
import pathlib
import sys

import db
from chunker import chunk_documento
from embeddings import embed, to_pgvector


def ingestar(carpeta: str):
    total = 0
    for f in sorted(pathlib.Path(carpeta).glob("*")):
        if f.suffix.lower() not in (".txt", ".md"):
            continue
        fuente, titulo, chunks = chunk_documento(f.name, f.read_text(encoding="utf-8"))
        db.execute("DELETE FROM documento_chunk WHERE fuente=%s AND titulo=%s", (fuente, titulo))
        vecs = embed([c["contenido"] for c in chunks])
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            db.execute("""INSERT INTO documento_chunk (fuente,titulo,seccion,chunk_index,contenido,metadata,embedding)
                          VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::vector)""",
                       (fuente, titulo, c["seccion"], i, c["contenido"], json.dumps({"archivo": f.name}), to_pgvector(v)))
        print(f"{f.name}: {len(chunks)} fragmentos ({fuente})")
        total += len(chunks)
    print("Total:", total)


if __name__ == "__main__":
    ingestar(sys.argv[1] if len(sys.argv) > 1 else "../rag_docs")
