# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** <número> · **Integrantes:** Dylan Andrés Fajardo, Valentina Huertas Quesada, Juan Manuel Molina Ortiz

> Todas las mutaciones se aplicaron sobre el servicio **ya corregido** (Parte B), se corrió la
> batería original (`pytest ia_tests_propuesta.py -q`) y la corregida
> (`pytest tests/test_ia_corregido.py -q`), y se restauró el archivo. El servicio sano pasa las dos.
> La batería corregida tiene 34 tests. Además de las tres mutaciones de abajo, se probó contra
> otras 18 (quitar el `commit` de cada ruta que escribe, quitar cada 404, 201 o 409, quitar cada
> validador, devolver `token_firma`…). La corregida se puso en rojo con todas. La original se
> quedó en verde con 17 de esas 18.

## Defecto 1

- **Qué está mal**: hay tests que no pueden fallar. Sus aserciones aceptan casi cualquier
  respuesta: `status_code in (200, 201, 422)` en los dos tests de creación, `in (200, 404)` en
  `test_consultar_poliza_inexistente`, `< 500` en `test_listar_polizas_no_falla`, y
  `"puntaje" in r.json() or "error" in r.json()` en el de puntuación. Cuando un test admite a la vez
  la respuesta correcta y la incorrecta, no puede distinguir un servicio sano de uno roto.
- **Por qué es un defecto** (M10 · 4. Framework pytest): una aserción tiene que fijar el resultado
  esperado. Según el contrato (M6 · 5. Routing y CRUD), una póliza inexistente da **404**, no
  «200 o 404». El seed respondía 200 con `{"error": ...}` y esta batería lo daba por bueno: es
  justo el hallazgo H3, y no lo habría detectado.
- **Cómo lo comprobamos**: con una mutación que hace que el 404 deje de devolverse.

```diff
--- a/main.py
+++ b/main.py
@@ -45 +45 @@ def _poliza_o_404(db: Session, id_poliza: int) -> Poliza:
-        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la póliza {id_poliza}")
+        raise HTTPException(status.HTTP_200_OK, f"no existe la póliza {id_poliza}")
```

```
$ pytest ia_tests_propuesta.py -q
......                                                                   [100%]
6 passed in 5.63s
```

```
$ pytest tests/test_ia_corregido.py -q
=========================== short test summary info ===========================
FAILED tests/test_ia_corregido.py::test_consultar_poliza_inexistente_da_404
FAILED tests/test_ia_corregido.py::test_actualizar_poliza_inexistente_da_404
FAILED tests/test_ia_corregido.py::test_siniestro_de_poliza_inexistente_da_404_y_no_se_guarda
3 failed, 31 passed in 5.77s
```

- **Corrección**: cada aserción fija un único código (`== 201`, `== 404`, `== 422`, `== 409`) y,
  cuando importa, también el cuerpo. Se añadieron los 404 de `PUT`, de `POST /polizas/{id}/siniestros`
  y de `/score`, y los 422 de cada regla de validación (`test_entrada_invalida_da_422_y_no_se_guarda`,
  `test_put_invalido_da_422_y_no_cambia_nada`).

## Defecto 2

- **Qué está mal**: hay tests que no prueban lo que dicen probar. El más grave es el aislamiento.
  El comentario promete que «la sesión real se sustituye por un doble», pero el archivo define su
  **propia** función `get_db` y la usa como clave en `app.dependency_overrides[get_db] = get_db`.
  Las rutas no dependen de esa función sino de `database.get_db`, así que el override nunca se
  aplica y las pruebas escriben en la base real de la aplicación. Lo mismo pasa con los nombres de
  los tests: `test_resumen_devuelve_lista` dice probar el resumen y solo mira que sea una lista;
  `test_crear_poliza_responde` no comprueba que la póliza quede guardada; el de `/score` no
  comprueba que la predicción se registre.
- **Por qué es un defecto** (M10 · 5. TestClient de FastAPI): `dependency_overrides` se indexa
  con **el mismo objeto función** que la ruta pasa a `Depends`. Una función homónima es otra clave
  y no sustituye nada. Un test que escribe en la base de la aplicación tampoco está aislado
  (M10 · 6. Fixtures en pytest): deja basura y depende del estado que encuentre.
- **Cómo lo comprobamos**: primero, la base de la aplicación **cambia** al correr la batería
  original, que pasa de 0 a 7 pólizas (las de prefijo `POL-IA-`).

```
$ alembic upgrade head            # app.db vacía, con el esquema
$ python -c "import sqlite3; print(sqlite3.connect('app.db').execute('select count(*) from polizas').fetchone()[0])"
0
$ pytest ia_tests_propuesta.py -q
......                                                                   [100%]
6 passed in 4.07s
$ python -c "import sqlite3; print(sqlite3.connect('app.db').execute('select count(*) from polizas').fetchone()[0])"
7
```

