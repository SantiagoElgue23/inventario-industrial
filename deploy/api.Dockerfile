FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY alembic.ini .
COPY backend backend

RUN useradd --system --no-create-home inventario
USER inventario

# Aplica las migraciones pendientes y arranca la API.
# --proxy-headers: solo Caddy llega a este puerto (no se publica en el servidor).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
