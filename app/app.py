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

# (etiqueta corta del botón, pregunta completa que se envía)
SUGERENCIAS = [
    ("Mi estado y avance", "¿Cuál es mi estado de matrícula y avance?"),
    ("Cursos del próximo semestre", "¿Qué cursos debo tomar el próximo semestre?"),
    ("Qué me falta para graduarme", "¿Cuántos semestres me faltan y qué requisitos tengo pendientes?"),
    ("Recomendaciones", "¿Qué me recomiendas para tener éxito en la carrera?"),
    ("Insignia digital", "¿Qué es la insignia de competencias digitales?"),
    ("Mis cursos CCD", "¿Qué cursos de competencias digitales he tomado?"),
    ("Fechas de inscripción", "¿Cuándo son las inscripciones y el inicio de clases?"),
    ("Prueba académica", "¿Qué pasa si quedo en prueba académica?"),
    ("Noticias y convocatorias", "¿Hay nuevos cursos o convocatorias?"),
]

# Fuerza el tema claro aunque el celular esté en modo oscuro.
JS_TEMA_CLARO = """
() => {
  const url = new URL(window.location);
  if (url.searchParams.get('__theme') !== 'light') {
    url.searchParams.set('__theme', 'light');
    window.location.replace(url.href);
  }
}
"""

CSS = """
:root { --naranja:#F7941D; --naranja-claro:#FFF4E6; --morado:#7B1FD8; --morado-claro:#F3EBFD;
        --tinta:#1F2937; --gris:#6B7280; --borde:#E5E7EB; --fondo:#F5F6FA; }
body, .gradio-container { background: var(--fondo) !important; }
.gradio-container { max-width: 760px !important; width: 100% !important; box-sizing: border-box !important; margin: auto !important; padding: 10px !important; }
.gradio-container .main, .gradio-container main.contain, .gradio-container .wrap.app { padding: 0 !important; max-width: 100% !important; }
footer { display: none !important; }
html, body { overflow-x: hidden !important; }
.gradio-container .column, .gradio-container .row, #panel-chat { min-width: 0 !important; max-width: 100% !important; }
#chips { width: 100% !important; max-width: calc(100vw - 20px) !important; }
/* Etiquetas de campos: texto simple en vez de pastillas */
#login span[data-testid="block-info"], #login label > span { background: transparent !important; color: var(--tinta) !important;
      padding: 0 !important; font-weight: 600 !important; font-size: .85rem !important; border: none !important; box-shadow:none !important; }

/* Encabezado */
#barra { display:flex; align-items:center; gap:12px; padding:14px 16px; border-radius:18px;
         background: linear-gradient(120deg, var(--naranja) 0%, #F26B21 45%, var(--morado) 100%);
         color:#fff; box-shadow: 0 6px 18px rgba(123,31,216,.18); }
#barra .logo { width:44px; height:44px; border-radius:12px; background:rgba(255,255,255,.2);
               display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; letter-spacing:.5px; flex-shrink:0; }
#barra h1 { margin:0; font-size:1.15rem; font-weight:800; color:#fff; line-height:1.2; }
#barra p { margin:2px 0 0; font-size:.8rem; color:rgba(255,255,255,.92); }

/* Tarjetas */
.tarjeta { background:#fff !important; border:1px solid var(--borde) !important; border-radius:18px !important;
           box-shadow: 0 2px 10px rgba(17,24,39,.05) !important; padding:18px !important; }
#login h2 { margin:0 0 4px; font-size:1.15rem; color:var(--tinta); }
#login .sub { margin:0 0 6px; color:var(--gris); font-size:.88rem; }
.nota { color:var(--gris); font-size:.78rem; text-align:center; }

/* Ficha del estudiante */
#ficha { display:flex; align-items:center; gap:10px; }
#ficha .avatar { width:40px; height:40px; border-radius:50%; background:var(--morado-claro); color:var(--morado);
                 font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
#ficha .nombre { font-weight:700; color:var(--tinta); font-size:.95rem; line-height:1.2; }
#ficha .detalle { color:var(--gris); font-size:.78rem; }
#fila-ficha { align-items:center !important; padding:10px 14px !important; flex-wrap:nowrap !important; }
#fila-ficha > div:first-child { flex:1 1 auto !important; }
#salir { max-width:110px; min-width:90px !important; }

/* Chat */
#chat { border:none !important; background:transparent !important; }
#chat .message-content { border:none !important; background:transparent !important; box-shadow:none !important; }
#chat .message.bot { background:#fff !important; border:1px solid var(--borde) !important; color:var(--tinta) !important; }
#chat .message.user { background:var(--naranja-claro) !important; border:1px solid #FDDDB5 !important; color:var(--tinta) !important; }
#chat .top-panel { display:none !important; }
#chat .message-row .flex-wrap, #chat .message-row .message { max-width: 100% !important; }
#chat .message-row.bubble { max-width: 94% !important; }
#chat .message { border-radius:16px !important; font-size:.93rem !important; }
#chat sub { color:#9CA3AF; font-size:.7rem; }

/* Entrada */
#entrada { gap:8px !important; align-items:stretch !important; }
#entrada textarea { border-radius:14px !important; font-size:.95rem !important; }
#enviar { min-width:84px !important; max-width:96px; border-radius:14px !important; font-size:.95rem !important; }

/* Sugerencias: fila deslizable de chips */
#chips-titulo { margin:0 2px -6px; color:var(--gris); font-size:.8rem; font-weight:600; }
#chips { display:flex !important; flex-wrap:nowrap !important; overflow-x:auto !important; gap:8px !important;
         padding:4px 2px 8px !important; scrollbar-width:none; }
#chips::-webkit-scrollbar { display:none; }
#chips button { flex:0 0 auto !important; width:auto !important; min-width:0 !important; white-space:nowrap !important;
                border-radius:999px !important; background:#fff !important; border:1px solid var(--borde) !important;
                color:var(--tinta) !important; font-size:.8rem !important; padding:6px 12px !important; box-shadow:none !important; }
#chips button:hover { border-color:var(--naranja) !important; background:var(--naranja-claro) !important; }

/* Botón principal */
button.primary { background: var(--naranja) !important; border:none !important; color:#fff !important; }
button.primary:hover { background:#E5820B !important; }
"""

