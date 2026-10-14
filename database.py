"""Conexión a la base de datos: un engine por URL y una sesión por petición."""
from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def crear_engine(url: str) -> Engine:
    """Engine para `url`. En SQLite activa las claves foráneas en cada conexión."""
    es_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if es_sqlite else {})
    if es_sqlite:
        @event.listens_for(engine, "connect")
        def _activar_fk(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


@lru_cache
def _fabrica_sesiones(url: str) -> sessionmaker[Session]:
    """Una fábrica (y un engine) por URL, creada la primera vez que se pide."""
    return sessionmaker(bind=crear_engine(url), autoflush=False, expire_on_commit=False)


def get_db(settings: Settings = Depends(get_settings)) -> Generator[Session, None, None]:
    """Abre una sesión para la petición y la cierra al terminar, pase lo que pase."""
    db = _fabrica_sesiones(settings.database_url)()
    try:
        yield db
    finally:
        db.close()
