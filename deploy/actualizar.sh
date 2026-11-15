#!/usr/bin/env bash
# Aplica la última versión del repositorio en la EC2 (código, BD, RAG y workflows).
set -euo pipefail
cd "$(dirname "$0")/.."
git pull
set -a; source .env; set +a
echo ">> Migraciones de BD"; for f in db/05_busqueda_hibrida.sql; do psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$f"; done
echo ">> Reconstruyendo servicios"; sudo docker compose up -d --build mcp app
for i in $(seq 1 60); do curl -s localhost:9000/health >/dev/null && break; sleep 5; done
echo ">> Reingesta RAG"; sudo docker compose exec -T mcp python ingesta_rag.py /rag_docs
echo ">> Workflows n8n"; bash deploy/importar_n8n.sh
sleep 15; sudo python3 deploy/n8n_versiones.py | head -3
echo ">> Actualización completa"
