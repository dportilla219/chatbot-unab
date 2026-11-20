"""Evaluación del RAG con un conjunto fijo de preguntas y su respuesta correcta conocida.

Para cada pregunta se sabe qué artículo del Reglamento (o qué sección de los documentos del CCD y del plan de
estudios) contiene la respuesta. Se compara la recuperación de tres configuraciones:

  vectorial          solo embeddings (pgvector, coseno)
  hibrida            embeddings + texto completo combinados con RRF (buscar_hibrido)
  hibrida+glosario   lo que usa el asistente: la jerga se traduce antes de buscar (rag_search)

Métricas (k = 5): acierto en la 1.a posición, en las 3 primeras y en las 5 primeras, y MRR (promedio de 1/posición
del primer fragmento correcto; 0 si no aparece). Solo lee la base de datos.

En la EC2, sin reconstruir el contenedor:
    sudo docker compose exec -T mcp python - < mcp_server/evaluar_rag.py
"""
import json
import re
import sys
import time

import db
import glosario
from embeddings import embed, to_pgvector

K = 5

# (pregunta, respuesta correcta). "art": artículos válidos del Reglamento. "sec": patrón de la sección esperada.
PREGUNTAS = [
    ("¿Cuántas fallas puedo tener antes de perder una materia?", {"art": {46}}),
    ("¿Qué pasa si quedo en prueba académica?", {"art": {11, 24, 85, 86}}),
    ("¿Cuándo queda un estudiante en estado académico condicional?", {"art": {10, 24}}),
    ("¿Cómo se calcula el promedio general acumulado?", {"art": {40}}),
    ("¿Qué requisitos necesito para obtener el título?", {"art": {67}}),
    ("¿Cuándo puedo presentar una habilitación?", {"art": {47, 48}}),
    ("¿Cómo pido la revisión de una calificación?", {"art": {52}}),
    ("Si repito un curso que perdí, ¿qué nota queda registrada?", {"art": {53}}),
    ("¿Qué necesito para recibir una distinción como Cum Laude?", {"art": {89}}),
    ("¿Qué es una homologación de cursos?", {"art": {17, 18, 19}}),
    ("Si no me matriculo a tiempo, ¿puedo reservar el cupo?", {"art": {8}}),
    ("¿Cómo cancelo materias del semestre?", {"art": {13}}),
    ("¿Por qué causas se pierde el derecho a renovar la matrícula?", {"art": {12}}),
    ("¿Qué se considera plagio?", {"art": {101}}),
    ("¿Qué es fraude académico?", {"art": {102}}),
    ("¿Qué es una prueba supletoria?", {"art": {45}}),
    ("¿Puedo validar un curso y con qué promedio?", {"art": {50}}),
    ("¿Para qué sirven las pruebas de suficiencia?", {"art": {42, 43}}),
    ("¿Cómo es la escala de calificación?", {"art": {37, 39}}),
    ("¿Qué es el Programa de Recuperación Académica?", {"art": {85, 86, 87}}),
    ("¿Puedo pasarme a la UNAB desde otra universidad?", {"art": {14, 15, 16}}),
    ("¿Cuáles son mis derechos como estudiante?", {"art": {74}}),
    # Jerga estudiantil
    ("cuanto me puedo volar de clase sin perder la materia", {"art": {46}}),
    ("que formas hay de quedar PFU", {"art": {12, 24}}),
    ("me rajé una materia, la puedo recuperar con un examen?", {"art": {47, 48}}),
    # Documentos del Centro de Competencias Digitales y plan de estudios
    ("¿Qué es la insignia digital y cuándo la recibo?", {"sec": r"insignia"}),
    ("¿Qué pasa si saco más del 70 % en la prueba diagnóstica?", {"sec": r"70 ?%"}),
    ("Ya vi informática en el plan antiguo, ¿se homologa?", {"sec": r"plan antiguo|homologar"}),
    ("¿Cuántos cursos de competencias digitales debo ver?", {"sec": r"[Cc]u[aá]ntos cursos"}),
    ("¿Qué materias se ven en quinto semestre?", {"sec": r"^Semestre 5"}),
]


def correcto(fila: dict, esperado: dict) -> bool:
    seccion = fila.get("seccion") or ""
    if "art" in esperado:
        m = re.search(r"Artículo (\d+)$", seccion)
        return fila.get("fuente") == "reglamento" and bool(m) and int(m.group(1)) in esperado["art"]
    return bool(re.search(esperado["sec"], seccion))


def buscar(modo: str, pregunta: str) -> list[dict]:
    texto = glosario.expandir(pregunta) if modo == "hibrida+glosario" else pregunta
    v = to_pgvector(embed([texto])[0])
    if modo == "vectorial":
        return db.fetch_all("SELECT * FROM buscar_chunks(%s::vector, %s, NULL)", (v, K))
    return db.fetch_all("SELECT * FROM buscar_hibrido(%s::vector, %s, %s, NULL)", (v, texto, K))


def main():
    modos = ["vectorial", "hibrida", "hibrida+glosario"]
    posiciones = {m: [] for m in modos}
    inicio = time.time()
    for pregunta, esperado in PREGUNTAS:
        for m in modos:
            filas = buscar(m, pregunta)
            pos = next((i + 1 for i, f in enumerate(filas) if correcto(f, esperado)), None)
            posiciones[m].append(pos)

    n = len(PREGUNTAS)
    print(f"Evaluación del RAG: {n} preguntas, k = {K}, {db.fetch_one('SELECT COUNT(*) AS c FROM documento_chunk')['c']} fragmentos\n")
    print("| Configuración | Acierto @1 | Acierto @3 | Acierto @5 | MRR |")
    print("|---|---|---|---|---|")
    resumen = {}
    for m in modos:
        p = posiciones[m]
        r = {"@1": sum(1 for x in p if x == 1), "@3": sum(1 for x in p if x and x <= 3),
             "@5": sum(1 for x in p if x), "mrr": round(sum(1 / x for x in p if x) / n, 3)}
        resumen[m] = r
        pct = lambda c: f"{c}/{n} ({100 * c / n:.0f} %)"
        print(f"| {m} | {pct(r['@1'])} | {pct(r['@3'])} | {pct(r['@5'])} | {r['mrr']:.3f} |")

    print("\nPosición del primer fragmento correcto (- = no aparece en los 5 primeros):\n")
    print("| # | Pregunta | Vectorial | Híbrida | Híbrida + glosario |")
    print("|---|---|---|---|---|")
    for i, (pregunta, _) in enumerate(PREGUNTAS):
        celdas = [str(posiciones[m][i] or "-") for m in modos]
        print(f"| {i + 1} | {pregunta} | " + " | ".join(celdas) + " |")
    print(f"\nTiempo total: {time.time() - inicio:.1f} s")
    print("JSON " + json.dumps({"n": n, "k": K, "resumen": resumen, "posiciones": posiciones}, ensure_ascii=False))


if __name__ == "__main__":
    main()
