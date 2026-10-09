# The backend and the agent, one image: docker build -t aimail-backend backend/
#   backend: docker run -p 8000:8000 --env-file <env> aimail-backend
#   agent:   docker run --env-file <env> -e APP=email_agent:app -e PORT=8001 aimail-backend
# Configuration comes from the environment only (AIMAIL_ENV_FILE is empty, so no .env is read). Outside
# dev, startup refuses a missing AGENT_TOKEN, so the agent cannot be reached without it once it leaves
# loopback. Apply migrations from the same image: python scripts/migrate.py.
# The category model is committed and copied in; the priority model is not (trained, not committed), so mount
# it at /app/models if it is needed.

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AIMAIL_ENV_FILE="" LOG_FORMAT=json \
    APP=app.main:app PORT=8000
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY app ./app
COPY email_agent.py gemini_client.py local_client.py model_gateway.py model_runtime.py ./
COPY scripts/migrate.py ./scripts/
COPY models/category-classifier.joblib ./models/
RUN useradd --uid 10001 --no-create-home aimail
USER aimail
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=2)"
# exec, so uvicorn is PID 1 and gets the stop signal for a graceful shutdown.
CMD exec uvicorn "$APP" --host 0.0.0.0 --port "$PORT" --no-access-log
