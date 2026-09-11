FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TEMPORAL_ADDRESS=temporal:7233 \
    TEMPORAL_NAMESPACE=default \
    TEMPORAL_TASK_QUEUE=keep-ops \
    TEMPORAL_WORKER_ROOT=/data \
    PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Sample directory the demo workflow can list; zip output lands in /data/output
RUN mkdir -p /data/sample /data/output \
    && echo "hello from temporal-worker sample" > /data/sample/readme.txt \
    && echo "alpha" > /data/sample/a.txt \
    && echo "beta" > /data/sample/b.txt

CMD ["python", "-m", "app.worker"]
