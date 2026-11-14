#!/usr/bin/env bash
# Ingesta RAG por script (equivalente al workflow 'RAG Ingesta y embeddings' de n8n)
set -euo pipefail
cd "$(dirname "$0")/.."
sudo docker compose exec -T mcp python ingesta_rag.py /rag_docs
sudo docker compose exec -T mcp python scraper.py