HEADER = """<div id='barra'><div class='logo'>UNAB</div>
<div><h1>Asistente Académico UNAB</h1>
<p>Ingeniería de Sistemas · matrícula, plan de estudios, reglamento y competencias digitales</p></div></div>"""

PLACEHOLDER = ("<div style='text-align:center;color:#6B7280;padding:24px'>"
               "<b>Pregúntame lo que necesites</b><br>"
               "<span style='font-size:.85rem'>o elige una de las sugerencias de abajo</span></div>")


def ficha_html(st):
    if not st:
        return ""
    ini = "".join(p[0] for p in st["nombre"].split()[:2]).upper()
    return (f"<div id='ficha'><div class='avatar'>{ini}</div><div><div class='nombre'>{st['nombre']}</div>"
            f"<div class='detalle'>{st['id']} · {st['programa']} · semestre {st['semestre']}</div></div></div>")


def historial_previo(nombre, sid, programa, limite=10):
    """Recupera los últimos intercambios guardados en chat_log (memoria entre sesiones)."""
    try:
        r = requests.post(f"{API_URL}/historial", json={"nombre_completo": nombre, "id_estudiante": sid,
                                                         "programa": programa, "limite": limite},
                          headers=HDR, timeout=15).json()
    except Exception:  # noqa: BLE001
        return []
    msgs = []
    for i, m in enumerate(r.get("mensajes") or []):
        if i == 0:
            msgs.append({"role": "assistant", "content": f"<sub>Conversación anterior · desde {m['fecha']}</sub>"})
        msgs.append({"role": "user", "content": m["pregunta"]})
        txt = m["respuesta"] + (f"\n\n<sub>Ruta: {m['intencion']}</sub>" if m.get("intencion") else "")
        msgs.append({"role": "assistant", "content": txt})
    return msgs


