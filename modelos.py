"""Tablas del servicio."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Poliza(Base):
    __tablename__ = "polizas"
    __table_args__ = (
        CheckConstraint("prima > 0", name="ck_polizas_prima_positiva"),
        CheckConstraint("fecha_fin > fecha_inicio", name="ck_polizas_fechas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    asegurado: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(10))
    prima: Mapped[float] = mapped_column(Float)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    # Dato interno: se guarda pero ningún esquema de salida lo expone.
    token_firma: Mapped[str] = mapped_column(String(64))

    # Parte C: la estrategia de carga se elige en cada consulta (ver main.py),
    # así que la relación se deja con el valor por defecto, lazy="select".
    siniestros: Mapped[list["Siniestro"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan", order_by="Siniestro.id")
    predicciones: Mapped[list["Prediccion"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan")


class Siniestro(Base):
    __tablename__ = "siniestros"
    __table_args__ = (CheckConstraint("monto > 0", name="ck_siniestros_monto_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[float] = mapped_column(Float)
    descripcion: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(10), default="abierto")

    poliza: Mapped["Poliza"] = relationship(back_populates="siniestros")

    @property
    def numero_poliza(self) -> str:
        return self.poliza.numero


class Prediccion(Base):
    __tablename__ = "predicciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    puntaje: Mapped[float] = mapped_column(Float)
    alto_riesgo: Mapped[bool]
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    poliza: Mapped["Poliza"] = relationship(back_populates="predicciones")

    @property
    def numero(self) -> str:
        return self.poliza.numero
