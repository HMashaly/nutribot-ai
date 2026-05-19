FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python rag/ingest.py || echo "RAG ingest skipped (no OPENAI_API_KEY at build time)"
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
