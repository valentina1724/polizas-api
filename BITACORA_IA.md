# Bitácora de uso de IA

**Integrantes:** Dylan Andrés Fajardo, Valentina Huertas Quesada, Juan Manuel Molina Ortiz
**Herramientas usadas:** Claude (Claude Code, aplicación de escritorio)

> Las tres secciones son obligatorias. **`## Rechazado` es la que se califica.**
> Una bitácora que solo lista prompts aceptados vale la mitad.

## Prompts

| # | Parte | Quién | Prompt (resumido si es largo) |
|---|-------|-------|-------------------------------|
| 1 | Todas | Dylan Andrés Fajardo | «Verifica este PDF de preguntas y respuestas del taller contra el enunciado publicado y dime qué está bien, qué hay que mejorar y qué está mal» (adjunto: un PDF con respuestas sobre otra copia del repositorio) |
| 2 | A–E | Dylan Andrés Fajardo | «El taller está en el repositorio del curso; termina de analizarlo, verifica lo anterior, resuélvelo y prepáralo para subirlo a otro repositorio» |
| 3 | A | Dylan Andrés Fajardo | Dentro de la sesión: levantar `v0-semilla`, reproducir cada defecto con un comando contra `localhost:8000` y copiar la salida literal |
| 4 | C | Dylan Andrés Fajardo | Dentro de la sesión: contar consultas con `contar_consultas.py` y medir la estrategia alternativa de cada endpoint |
| 5 | D | Dylan Andrés Fajardo | Dentro de la sesión: demostrar cada defecto de `ia_tests_propuesta.py` con una mutación y barrer otras mutaciones contra la batería corregida |

## Aceptado

| # | Qué propuso la IA | Por qué lo aceptamos | Qué cambiamos antes de usarlo |
|---|-------------------|----------------------|-------------------------------|
| 1 | Sesión por petición con `get_db` + `yield`, engine cacheado por URL y `PRAGMA foreign_keys=ON` en el evento `connect` | Es el patrón de M8 · 4 y M9 · 7; arregla H4 y H10 de raíz | Se comprobó con `test_contrato.py` (12/12) y con la mutación «409 → 500» |
| 2 | Estrategias de carga: `selectinload` en `/polizas`, `lazy` en `/polizas/{id}`, `joinedload` en `/siniestros`, `agregada` en `/resumen` | Los conteos medidos (2/5, 2/2, 1/1, 1/1) las respaldan | Se midió también la alternativa de cada una antes de decidir (tabla en HALLAZGOS.md) |
| 3 | Evidencias de la Parte A como comandos de una línea que imprimen solo el código HTTP o un `grep -o` | La salida es determinista y se puede comparar literal | Se reejecutaron los 14 en orden sobre un checkout limpio de `v0-semilla`; H10 va al final porque rompe la sesión del semilla |
| 4 | Batería corregida con códigos exactos, comprobación de persistencia y datos fijos con `parametrize` | Ataca los tres defectos de la Parte D | Se probó contra 21 mutaciones en total antes de entregarla |
| 5 | `.gitattributes` con `eol=lf` | En Windows `core.autocrlf` convertía `tests/test_contrato.py` a CRLF y `verificar_entrega.py` lo marcaba como modificado | — |

## Rechazado

| # | Qué propuso la IA | Por qué lo rechazamos | Qué hicimos en su lugar |
|---|-------------------|-----------------------|-------------------------|
| 1 | (PDF previo hecho con IA) Contar «no existe `GET /health`» como hallazgo H1 | El enunciado lo pide en el contrato («hay que crearlo»): es un requisito, no un defecto, y una fila que no es defecto resta la mitad | Se dejó fuera de la tabla; en su lugar va H14 (`create_all` sin migraciones), que sí es un defecto (B5) |
| 2 | (PDF previo) Dar por buenos resultados de una batería corregida («15 failed, 15 passed») y un `alembic/` que no existían en esa copia | Una salida que no se puede reproducir es una salida inventada, y el calificador la compara con la real | Se escribió `tests/test_ia_corregido.py` desde cero y todas las salidas del dictamen se copiaron de corridas reales |
| 3 | (PDF previo) Cambiar la semilla de `sembrar_datos.py` de 20262 a 20261016 | No arregla nada: el conteo de consultas no depende de la semilla y el cambio solo añade un archivo modificado que defender | Se dejó `sembrar_datos.py` como venía |
| 4 | Usar la mutación «quitar el `commit` de `POST /polizas`» para el Defecto 2 | Con esa mutación la batería original **también** se pone en rojo (`test_score...` da 404), así que no demuestra que el test no prueba lo que dice | Se usó `COUNT(*)` en vez de `COUNT(siniestros.id)` en `/resumen`: la original sigue en verde y la corregida falla |
| 5 | `HEALTHCHECK CMD curl -f http://localhost:8000/health` | `python:3.11.9-slim-bookworm` no trae `curl`: el chequeo fallaría siempre y el contenedor quedaría `unhealthy` | `HEALTHCHECK` con `python -c "urllib.request..."`, que además exige `base_datos: true` |
| 6 | Hacer `SECRETO_FIRMA` obligatorio en `Settings` (sin valor por defecto) | `docker run -p 8000:8000 polizas-api` sin `--env-file` (como en la demo y en el calificador) haría caer el servicio al arrancar | Valor por defecto vacío, sin secreto real en el código; el valor de verdad llega por `.env` o `-e` |
| 7 | Primera versión de la batería corregida (30 tests) | En el barrido de mutaciones, quitar la validación de fechas del `PUT` la dejaba en verde | Se añadió `test_put_invalido_da_422_y_no_cambia_nada`; con 34 tests detecta las 18 mutaciones del barrido |
