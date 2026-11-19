#!/usr/bin/env bash
# Migración 06: profesores, certificados (inglés y externos), contraseñas y sesiones guardadas.
# Es idempotente: si se corre dos veces no duplica datos. La contraseña inicial de cada estudiante es su ID.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
echo ">> Aplicando db/06_perfil_y_acceso.sql en Supabase"
psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f db/06_perfil_y_acceso.sql
echo ">> Reiniciando el servidor MCP para que detecte las tablas nuevas"
docker compose restart mcp
echo ">> Listo. Desde ahora la app pide contraseña (la primera vez es el mismo ID) y recuerda las sesiones."
