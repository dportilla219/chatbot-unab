#!/usr/bin/env bash
# Configuración interactiva completa. Ejecutar en la EC2:  cd ~/chatbot-unab && bash deploy/configurar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git pull -q || true
[ -f .env ] || cp .env.example .env
IP=$(curl -s https://checkip.amazonaws.com); DOM="$(echo "$IP" | tr . -).sslip.io"
sed -i "s/^DOMINIO_BASE=.*/DOMINIO_BASE=$DOM/" .env
grep -q "^API_TOKEN=cambia-esto" .env && sed -i "s/^API_TOKEN=.*/API_TOKEN=$(openssl rand -hex 24)/" .env
grep -q "^N8N_ENCRYPTION_KEY=cambia-esto" .env && sed -i "s/^N8N_ENCRYPTION_KEY=.*/N8N_ENCRYPTION_KEY=$(openssl rand -hex 24)/" .env
set_var(){ python3 - "$1" "$2" <<'PY'
import sys,re
k,v=sys.argv[1],sys.argv[2]
s=open('.env').read()
s=re.sub(rf'(?m)^{k}=.*$', lambda m:f'{k}={v}', s) if re.search(rf'(?m)^{k}=',s) else s+f'\n{k}={v}\n'
open('.env','w').write(s)
PY
}
echo "== Cadena de conexión de Supabase (Connect > Session pooler, puerto 5432):"
read -r -p "DATABASE_URL: " DBURL; set_var DATABASE_URL "$DBURL"
echo "== API key de Anthropic (no se mostrará al escribir):"
read -r -s -p "ANTHROPIC_API_KEY: " AK; echo; set_var ANTHROPIC_API_KEY "$AK"
echo "Calendario: $(grep ^CALENDARIO_CSV_URL .env | cut -d= -f2-)"
echo ">> 1/5 Base de datos";  bash deploy/cargar_bd.sh
echo ">> 2/5 Contenedores";   sudo docker compose up -d --build
echo ">> Esperando n8n...";   for i in $(seq 1 60); do sudo docker compose exec -T n8n wget -qO- localhost:5678/healthz >/dev/null 2>&1 && break; sleep 5; done
echo ">> 3/5 Workflows n8n";  bash deploy/importar_n8n.sh
echo ">> 4/5 RAG + noticias"; for i in $(seq 1 60); do curl -s localhost:9000/health >/dev/null && break; sleep 5; done; bash deploy/ingestar_rag.sh
echo ">> 5/5 Verificación";   curl -s localhost:9000/health; echo
echo
echo "================ LISTO ================"
echo "n8n : https://n8n.$DOM   (crea tu usuario dueño la primera vez)"
echo "App : https://app.$DOM"
echo "MCP : http://$IP:9000/mcp"
