FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py README.md ./

ENV SHELLY_HOST="" \
    SHELLY_PROTOCOL="http" \
    SHELLY_PORT="" \
    LISTEN_ADDRESS="0.0.0.0" \
    LISTEN_PORT="8000"

EXPOSE 8000

CMD ["python", "exporter.py"]
