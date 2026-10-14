"""
Batería de `ia_tests_propuesta.py`, corregida (Parte D). Ver DICTAMEN_IA.md.

Qué cambia respecto a la propuesta de la IA:
  1. Cada aserción fija UN resultado esperado (201, 404, 422, 409...), no una
     lista de resultados admisibles: un test que acepta 200 y 404 no puede fallar.
  2. El aislamiento es real: la fixture `cliente` (conftest.py) sustituye
     `database.get_db`, la dependencia que usan las rutas, por una sesión sobre una
     base temporal. Y cada test comprueba lo que su nombre promete: que el dato
     quedó guardado, que el resumen cuenta y suma bien, que la predicción se registró.
  3. Los datos son fijos y explícitos: nada de `random` sin semilla. Los casos
     «variados» se enumeran con `parametrize`, incluidos los bordes.

    pytest tests/test_ia_corregido.py -v
"""
import pytest

SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve", "estado": "abierto"}


def _poliza(numero="POL-IA-00001", **extra) -> dict:
    base = {
        "numero": numero,
        "asegurado": "Prueba Automática",
        "tipo": "auto",
        "prima": 1_250_000,
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-12-31",
    }
    base.update(extra)
    return base


def _crear(cliente, **extra) -> dict:
    r = cliente.post("/polizas", json=_poliza(**extra))
    assert r.status_code == 201, r.text
    return r.json()


# --- Creación -----------------------------------------------------------------

def test_crear_poliza_devuelve_201_y_queda_guardada(cliente):
    r = cliente.post("/polizas", json=_poliza())
    assert r.status_code == 201
    creada = r.json()
    assert "token_firma" not in creada
    guardada = cliente.get(f"/polizas/{creada['id']}")
    assert guardada.status_code == 200
    assert guardada.json() == creada


@pytest.mark.parametrize("tipo, prima", [
    ("auto", 1),
    ("hogar", 350_000),
    ("vida", 2_500_000.01),
    ("auto", 4_800_000),
    ("hogar", 5_000_000),
])
def test_primas_y_tipos_variados_son_aceptados(cliente, tipo, prima):
    r = cliente.post("/polizas", json=_poliza(tipo=tipo, prima=prima))
    assert r.status_code == 201, r.text
    assert (r.json()["tipo"], r.json()["prima"]) == (tipo, prima)


def test_el_asegurado_se_normaliza_y_se_conserva(cliente):
    creada = _crear(cliente, asegurado="  carla   ibáñez ")
    assert creada["asegurado"] == "Carla Ibáñez"


def test_poliza_con_siniestros_anidados(cliente):
    creada = _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}])
    assert [s["monto"] for s in creada["siniestros"]] == [850_000, 150_000]


# --- Validación (422) ---------------------------------------------------------

@pytest.mark.parametrize("cambio", [
    {"prima": 0},
    {"prima": -1},
    {"tipo": "moto"},
    {"asegurado": "AB"},
    {"numero": "POL-1"},
    {"fecha_inicio": "2026-12-31", "fecha_fin": "2026-01-01"},
    {"fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-01"},
    {"siniestros": [{**SINIESTRO, "monto": -50}]},
    {"siniestros": [{**SINIESTRO, "monto": 0}]},
    {"siniestros": [{**SINIESTRO, "estado": "inventado"}]},
], ids=["prima-cero", "prima-negativa", "tipo-desconocido", "asegurado-corto", "numero-corto",
        "fechas-invertidas", "fechas-iguales", "siniestro-negativo", "siniestro-cero",
        "estado-desconocido"])
def test_entrada_invalida_da_422_y_no_se_guarda(cliente, cambio):
    r = cliente.post("/polizas", json=_poliza(**cambio))
    assert r.status_code == 422
    assert cliente.get("/polizas").json() == []


# --- Recursos que no existen (404) --------------------------------------------

def test_consultar_poliza_inexistente_da_404(cliente):
    assert cliente.get("/polizas/999999").status_code == 404


