#!/usr/bin/env bash
# Importa credenciales (Supabase + Anthropic) y los 3 workflows en n8n, y publica el principal.
# Requiere en .env: DATABASE_URL y ANTHROPIC_API_KEY
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${ANTHROPIC_API_KEY:?Falta ANTHROPIC_API_KEY en .env}"
# postgresql://USER:PASS@HOST:PORT/DB
re='^postgres(ql)?://([^:]+):([^@]+)@([^:/]+):?([0-9]*)/(.*)$'
[[ "$DATABASE_URL" =~ $re ]] || { echo "DATABASE_URL con formato inesperado"; exit 1; }
PGUSER="${BASH_REMATCH[2]}"; PGPASSWORD="${BASH_REMATCH[3]}"; PGHOST="${BASH_REMATCH[4]}"; PGPORT="${BASH_REMATCH[5]:-5432}"; PGDB="${BASH_REMATCH[6]%%\?*}"
TMP=$(mktemp)
python3 - "$TMP" <<PY
import json,sys
cred=[{"id":"supabaseUnab01","name":"Supabase UNAB","type":"postgres",
       "data":{"host":"$PGHOST","database":"$PGDB","user":"$PGUSER","password":"$PGPASSWORD","port":int("$PGPORT"),"ssl":"require","allowUnauthorizedCerts":True}},
      {"id":"anthropicUnab01","name":"Anthropic Claude","type":"anthropicApi","data":{"apiKey":"$ANTHROPIC_API_KEY","url":"https://api.anthropic.com"}}]
json.dump(cred,open(sys.argv[1],"w"))
PY
C=$(sudo docker compose ps -q n8n)
sudo docker cp "$TMP" "$C":/tmp/creds.json && rm -f "$TMP"
sudo docker cp n8n/workflows "$C":/tmp/workflows
sudo docker compose exec -T n8n n8n import:credentials --input=/tmp/creds.json
sudo docker compose exec -T n8n sh -c 'rm -f /tmp/creds.json'
for f in 00_principal_ruteo_agente.json 01_rag_ingesta_embeddings.json 04_scraper_noticias.json; do
  sudo docker compose exec -T n8n n8n import:workflow --input=/tmp/workflows/$f
done
sudo docker compose exec -T n8n n8n publish:workflow --id=unabChatPrincip1
sudo docker compose exec -T n8n n8n publish:workflow --id=unabScraperNews1
sudo docker compose restart n8n
echo ">> Listo. Abre https://n8n.$DOMINIO_BASE , crea tu usuario y revisa los workflows."
