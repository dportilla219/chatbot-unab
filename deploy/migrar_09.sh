#!/usr/bin/env bash
# Migración 09: calificación de respuestas (útil / no útil). Idempotente; no modifica datos existentes.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
echo ">> Aplicando db/09_calificaciones.sql en Supabase"
psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f db/09_calificaciones.sql
echo ">> Reiniciando el servidor MCP para que detecte la tabla nueva"
docker compose restart mcp
echo ">> Listo. En el chat ya se pueden calificar las respuestas."
