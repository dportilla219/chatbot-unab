"""Servidor que imita la API Messages de Anthropic para probar los workflows de n8n sin API key.
Heurísticas:
  - Guardrails (system menciona 'flagged')        -> {"confidenceScore":..,"flagged":..}
  - Text Classifier (pide clasificar en categorías) -> JSON con la categoría por palabras clave
  - Agente con herramientas                       -> 1ª vuelta: tool_use; 2ª vuelta: texto con el resultado
Uso: python mock_anthropic.py  (puerto 5690)  y en la credencial Anthropic de n8n: Base URL http://localhost:5690
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = open("/tmp/mock_anthropic.log", "a")


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(c.get("text", "") if c.get("type") == "text" else json.dumps(c.get("content", ""))[:3000]
                    for c in content)


def clasificar(t):
    t = t.lower()
    if re.search(r"fecha|cu[aá]ndo|calendario|inscripci|inicio de clases|prueba diagn", t):
        return "calendario"
    if re.search(r"noticia|nuevo|convocatoria|novedad|certificaci", t):
        return "noticias"
    if re.search(r"mi |mis |he tomado|debo tomar|me faltan|avance|matr[ií]cula|proyecci|semestres", t):
        return "historial_personal"
    if re.search(r"jailbreak|hackea|insulto", t):
        return "manipulacion"
    if re.search(r"receta|f[uú]tbol|chiste|clima", t):
        return "fuera_de_alcance"
    return "consulta_general"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system = body.get("system", "")
        system = system if isinstance(system, str) else " ".join(s.get("text", "") for s in system)
        msgs = body.get("messages", [])
        last = msgs[-1] if msgs else {"content": ""}
        user_text = text_of(last.get("content", ""))
        tools = body.get("tools") or []
        LOG.write(json.dumps({"system": system[:300], "user": user_text[:300], "tools": [t["name"] for t in tools]}) + "\n")
        LOG.flush()
        allt = system + " " + " ".join(text_of(m.get("content", "")) for m in msgs)
        if '"flagged"' in allt or "flagged" in system:
            bad = bool(re.search(r"ignora (todas )?las instrucciones|ignore (all )?previous|modo desarrollador|jailbreak", user_text, re.I))
            out = json.dumps({"confidenceScore": 0.95 if bad else 0.05, "flagged": bad})
        elif "classify" in allt.lower() or "categor" in system.lower() and not tools:
            q = re.findall(r"(?s)(?:Text to classify|text)[:\s]*(.*)$", user_text)
            out = json.dumps({"categories": {clasificar(user_text): True}}) if False else None
            cats = ["consulta_general", "calendario", "historial_personal", "noticias", "fuera_de_alcance", "manipulacion", "fallback"]
            c = clasificar(user_text)
            out = json.dumps({k: (k == c) for k in cats})
        elif tools and not any(isinstance(m.get("content"), list) and any(x.get("type") == "tool_result" for x in m["content"]) for m in msgs[-1:]):
            names = [t["name"] for t in tools]
            sid = (re.findall(r"U\d{8}", allt) or ["U00174957"])[-1]
            pick, args = None, {}
            for n in names:
                if "proyeccion" in n and re.search(r"debo tomar|me faltan|proyecci|recomend", allt.lower()):
                    pick, args = n, {"id_estudiante": sid}
            if not pick:
                for n in names:
                    if "buscar_reglamento" in n:
                        pick, args = n, {"pregunta": user_text[-200:], "k": 3}
            if not pick:
                pick, args = names[0], {"id_estudiante": sid}
            return self.reply({"type": "tool_use", "id": "toolu_mock1", "name": pick, "input": args}, "tool_use")
        else:
            out = "Respuesta simulada (mock) basada en el contexto: " + user_text[-700:]
        return self.reply({"type": "text", "text": out}, "end_turn")

    def reply(self, block, stop):
        resp = {"id": "msg_mock", "type": "message", "role": "assistant", "model": "mock",
                "content": [block], "stop_reason": stop, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10}}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 5690), H).serve_forever()
