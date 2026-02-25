FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    SM_DB_PATH=/data/storage_manager.db \
    SM_CHECK_INTERVAL_SECONDS=300 \
    SM_API_PORT=9100 \
    SM_LOG_LEVEL=INFO

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src

EXPOSE 9100

CMD ["python", "-m", "src.app"]
