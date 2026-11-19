#!/usr/bin/env bash
# Crea el esquema, vistas y datos sintéticos en Supabase usando DATABASE_URL del .env
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
for f in db/01_schema.sql db/02_views.sql db/03_seed.sql db/04_calendario.sql db/05_busqueda_hibrida.sql db/06_perfil_y_acceso.sql db/07_eventos_personales.sql; do
  echo ">> $f"
  psql "$DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$f"
done
echo ">> Verificación"
psql "$DATABASE_URL" -c "SELECT estado_academico, COUNT(*) FROM academico.v_resumen_estudiante GROUP BY 1;"
