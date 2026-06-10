#!/bin/sh
set -e

if [ "${RUN_RAG_INGEST:-0}" = "1" ]; then
  python rag/ingest.py
fi

if [ "${RUN_OFFERS_INGEST:-0}" = "1" ]; then
  python offers/ingest.py
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
