"""
App móvil (Gradio, instalable como PWA en Android) del Chatbot Académico UNAB.

Variables de entorno:
  N8N_CHAT_URL   webhook del workflow principal de n8n  (p. ej. http://n8n:5678/webhook/chat-unab)
  API_URL        servidor MCP/API para autenticar        (p. ej. http://mcp:9000)
  API_TOKEN      clave compartida (opcional)
"""
import html
import os
import uuid

import gradio as gr
import requests

import vistas

N8N_CHAT_URL = os.getenv("N8N_CHAT_URL", "http://localhost:5678/webhook/chat-unab")
API_URL = os.getenv("API_URL", "http://localhost:9000")
API_TOKEN = os.getenv("API_TOKEN", "")
HDR = {"X-API-Key": API_TOKEN} if API_TOKEN else {}
# Botón "Entrar con perfil de prueba" (se apaga con DEMO_HABILITADO=0)
DEMO_HABILITADO = os.getenv("DEMO_HABILITADO", "1") == "1"
DEMO_NOMBRE = os.getenv("DEMO_NOMBRE", "Valentina Rojas Méndez")
DEMO_ID = os.getenv("DEMO_ID", "U00174957")

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
.tarjeta span[data-testid="block-info"], .tarjeta label > span { background: transparent !important; color: var(--tinta) !important;
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
/* Barra superior delgada */
#appbar { position:sticky; top:0; z-index:40; align-items:center !important; flex-wrap:nowrap !important;
          background:rgba(245,246,250,.96) !important; backdrop-filter:blur(8px); padding:4px 2px 8px !important;
          border-bottom:1px solid var(--borde); margin-bottom:6px !important; gap:8px !important; }
#appbar > div:first-child { flex:1 1 auto !important; min-width:0 !important; }
#appbar .marca { display:flex; align-items:center; gap:8px; font-weight:800; color:var(--tinta); font-size:1rem; }
#appbar .sello { background:linear-gradient(120deg, var(--naranja), var(--morado)); color:#fff; font-size:.62rem;
                 letter-spacing:.5px; padding:5px 7px; border-radius:8px; }
#ficha-personal { margin-bottom:4px; }
#filtro-tema { background:transparent !important; border:none !important; padding:0 !important; margin-bottom:6px !important; }
#filtro-tema .wrap { display:flex !important; flex-wrap:nowrap !important; overflow-x:auto !important; gap:8px !important; scrollbar-width:none; }
#filtro-tema .wrap::-webkit-scrollbar { display:none; }
#filtro-tema label { flex:0 0 auto !important; border-radius:999px !important; background:#fff !important; border:1px solid var(--borde) !important;
      padding:6px 12px !important; font-size:.8rem !important; color:var(--tinta) !important; box-shadow:none !important; }
#filtro-tema label.selected, #filtro-tema label:has(input:checked) { background:var(--naranja-claro) !important; border-color:var(--naranja) !important; }
#filtro-tema input { display:none !important; }
#mis-eventos { padding:6px 12px !important; margin-bottom:8px !important; border-color:#D9C4F7 !important; }
#ficha-personal #ficha { background:#fff; border:1px solid var(--borde); border-radius:14px; padding:12px 14px; }
#salir { margin-top:10px !important; background:#fff !important; border:1px solid #F3C2C2 !important; color:#B42318 !important; }

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

/* Pestañas: barra fija abajo con íconos, el chat en el centro y destacado */
#tabs > .tab-wrapper, #tabs > div:first-child:not(.tabitem) { position:fixed !important; bottom:0 !important; left:0; right:0; z-index:50; margin:0 !important;
      background:rgba(255,255,255,.97) !important; backdrop-filter:blur(8px); border-top:1px solid var(--borde) !important;
      padding:6px 8px calc(8px + env(safe-area-inset-bottom)) !important; box-shadow:0 -6px 20px rgba(17,24,39,.07);
      overflow:visible !important; }
#tabs [role="tablist"] { display:flex !important; justify-content:space-around !important; align-items:flex-end !important;
      width:100% !important; max-width:560px; margin:auto; gap:0 !important; border:none !important; border-bottom:none !important;
      box-shadow:none !important; overflow:visible !important; }
#tabs .tab-wrapper::after, #tabs [role="tablist"]::after { display:none !important; }
#tabs [role="tab"] { flex:1 1 0 !important; display:flex !important; flex-direction:column !important; align-items:center !important;
      gap:3px !important; font-size:.68rem !important; font-weight:600 !important; color:#9CA3AF !important;
      padding:4px 2px !important; border:none !important; border-radius:12px !important; background:transparent !important;
      min-width:0 !important; height:auto !important; min-height:52px !important; overflow:visible !important;
      justify-content:flex-end !important; transition:color .15s ease; }