def test_actualizar_poliza_inexistente_da_404(cliente):
    assert cliente.put("/polizas/999999", json={"prima": 10}).status_code == 404


def test_siniestro_de_poliza_inexistente_da_404_y_no_se_guarda(cliente):
    assert cliente.post("/polizas/999999/siniestros", json=SINIESTRO).status_code == 404
    assert cliente.get("/siniestros").json() == []


def test_score_de_poliza_inexistente_da_404_y_no_registra(cliente):
    assert cliente.post("/score", json={"numero": "POL-NO-EXISTE"}).status_code == 404
    assert cliente.get("/predicciones").json() == []


# --- Actualización y siniestros ------------------------------------------------

def test_put_parcial_cambia_solo_lo_enviado_y_queda_guardado(cliente):
    creada = _crear(cliente, asegurado="Bruno Celis", tipo="hogar")
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200
    guardada = cliente.get(f"/polizas/{creada['id']}").json()
    assert guardada == {**creada, "prima": 999_000}


@pytest.mark.parametrize("cambio", [{"prima": 0}, {"tipo": "moto"}, {"fecha_fin": "2025-12-31"},
                                    {"fecha_fin": "2026-01-01"}],
                         ids=["prima-cero", "tipo-desconocido", "fin-antes-del-inicio", "fin-igual-al-inicio"])
def test_put_invalido_da_422_y_no_cambia_nada(cliente, cambio):
    creada = _crear(cliente)
    assert cliente.put(f"/polizas/{creada['id']}", json=cambio).status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json() == creada


def test_declarar_siniestro_da_201_y_queda_en_la_poliza(cliente):
    creada = _crear(cliente)
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201
    assert r.json()["poliza_id"] == creada["id"]
    guardada = cliente.get(f"/polizas/{creada['id']}").json()
    assert [s["id"] for s in guardada["siniestros"]] == [r.json()["id"]]
    listado = cliente.get("/siniestros").json()
    assert [(s["id"], s["numero_poliza"]) for s in listado] == [(r.json()["id"], creada["numero"])]


def test_listar_polizas_trae_cada_una_con_sus_siniestros(cliente):
    a = _crear(cliente, numero="POL-IA-00001", siniestros=[SINIESTRO])
    b = _crear(cliente, numero="POL-IA-00002")
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert [(p["id"], len(p["siniestros"])) for p in r.json()] == [(a["id"], 1), (b["id"], 0)]


# --- Resumen ------------------------------------------------------------------

def test_resumen_cuenta_y_suma_por_poliza(cliente):
    _crear(cliente, numero="POL-IA-00001",
           siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000.5}])
    _crear(cliente, numero="POL-IA-00002")
    r = cliente.get("/resumen")
    assert r.status_code == 200
    assert r.json() == [
        {"numero": "POL-IA-00001", "n_siniestros": 2, "monto_total": 1_000_000.5},
        {"numero": "POL-IA-00002", "n_siniestros": 0, "monto_total": 0.0},
    ]


# --- Puntuación ---------------------------------------------------------------

@pytest.mark.parametrize("prima", [350_000, 2_500_000.01, 4_800_000])
def test_score_de_poliza_recien_creada_registra_la_prediccion(cliente, prima):
    datos = _poliza(prima=prima)
    assert cliente.post("/polizas", json=datos).status_code == 201
    r = cliente.post("/score", json={"numero": datos["numero"]})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["numero"] == datos["numero"]
    assert 0.0 <= cuerpo["puntaje"] <= 1.0
    assert isinstance(cuerpo["alto_riesgo"], bool)
    registradas = cliente.get("/predicciones").json()
    assert [(p["numero"], round(p["puntaje"], 4)) for p in registradas] == \
        [(datos["numero"], cuerpo["puntaje"])]


# --- Conflicto ----------------------------------------------------------------

def test_numero_duplicado_da_409_y_el_servicio_sigue_vivo(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=_poliza()).status_code == 409
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert len(r.json()) == 1
