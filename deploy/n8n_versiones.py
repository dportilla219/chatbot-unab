"""Muestra qué versión del workflow principal está publicada en n8n y, con --activar, publica la última importada.
Uso:  sudo python3 deploy/n8n_versiones.py            (solo diagnóstico)
      sudo python3 deploy/n8n_versiones.py --activar  (detiene n8n, activa la última versión y lo arranca)
"""
import glob, json, sqlite3, subprocess, sys, os
WID = "unabChatPrincip1"
db = (glob.glob('/var/lib/docker/volumes/*n8n_data/_data/database.sqlite') or [None])[0]
if not db: sys.exit("No encontré la base de datos de n8n")
def estado():
    c = sqlite3.connect(db)
    w = c.execute("SELECT versionId, activeVersionId, active, nodes FROM workflow_entity WHERE id=?", (WID,)).fetchone()
    print("workflow_entity -> versionId:", w[0], "| activeVersionId:", w[1], "| active:", w[2])
    print("   nodos actuales incluyen 'Guardrails (PII + palabras clave)':", 'Guardrails (PII + palabras clave)' in w[3])
    hist = c.execute("SELECT versionId, createdAt, nodes FROM workflow_history WHERE workflowId=? ORDER BY createdAt", (WID,)).fetchall()
    for v, t, n in hist:
        print("   historia:", v, t, "| nueva:", 'Guardrails (PII + palabras clave)' in n, "| ACTIVA" if v == w[1] else "")
    return c, w, hist
c, w, hist = estado()
if "--activar" in sys.argv:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    subprocess.run(["docker", "compose", "stop", "n8n"], check=True)
    c = sqlite3.connect(db)
    cur_nodes, cur_conn = c.execute("SELECT nodes, connections FROM workflow_entity WHERE id=?", (WID,)).fetchone()
    nuevo = [h for h in hist if 'Guardrails (PII + palabras clave)' in h[2]]
    if nuevo:
        vid = nuevo[-1][0]
    else:  # crea una entrada de historia con los nodos actuales
        import uuid, datetime
        vid = str(uuid.uuid4()); now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.000')
        c.execute("INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections) VALUES (?,?,?,?,?,?,?)",
                  (vid, WID, 'importar', now, now, cur_nodes, cur_conn))
    hn, hc = c.execute("SELECT nodes, connections FROM workflow_history WHERE versionId=?", (vid,)).fetchone()
    c.execute("UPDATE workflow_entity SET versionId=?, activeVersionId=?, active=1, nodes=?, connections=? WHERE id=?", (vid, vid, hn, hc, WID))
    c.commit(); c.close()
    subprocess.run(["docker", "compose", "start", "n8n"], check=True)
    print("\n>> Activada la versión", vid); estado()
