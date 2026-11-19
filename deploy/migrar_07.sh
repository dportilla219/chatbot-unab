#!/usr/bin/env bash
# Migración 07: tabla de eventos personales. Idempotente; no modifica datos existentes.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
echo ">> Aplicando db/07_eventos_personales.sql en Supabase"
psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f db/07_eventos_personales.sql
echo ">> Reiniciando el servidor MCP para que detecte la tabla nueva"
docker compose restart mcp
echo ">> Listo. En la pestaña Eventos ya se pueden agregar eventos personales."
