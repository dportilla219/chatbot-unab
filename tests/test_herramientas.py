"""Pruebas del servidor MCP.

Las de reglas (estado académico y simulador) no necesitan base de datos. La prueba de humo recorre todas las
herramientas con estudiantes reales de la base sintética y se salta si no hay base disponible.

    cd mcp_server && DATABASE_URL=postgresql://... python -m pytest ../tests/test_herramientas.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_server"))
import server  # noqa: E402


@pytest.mark.parametrize("pga,actual,esperado", [
    (3.50, "NORMAL", "NORMAL"),
    (3.20, "NORMAL", "CONDICIONAL"),          # 3.20 no es "superior a 3.20" (Art. 24 a)
    (3.10, "CONDICIONAL", "PRUEBA_ACADEMICA"),  # segundo periodo consecutivo en 3.00-3.20 (Art. 24 c)
    (2.99, "NORMAL", "PRUEBA_ACADEMICA"),     # PGA inferior a 3.00
    (3.21, "CONDICIONAL", "NORMAL"),
])
def test_estado_por_pga(pga, actual, esperado):
    assert server._estado_por_pga(pga, actual) == esperado


def _base():
    return {"mejores": [{"codigo": "A", "creditos": 3, "nota": 4.0, "estado": "APROBADA"},
                        {"codigo": "B", "creditos": 3, "nota": 2.0, "estado": "REPROBADA"}],
            "en_curso": [{"codigo": "B", "asignatura": "B", "creditos": 3, "repite": True},
                         {"codigo": "C", "asignatura": "C", "creditos": 2, "repite": False}],
            "resumen": {"pga": 3.0, "estado_academico": "CONDICIONAL", "creditos_aprobados": 3, "creditos_totales": 10}}


def test_simulador_reemplaza_nota_reprobada():
    r = server._calcular(_base(), {"B": 4.0})
    assert r["pga"] == 4.0 and r["creditos_aprobados"] == 6   # la nota 2.0 deja de contar


def test_simulador_curso_nuevo_y_reprobado():
    r = server._calcular(_base(), {"C": 2.5})
    assert r["pga"] == round((4 * 3 + 2 * 3 + 2.5 * 2) / 8, 2) and r["creditos_aprobados"] == 3


def test_nota_minima():
    b = _base()
    n = server._nota_minima(b, ["B", "C"], lambda r: r["pga"] > 3.20)
    assert n is not None and server._calcular(b, {"B": n, "C": n})["pga"] > 3.20
    assert server._calcular(b, {"B": n - 0.1, "C": n - 0.1})["pga"] <= 3.20


def _hay_bd():
    try:
        return bool(server.db.fetch_one("SELECT 1 AS ok"))
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _hay_bd(), reason="sin base de datos")
def test_humo_todas_las_herramientas():
    ids = [r["id_estudiante"] for r in server.db.fetch_all("SELECT id_estudiante FROM estudiante ORDER BY random() LIMIT 20")]
    for sid in ids:
        server.estado_academico(sid)
        server.historial_cursos(sid)
        server.asignaturas_pendientes(sid)
        p = server.proyeccion_y_recomendaciones(sid)
        assert "propuesta_proximo_periodo" in p
        server.competencias_digitales(sid)
        server._simular(sid, nota_uniforme=3.5)
        server._app_personal(sid)
        server._app_alertas(sid)
        server._app_eventos(sid)
    server.plan_de_estudios()
    server.calendario_academico()
