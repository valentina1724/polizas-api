# Hallazgos — Parte A

**Grupo:** <número> · **Integrantes:** Dylan Andrés Fajardo, Valentina Huertas Quesada, Juan Manuel Molina Ortiz

> Todas las evidencias se tomaron sobre la etiqueta `v0-semilla` (commit `5a5cc5b`) con el
> servicio levantado con `uvicorn main:app --port 8000` y la `app.db` tal como viene en el
> semilla. Los comandos se ejecutaron **en el orden de la tabla**: el de H10 deja inservible la
> sesión compartida del semilla, así que va el último de los que hablan con el servicio
> (H11 a H14 leen archivos y no lo necesitan). Los que crean pólizas usan `$(date +%N)` en el
> número para poder repetirse sin chocar con el `UNIQUE`.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | `POST /polizas` crea la póliza y responde 200, no 201 | La ruta no declara `status_code=201` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-H1-$(date +%N)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}"` | `200` | `status_code=status.HTTP_201_CREATED` en `POST /polizas` y en `POST /polizas/{id}/siniestros` |
| H2 | Las respuestas exponen `token_firma`, un hash del secreto de firma | Las rutas devuelven diccionarios armados a mano (`_poliza`) que copian todas las columnas; no hay `response_model` que filtre | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| grep -o '"token_firma"'` | `"token_firma"` | `response_model=PolizaSalida` en todas las rutas de pólizas; el esquema de salida no tiene `token_firma` |
| H3 | Una póliza que no existe responde 200 con un cuerpo `{"error": ...}` | Las rutas hacen `return {"error": ...}` en vez de lanzar `HTTPException(404)`; igual en `PUT /polizas/{id}` y `POST /score` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w " %{http_code}" localhost:8000/polizas/999999` | `{"error":"no existe la póliza 999999"} 200` | `_poliza_o_404` lanza `HTTPException(404)`; `/score` también da 404 si el número no existe |
| H4 | Se acepta un siniestro de una póliza que no existe (200) y desde ese momento `GET /siniestros` da 500 | La ruta no comprueba la póliza y SQLite no aplica las claves foráneas sin `PRAGMA foreign_keys=ON`: queda una fila huérfana con `poliza=None` | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d '{"fecha":"2026-03-02","monto":850000,"descripcion":"Choque leve"}'; curl -s -o /dev/null -w "%{http_code}" localhost:8000/siniestros` | `200 500` | 404 si la póliza no existe y `PRAGMA foreign_keys=ON` en cada conexión (`database.crear_engine`) |
| H5 | Un `PUT` que solo cambia la prima borra `tipo`, `asegurado` y `fecha_fin` | `datos.model_dump()` incluye los campos no enviados con valor `None` y se copian todos a la póliza | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -X PUT localhost:8000/polizas/2 -H "Content-Type: application/json" -d '{"prima":999000}' \| grep -o '"tipo":[a-z"]*'` | `"tipo":null` | `model_dump(exclude_unset=True, exclude_none=True)`: solo se toca lo que llega; además se valida que `fecha_fin` siga siendo posterior al inicio |
| H6 | El asegurado se guarda como `null` aunque se envíe | El `field_validator` `normalizar_asegurado` calcula el nombre normalizado pero no lo devuelve: retorna `None` | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-H6-$(date +%N)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}" \| grep -o '"asegurado":[a-z"]*'` | `"asegurado":null` | El validador hace `return`; la columna pasa a `NOT NULL` |
| H7 | Se acepta una póliza con `fecha_fin` anterior a `fecha_inicio` | `PolizaEntrada` no tiene ninguna regla que relacione las dos fechas | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-H7-$(date +%N)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2027-01-14\",\"fecha_fin\":\"2026-01-15\"}"` | `200` | `model_validator(mode="after")` que exige `fecha_fin > fecha_inicio` (422) y `CheckConstraint` en la tabla |
| H8 | Se acepta una póliza con un siniestro anidado de monto negativo | `siniestros` está tipado como `list[dict]`: Pydantic no valida su contenido y la ruta lo copia con `s.get(...)` | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-H8-$(date +%N)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\",\"siniestros\":[{\"fecha\":\"2026-03-02\",\"monto\":-50,\"descripcion\":\"Choque leve\"}]}"` | `200` | `siniestros: list[SiniestroEntrada]` (con `monto > 0` y `estado` cerrado); `tipo` también pasa a `Literal` |
| H9 | `GET /predicciones` no dice de qué póliza es cada predicción: no trae `numero` | La ruta arma el diccionario solo con `poliza_id`; no usa la relación `Prediccion.poliza` | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `curl -s -o /dev/null -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero":"POL-2026-00001"}'; curl -s localhost:8000/predicciones \| grep -c '"numero"'` | `0` | `PrediccionSalida` incluye `numero` (propiedad sobre la relación), cargada con `joinedload(Prediccion.poliza)` |
| H10 | Un número de póliza repetido da 500 y, después, **todo** el servicio responde 500 | Hay una única sesión de módulo (`database.sesion`) compartida por todas las peticiones: el `IntegrityError` la deja en estado de rollback pendiente y nadie la repara | M8 · 4. Inyección de dependencias con Depends | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-00001","asegurado":"Ana Rueda","tipo":"auto","prima":1250000,"fecha_inicio":"2026-01-15","fecha_fin":"2027-01-14"}'; curl -s -o /dev/null -w "%{http_code}" localhost:8000/polizas` | `500 500` | Sesión por petición (`database.get_db` con `yield` y `Depends`); el `IntegrityError` hace `rollback` y responde 409 |
| H11 | La aplicación ignora `DATABASE_URL` y los secretos están escritos en el código | `config.py` define constantes: la URL de la base, `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` están cableados y versionados | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `echo $(DATABASE_URL=sqlite:///otra.db python -c "import database; print(database.engine.url)") $(grep -cE "^(SECRETO_FIRMA\|CLAVE_API_REASEGURO) = " config.py)` | `sqlite:///app.db 2` | `Settings(BaseSettings)` que lee `.env` y el entorno, entregada por `get_settings()` con `lru_cache` e inyectada con `Depends`; `.env.example` sin secretos reales |
| H12 | El entorno no es reproducible: dependencias sin versión y la base de datos versionada | `requirements.txt` no fija ninguna versión, `app.db` está en el índice y `.gitignore` solo cubre `*.pyc` (ni `.env` ni `*.db` ni el entorno virtual) | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `echo $(git ls-files "*.db") $(grep -c "==" requirements.txt) $(grep -c "^\.env" .gitignore)` | `app.db 0 0` | Versiones fijadas con `==`, `git rm --cached app.db` y `.gitignore` con `.env`, `*.db`, `venv/` y cachés |
| H13 | La imagen no sirve para producción ni responde desde el host | `FROM python:latest` (sin fijar), `--reload` y `--host 127.0.0.1` en el `CMD` (dentro del contenedor no se alcanza desde fuera), una sola etapa, sin `USER` ni `HEALTHCHECK`, y `COPY . .` mete `app.db` en la imagen | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `grep -oE "python:latest\|--reload\|127\.0\.0\.1\|USER\|HEALTHCHECK" Dockerfile \| paste -sd " " -` | `python:latest --reload 127.0.0.1` | Multietapa sobre `python:3.11.9-slim-bookworm`, `.dockerignore`, usuario `app`, `HEALTHCHECK` contra `/health`, `CMD` sin `--reload` con `--host 0.0.0.0` |
| H14 | El esquema se crea con `create_all` al importar la aplicación y no hay migraciones | `main.py` ejecuta `Base.metadata.create_all(engine)` en el arranque y no existe `alembic/`: un cambio de modelo no tiene forma versionada de llegar a una base existente | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `echo $(grep -c "create_all" main.py) $(ls -d alembic 2>/dev/null \|\| echo sin-alembic)` | `1 sin-alembic` | `alembic/` con la revisión `5c49a08b1389`; `env.py` toma `DATABASE_URL` de `get_settings()`; `create_all` sale del arranque |

