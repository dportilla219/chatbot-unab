"""
App móvil (Gradio, instalable como PWA en Android) del Chatbot Académico UNAB.

Variables de entorno:
  N8N_CHAT_URL   webhook del workflow principal de n8n  (p. ej. http://n8n:5678/webhook/chat-unab)
  API_URL        servidor MCP/API para autenticar        (p. ej. http://mcp:9000)
  API_TOKEN      clave compartida (opcional)
"""
import os
import uuid

import gradio as gr
import requests

N8N_CHAT_URL = os.getenv("N8N_CHAT_URL", "http://localhost:5678/webhook/chat-unab")
API_URL = os.getenv("API_URL", "http://localhost:9000")
API_TOKEN = os.getenv("API_TOKEN", "")
HDR = {"X-API-Key": API_TOKEN} if API_TOKEN else {}

PROGRAMAS = ["Ingeniería de Sistemas", "Ingeniería Biomédica", "Ingeniería Industrial",
             "Ingeniería en Energía", "Ingeniería Mecatrónica", "Ingeniería Financiera"]

SUGERENCIAS = [
    "¿Cuál es mi estado de matrícula y avance?",
    "¿Qué cursos debo tomar el próximo semestre?",
    "¿Cuántos semestres me faltan y qué requisitos tengo pendientes?",
    "¿Qué es la insignia de competencias digitales?",
    "¿Qué cursos de competencias digitales he tomado?",
    "¿Cuándo son las inscripciones y el inicio de clases?",
    "¿Qué pasa si quedo en prueba académica?",
    "¿Hay nuevos cursos o convocatorias?",
]

CSS = """
:root { --unab-naranja:#FFA300; --unab-morado:#8E00F0; --unab-azul:#1C2B4B; }
.gradio-container { max-width: 760px !important; margin: auto; }
#header { background: linear-gradient(90deg, var(--unab-naranja) 0%, var(--unab-naranja) 62%, var(--unab-morado) 62%);
          border-radius: 14px; padding: 14px 18px; color: white; }
#header h1 { color: white; margin: 0; font-size: 1.35rem; font-weight: 800; }
#header p { color: white; margin: 2px 0 0 0; font-size: .85rem; opacity: .95; }
.sug button { font-size: .8rem !important; }
#estado { font-size: .85rem; }
footer { display: none !important; }
"""

HEADER = """<div id='header'><h1>🎓 Asistente Académico UNAB</h1>
<p>Ingeniería de Sistemas · Matrícula, plan de estudios, competencias digitales y reglamento</p></div>"""


def login(nombre, sid, programa, state):
    try:
        r = requests.post(f"{API_URL}/auth", json={"nombre_completo": nombre, "id_estudiante": sid,
                                                    "programa": programa}, headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return state, gr.update(), gr.update(), f"⚠️ No se pudo conectar con el servidor: {e}", []
    if not r.get("ok"):
        return state, gr.update(visible=True), gr.update(visible=False), f"❌ {r.get('mensaje')}", []
    est = r["estudiante"]
    state = {"id": est["id_estudiante"], "nombre": est["nombre_completo"], "programa": est["programa"],
             "semestre": est["semestre_actual"], "session": f"{est['id_estudiante']}"}
    saludo = (f"¡Hola, **{est['nombre_completo'].split()[0]}**! 👋 Soy tu asistente académico. "
              f"Estás en **{est['programa']}**, semestre {est['semestre_actual']}. "
              "Puedo ayudarte con tu matrícula, avance del plan, proyección de grado, competencias digitales, "
              "calendario académico, reglamento y noticias. ¿En qué te ayudo?")
    return (state, gr.update(visible=False), gr.update(visible=True),
            f"✅ Sesión iniciada: {est['nombre_completo']} ({est['id_estudiante']})",
            [{"role": "assistant", "content": saludo}])


def responder(mensaje, historial, state):
    historial = historial or []
    if not mensaje or not mensaje.strip():
        return "", historial
    if not state or not state.get("id"):
        return "", historial + [{"role": "assistant", "content": "Primero inicia sesión."}]
    historial = historial + [{"role": "user", "content": mensaje}]
    payload = {"sessionId": state["session"], "id_estudiante": state["id"], "nombre": state["nombre"],
               "programa": state["programa"], "mensaje": mensaje, "request_id": str(uuid.uuid4())}
    try:
        r = requests.post(N8N_CHAT_URL, json=payload, headers=HDR, timeout=120)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        texto = data.get("respuesta") or data.get("output") or data.get("text") or str(data)
        intent = data.get("intencion")
        if intent:
            texto += f"\n\n<sub>🔀 ruta: {intent}</sub>"
    except Exception as e:  # noqa: BLE001
        texto = f"⚠️ Ocurrió un problema consultando el asistente ({e.__class__.__name__}). Intenta de nuevo."
    return "", historial + [{"role": "assistant", "content": texto}]


def logout():
    return {}, gr.update(visible=True), gr.update(visible=False), "Sesión cerrada.", []


with gr.Blocks(title="Asistente Académico UNAB") as demo:
    state = gr.State({})
    gr.HTML(HEADER)
    estado = gr.Markdown("", elem_id="estado")

    with gr.Column(visible=True) as panel_login:
        gr.Markdown("### Identifícate\nIngresa tu nombre completo, tu ID estudiantil y tu carrera.")
        nombre = gr.Textbox(label="Nombre completo", placeholder="Ej: Valentina Rojas Méndez")
        sid = gr.Textbox(label="ID estudiantil", placeholder="U00174957", max_lines=1)
        programa = gr.Dropdown(PROGRAMAS, value="Ingeniería de Sistemas", label="Carrera")
        btn_login = gr.Button("Ingresar", variant="primary")
        gr.Markdown("<sub>Proyecto académico · Datos de estudiantes sintéticos que simulan Banner/COSMOS.</sub>")

    with gr.Column(visible=False) as panel_chat:
        chat = gr.Chatbot(height=480, label="Asistente", show_label=False)
        with gr.Row():
            msg = gr.Textbox(placeholder="Escribe tu pregunta…", show_label=False, scale=5, max_lines=3)
            enviar = gr.Button("Enviar", variant="primary", scale=1)
        gr.Markdown("**Preguntas frecuentes**")
        with gr.Row(elem_classes="sug"):
            botones = [gr.Button(s, size="sm") for s in SUGERENCIAS[:4]]
        with gr.Row(elem_classes="sug"):
            botones += [gr.Button(s, size="sm") for s in SUGERENCIAS[4:]]
        btn_logout = gr.Button("Cerrar sesión", size="sm", variant="secondary")

    btn_login.click(login, [nombre, sid, programa, state], [state, panel_login, panel_chat, estado, chat])
    sid.submit(login, [nombre, sid, programa, state], [state, panel_login, panel_chat, estado, chat])
    enviar.click(responder, [msg, chat, state], [msg, chat])
    msg.submit(responder, [msg, chat, state], [msg, chat])
    for b, s in zip(botones, SUGERENCIAS):
        b.click(lambda h, st, s=s: responder(s, h, st), [chat, state], [msg, chat])
    btn_logout.click(logout, None, [state, panel_login, panel_chat, estado, chat])


if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")),
                        pwa=True, favicon_path=os.path.join(os.path.dirname(__file__), "icon.png"),
                        css=CSS, theme=gr.themes.Soft(primary_hue="orange", secondary_hue="purple"))