#tabs [role="tablist"], #tabs .tab-container, #tabs > .tab-wrapper { height:auto !important; overflow:visible !important; }
#tabs [role="tab"]::before { content:""; flex:0 0 auto; width:22px; height:22px; background-color:currentColor;
      -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-position:center; mask-position:center;
      -webkit-mask-size:contain; mask-size:contain; transition:transform .15s ease; }
#tabs [role="tab"][aria-selected="true"] { color:var(--naranja) !important; }
#tabs [role="tab"][aria-selected="true"]::before { transform:translateY(-1px) scale(1.06); }
#tabs [role="tab"][aria-selected="true"]::after { display:none !important; }
/* Chat: botón central elevado */
#tabs [role="tab"][data-tab-id="chat"] { color:var(--tinta) !important; }
#tabs [role="tab"][data-tab-id="chat"]::before { width:50px; height:50px; margin-top:-24px; border-radius:50%;
      -webkit-mask-image:none !important; mask-image:none !important; background-color:transparent;
      background: url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%205h16v11H9l-5%204z%27/%3E%3Cpath%20d%3D%27M8%209h8M8%2012h5%27/%3E%3C/svg%3E") center / 24px no-repeat, linear-gradient(135deg, var(--naranja), #F26B21);
      box-shadow:0 0 0 4px #fff, 0 6px 16px rgba(247,148,29,.45); }
#tabs [role="tab"][data-tab-id="chat"]::after { display:none !important; }
#tabs [role="tab"][data-tab-id="chat"][aria-selected="true"] { color:var(--naranja) !important; }
#tabs [role="tab"][data-tab-id="chat"] { position:relative; }
#tabs .tabitem { padding:0 !important; border:none !important; background:transparent !important; }
#tabs .overflow-menu, #tabs .overflow-item-selected { display:none !important; }
#tabs .tab-container.visually-hidden button { padding:2px 1px !important; font-size:.55rem !important; min-width:0 !important; }
.gradio-container { padding-bottom:118px !important; }
#tabs [role="tab"][data-tab-id="noticias"]::before { -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%204h13v16H6a2%202%200%200%201-2-2z%27/%3E%3Cpath%20d%3D%27M17%208h3v10a2%202%200%200%201-2%202%27/%3E%3Cpath%20d%3D%27M8%208h5M8%2012h5M8%2016h3%27/%3E%3C/svg%3E"); mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%204h13v16H6a2%202%200%200%201-2-2z%27/%3E%3Cpath%20d%3D%27M17%208h3v10a2%202%200%200%201-2%202%27/%3E%3Cpath%20d%3D%27M8%208h5M8%2012h5M8%2016h3%27/%3E%3C/svg%3E"); }
#tabs [role="tab"][data-tab-id="historial"]::before { -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Ccircle%20cx%3D%2712%27%20cy%3D%2712%27%20r%3D%279%27/%3E%3Cpath%20d%3D%27M12%207v5l3%202%27/%3E%3C/svg%3E"); mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Ccircle%20cx%3D%2712%27%20cy%3D%2712%27%20r%3D%279%27/%3E%3Cpath%20d%3D%27M12%207v5l3%202%27/%3E%3C/svg%3E"); }
#tabs [role="tab"][data-tab-id="chat"]::before { -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%205h16v11H9l-5%204z%27/%3E%3Cpath%20d%3D%27M8%209h8M8%2012h5%27/%3E%3C/svg%3E"); mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%205h16v11H9l-5%204z%27/%3E%3Cpath%20d%3D%27M8%209h8M8%2012h5%27/%3E%3C/svg%3E"); }
#tabs [role="tab"][data-tab-id="eventos"]::before { -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Crect%20x%3D%273%27%20y%3D%275%27%20width%3D%2718%27%20height%3D%2716%27%20rx%3D%272%27/%3E%3Cpath%20d%3D%27M3%2010h18M8%203v4M16%203v4%27/%3E%3C/svg%3E"); mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Crect%20x%3D%273%27%20y%3D%275%27%20width%3D%2718%27%20height%3D%2716%27%20rx%3D%272%27/%3E%3Cpath%20d%3D%27M3%2010h18M8%203v4M16%203v4%27/%3E%3C/svg%3E"); }
#tabs [role="tab"][data-tab-id="personal"]::before { -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Ccircle%20cx%3D%2712%27%20cy%3D%278%27%20r%3D%274%27/%3E%3Cpath%20d%3D%27M4%2021c0-4%204-6%208-6s8%202%208%206%27/%3E%3C/svg%3E"); mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27black%27%20stroke-width%3D%272%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Ccircle%20cx%3D%2712%27%20cy%3D%278%27%20r%3D%274%27/%3E%3Cpath%20d%3D%27M4%2021c0-4%204-6%208-6s8%202%208%206%27/%3E%3C/svg%3E"); }

