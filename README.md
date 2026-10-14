# polizas-api

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas y los siniestros
que se les declaran, resume la cartera y puntúa el riesgo de cada póliza con un modelo, guardando
cada predicción.

Versión corregida de `polizas-api-v0` (Taller del Corte II). Qué estaba mal y cómo se corrigió:
[`HALLAZGOS.md`](HALLAZGOS.md).

## Puesta en marcha local

Requiere Python 3.11.

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # y cambien SECRETO_FIRMA y CLAVE_API_REASEGURO
alembic upgrade head                # crea el esquema en la base de DATABASE_URL
uvicorn main:app --host 127.0.0.1 --port 8000
```

```bash
curl localhost:8000/health          # {"estado":"ok","base_datos":true}
```

La aplicación **no crea tablas al arrancar**: el esquema lo crea `alembic upgrade head`. Si se
cambian los modelos, se genera una revisión nueva con
`alembic revision --autogenerate -m "..."`. No se usa `--reload`: es para desarrollo y no va en
el comando de arranque.

### Configuración

Se lee del entorno y de `.env` (`config.Settings`); `.env` no se versiona.

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | `sqlite:///app.db` | Base de datos de la aplicación y de Alembic |
| `SECRETO_FIRMA` | *(vacío)* | Secreto con el que se firma cada póliza (`token_firma`, interno) |
| `CLAVE_API_REASEGURO` | *(vacío)* | Clave del servicio de reaseguro |
| `RUTA_MODELO` | `modelo.pkl` | Modelo serializado que usa `/score` |
| `UMBRAL_ALTO_RIESGO` | `0.6` | Puntaje por encima del cual una póliza es de alto riesgo |

## En contenedor

```bash
docker build -t polizas-api .
docker run -d --name polizas -p 8000:8000 polizas-api
curl localhost:8000/health
```

La imagen es multietapa sobre `python:3.11.9-slim-bookworm`, corre con el usuario `app` (no root)
y no contiene `.env` ni ninguna base de datos. Al arrancar aplica `alembic upgrade head` sobre
`DATABASE_URL=sqlite:////app/data/app.db` y luego levanta `uvicorn` en `0.0.0.0:8000`. El
`HEALTHCHECK` consulta `/health` y exige que la base responda. Los secretos se pasan al ejecutar,
por ejemplo con `docker run --env-file .env -e DATABASE_URL=sqlite:////app/data/app.db ...`.

### Qué pasa con los datos

- **`docker restart polizas`**: los datos **siguen**. Es el mismo contenedor y su capa de escritura,
  donde vive `/app/data/app.db`, no se borra al reiniciar.
- **`docker rm -f polizas` y un `docker run` nuevo desde la misma imagen**: los datos **se pierden**.
  El contenedor nuevo arranca con una capa de escritura vacía, la imagen no trae base de datos y
  `alembic upgrade head` crea un esquema vacío.
- Para que sobrevivan al contenedor hay que montar un volumen en `/app/data`:

```bash
docker run -d --name polizas -p 8000:8000 -v polizas-datos:/app/data polizas-api
```

## Endpoints

| Método | Ruta | Respuesta |
|---|---|---|
| POST | `/polizas` | 201 con la póliza creada · 409 si el número ya existe · 422 si la entrada es inválida |
| GET | `/polizas` | 200, cada póliza con sus siniestros |
| GET | `/polizas/{id}` | 200 · 404 si no existe |
| PUT | `/polizas/{id}` | 200 con la póliza actualizada · 404 · 422; **parcial**: solo cambia lo enviado |
| POST | `/polizas/{id}/siniestros` | 201 · 404 si la póliza no existe · 422 |
| GET | `/siniestros` | 200, cada siniestro con el número de su póliza |
| GET | `/resumen` | 200, número de siniestros y monto total por póliza |
| POST | `/score` | 200 con `numero`, `puntaje` en [0, 1] y `alto_riesgo` · 404 · 422; registra la predicción |
| GET | `/predicciones` | 200, cada predicción con el `numero` de su póliza y su `puntaje` |
| GET | `/health` | 200 con `{"estado": ..., "base_datos": true/false}` |

### Ejemplo

```bash
curl -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
```

```bash
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-2026-09001"}'
```

## Pruebas

```bash
pytest                              # todas: tests/test_contrato.py, test_api.py y test_ia_corregido.py
```

Los tests propios (`tests/conftest.py`) sustituyen `database.get_db` con
`app.dependency_overrides` por una sesión sobre una SQLite temporal, así que `app.db` no cambia
y `pytest` da lo mismo si se corre dos veces seguidas. `tests/test_contrato.py` es la batería del
taller y no se modifica.

## Utilidades y entregables del taller

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API.
- `contar_consultas.py` cuenta las sentencias SQL de cada endpoint y escribe `CONSULTAS.csv` (Parte C).
- `python verificar_entrega.py` comprueba la forma de la entrega.
- `HALLAZGOS.md` (Partes A y C), `CONSULTAS.csv`, `DICTAMEN_IA.md` (Parte D), `BITACORA_IA.md`
  (Parte E) y `EQUIPO.md`.
