"""Cliente MCP independiente: Claude conversa con el servidor FastMCP de la UNAB.

Se conecta al servidor MCP (HTTP streamable), descubre sus herramientas, se las ofrece a Claude
y ejecuta las llamadas que Claude decida (bucle de *tool use*). Demuestra que el mismo servidor
sirve a clientes distintos de n8n (este script, Claude Desktop, etc.).

Uso:
    pip install fastmcp anthropic
    python cliente_mcp_claude.py --listar                       # solo lista herramientas (sin costo de API)
    python cliente_mcp_claude.py --llamar estado_academico U00174957   # llama una herramienta directamente
    ANTHROPIC_API_KEY=... python cliente_mcp_claude.py "Soy U00160001, ¿qué me recomiendas para mejorar?"

Variables: MCP_URL (por defecto https://mcp.3-222-163-239.sslip.io/mcp), MODELO (claude-haiku-5-5).
"""
import asyncio
import json
import os
import sys

from fastmcp import Client

MCP_URL = os.getenv("MCP_URL", "https://mcp.3-222-163-239.sslip.io/mcp")
MODELO = os.getenv("MODELO", "claude-haiku-5-5")
SYSTEM = ("Eres el asistente académico de Ingeniería de Sistemas de la UNAB. Usa las herramientas MCP para "
          "consultar datos reales del estudiante, el plan de estudios y el Reglamento. Responde en español, breve y "
          "citando artículos cuando apliquen.")


def _schema(t) -> dict:
    return getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}


def _texto(resultado) -> str:
    partes = [getattr(c, "text", "") for c in (resultado.content or [])]
    return "\n".join(p for p in partes if p) or json.dumps(getattr(resultado, "structured_content", None), ensure_ascii=False)


async def listar():
    async with Client(MCP_URL) as c:
        for t in await c.list_tools():
            print(f"- {t.name}: {(t.description or '').splitlines()[0]}")


async def llamar(nombre: str, arg: str | None):
    async with Client(MCP_URL) as c:
        tools = {t.name: t for t in await c.list_tools()}
        props = list(_schema(tools[nombre]).get("properties", {}))
        args = {props[0]: arg} if (arg and props) else {}
        print(_texto(await c.call_tool(nombre, args))[:4000])


async def conversar(pregunta: str):
    import anthropic
    claude = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY (y ANTHROPIC_BASE_URL si se define)
    async with Client(MCP_URL) as c:
        tools = [{"name": t.name, "description": t.description or "", "input_schema": _schema(t)}
                 for t in await c.list_tools()]
        mensajes = [{"role": "user", "content": pregunta}]
        for _ in range(8):
            r = claude.messages.create(model=MODELO, max_tokens=2000, system=SYSTEM, tools=tools, messages=mensajes)
            mensajes.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
            usos = [b for b in r.content if b.type == "tool_use"]
            if not usos:
                print("\n".join(b.text for b in r.content if b.type == "text"))
                print(f"\n[tokens: entrada {r.usage.input_tokens} · salida {r.usage.output_tokens}]")
                return
            resultados = []
            for u in usos:
                print(f"  → herramienta MCP: {u.name}({json.dumps(u.input, ensure_ascii=False)})")
                try:
                    out = _texto(await c.call_tool(u.name, u.input))
                except Exception as e:  # noqa: BLE001
                    out = f"Error: {e}"
                resultados.append({"type": "tool_result", "tool_use_id": u.id, "content": out[:20000]})
            mensajes.append({"role": "user", "content": resultados})
        print("Se alcanzó el máximo de iteraciones.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--listar":
        asyncio.run(listar())
    elif a[0] == "--llamar":
        asyncio.run(llamar(a[1], a[2] if len(a) > 2 else None))
    else:
        asyncio.run(conversar(" ".join(a)))
