FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && groupadd --gid 10001 voicegen && useradd --uid 10001 --gid 10001 --no-create-home voicegen
COPY production ./production
COPY alembic ./alembic
COPY alembic.ini ./
COPY deploy/logging_config.py ./ops_logging.py
COPY deploy/logging.json ./logging.json
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "production.app:create_app", "--factory", "--log-config", "/app/logging.json", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
