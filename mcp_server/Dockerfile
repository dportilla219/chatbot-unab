FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 EMBED_CACHE=/models PORT=9000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
# Descarga el modelo de embeddings en la imagen (evita demoras en el primer uso)
RUN python -c "from embeddings import embed; embed(['precarga del modelo'])" || echo "modelo se descargará en el primer uso"
EXPOSE 9000
CMD ["python", "server.py"]
