#!/usr/bin/env bash
# Migración 08: columnas fuente y tema en las noticias. Idempotente.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
echo ">> Aplicando db/08_noticias_fuentes.sql en Supabase"
psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f db/08_noticias_fuentes.sql
docker compose restart mcp
echo ">> Listo."