def login(nombre, sid, programa, state):
    try:
        r = requests.post(f"{API_URL}/auth", json={"nombre_completo": nombre, "id_estudiante": sid,
                                                    "programa": programa}, headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return state, gr.update(), gr.update(), "", [], f"No se pudo conectar con el servidor ({e.__class__.__name__})."
    if not r.get("ok"):
        return state, gr.update(visible=True), gr.update(visible=False), "", [], f"{r.get('mensaje')}"
    est = r["estudiante"]
    state = {"id": est["id_estudiante"], "nombre": est["nombre_completo"], "programa": est["programa"],
             "semestre": est["semestre_actual"], "session": f"{est['id_estudiante']}"}
    previos = historial_previo(nombre, sid, programa)
    if previos:
        saludo = (f"¡Hola de nuevo, **{est['nombre_completo'].split()[0]}**! Arriba está nuestra conversación anterior; "
                  "puedes continuar donde la dejaste o preguntarme algo nuevo.")
        return (state, gr.update(visible=False), gr.update(visible=True), ficha_html(state),
                previos + [{"role": "assistant", "content": saludo}], "")
    saludo = (f"¡Hola, **{est['nombre_completo'].split()[0]}**! Soy tu asistente académico. "
              f"Estás en **{est['programa']}**, semestre {est['semestre_actual']}. "
              "Puedo ayudarte con tu matrícula, avance del plan, proyección de grado, competencias digitales, "
              "calendario académico, reglamento y noticias. ¿En qué te ayudo?")
    return (state, gr.update(visible=False), gr.update(visible=True), ficha_html(state),
            [{"role": "assistant", "content": saludo}], "")


def agregar_pregunta(mensaje, historial, state):
    """Paso 1: muestra la pregunta del estudiante de inmediato."""
    historial = historial or []
    if not mensaje or not mensaje.strip() or not state or not state.get("id"):
        return "", historial, ""
    return "", historial + [{"role": "user", "content": mensaje.strip()}], mensaje.strip()


def responder(pendiente, historial, state):
    """Paso 2: consulta al asistente (n8n) y agrega la respuesta."""
    historial = historial or []
    if not pendiente:
        return historial
    payload = {"sessionId": state["session"], "id_estudiante": state["id"], "nombre": state["nombre"],
               "programa": state["programa"], "mensaje": pendiente, "request_id": str(uuid.uuid4())}
    try:
        r = requests.post(N8N_CHAT_URL, json=payload, headers=HDR, timeout=120)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        texto = data.get("respuesta") or data.get("output") or data.get("text") or str(data)
        intent = data.get("intencion")
        if intent:
            texto += f"\n\n<sub>Ruta: {intent}</sub>"
    except Exception as e:  # noqa: BLE001
        texto = f"Ocurrió un problema consultando el asistente ({e.__class__.__name__}). Intenta de nuevo."
    return historial + [{"role": "assistant", "content": texto}]


def logout():
    return {}, gr.update(visible=True), gr.update(visible=False), "", [], ""


with gr.Blocks(title="Asistente Académico UNAB") as demo:
    state = gr.State({})
    pendiente = gr.State("")
    gr.HTML(HEADER)

    with gr.Column(visible=True, elem_id="login", elem_classes="tarjeta") as panel_login:
        gr.HTML("<h2>Inicia sesión</h2><p class='sub'>Ingresa tu nombre completo, tu ID estudiantil y tu carrera.</p>")
        nombre = gr.Textbox(label="Nombre completo", placeholder="Ej: Valentina Rojas Méndez", max_lines=1)
        sid = gr.Textbox(label="ID estudiantil", placeholder="Ej: U00174957", max_lines=1)
        programa = gr.Dropdown(PROGRAMAS, value="Ingeniería de Sistemas", label="Carrera")
        error = gr.Markdown("")
        btn_login = gr.Button("Ingresar", variant="primary", size="lg")
        with gr.Accordion("¿Probando la app? Usuarios de demostración", open=False):
            gr.Markdown("- **Valentina Rojas Méndez** · U00174957 (estado normal)\n"
                        "- **Andrés Felipe Gómez Pardo** · U00160001 (condicional)\n"
                        "- **Laura Camila Suárez Díaz** · U00160002\n"
                        "- **Santiago Pérez Villamizar** · U00160003 (primer semestre)")
        gr.HTML("<p class='nota'>Proyecto académico · datos sintéticos que simulan Banner/COSMOS</p>")

    with gr.Column(visible=False, elem_id="panel-chat") as panel_chat:
        with gr.Row(elem_id="fila-ficha", elem_classes="tarjeta", equal_height=True):
            ficha = gr.HTML("", padding=False)
            btn_logout = gr.Button("Salir", size="sm", variant="secondary", elem_id="salir", scale=0)
        chat = gr.Chatbot(elem_id="chat", show_label=False, height="58vh", buttons=["copy"],
                          group_consecutive_messages=False, placeholder=PLACEHOLDER,
                          avatar_images=(None, os.path.join(os.path.dirname(__file__), "icon.png")))
        gr.HTML("<p id='chips-titulo'>Sugerencias</p>")
        with gr.Row(elem_id="chips"):
            botones = [gr.Button(e, size="sm") for e, _ in SUGERENCIAS]
        with gr.Row(elem_id="entrada", equal_height=True):
            msg = gr.Textbox(placeholder="Escribe tu pregunta…", show_label=False, scale=6, max_lines=4,
                             container=False)
            enviar = gr.Button("Enviar", variant="primary", scale=0, elem_id="enviar")

    salidas_login = [state, panel_login, panel_chat, ficha, chat, error]
    btn_login.click(login, [nombre, sid, programa, state], salidas_login)
    sid.submit(login, [nombre, sid, programa, state], salidas_login)
    for disparador in (enviar.click, msg.submit):
        disparador(agregar_pregunta, [msg, chat, state], [msg, chat, pendiente], queue=False).then(
            responder, [pendiente, chat, state], chat)
    for b, (_, q) in zip(botones, SUGERENCIAS):
        b.click(lambda h, st, q=q: agregar_pregunta(q, h, st), [chat, state], [msg, chat, pendiente], queue=False).then(
            responder, [pendiente, chat, state], chat)
    btn_logout.click(logout, None, salidas_login)


if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")),
                        pwa=True, favicon_path=os.path.join(os.path.dirname(__file__), "icon.png"),
                        css=CSS, js=JS_TEMA_CLARO,
                        theme=gr.themes.Soft(primary_hue="orange", secondary_hue="purple", neutral_hue="slate",
                                             font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"]))
