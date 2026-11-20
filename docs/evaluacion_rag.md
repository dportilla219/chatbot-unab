# Evaluación del RAG

Medición hecha en la EC2 el 20 de noviembre de 2026 con `mcp_server/evaluar_rag.py`, sobre los 386 fragmentos indexados en Supabase (Reglamento Estudiantil 2019, plan de estudios, documentos del CCD y noticias). El script solo lee la base de datos:

```bash
sudo docker compose exec -T mcp python - < mcp_server/evaluar_rag.py
```

**Método.** 30 preguntas con la respuesta correcta conocida de antemano: 22 sobre el Reglamento, 3 escritas con jerga estudiantil y 5 sobre el CCD y el plan de estudios. Una respuesta cuenta como recuperada si alguno de los 5 primeros fragmentos pertenece al artículo (o a la sección) que contiene la respuesta. Se comparan tres configuraciones:

- **Vectorial:** solo embeddings (pgvector, distancia coseno).
- **Híbrida:** embeddings y búsqueda de texto completo combinados con Reciprocal Rank Fusion (k = 60).
- **Híbrida + glosario:** la que usa el asistente; antes de buscar, la jerga se traduce a términos del Reglamento.

**Métricas.** Acierto @k: preguntas cuyo fragmento correcto aparece entre los k primeros. MRR (*Mean Reciprocal Rank*): promedio de 1 / posición del primer fragmento correcto (1 si sale primero, 0,5 si sale segundo, 0 si no aparece).

## Resultados

| Configuración | Acierto @1 | Acierto @3 | Acierto @5 | MRR |
|---|---|---|---|---|
| Vectorial | 15/30 (50 %) | 18/30 (60 %) | 21/30 (70 %) | 0,572 |
| Híbrida (RRF) | 17/30 (57 %) | 21/30 (70 %) | 23/30 (77 %) | 0,648 |
| **Híbrida + glosario (la del asistente)** | **20/30 (67 %)** | **24/30 (80 %)** | **26/30 (87 %)** | **0,744** |

Cada capa mejora la anterior: la búsqueda híbrida sube el MRR de 0,572 a 0,648 porque encuentra términos exactos ("habilitación", "Cum Laude") que los embeddings confunden, y el glosario lo sube a 0,744 porque traduce la forma en que escriben los estudiantes ("PFU", "me rajé una materia", "fallas") a la del Reglamento.

## Posición del primer fragmento correcto por pregunta

`-` = no aparece entre los 5 primeros.