**Otros defectos que se corrigieron y no tienen fila** (el máximo es 14):

- **No existía `GET /health`** (respondía 404). Se creó: hace `SELECT 1` y responde
  `{"estado": "ok", "base_datos": true}`. Lo pedía el contrato, por eso no se cuenta como hallazgo.
- **`tests/test_api.py` escribía en `app.db`** y fallaba la segunda vez (número fijo repetido).
  Ahora usa la fixture `cliente` de `tests/conftest.py`, que sustituye `database.get_db` sobre una
  base temporal.
- **N+1 en `/polizas`, `/siniestros` y `/resumen`**: se trata en la Parte C.
- **El README recomendaba `--reload` en producción** y decía que las claves estaban en `config.py`
  «para no configurar nada». Se reescribió con el arranque real.

**`contar_consultas.py` no se modificó.** `CONSULTAS.csv` es su salida, a la que solo se le
rellenó la columna `estrategia`.

---

# Parte C — Interpretación de las consultas

> Conteos obtenidos con `python contar_consultas.py` (10 y 2000 pólizas, 3 siniestros cada una).
> Para contrastar, se cambió **temporalmente** la estrategia de cada endpoint en una copia del
> código y se volvió a correr el mismo script; esos números («alternativa») no están en el CSV.

| Endpoint | Estrategia en el código | 10 pólizas | 2000 pólizas | Alternativa medida | 10 | 2000 |
|---|---|---:|---:|---|---:|---:|
| `/polizas` | `selectinload` | 2 | 5 | `lazy` | 11 | 2001 |
| `/polizas/{id}` | `lazy` | 2 | 2 | `selectinload` | 2 | 2 |
| `/siniestros` | `joinedload` | 1 | 1 | `lazy` | 11 | 2001 |
| `/resumen` | `agregada` | 1 | 1 | `joinedload` (contar en Python) | 1 | 1 |

