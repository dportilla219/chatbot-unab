"""Glosario de jerga estudiantil (misma lista que el nodo "Normalizar entrada" de n8n).

Expande expresiones como "PFU", "rajarse una materia" o "fallas" a los términos del Reglamento antes de
buscar en el RAG, para que la búsqueda por texto y por vector encuentre los artículos correctos.
"""
import re

GLOSARIO = [
    (re.compile('\\bpfu\\b|por\\s*fuera\\s*(de\\s*la\\s*(u|universidad))?|quedar\\s*(por\\s*)?fuera|me\\s*sacan\\s*de\\s*la\\s*u|perder\\s*el\\s*cupo', re.I), 'PFU = quedar por fuera de la universidad: estado Fuera del Programa, pérdida del derecho de renovar matrícula por bajo rendimiento académico (prueba académica, PGA inferior a 3.00, Programa de Recuperación Académica)'),
    (re.compile('\\b(raj|tir[eéa]|jal[eéa]|vol[eéa]|perd[ií]|perder|pierdo|quem[eéa])\\w*\\s*(una\\s*|la\\s*|el\\s*|\\d+\\s*)?(materia|materias|curso|cursos|clase|ramo)', re.I), 'reprobar un curso o asignatura (nota inferior a 3.0), repetir curso, nota más alta'),
    (re.compile('\\b(me\\s+)?(raj|jal|quem|tir|vol)(o|e|é|ar|aron|ando|ada|ado)\\b(?!.*materia)', re.I), 'reprobar un curso o asignatura (nota inferior a 3.0), repetir curso, nota más alta'),
    (re.compile('habilit', re.I), 'prueba de habilitación'),
    (re.compile('cancel\\w*\\s*(una\\s*|la\\s*|las\\s*)?(materia|materias|curso|cursos|semestre)', re.I), 'cancelación ordinaria o extraordinaria de cursos'),
    (re.compile('\\b(el\\s*)?promedio\\b|\\bpga\\b|\\bppa\\b', re.I), 'Promedio General Acumulado (PGA) y Promedio del Periodo Académico (PPA)'),
    (re.compile('condicional', re.I), 'estado académico condicional (PGA entre 3.00 y 3.20)'),
    (re.compile('\\ben\\s*prueba\\b|prueba\\s*acad', re.I), 'prueba académica, Programa de Recuperación Académica'),
    (re.compile('pasant[ií]a|\\bpr[aá]ctica(s)?\\b', re.I), 'práctica profesional o práctica académica'),
    (re.compile('fallas|faltas|inasistencia|no\\s*ir\\s*a\\s*clase', re.I), 'fallas por inasistencia (20 %)'),
    (re.compile('cart[oó]n|diploma|graduar\\w*|graduaci[oó]n|\\bgrado\\b', re.I), 'requisitos de grado (Art. 67)'),
    (re.compile('\\binfo\\b|inform[aá]tica|compu|ofim[aá]tica|excel|word', re.I), 'competencias digitales (antes cursos de informática), rutas del CCD'),
    (re.compile('homolog|convalid|reconoc\\w*\\s*(materia|curso)', re.I), 'homologación o reconocimiento de cursos'),
    (re.compile('doble\\s*(titulaci[oó]n|programa|carrera)|segunda\\s*carrera', re.I), 'segundo programa académico (30 % de créditos y PGA 3.50)'),
    (re.compile('\\bpagar\\s*(la\\s*)?(u|matr[ií]cula|semestre)|cup[oó]n|recargo', re.I), 'pago de matrícula y fechas de pago'),
    (re.compile('\\b(parcial|parciales|cortes?|finales?)\\b', re.I), 'evaluación del aprendizaje: cortes del 30 %, 30 % y 40 %'),
    (re.compile('reserva\\s*(de\\s*)?cupo|congelar|aplazar\\s*(el\\s*)?semestre|retirarme', re.I), 'reserva de cupo, retiro, reintegro'),
]


def expandir(texto: str) -> str:
    """Agrega entre paréntesis los términos del Reglamento que corresponden a la jerga detectada."""
    if not texto or "(" in texto and any(t in texto for _, t in GLOSARIO):
        return texto  # ya viene expandido desde n8n
    extra = [t for rx, t in GLOSARIO if rx.search(texto)]
    return f"{texto} ({'; '.join(extra)})" if extra else texto