| # | Pregunta | Respuesta esperada | Vectorial | Híbrida | Híbrida + glosario |
|---|---|---|---|---|---|
| 1 | ¿Cuántas fallas puedo tener antes de perder una materia? | Art. 46 | 1 | - | 1 |
| 2 | ¿Qué pasa si quedo en prueba académica? | Art. 11, 24, 85, 86 | 5 | 1 | 1 |
| 3 | ¿Cuándo queda un estudiante en estado académico condicional? | Art. 10, 24 | 2 | 2 | 1 |
| 4 | ¿Cómo se calcula el promedio general acumulado? | Art. 40 | 4 | 1 | 1 |
| 5 | ¿Qué requisitos necesito para obtener el título? | Art. 67 | 1 | 1 | 1 |
| 6 | ¿Cuándo puedo presentar una habilitación? | Art. 47, 48 | - | 1 | 3 |
| 7 | ¿Cómo pido la revisión de una calificación? | Art. 52 | 1 | 1 | 1 |
| 8 | Si repito un curso que perdí, ¿qué nota queda registrada? | Art. 53 | 1 | 2 | 2 |
| 9 | ¿Qué necesito para recibir una distinción como Cum Laude? | Art. 89 | - | 1 | 1 |
| 10 | ¿Qué es una homologación de cursos? | Art. 17, 18, 19 | 1 | 5 | 1 |
| 11 | Si no me matriculo a tiempo, ¿puedo reservar el cupo? | Art. 8 | 1 | 1 | 1 |
| 12 | ¿Cómo cancelo materias del semestre? | Art. 13 | 1 | 1 | 1 |
| 13 | ¿Por qué causas se pierde el derecho a renovar la matrícula? | Art. 12 | 1 | 1 | 1 |
| 14 | ¿Qué se considera plagio? | Art. 101 | 1 | 1 | 1 |
| 15 | ¿Qué es fraude académico? | Art. 102 | 1 | 1 | 1 |
| 16 | ¿Qué es una prueba supletoria? | Art. 45 | - | 4 | 4 |
| 17 | ¿Puedo validar un curso y con qué promedio? | Art. 50 | - | - | - |
| 18 | ¿Para qué sirven las pruebas de suficiencia? | Art. 42, 43 | 2 | 1 | 1 |
| 19 | ¿Cómo es la escala de calificación? | Art. 37, 39 | 5 | 2 | 2 |
| 20 | ¿Qué es el Programa de Recuperación Académica? | Art. 85, 86, 87 | 1 | 1 | 1 |
| 21 | ¿Puedo pasarme a la UNAB desde otra universidad? | Art. 14, 15, 16 | - | - | - |
| 22 | ¿Cuáles son mis derechos como estudiante? | Art. 74 | 1 | 2 | 2 |
| 23 | cuanto me puedo volar de clase sin perder la materia | Art. 46 | - | - | - |
| 24 | que formas hay de quedar PFU | Art. 12, 24 | - | - | 1 |
| 25 | me rajé una materia, la puedo recuperar con un examen? | Art. 47, 48 | - | - | 4 |
| 26 | ¿Qué es la insignia digital y cuándo la recibo? | CCD: insignia digital | 1 | 1 | 1 |
| 27 | ¿Qué pasa si saco más del 70 % en la prueba diagnóstica? | CCD: prueba diagnóstica (70 %) | 1 | 1 | 1 |
| 28 | Ya vi informática en el plan antiguo, ¿se homologa? | CCD: homologación del plan antiguo | 1 | 1 | 1 |
| 29 | ¿Cuántos cursos de competencias digitales debo ver? | CCD: cuántos cursos debo ver | 2 | 1 | 1 |
| 30 | ¿Qué materias se ven en quinto semestre? | Plan de estudios: semestre 5 | - | - | - |

## Fallos y qué los explica

| # | Pregunta | Por qué falla | Cómo se mitiga hoy / mejora posible |
|---|---|---|---|
| 17 | ¿Puedo validar un curso y con qué promedio? | "Validar" aparece en muchos artículos (pruebas de suficiencia, homologaciones) y el Art. 50 queda por debajo de ellos | El agente puede volver a buscar con `buscar_reglamento_y_documentos`. Mejora: agregar "validar un curso" → "validaciones" al glosario |
| 21 | ¿Puedo pasarme a la UNAB desde otra universidad? | El Reglamento habla de "transferencia externa", palabras que la pregunta no usa | Mejora: agregar "pasarme de universidad" → "transferencia externa" al glosario |
| 23 | cuanto me puedo volar de clase sin perder la materia | El glosario reconoce "perder la materia" como reprobar y lleva la búsqueda hacia la repetición de cursos; "volarse de clase" no está registrado como inasistencia (con "fallas", la pregunta 1 sale primera) | Mejora: agregar "volarse de clase" → "fallas por inasistencia" al glosario |
| 30 | ¿Qué materias se ven en quinto semestre? | El plan nombra "Semestre 5", no "quinto semestre" | El agente responde estas preguntas con la herramienta MCP `plan_de_estudios`, que consulta la base de datos y no depende del RAG |

Los tres primeros fallos se corrigen ampliando el glosario. No se cambió antes de la sustentación para no modificar el sistema desplegado, y quedan registrados como siguiente paso.
