FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=7860 GRADIO_ANALYTICS_ENABLED=False
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py icon.png ./
EXPOSE 7860
CMD ["python", "app.py"]
