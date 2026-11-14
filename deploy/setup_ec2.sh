#!/usr/bin/env bash
# Prepara una instancia Ubuntu 24.04 en EC2: swap, Docker, firewall y arranque del stack.
set -euo pipefail
echo ">> Swap de 2 GB (útil en instancias de 1-2 GB de RAM)"
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
echo ">> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
echo ">> Dominio sslip.io"
IP=$(curl -s https://checkip.amazonaws.com)
DOM="$(echo "$IP" | tr . -).sslip.io"
[ -f .env ] || cp .env.example .env
sed -i "s/^DOMINIO_BASE=.*/DOMINIO_BASE=$DOM/" .env
grep -q "cambia-esto" .env && sed -i "s/^API_TOKEN=.*/API_TOKEN=$(openssl rand -hex 24)/; s/^N8N_ENCRYPTION_KEY=.*/N8N_ENCRYPTION_KEY=$(openssl rand -hex 24)/" .env
echo ">> Edita .env para poner DATABASE_URL (Supabase) y CALENDARIO_CSV_URL, luego ejecuta:"
echo "   sudo docker compose up -d --build"
echo ">> URLs:"
echo "   n8n : https://n8n.$DOM"
echo "   App : https://app.$DOM"
echo "   MCP : http://$IP:9000/mcp   y   https://mcp.$DOM/mcp"