/* Historial de conversaciones */
#conv-cabecera { align-items:center !important; }
#conv-cabecera h3 { margin:0; font-size:1rem; color:var(--tinta); }
#lista-conv { background:transparent !important; border:none !important; padding:0 !important; }
#lista-conv .wrap { display:flex !important; flex-direction:column !important; gap:8px !important; }
#lista-conv label { display:block !important; width:100% !important; background:#fff !important; border:1px solid var(--borde) !important;
      border-radius:14px !important; padding:12px 14px !important; color:var(--tinta) !important; font-size:.88rem !important;
      font-weight:600 !important; box-shadow:none !important; white-space:normal !important; line-height:1.35; }
#lista-conv label.selected, #lista-conv label:has(input:checked) { border-color:var(--naranja) !important; background:var(--naranja-claro) !important; }
#lista-conv input { display:none !important; }
#lista-conv label span { white-space:pre-line !important; }
#nueva-conv { max-width:170px; }
#buscar-conv textarea, #buscar-conv input { border-radius:12px !important; font-size:.88rem !important; }
#simulador { padding:6px 12px !important; margin:8px 12px !important; width:auto !important; border-color:#FDDDB5 !important; }
#conv-vacio .vacio { padding:18px 8px; }
#simulador input[type=range] { accent-color:var(--naranja); }
#chat-acciones { justify-content:flex-end !important; margin-bottom:-6px !important; }
#nueva-chat { max-width:96px; min-width:80px !important; border-radius:999px !important; background:#fff !important;
               border:1px solid var(--borde) !important; color:var(--tinta) !important; font-weight:600 !important; }

