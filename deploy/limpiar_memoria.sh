#!/usr/bin/env bash
# Borra el historial de conversaciones de la memoria persistente (tabla n8n_chat_histories).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
psql "$DATABASE_URL" -c "TRUNCATE public.n8n_chat_histories RESTART IDENTITY;" && echo ">> Memoria del chat borrada"
