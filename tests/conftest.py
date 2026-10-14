"""Fixtures compartidas por los tests propios.

Cada test recibe un servicio que habla con una base SQLite temporal y vacía: se
sustituye `database.get_db` —la dependencia real— con `app.dependency_overrides`.
La base de la aplicación (`app.db`) no se abre nunca.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import database
import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from main import app


@pytest.fixture
def motor(tmp_path):
    engine = database.crear_engine(f"sqlite:///{tmp_path / 'pruebas.db'}")
    database.Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def cliente(motor):
    Sesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(database.get_db, None)