## `/polizas`

Estrategia: **`selectinload(Poliza.siniestros)`**. Con 10 pólizas salen 2 consultas: un `SELECT`
de pólizas y un `SELECT ... WHERE siniestros.poliza_id IN (...)` con los 10 ids. Con 2000 salen 5,
no 2: SQLAlchemy parte la lista del `IN` en lotes de 500 ids, así que son 1 + ⌈2000/500⌉ = 1 + 4.
El número crece con el tamaño, pero a saltos de 500 y no de uno en uno. Con `lazy` (la carga por
defecto) medimos 11 y 2001: una consulta por póliza al serializar sus siniestros, el N+1 de
manual. `joinedload` también daría pocas consultas, pero repetiría las columnas de cada póliza
en cada una de sus 3 filas de siniestros. Con una colección uno a muchos, `selectinload` trae
cada fila una sola vez.

## `/polizas/{id}`

Estrategia: **`lazy`**, a propósito. Salen 2 consultas con 10 y con 2000 pólizas: `db.get` trae
la póliza y, al serializar, el acceso a `poliza.siniestros` lanza una consulta por los siniestros
de esa póliza. Esto incumple la regla de «cargar todo de una vez», pero al medir `selectinload`
también da 2: una consulta por la póliza y otra por sus hijos. El N+1 aparece cuando se recorre una
colección de padres. Aquí hay un solo padre, así que el «+N» vale 1 y no depende del tamaño de la
cartera. Esto nos sorprendió: esperábamos que `selectinload` ahorrara algo, y medido no cambia
nada. Por eso se dejó la forma más simple.

## `/siniestros`

Estrategia: **`joinedload(Siniestro.poliza)`**. Sale 1 consulta con 10 y con 2000. La relación es
muchos a uno: cada siniestro tiene exactamente una póliza, así que el `JOIN` le añade a cada fila
las columnas de su póliza sin multiplicar filas. Con `lazy` medimos 11 y 2001: no 1 + 30 ni
1 + 6000, porque el identity map de la sesión reutiliza la póliza ya cargada y solo se consulta
una vez por póliza distinta. Aun así crece con la cartera. Aquí `joinedload` sí es la mejor opción.

## `/resumen`

Estrategia: **`agregada`**: `COUNT(siniestros.id)` y `SUM(siniestros.monto)` con `LEFT OUTER JOIN`
y `GROUP BY polizas.id`. Sale 1 consulta con 10 y con 2000, y devuelve una fila por póliza. Los
siniestros no llegan a Python. Aquí la regla «cargar todo de una vez» **empeora** el resultado. Con
`joinedload` y contando en Python también sale 1 consulta, así que el conteo no las distingue, pero
esa consulta trae 6000 filas (póliza × siniestro) y construye 8000 objetos. En nuestra máquina,
con 2000 pólizas, la agregada tardó 113.8 ms y la de `joinedload` 432.2 ms. Además, contar
`siniestros.id` (y no `*`) en el `LEFT JOIN` hace que una póliza sin siniestros salga con 0 y no
con 1; esa es justamente la mutación que usamos en el Defecto 2 de la Parte D.
