"""Esquemas de entrada y de salida."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TipoPoliza = Literal["auto", "hogar", "vida"]
EstadoSiniestro = Literal["abierto", "pagado", "rechazado"]


def _normalizar_nombre(v: str) -> str:
    """Quita espacios sobrantes y pone el nombre con mayúscula inicial."""
    return " ".join(v.split()).title()


# --- Entrada -----------------------------------------------------------------

class SiniestroEntrada(BaseModel):
    fecha: date
    monto: float = Field(gt=0, description="Monto reclamado, en pesos")
    descripcion: str = Field(min_length=3, max_length=200)
    estado: EstadoSiniestro = "abierto"


class PolizaEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")
    asegurado: str = Field(min_length=3, max_length=80)
    tipo: TipoPoliza
    prima: float = Field(gt=0, description="Prima anual, en pesos")
    fecha_inicio: date
    fecha_fin: date
    siniestros: list[SiniestroEntrada] = Field(default_factory=list, description="Siniestros ya declarados")

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: str) -> str:
        return _normalizar_nombre(v)

    @model_validator(mode="after")
    def fechas_coherentes(self) -> "PolizaEntrada":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PolizaActualizacion(BaseModel):
    """PUT parcial: solo se tocan los campos que llegan en el cuerpo."""
    asegurado: Optional[str] = Field(default=None, min_length=3, max_length=80)
    tipo: Optional[TipoPoliza] = None
    prima: Optional[float] = Field(default=None, gt=0)
    fecha_fin: Optional[date] = None

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalizar_nombre(v)


class PuntuacionEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20)


# --- Salida ------------------------------------------------------------------

class SiniestroSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    monto: float
    descripcion: str
    estado: str


class SiniestroDeclarado(SiniestroSalida):
    poliza_id: int


class SiniestroConPoliza(SiniestroDeclarado):
    numero_poliza: str


class PolizaSalida(BaseModel):
    """Lo que el servicio devuelve de una póliza. `token_firma` no está: es interno."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    asegurado: str
    tipo: str
    prima: float
    fecha_inicio: date
    fecha_fin: date
    siniestros: list[SiniestroSalida]


class ResumenPoliza(BaseModel):
    numero: str
    n_siniestros: int
    monto_total: float


class PuntuacionSalida(BaseModel):
    numero: str
    puntaje: float = Field(ge=0, le=1)
    alto_riesgo: bool


class PrediccionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int
    numero: str
    puntaje: float
    alto_riesgo: bool
    creado_en: datetime


class Salud(BaseModel):
    estado: Literal["ok", "degradado"]
    base_datos: bool
