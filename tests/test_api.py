"""Pruebas propias del servicio, aisladas en una base temporal (ver conftest.py).

    pytest tests/test_api.py
"""
from sqlalchemy import func, select

import database
from main import app
from modelos import Poliza

POLIZA = {
    "numero": "POL-TEST-00001",
    "asegurado": "Prueba Interna",
    "tipo": "auto",
    "prima": 1_000_000,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-12-31",
}


def test_la_sesion_real_esta_sustituida(cliente, motor):
    """Lo que crea el cliente aparece en la base temporal: el override sí aplica."""
    assert database.get_db in app.dependency_overrides
    assert cliente.post("/polizas", json=POLIZA).status_code == 201
    with motor.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Poliza)) == 1


def test_crear_poliza(cliente):
    r = cliente.post("/polizas", json=POLIZA)
    assert r.status_code == 201
    assert r.json()["numero"] == POLIZA["numero"]


def test_listar_polizas(cliente):
    cliente.post("/polizas", json=POLIZA)
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert [p["numero"] for p in r.json()] == [POLIZA["numero"]]


def test_health_indica_que_la_base_responde(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "base_datos": True}


def test_put_con_fecha_fin_anterior_al_inicio_da_422(cliente):
    creada = cliente.post("/polizas", json=POLIZA).json()
    r = cliente.put(f"/polizas/{creada['id']}", json={"fecha_fin": "2025-06-30"})
    assert r.status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json()["fecha_fin"] == "2026-12-31"
