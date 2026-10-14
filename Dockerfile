# --- Etapa 1: construir el entorno con las dependencias ----------------------
FROM python:3.11.9-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements.txt

# --- Etapa 2: imagen final, solo con el entorno y el código del servicio -----
FROM python:3.11.9-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/data/app.db

RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini config.py database.py esquemas.py main.py modelos.py modelo.pkl ./
COPY alembic ./alembic
# La base vive en /app/data: es lo único escribible por el usuario app, y es
# lo que se monta como volumen si los datos deben sobrevivir al contenedor.
RUN mkdir /app/data && chown app:app /app/data

USER app
EXPOSE 8000

# slim no trae curl: el chequeo usa Python y exige que /health diga que la base responde.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import json, sys, urllib.request; r = json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)); sys.exit(0 if r['base_datos'] else 1)"

# Aplica las migraciones sobre la base (vacía la primera vez) y arranca sin --reload.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