/* Botón principal */
button.primary { background: var(--naranja) !important; border:none !important; color:#fff !important; }
button.primary:hover { background:#E5820B !important; }
#demo-btn { background:#fff !important; border:1.5px dashed var(--morado) !important; color:var(--morado) !important; }
"""

CSS = CSS + vistas.CSS_VISTAS

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


def datos_app(seccion, state, **extra):
    sid = (state or {}).get("id", "")
    try:
        r = requests.post(f"{API_URL}/app/datos", json={"seccion": seccion, "id_estudiante": sid, **extra},
                          headers=HDR, timeout=20).json()
        return r.get("datos") if r.get("ok") else None
    except Exception:  # noqa: BLE001
        return None


TEMAS_NOTICIAS = ["Todas", "Educación", "Tecnología", "Ingeniería de Sistemas", "Institucional"]


def ver_noticias(state, tema="Todas"):
    return vistas.noticias(datos_app("noticias", state, tema="" if tema in (None, "Todas") else tema))


def ver_eventos(state):
    datos = datos_app("eventos", state)
    activos = bool(config_servidor().get("eventos_personales"))
    propios = [(f"{e['inicio']} · {e['actividad']}", e["id"]) for e in (datos or []) if e.get("origen") == "personal"]
    return (vistas.eventos(datos), gr.Column(visible=activos and bool(state)),
            gr.update(choices=propios, value=None))


def guardar_evento(nombre, fecha, descripcion, state):
    if not state:
        return "Inicia sesión primero.", gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    fecha = str(fecha or "")[:10]
    try:
        r = requests.post(f"{API_URL}/app/eventos", json={"id_estudiante": state["id"], "nombre": nombre, "fecha": fecha,
                                                           "descripcion": descripcion}, headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        r = {"ok": False, "mensaje": f"No se pudo conectar con el servidor ({e.__class__.__name__})."}
    html, vis, lista = ver_eventos(state)
    if r.get("ok"):
        return r["mensaje"], html, vis, lista, "", None, ""
    return r.get("mensaje", "No se pudo guardar."), html, vis, lista, gr.update(), gr.update(), gr.update()


def eliminar_evento(ev_id, state):
    if not state or not ev_id:
        return "Elige un evento de la lista.", gr.update(), gr.update(), gr.update()
    try:
        r = requests.post(f"{API_URL}/app/eventos", json={"id_estudiante": state["id"], "accion": "eliminar", "id": ev_id},
                          headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        r = {"ok": False, "mensaje": f"No se pudo conectar con el servidor ({e.__class__.__name__})."}
    html, vis, lista = ver_eventos(state)
    return r.get("mensaje", ""), html, vis, lista


def _nueva_conv(sid):
    return f"{sid}:{uuid.uuid4().hex[:12]}"


def _titulo_conv(c):
    if c["id"] == c.get("_sid"):
        t = "Conversaciones anteriores"
    else:
        t = " ".join((c.get("primera") or "Conversación").split())
        t = t[:52] + ("…" if len(t) > 52 else "")
    n = c.get("mensajes") or 0
    return f"{t}\n{c['ultima']} · {n} pregunta{'s' if n != 1 else ''}"


def lista_conversaciones(state, q=""):
    if not state:
        return gr.update(choices=[], value=None), ""
    q = (q or "").strip()
    convs = datos_app("conversaciones", state, q=q) or []
    for c in convs:
        c["_sid"] = state["id"]
    actual = state.get("conv") if any(c["id"] == state.get("conv") for c in convs) else None
    if convs:
        aviso = ""
    elif q:
        aviso = f"<div class='vacio'>Ninguna conversación menciona \"{html.escape(q)}\".</div>"
    else:
        aviso = "<div class='vacio'>Aún no tienes conversaciones guardadas. Escríbele al asistente desde la pestaña Chat.</div>"
    return gr.update(choices=[(_titulo_conv(c), c["id"]) for c in convs], value=actual), aviso


def abrir_conversacion(conv, state):
    if not conv or not state:
        return gr.update(), state, gr.update()
    try:
        r = requests.post(f"{API_URL}/app/datos", json={"seccion": "conversacion", "id_estudiante": state["id"],
                                                         "conversacion": conv}, headers=HDR, timeout=20).json()
        filas = r.get("datos") or []
    except Exception:  # noqa: BLE001
        filas = []
    msgs = []
    for m in filas:
        msgs.append({"role": "user", "content": m["pregunta"]})
        msgs.append({"role": "assistant", "content": m["respuesta"] + (
            f"\n\n<sub>Ruta: {m['intencion']}</sub>" if m.get("intencion") else "")})
    state = {**state, "conv": conv}
    return msgs, state, gr.Tabs(selected="chat")


def nueva_conversacion(state):
    if not state:
        return gr.update(), state, gr.update()
    state = {**state, "conv": _nueva_conv(state["id"])}
    nombre = state["nombre"].split()[0]
    return ([{"role": "assistant", "content": f"Nueva conversación, **{nombre}**. ¿En qué te ayudo?"}], state,
            gr.Tabs(selected="chat"))


def ver_historial(state):
    return vistas.historial(datos_app("historial", state)) if state else ""


MAX_SIM = 9  # cursos en curso que admite el simulador


def ver_personal(state):
    """Pestaña Personal: progreso, plan sugerido, simulador (un deslizador por curso en curso) y detalle."""
    datos = datos_app("personal", state) if state else None
    cursos = (datos or {}).get("simulador") or []
    sliders = [gr.Slider(visible=i < len(cursos), label=(f"{cursos[i]['asignatura']} ({cursos[i]['creditos']} cr.)" if i < len(cursos) else ""),
                         value=3.5) for i in range(MAX_SIM)]
    return ([vistas.personal_resumen(datos), vistas.personal(datos) if state else "",
             gr.Column(visible=bool(cursos)), [c["codigo"] for c in cursos], ""] + sliders)


def simular(state, codigos, *notas):
    if not state or not codigos:
        return "<div class='vacio'>No tienes cursos en curso para simular.</div>"
    try:
        r = requests.post(f"{API_URL}/app/simular", json={"id_estudiante": state["id"],
                                                          "notas": {c: n for c, n in zip(codigos, notas)}},
                          headers=HDR, timeout=20).json()
    except Exception:  # noqa: BLE001
        r = {}
    return vistas.simulacion(r.get("datos") if r.get("ok") else None)


def ver_avisos(state):
    return vistas.avisos(datos_app("alertas", state)) if state else ""


def calificar(state, historial, dato: gr.LikeData):
    """Guarda el pulgar arriba o abajo de una respuesta del asistente."""
    if not state or not historial:
        return
    i = dato.index if isinstance(dato.index, int) else dato.index[0]
    if i >= len(historial) or historial[i].get("role") != "assistant":
        return
    pregunta = next((historial[j]["content"] for j in range(i - 1, -1, -1) if historial[j].get("role") == "user"), "")
    valor = 1 if dato.liked is True else (-1 if dato.liked is False else 0)
    contenido = historial[i]["content"]
    if isinstance(contenido, list):
        contenido = " ".join(str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in contenido)
    try:
        requests.post(f"{API_URL}/app/calificar", json={"id_estudiante": state["id"], "session_id": state.get("conv"),
                                                        "pregunta": pregunta if isinstance(pregunta, str) else str(pregunta),
                                                        "respuesta": contenido, "valor": valor}, headers=HDR, timeout=10)
    except Exception:  # noqa: BLE001
        pass


def config_servidor():
    """Funciones activas en el servidor (contraseñas y sesiones existen solo tras la migración 06)."""
    try:
        return requests.get(f"{API_URL}/auth/config", headers=HDR, timeout=10).json()
    except Exception:  # noqa: BLE001
        return {"password": False, "sesiones": False, "demo": DEMO_HABILITADO}


def nombre_dispositivo(request: gr.Request | None) -> str:
    ua = ((request.headers.get("user-agent") if request else "") or "").lower()
    so = next((n for k, n in [("android", "Android"), ("iphone", "iPhone"), ("ipad", "iPad"), ("windows", "Windows"),
                              ("mac os", "Mac"), ("linux", "Linux")] if k in ua), "Dispositivo")
    nav = next((n for k, n in [("edg", "Edge"), ("chrome", "Chrome"), ("firefox", "Firefox"), ("safari", "Safari")]
                if k in ua), "navegador")
    return f"{so} · {nav}"


# Salidas comunes del inicio de sesión:
# state, panel_login, panel_chat, ficha, chat, error, token guardado, panel de cambio obligatorio, cabecera
def _entrar(r, recordar, password_usada=""):
    est = r["estudiante"]
    state = {"id": est["id_estudiante"], "nombre": est["nombre_completo"], "programa": est["programa"],
             "semestre": est["semestre_actual"], "conv": _nueva_conv(est["id_estudiante"]), "token": r.get("token") or "",
             "demo": bool(r.get("demo")), "pw": password_usada if r.get("debe_cambiar") else ""}
    previos = []
    nombre = est["nombre_completo"].split()[0]
    if datos_app("conversaciones", state):
        saludo = (f"¡Hola de nuevo, **{nombre}**! Empezamos una conversación nueva. "
                  "Tus conversaciones anteriores están en la pestaña **Historial**, donde puedes abrirlas y continuarlas.")
    else:
        saludo = (f"¡Hola, **{nombre}**! Soy tu asistente académico. "
                  f"Estás en **{est['programa']}**, semestre {est['semestre_actual']}. "
                  "Puedo ayudarte con tu matrícula, avance del plan, proyección de grado, competencias digitales, "
                  "calendario académico, reglamento y noticias. ¿En qué te ayudo?")
    importantes = [a for a in (datos_app("alertas", state) or []) if a.get("nivel") in ("alta", "personal")]
    if importantes:
        saludo += "\n\n**Avisos para ti:** " + " · ".join(a["titulo"] for a in importantes[:3]) + \
            ". Los detalles están en la pestaña **Eventos**."
    guardar = state["token"] if (recordar and state["token"]) else ""
    debe = bool(r.get("debe_cambiar"))
    return (state, gr.update(visible=False), gr.update(visible=not debe), ficha_html(state),
            previos + [{"role": "assistant", "content": saludo}], "", guardar, gr.update(visible=debe),
            gr.update(visible=False))


def _error(msg):
    return ({}, gr.update(visible=True), gr.update(visible=False), "", [], msg, gr.update(),
            gr.update(visible=False), gr.update(visible=True))


def login(nombre, sid, programa, password, recordar, request: gr.Request):
    try:
        r = requests.post(f"{API_URL}/auth", json={"nombre_completo": nombre, "id_estudiante": sid, "programa": programa,
                                                    "password": password, "recordar": bool(recordar),
                                                    "dispositivo": nombre_dispositivo(request)},
                          headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return _error(f"No se pudo conectar con el servidor ({e.__class__.__name__}).")
    if not r.get("ok"):
        return _error(r.get("mensaje") or "No se pudo iniciar sesión.")
    return _entrar(r, recordar, password)


def login_demo(request: gr.Request):
    try:
        r = requests.post(f"{API_URL}/auth", json={"demo": True, "recordar": True,
                                                    "dispositivo": nombre_dispositivo(request) + " (prueba)"},
                          headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return _error(f"No se pudo conectar con el servidor ({e.__class__.__name__}).")
    if not r.get("ok"):  # servidor sin la ruta demo: se entra con nombre e ID del perfil de prueba
        r = requests.post(f"{API_URL}/auth", json={"nombre_completo": DEMO_NOMBRE, "id_estudiante": DEMO_ID,
                                                    "programa": "Ingeniería de Sistemas"}, headers=HDR, timeout=15).json()
        if not r.get("ok"):
            return _error(r.get("mensaje") or "No se pudo entrar al perfil de prueba.")
    r["debe_cambiar"] = False
    return _entrar(r, True)


def reanudar(token_guardado):
    """Al abrir la app: si este dispositivo tiene una sesión guardada, entra directo."""
    cfg = config_servidor()
    campos = (gr.update(visible=bool(cfg.get("password"))), gr.update(visible=bool(cfg.get("sesiones"))))
    if not token_guardado:
        return _error("") + campos
    try:
        r = requests.post(f"{API_URL}/auth/token", json={"token": token_guardado}, headers=HDR, timeout=15).json()
    except Exception:  # noqa: BLE001
        r = {}
    if not r.get("ok"):
        out = list(_error(""))
        out[6] = ""  # borra el token inválido del dispositivo
        return tuple(out) + campos
    r["token"] = token_guardado
    return _entrar(r, True) + campos


def cambiar_password(actual, nueva, confirmar, state):
    if not state or not state.get("token"):
        return "Para cambiar la contraseña, cierra sesión y vuelve a entrar.", state, gr.update(), gr.update()
    if nueva != confirmar:
        return "La confirmación no coincide con la contraseña nueva.", state, gr.update(), gr.update()
    actual = actual or state.get("pw", "")
    try:
        r = requests.post(f"{API_URL}/auth/password", json={"token": state["token"], "actual": actual, "nueva": nueva},
                          headers=HDR, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return f"No se pudo conectar con el servidor ({e.__class__.__name__}).", state, gr.update(), gr.update()
    if r.get("ok"):
        state = {**state, "pw": ""}
        return "Contraseña actualizada. Las demás sesiones abiertas se cerraron.", state, gr.update(visible=False), gr.update(visible=True)
    return r.get("mensaje", "No se pudo cambiar la contraseña."), state, gr.update(), gr.update()


def sesiones(state, cerrar=None):
    if not state or not state.get("token"):
        return gr.update(choices=[], value=None), "No hay sesiones guardadas para este ingreso."
    body = {"token": state["token"]}
    if cerrar:
        body["cerrar"] = cerrar
    try:
        r = requests.post(f"{API_URL}/auth/sesiones", json=body, headers=HDR, timeout=15).json()
    except Exception:  # noqa: BLE001
        return gr.update(), "No se pudo consultar las sesiones."
    filas = r.get("sesiones") or []
    opciones = [(f"{f['dispositivo']} · desde {f['creada']}" + (" (este dispositivo)" if f["actual"] else ""), f["id"])
                for f in filas]
    return gr.update(choices=opciones, value=None), f"{len(filas)} sesión(es) abierta(s)."


def logout(state):
    if state and state.get("token"):
        try:
            requests.post(f"{API_URL}/auth/sesiones", json={"token": state["token"], "cerrar": "esta"},
                          headers=HDR, timeout=10)
        except Exception:  # noqa: BLE001
            pass
    return _error("Sesión cerrada.")[:6] + ("", gr.update(visible=False), gr.update(visible=True))


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
    payload = {"sessionId": state.get("conv") or state["id"], "id_estudiante": state["id"], "nombre": state["nombre"],
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


with gr.Blocks(title="Asistente Académico UNAB") as demo:
    state = gr.State({})
    pendiente = gr.State("")
    token_guardado = gr.BrowserState("", storage_key="unab_sesion",
                                     secret=os.getenv("BROWSER_SECRET", API_TOKEN or "unab-asistente"))

    with gr.Column(visible=True) as cabecera:
        gr.HTML(HEADER)
    with gr.Column(visible=True, elem_id="login", elem_classes="tarjeta") as panel_login:
        gr.HTML("<h2>Inicia sesión</h2><p class='sub'>Ingresa tu nombre completo, tu ID estudiantil y tu carrera.</p>")
        nombre = gr.Textbox(label="Nombre completo", placeholder="Ej: Valentina Rojas Méndez", max_lines=1)
        sid = gr.Textbox(label="ID estudiantil", placeholder="Ej: U00174957", max_lines=1)
        programa = gr.Dropdown(PROGRAMAS, value="Ingeniería de Sistemas", label="Carrera")
        password = gr.Textbox(label="Contraseña", type="password", max_lines=1, visible=False,
                              info="Si es tu primer ingreso, tu contraseña es tu mismo ID.")
        recordar = gr.Checkbox(value=True, label="Mantener la sesión abierta en este dispositivo", visible=False)
        error = gr.Markdown("")
        btn_login = gr.Button("Ingresar", variant="primary", size="lg")
        btn_demo = gr.Button("Entrar con perfil de prueba", size="lg", elem_id="demo-btn", visible=DEMO_HABILITADO)
        with gr.Accordion("Otros usuarios de demostración", open=False):
            gr.Markdown("- **Valentina Rojas Méndez** · U00174957 (estado normal)\n"
                        "- **Andrés Felipe Gómez Pardo** · U00160001 (condicional)\n"
                        "- **Laura Camila Suárez Díaz** · U00160002\n"
                        "- **Santiago Pérez Villamizar** · U00160003 (primer semestre)\n\n"
                        "Si el servidor pide contraseña, la primera vez es el mismo ID.")
        gr.HTML("<p class='nota'>Proyecto académico · datos sintéticos que simulan Banner/COSMOS</p>")

    with gr.Column(visible=False, elem_classes="tarjeta") as panel_cambio:
        gr.HTML("<h2 style='margin:0;font-size:1.1rem'>Crea tu contraseña</h2><p class='sub' style='color:#6B7280'>"
                "Es tu primer ingreso. Por seguridad, cambia la contraseña inicial (tu ID) por una nueva: "
                "mínimo 8 caracteres, con letras y números.</p>")
        pw_nueva1 = gr.Textbox(label="Contraseña nueva", type="password", max_lines=1)
        pw_conf1 = gr.Textbox(label="Repite la contraseña nueva", type="password", max_lines=1)
        msg_cambio1 = gr.Markdown("")
        btn_cambio1 = gr.Button("Guardar y continuar", variant="primary")

    with gr.Column(visible=False, elem_id="panel-chat") as panel_chat:
        with gr.Row(elem_id="appbar", equal_height=True):
            gr.HTML("<div class='marca'><span class='sello'>UNAB</span><span>Asistente Académico</span></div>", padding=False)
            btn_nueva_chat = gr.Button("+ Nueva", size="sm", elem_id="nueva-chat", scale=0)
        with gr.Tabs(selected="chat", elem_id="tabs") as tabs:
            with gr.Tab("Noticias", id="noticias") as tab_noticias:
                filtro_tema = gr.Radio(TEMAS_NOTICIAS, value="Todas", show_label=False, container=False, elem_id="filtro-tema")
                html_noticias = gr.HTML(padding=False)
            with gr.Tab("Historial", id="historial") as tab_historial:
                with gr.Row(elem_id="conv-cabecera"):
                    gr.HTML("<h3>Tus conversaciones</h3>", padding=False)
                    btn_nueva_conv = gr.Button("Nueva conversación", size="sm", variant="primary", elem_id="nueva-conv", scale=0)
                buscar_conv = gr.Textbox(placeholder="Buscar en tus conversaciones (ej. PFU, inglés, matrícula)", show_label=False,
                                         max_lines=1, container=False, elem_id="buscar-conv")
                conv_vacio = gr.HTML(padding=False, elem_id="conv-vacio")
                lista_conv = gr.Radio(choices=[], show_label=False, elem_id="lista-conv", container=False)
            with gr.Tab("Chat", id="chat"):
                chat = gr.Chatbot(elem_id="chat", show_label=False, height="calc(100vh - 330px)", buttons=["copy"],
                                  feedback_options=("Like", "Dislike"),
                                  group_consecutive_messages=False, placeholder=PLACEHOLDER,
                                  avatar_images=(None, os.path.join(os.path.dirname(__file__), "icon.png")))
                gr.HTML("<p id='chips-titulo'>Sugerencias</p>")
                with gr.Row(elem_id="chips"):
                    botones = [gr.Button(e, size="sm") for e, _ in SUGERENCIAS]
                with gr.Row(elem_id="entrada", equal_height=True):
                    msg = gr.Textbox(placeholder="Escribe tu pregunta…", show_label=False, scale=6, max_lines=4,
                                     container=False)
                    enviar = gr.Button("Enviar", variant="primary", scale=0, elem_id="enviar")
            with gr.Tab("Eventos", id="eventos") as tab_eventos:
                with gr.Column(visible=False, elem_classes="tarjeta", elem_id="mis-eventos") as panel_eventos:
                    with gr.Accordion("Agregar un evento personal", open=False):
                        ev_nombre = gr.Textbox(label="Nombre", placeholder="Ej: Parcial de Bases de Datos", max_lines=1)
                        ev_fecha = gr.DateTime(label="Fecha", include_time=False, type="string")
                        ev_desc = gr.Textbox(label="Descripción", placeholder="Opcional: salón, temas, recordatorios…",
                                             lines=2, max_lines=4)
                        ev_msg = gr.Markdown("")
                        ev_guardar = gr.Button("Guardar evento", variant="primary")
                        gr.HTML("<p class='nota' style='text-align:left'>Solo tú puedes ver tus eventos.</p>")
                    with gr.Accordion("Eliminar uno de mis eventos", open=False):
                        ev_lista = gr.Dropdown(label="Mis eventos", choices=[])
                        ev_borrar = gr.Button("Eliminar evento", size="sm")
                html_avisos = gr.HTML(padding=False)
                html_eventos = gr.HTML(padding=False)
            with gr.Tab("Personal", id="personal") as tab_personal:
                ficha = gr.HTML("", padding=False, elem_id="ficha-personal")
                html_resumen = gr.HTML(padding=False)
                sim_codigos = gr.State([])
                with gr.Column(visible=False, elem_classes="tarjeta", elem_id="simulador") as panel_sim:
                    with gr.Accordion("Simulador de notas: ¿qué pasa si...?", open=False):
                        gr.HTML("<p class='nota' style='text-align:left;margin:0'>Mueve cada barra a la nota que esperas sacar "
                                "en tus cursos actuales y mira cómo quedarían tu PGA y tu estado académico.</p>")
                        sim_sliders = [gr.Slider(0, 5, value=3.5, step=0.1, visible=False) for _ in range(MAX_SIM)]
                        btn_simular = gr.Button("Calcular", variant="primary")
                        html_sim = gr.HTML(padding=False)
                html_personal = gr.HTML(padding=False)
                with gr.Column(visible=False, elem_classes="tarjeta") as seguridad:
                    gr.HTML("<h3 style='margin:0'>Seguridad</h3>")
                    with gr.Accordion("Cambiar contraseña", open=False):
                        pw_actual = gr.Textbox(label="Contraseña actual", type="password", max_lines=1)
                        pw_nueva = gr.Textbox(label="Contraseña nueva", type="password", max_lines=1,
                                              info="Mínimo 8 caracteres, con letras y números.")
                        pw_conf = gr.Textbox(label="Repite la contraseña nueva", type="password", max_lines=1)
                        msg_pw = gr.Markdown("")
                        btn_pw = gr.Button("Cambiar contraseña", variant="primary")
                    with gr.Accordion("Sesiones abiertas", open=False):
                        lista_ses = gr.Radio(label="Dispositivos con la sesión abierta", choices=[])
                        msg_ses = gr.Markdown("")
                        with gr.Row():
                            btn_cerrar_una = gr.Button("Cerrar la seleccionada", size="sm")
                            btn_cerrar_otras = gr.Button("Cerrar todas las demás", size="sm")
                btn_logout = gr.Button("Cerrar sesión", size="lg", elem_id="salir")

    salidas = [state, panel_login, panel_chat, ficha, chat, error, token_guardado, panel_cambio, cabecera]
    a_chat = dict(fn=lambda: gr.Tabs(selected="chat"), outputs=tabs)
    btn_login.click(login, [nombre, sid, programa, password, recordar], salidas).then(**a_chat)
    sid.submit(login, [nombre, sid, programa, password, recordar], salidas).then(**a_chat)
    password.submit(login, [nombre, sid, programa, password, recordar], salidas).then(**a_chat)
    btn_demo.click(login_demo, None, salidas).then(**a_chat)
    demo.load(reanudar, token_guardado, salidas + [password, recordar])
    btn_cambio1.click(lambda n, c, st: cambiar_password("", n, c, st), [pw_nueva1, pw_conf1, state],
                      [msg_cambio1, state, panel_cambio, panel_chat])
    for disparador in (enviar.click, msg.submit):
        disparador(agregar_pregunta, [msg, chat, state], [msg, chat, pendiente], queue=False).then(
            responder, [pendiente, chat, state], chat)
    for b, (_, q) in zip(botones, SUGERENCIAS):
        b.click(lambda h, st, q=q: agregar_pregunta(q, h, st), [chat, state], [msg, chat, pendiente], queue=False).then(
            responder, [pendiente, chat, state], chat)
    tab_noticias.select(ver_noticias, [state, filtro_tema], html_noticias)
    filtro_tema.change(ver_noticias, [state, filtro_tema], html_noticias)
    tab_historial.select(lista_conversaciones, [state, buscar_conv], [lista_conv, conv_vacio])
    buscar_conv.submit(lista_conversaciones, [state, buscar_conv], [lista_conv, conv_vacio])
    buscar_conv.change(lambda st, q: lista_conversaciones(st, q) if not q else (gr.update(), gr.update()),
                       [state, buscar_conv], [lista_conv, conv_vacio])
    chat.like(calificar, [state, chat], None)
    lista_conv.input(abrir_conversacion, [lista_conv, state], [chat, state, tabs])
    btn_nueva_conv.click(nueva_conversacion, state, [chat, state, tabs])
    btn_nueva_chat.click(nueva_conversacion, state, [chat, state, tabs])
    tab_eventos.select(ver_eventos, state, [html_eventos, panel_eventos, ev_lista]).then(ver_avisos, state, html_avisos)
    ev_guardar.click(guardar_evento, [ev_nombre, ev_fecha, ev_desc, state],
                     [ev_msg, html_eventos, panel_eventos, ev_lista, ev_nombre, ev_fecha, ev_desc])
    ev_borrar.click(eliminar_evento, [ev_lista, state], [ev_msg, html_eventos, panel_eventos, ev_lista])
    tab_personal.select(ver_personal, state, [html_resumen, html_personal, panel_sim, sim_codigos, html_sim] + sim_sliders).then(
        lambda st: gr.Column(visible=bool(st and st.get("token"))), state, seguridad).then(
        sesiones, state, [lista_ses, msg_ses])
    btn_pw.click(lambda a, n, c, st: cambiar_password(a, n, c, st)[:2], [pw_actual, pw_nueva, pw_conf, state], [msg_pw, state]).then(
        sesiones, state, [lista_ses, msg_ses])
    btn_cerrar_una.click(lambda st, v: sesiones(st, v) if v else (gr.update(), "Selecciona una sesión."),
                         [state, lista_ses], [lista_ses, msg_ses])
    btn_cerrar_otras.click(lambda st: sesiones(st, "otras"), state, [lista_ses, msg_ses])
    btn_simular.click(simular, [state, sim_codigos] + sim_sliders, html_sim)
    btn_logout.click(logout, state, salidas)


if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")),
                        pwa=True, favicon_path=os.path.join(os.path.dirname(__file__), "icon.png"),
                        css=CSS, js=JS_TEMA_CLARO,
                        theme=gr.themes.Soft(primary_hue="orange", secondary_hue="purple", neutral_hue="slate",
                                             font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"]))
