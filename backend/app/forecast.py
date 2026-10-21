"""Pronóstico local sobre el histórico de egresos persistido en la base de datos.

Estado completado y cobertura homogénea son criterios de elegibilidad, no un
cierre contable certificado. Nunca se utiliza el importe real como objetivo.
"""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sqlalchemy import select

from .database import DB
from .models import Entry
from .security import Financial

MIN_MONTHS = 6
MAX_MONTHS = 24
MAX_RELATIVE_MAE = 0.30
CENT = Decimal("0.01")
router = APIRouter(tags=["Predicción de presupuestos"])


class HistoryPoint(BaseModel):
    periodo: str
    presupuesto: float
    completo: bool


class Evaluation(BaseModel):
    mae: float
    mae_referencia: float
    meses_validacion: int
    metodo: str = "Origen móvil: hasta tres cortes, entrenando solo con el pasado"


class BudgetForecastResponse(BaseModel):
    disponible: bool = False
    codigo: str = "sin_datos"
    mensaje: str | None = None
    periodo_base: str | None = None
    periodo_pronosticado: str | None = None
    presupuesto_actual: float | None = None
    presupuesto_estimado: float | None = None
    variacion_porcentual: float | None = None
    modelo: str = "LinearRegression"
    meses_analizados: int = 0
    minimo_meses: int = MIN_MONTHS
    moneda: str
    naturaleza: str = "egresos"
    origen: str = "base_de_datos"
    registros_analizados: int = 0
    importaciones_analizadas: int = 0
    historial: list[HistoryPoint] = Field(default_factory=list)
    evaluacion: Evaluation | None = None
    ajuste_no_negativo: bool = False
    advertencias: list[str] = Field(default_factory=list)


def month_number(period):
    year, month = map(int, period.split("-"))
    return year * 12 + month - 1


def period_label(number):
    year, zero_based_month = divmod(number, 12)
    return f"{year:04}-{zero_based_month + 1:02}"


