FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api ./services/api
COPY data ./data

ENV PYTHONPATH=/app/services/api \
    PYTHONUNBUFFERED=1 \
    APTURA_API_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
