"""
polizas-api-v0 — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.

El esquema de la base lo crea Alembic (`alembic upgrade head`), no el arranque.
"""
import hashlib
import pickle
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from config import Settings, get_settings
from database import get_db
from esquemas import (PolizaActualizacion, PolizaEntrada, PolizaSalida, PrediccionSalida,
                      PuntuacionEntrada, PuntuacionSalida, ResumenPoliza, Salud,
                      SiniestroConPoliza, SiniestroDeclarado, SiniestroEntrada)
from modelos import Poliza, Prediccion, Siniestro

app = FastAPI(title="Pólizas API", version="1.0.0")


@lru_cache
def _cargar_modelo(ruta: str):
    with open(ruta, "rb") as fh:
        return pickle.load(fh)


def get_modelo(settings: Settings = Depends(get_settings)):
    """El modelo se carga una vez, la primera vez que alguien lo pide."""
    return _cargar_modelo(settings.ruta_modelo)


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


def _poliza_o_404(db: Session, id_poliza: int) -> Poliza:
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la póliza {id_poliza}")
    return poliza


@app.get("/health", response_model=Salud)
def salud(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        base_ok = True
    except SQLAlchemyError:
        base_ok = False
    return Salud(estado="ok" if base_ok else "degradado", base_datos=base_ok)


@app.post("/polizas", response_model=PolizaSalida, status_code=status.HTTP_201_CREATED)
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    poliza = Poliza(**datos.model_dump(exclude={"siniestros"}),
                    token_firma=firmar(datos.numero, settings.secreto_firma))
    poliza.siniestros = [Siniestro(**s.model_dump()) for s in datos.siniestros]
    db.add(poliza)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"ya existe la póliza {datos.numero}")
    return poliza


# Parte C · /polizas → selectinload: 1 consulta de pólizas + 1 de siniestros por cada lote de 500 ids.
@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Session = Depends(get_db)):
    consulta = select(Poliza).options(selectinload(Poliza.siniestros)).order_by(Poliza.id)
    return db.scalars(consulta).all()


# Parte C · /polizas/{id} → lazy: con un solo padre, cargar al acceder cuesta lo mismo (2 consultas).
@app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
    return _poliza_o_404(db, id_poliza)


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida)
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    if cambios.get("fecha_fin", poliza.fecha_fin) <= poliza.fecha_inicio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "fecha_fin debe ser posterior a fecha_inicio")
    for campo, valor in cambios.items():
        setattr(poliza, campo, valor)
    db.commit()
    return poliza


@app.post("/polizas/{id_poliza}/siniestros", response_model=SiniestroDeclarado,
          status_code=status.HTTP_201_CREATED)
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)
    siniestro = Siniestro(poliza_id=poliza.id, **datos.model_dump())
    db.add(siniestro)
    db.commit()
    return siniestro


# Parte C · /siniestros → joinedload: muchos a uno, el JOIN no duplica filas (1 consulta).
@app.get("/siniestros", response_model=list[SiniestroConPoliza])
def listar_siniestros(db: Session = Depends(get_db)):
    consulta = select(Siniestro).options(joinedload(Siniestro.poliza)).order_by(Siniestro.id)
    return db.scalars(consulta).all()


# Parte C · /resumen → agregada: la base cuenta y suma con GROUP BY (1 consulta, sin traer siniestros).
@app.get("/resumen", response_model=list[ResumenPoliza])
def resumen(db: Session = Depends(get_db)):
    consulta = (select(Poliza.numero,
                       func.count(Siniestro.id).label("n_siniestros"),
                       func.coalesce(func.sum(Siniestro.monto), 0.0).label("monto_total"))
                .outerjoin(Poliza.siniestros)
                .group_by(Poliza.id)
                .order_by(Poliza.id))
    return [ResumenPoliza(numero=f.numero, n_siniestros=f.n_siniestros,
                          monto_total=round(f.monto_total, 2))
            for f in db.execute(consulta)]


@app.post("/score", response_model=PuntuacionSalida)
def puntuar(datos: PuntuacionEntrada, db: Session = Depends(get_db),
            settings: Settings = Depends(get_settings), modelo=Depends(get_modelo)):
    poliza = db.scalar(select(Poliza).where(Poliza.numero == datos.numero))
    if poliza is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la póliza {datos.numero}")
    n_siniestros, monto_total = db.execute(
        select(func.count(Siniestro.id), func.coalesce(func.sum(Siniestro.monto), 0.0))
        .where(Siniestro.poliza_id == poliza.id)).one()
    rasgos = [[poliza.prima, n_siniestros, monto_total, (date.today() - poliza.fecha_inicio).days]]
    puntaje = float(modelo.predict_proba(rasgos)[0][1])
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje,
                            alto_riesgo=puntaje > settings.umbral_alto_riesgo)
    db.add(prediccion)
    db.commit()
    return PuntuacionSalida(numero=poliza.numero, puntaje=round(puntaje, 4),
                            alto_riesgo=prediccion.alto_riesgo)


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Session = Depends(get_db)):
    consulta = select(Prediccion).options(joinedload(Prediccion.poliza)).order_by(Prediccion.id)
    return db.scalars(consulta).all()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