def rounded(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Importe no finito")
    return float(number.quantize(CENT, rounding=ROUND_HALF_UP))


def predict_budget(records, *, currency, category=None, period=None):
    """Agrupa las partidas persistidas de todas las importaciones del espacio financiero."""
    result = BudgetForecastResponse(moneda=currency, periodo_base=period).model_dump()

    def unavailable(code, message):
        result.update(codigo=code, mensaje=message)
        return result

    cutoff = month_number(period) if period else None
    selected = [
        row
        for row in records
        if row.currency == currency
        and row.nature == "expense"
        and (not category or row.category == category)
        and (cutoff is None or row.year * 12 + row.month - 1 <= cutoff)
    ]
    if not selected:
        return unavailable(
            "sin_datos", "No hay presupuestos de egresos para estos filtros."
        )
    base = (
        cutoff
        if cutoff is not None
        else max(row.year * 12 + row.month - 1 for row in selected)
    )
    result["periodo_base"] = period_label(base)
    if base >= month_number("9999-12"):
        return unavailable(
            "periodo_fuera_rango", "El siguiente mes queda fuera del rango admitido."
        )
    result["periodo_pronosticado"] = period_label(base + 1)
    selected = [
        row
        for row in selected
        if row.year * 12 + row.month - 1 >= base - MAX_MONTHS + 1
    ]
    groups = defaultdict(list)
    seen = {}
    try:
        for row in selected:
            amount = Decimal(str(row.budget))
            if not amount.is_finite() or amount < 0 or not isfinite(float(amount)):
                raise ValueError("Importe inválido")
            # The same persisted source row is counted once, never per join occurrence.
            key = (row.year, row.source_id, row.currency)
            fingerprint = (
                row.month,
                row.category,
                row.subcategory,
                row.concept,
                amount,
                row.status,
            )
            if key in seen:
                if seen[key] != fingerprint:
                    raise ValueError("Duplicado inconsistente")
                continue
            seen[key] = fingerprint
            groups[row.year * 12 + row.month - 1].append(row)
        for number, rows in sorted(groups.items()):
            total = rounded(sum((Decimal(str(row.budget)) for row in rows), Decimal(0)))
            result["historial"].append(
                dict(
                    periodo=period_label(number),
                    presupuesto=total,
                    completo=all(row.status == "completado" for row in rows),
                )
            )
    except (ValueError, InvalidOperation, OverflowError):
        result["historial"] = []
        return unavailable(
            "datos_invalidos",
            "Hay presupuestos inválidos o registros duplicados inconsistentes.",
        )

    result["meses_analizados"] = len(groups)
    result["registros_analizados"] = len(seen)
    result["importaciones_analizadas"] = len(
        {row.batch_id for rows in groups.values() for row in rows}
    )
    if base not in groups:
        return unavailable(
            "sin_mes_base",
            "No hay partidas almacenadas en el mes seleccionado para estos filtros.",
        )
    if not all(point["completo"] for point in result["historial"]):
        return unavailable(
            "meses_pendientes",
            "El histórico incluye partidas pendientes. Selecciona un periodo con histórico completado.",
        )
    numbers = sorted(groups)
    if numbers != list(range(numbers[0], base + 1)):
        return unavailable(
            "meses_faltantes",
            "Faltan meses dentro del histórico; no se rellenan con ceros.",
        )
    coverage = [
        Counter((row.category, row.subcategory, row.concept) for row in groups[number])
        for number in numbers
    ]
    if any(signature != coverage[0] for signature in coverage[1:]):
        return unavailable(
            "cobertura_variable",
            "Las partidas incluidas cambian entre meses. Se requiere un histórico comparable.",
        )
    result["presupuesto_actual"] = result["historial"][-1]["presupuesto"]
    result["advertencias"].append(
        "Completado y cobertura homogénea no certifican el cierre contable del mes."
    )
    if len(numbers) < MIN_MONTHS:
        return unavailable(
            "historico_insuficiente",
            f"Se necesitan al menos {MIN_MONTHS} meses consecutivos y comparables; hay {len(numbers)}.",
        )

    x = [[number - numbers[0]] for number in numbers]
    y = [point["presupuesto"] for point in result["historial"]]
    try:
        # Expanding windows: the held-out month is never included in its own fit.
        validation_start = max(3, len(y) - 3)
        predicted, reference = [], []
        for index in range(validation_start, len(y)):
            model = LinearRegression().fit(x[:index], y[:index])
            prediction = float(model.predict([x[index]])[0])
            if not isfinite(prediction):
                raise ValueError("Predicción no finita")
            predicted.append(max(0.0, prediction))
            reference.append(y[index - 1])
        mae = float(mean_absolute_error(y[validation_start:], predicted))
        naive_mae = float(mean_absolute_error(y[validation_start:], reference))
        scale = sum(y[validation_start:]) / len(predicted)
        if not all(isfinite(value) for value in (mae, naive_mae, scale)):
            raise ValueError("Métrica no finita")
        result["evaluacion"] = dict(
            mae=rounded(mae),
            mae_referencia=rounded(naive_mae),
            meses_validacion=len(predicted),
        )
        # Eligibility policy, not a confidence percentage or a calibrated guarantee.
        if mae > max(CENT, Decimal(str(scale)) * Decimal(str(MAX_RELATIVE_MAE))):
            return unavailable(
                "error_elevado",
                "El error temporal supera el umbral de publicación del modelo (MAE relativo del 30%).",
            )
        if mae > naive_mae + float(CENT):
            return unavailable(
                "referencia_mejor",
                "La regresión no mejora la referencia de repetir el presupuesto anterior.",
            )
        model = LinearRegression().fit(x, y)
        raw = float(model.predict([[base + 1 - numbers[0]]])[0])
        if not isfinite(raw):
            raise ValueError("Predicción no finita")
        estimated = rounded(max(0.0, raw))
        variation = (
            rounded(
                (Decimal(str(estimated)) - Decimal(str(y[-1])))
                * 100
                / Decimal(str(y[-1]))
            )
            if y[-1]
            else None
        )
    except (ValueError, InvalidOperation, OverflowError, FloatingPointError):
        return unavailable(
            "calculo_invalido",
            "No se pudo obtener una estimación numéricamente válida.",
        )

    result.update(
        disponible=True,
        codigo="ok",
        presupuesto_estimado=estimated,
        variacion_porcentual=variation,
        ajuste_no_negativo=raw < 0,
    )
    result["advertencias"].append(
        "Tendencia lineal sin estacionalidad; el error histórico no garantiza resultados futuros."
    )
    if raw < 0:
        result["advertencias"].append(
            "La tendencia dio un importe negativo y se limitó explícitamente a cero."
        )
    if not y[-1]:
        result["advertencias"].append(
            "No se calcula variación porcentual porque el presupuesto base es cero."
        )
    return result


@router.get("/api/forecast/budget", response_model=BudgetForecastResponse)
def budget_forecast(
    db: DB,
    user: Financial,
    response: Response,
    currency: Annotated[str, Query(pattern=r"^[A-Z]{3}$")] = "MXN",
    category: Annotated[str | None, Query(max_length=150)] = None,
    period: Annotated[
        str | None, Query(pattern=r"^(19\d{2}|[2-9]\d{3})-(0[1-9]|1[0-2])$")
    ] = None,
):
    response.headers["Cache-Control"] = "no-store"
    query = select(Entry).where(Entry.currency == currency, Entry.nature == "expense")
    if category:
        query = query.where(Entry.category == category)
    if period:
        query = query.where(Entry.year * 12 + Entry.month - 1 <= month_number(period))
    # batch_id preserves upload provenance, not the identity of a budget series.
    # Read committed entries only: prediction never opens or parses an uploaded file.
    latest = db.scalar(
        query.with_only_columns(Entry.year * 12 + Entry.month - 1)
        .order_by((Entry.year * 12 + Entry.month - 1).desc())
        .limit(1)
    )
    base = month_number(period) if period else latest
    if base is not None:
        query = query.where(Entry.year * 12 + Entry.month - 1 >= base - MAX_MONTHS + 1)
    rows = db.scalars(query.order_by(Entry.year, Entry.month, Entry.id)).all()
    return predict_budget(rows, currency=currency, category=category, period=period)
