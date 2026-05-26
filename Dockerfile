# TinyTastes AI — Pediatric Nutritionist Engine
# Uses DeepSeek API (OpenAI-compatible) — no Ollama sidecar needed.
# Required env vars:
#   DEEPSEEK_API_KEY  — your DeepSeek API key
# Optional:
#   DEEPSEEK_MODEL    — override model (default: deepseek-chat)
#   DB_PATH           — SQLite path (default: tinytastes_core.db)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY tinytastes_core.db .

EXPOSE 8000

ENV DEEPSEEK_MODEL=deepseek-chat

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
