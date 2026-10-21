"""Pronóstico local de presupuestos de egresos, aislado por importación.

Estado completado y cobertura homogénea son criterios de elegibilidad, no un
cierre contable certificado. Nunca se utiliza el importe real como objetivo.
"""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sqlalchemy import select

from .database import DB
from .models import Entry, ImportBatch
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


class Dataset(BaseModel):
    id: int
    nombre: str


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
    batch_id: int | None = None
    conjuntos_disponibles: list[Dataset] = Field(default_factory=list)
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
    """Función sin acceso a DB. Admite exactamente una importación por serie."""
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
    if len({row.batch_id for row in selected}) != 1:
        return unavailable(
            "conjuntos_distintos", "No se pueden mezclar distintas importaciones."
        )
    result["batch_id"] = selected[0].batch_id
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
            key = (row.batch_id, row.year, row.source_id, row.currency)
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
    if base not in groups:
        return unavailable(
            "sin_mes_base",
            "No hay partidas en el mes seleccionado para esta importación.",
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
    batch_id: Annotated[int | None, Query(gt=0)] = None,
):
    response.headers["Cache-Control"] = "no-store"
    query = select(Entry).where(Entry.currency == currency, Entry.nature == "expense")
    if category:
        query = query.where(Entry.category == category)
    if period:
        query = query.where(Entry.year * 12 + Entry.month - 1 <= month_number(period))
    if batch_id is not None and db.get(ImportBatch, batch_id) is None:
        raise HTTPException(404, "La importación solicitada no existe.")
    batches = db.scalars(
        select(ImportBatch)
        .where(ImportBatch.id.in_(query.with_only_columns(Entry.batch_id)))
        .order_by(ImportBatch.id)
    ).all()
    datasets = [dict(id=batch.id, nombre=batch.filename) for batch in batches]
    if batch_id is None and len(batches) > 1:
        return BudgetForecastResponse(
            moneda=currency,
            codigo="seleccion_requerida",
            mensaje="Selecciona una importación para no mezclar conjuntos de datos.",
            periodo_base=period,
            conjuntos_disponibles=datasets,
        )
    chosen = batch_id if batch_id is not None else batches[0].id if batches else None
    rows = (
        db.scalars(
            query.where(Entry.batch_id == chosen).order_by(
                Entry.year, Entry.month, Entry.id
            )
        ).all()
        if chosen is not None
        else []
    )
    result = predict_budget(rows, currency=currency, category=category, period=period)
    result.update(batch_id=chosen, conjuntos_disponibles=datasets)
    return result