Después, una mutación que rompe el resumen: con `COUNT(*)` en el `LEFT JOIN`, una póliza sin
siniestros aparece con 1.

```diff
--- a/main.py
+++ b/main.py
@@ -121 +121 @@ def resumen(db: Session = Depends(get_db)):
-                       func.count(Siniestro.id).label("n_siniestros"),
+                       func.count().label("n_siniestros"),
```

```
$ pytest ia_tests_propuesta.py -q
......                                                                   [100%]
6 passed in 2.27s
```

```
$ pytest tests/test_ia_corregido.py -q
=========================== short test summary info ===========================
FAILED tests/test_ia_corregido.py::test_resumen_cuenta_y_suma_por_poliza - As...
1 failed, 33 passed in 3.03s
```

- **Corrección**: la fixture `cliente` de `tests/conftest.py` sustituye `database.get_db`, la
  dependencia real, por una sesión sobre una SQLite temporal (`tmp_path`). `tests/test_api.py`
  incluye `test_la_sesion_real_esta_sustituida`, que comprueba que lo creado por la API está en esa
  base. Cada test comprueba lo que su nombre promete: tras crear, un `GET` devuelve lo mismo; tras
  un `PUT` o un siniestro, el cambio persiste; el resumen se compara con los valores exactos
  (incluida una póliza con 0 siniestros); y la predicción aparece en `/predicciones` con su `numero`.

## Defecto 3

- **Qué está mal**: hay tests que unas veces pasan y otras no. `_poliza()` genera `tipo` y `prima`
  con `random` sin semilla (`random.uniform(1, 5_000_000)`), así que cada corrida prueba datos
  distintos. Mientras el servicio acepta todo, no se nota. En cuanto una regla rechaza parte de
  ese rango, el resultado depende del azar: si la prima sorteada cae fuera, el `POST` da 422 (y la
  batería lo da por bueno), la póliza no existe y `/score` da 404.
- **Por qué es un defecto** (M10 · 7. Reproducibilidad sin Docker): un test tiene que dar el
  mismo resultado con el mismo código. Si una corrida en rojo no se puede repetir, no se puede
  diagnosticar, y una corrida en verde no demuestra nada. Los datos «variados» deben ser casos
  enumerados (o una semilla fija), no un sorteo.
- **Cómo lo comprobamos**: con un validador que rechaza lo que no debe, en este caso primas
  mayores de 2 500 000.

```diff
--- a/esquemas.py
+++ b/esquemas.py
@@ -29 +29 @@ class PolizaEntrada(BaseModel):
-    prima: float = Field(gt=0, description="Prima anual, en pesos")
+    prima: float = Field(gt=0, le=2_500_000, description="Prima anual, en pesos")
```

Diez corridas seguidas de la batería original sobre el mismo servicio mutado: **5 en verde y 5 en
rojo**, según la prima que tocara.

```
$ for i in $(seq 10); do pytest ia_tests_propuesta.py -q | tail -1; done
6 passed in 2.47s
6 passed in 2.14s
1 failed, 5 passed in 2.49s
6 passed in 3.25s
6 passed in 2.20s
1 failed, 5 passed in 3.39s
1 failed, 5 passed in 4.22s
1 failed, 5 passed in 4.65s
6 passed in 3.70s
1 failed, 5 passed in 4.46s
```

Cuando sale en rojo, el fallo no apunta a la causa: dice que `/score` dio 404.

```
FAILED ia_tests_propuesta.py::test_score_de_poliza_recien_creada - assert 404...
1 failed, 5 passed in 2.11s
```

La corregida falla **siempre**, y nombra el caso:

```
$ pytest tests/test_ia_corregido.py -q
=========================== short test summary info ===========================
FAILED tests/test_ia_corregido.py::test_primas_y_tipos_variados_son_aceptados[vida-2500000.01]
FAILED tests/test_ia_corregido.py::test_primas_y_tipos_variados_son_aceptados[auto-4800000]
FAILED tests/test_ia_corregido.py::test_primas_y_tipos_variados_son_aceptados[hogar-5000000]
FAILED tests/test_ia_corregido.py::test_score_de_poliza_recien_creada_registra_la_prediccion[2500000.01]
FAILED tests/test_ia_corregido.py::test_score_de_poliza_recien_creada_registra_la_prediccion[4800000]
5 failed, 29 passed in 3.02s
```

- **Corrección**: se eliminó `random`. Los datos variados se enumeran con
  `@pytest.mark.parametrize`, con valores fijos que cubren los tres tipos y primas en los bordes
  (1, 350 000, 2 500 000.01, 4 800 000 y 5 000 000). Los números de póliza también son fijos: cada
  test arranca con una base vacía, así que no hace falta `uuid` para evitar colisiones.
