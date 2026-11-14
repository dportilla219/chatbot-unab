"""Muestra el detalle de las últimas ejecuciones de n8n (nodo que falló y mensaje).
Uso en la EC2:  sudo python3 deploy/ultimo_error.py [cantidad]
"""
import json, sqlite3, sys, glob
db = (glob.glob('/var/lib/docker/volumes/*n8n_data/_data/database.sqlite') or [None])[0]
if not db:
    sys.exit("No encontré la base de datos de n8n")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
rows = c.execute("""SELECT e.id, e.status, w.name, d.data FROM execution_entity e
                    JOIN execution_data d ON d.executionId = e.id
                    LEFT JOIN workflow_entity w ON w.id = e.workflowId
                    ORDER BY e.id DESC LIMIT ?""", (n,)).fetchall()
for eid, status, wname, raw in rows:
    arr = json.loads(raw)
    def rev(v, seen):
        if isinstance(v, str) and v.isdigit() and int(v) not in seen:
            return walk(arr[int(v)], seen | {int(v)})
        return v
    def walk(o, seen):
        if isinstance(o, dict): return {k: rev(v, seen) for k, v in o.items()}
        if isinstance(o, list): return [rev(v, seen) for v in o]
        return o
    rd = walk(arr[0], {0}).get('resultData', {})
    print(f"\n=== Ejecución {eid} | {status} | {wname} | último nodo: {rd.get('lastNodeExecuted')}")
    if rd.get('error'):
        e = rd['error']
        print("ERROR:", e.get('message'), "|", str(e.get('description'))[:800])
    for name, runs in (rd.get('runData') or {}).items():
        e = runs[-1].get('error')
        print(f" - {name}" + (f"  <-- ERROR: {e.get('message')} | {str(e.get('description'))[:600]}" if e else ""))
