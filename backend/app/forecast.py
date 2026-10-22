"""Pronóstico local sobre el histórico de egresos persistido en la base de datos.

La composición mensual se informa como advertencia, no como certificado
de cierre contable. El estado de ejecución no determina si el presupuesto es conocido.
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
SEASONAL_MIN_MONTHS = 24
MAX_RELATIVE_MAE = 0.30
CENT = Decimal("0.01")
router = APIRouter(tags=["Predicción de presupuestos"])


class HistoryPoint(BaseModel):
    periodo: str
    presupuesto: float
    ejecucion_completada: bool = Field(
        description="Indica si el gasto real del mes está completado; no condiciona el entrenamiento."
    )


class Evaluation(BaseModel):
    mae: float
    mae_referencia: float
    meses_validacion: int
    supera_referencia: bool = True
    metodo: str = "Origen móvil: hasta tres cortes, entrenando solo con el pasado"


class ModelSelection(BaseModel):
    periodos: list[str]
    mae_tendencia: float
    mae_estacional: float
    metodo: str = "Selección en tres meses anteriores al bloque de evaluación final"


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
    configuracion: str = "tendencia"
    descripcion_modelo: str = "Regresión lineal con tendencia"
    seleccion_modelo: ModelSelection | None = None
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
    composicion_variable: bool = False


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


def model_features(number, origin, seasonal):
    """Tendencia y once indicadores del mes del año; enero es la referencia."""
    return [number - origin] + (
        [int(number % 12 == month) for month in range(1, 12)] if seasonal else []
    )


def temporal_predictions(numbers, amounts, indices, seasonal):
    predictions = []
    for index in indices:
        x = [model_features(number, numbers[0], seasonal) for number in numbers[:index]]
        model = LinearRegression().fit(x, amounts[:index])
        predicted = float(
            model.predict([model_features(numbers[index], numbers[0], seasonal)])[0]
        )
        if not isfinite(predicted):
            raise ValueError("Predicción no finita")
        predictions.append(max(0.0, predicted))
    return predictions


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
                    ejecucion_completada=all(
                        row.status == "completado" for row in rows
                    ),
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
    result["composicion_variable"] = any(
        signature != coverage[0] for signature in coverage[1:]
    )
    if result["composicion_variable"]:
        result["advertencias"].append(
            "La composición de las partidas cambia entre meses. Se modela el presupuesto total registrado; verifica que las cargas cubran el mismo ámbito financiero y que no falten partidas."
        )
    result["presupuesto_actual"] = result["historial"][-1]["presupuesto"]
    result["advertencias"].append(
        "La existencia de partidas no certifica que el presupuesto mensual esté cerrado o completo."
    )
    if not all(point["ejecucion_completada"] for point in result["historial"]):
        result["advertencias"].append(
            "Hay gastos reales pendientes; se utilizan los presupuestos asignados ya registrados, sin sustituir el gasto real por cero."
        )
    if len(numbers) < MIN_MONTHS:
        return unavailable(
            "historico_insuficiente",
            f"Se necesitan al menos {MIN_MONTHS} meses consecutivos de presupuestos; hay {len(numbers)}.",
        )

    y = [point["presupuesto"] for point in result["historial"]]
    try:
        validation_start = max(3, len(y) - 3)
        seasonal = False
        # Select using a separate earlier block, never the final evaluation months.
        if len(numbers) >= SEASONAL_MIN_MONTHS:
            selection_indices = range(validation_start - 3, validation_start)
            actuals = y[validation_start - 3 : validation_start]
            trend_mae = float(
                mean_absolute_error(
                    actuals, temporal_predictions(numbers, y, selection_indices, False)
                )
            )
            seasonal_mae = float(
                mean_absolute_error(
                    actuals, temporal_predictions(numbers, y, selection_indices, True)
                )
            )
            if not all(isfinite(value) for value in (trend_mae, seasonal_mae)):
                raise ValueError("Selección no finita")
            seasonal = seasonal_mae + float(CENT) < trend_mae
            result["seleccion_modelo"] = dict(
                periodos=[period_label(numbers[index]) for index in selection_indices],
                mae_tendencia=rounded(trend_mae),
                mae_estacional=rounded(seasonal_mae),
            )
        if seasonal:
            result["configuracion"] = "tendencia_y_mes"
            result["descripcion_modelo"] = (
                "Regresión lineal con tendencia y mes del año"
            )
        predicted = temporal_predictions(
            numbers, y, range(validation_start, len(y)), seasonal
        )
        reference = y[validation_start - 1 : -1]
        mae = float(mean_absolute_error(y[validation_start:], predicted))
        naive_mae = float(mean_absolute_error(y[validation_start:], reference))
        scale = sum(y[validation_start:]) / len(predicted)
        if not all(isfinite(value) for value in (mae, naive_mae, scale)):
            raise ValueError("Métrica no finita")
        result["evaluacion"] = dict(
            mae=rounded(mae),
            mae_referencia=rounded(naive_mae),
            meses_validacion=len(predicted),
            supera_referencia=mae <= naive_mae + float(CENT),
        )
        # Eligibility policy, not a confidence percentage or a calibrated guarantee.
        if mae > max(CENT, Decimal(str(scale)) * Decimal(str(MAX_RELATIVE_MAE))):
            return unavailable(
                "error_elevado",
                "El error temporal supera el umbral de publicación del modelo (MAE relativo del 30%).",
            )
        if mae > naive_mae + float(CENT):
            result["advertencias"].append(
                "En la evaluación temporal, repetir el presupuesto anterior tuvo menor error que este modelo. Consulta ambos MAE antes de utilizar la estimación."
            )
        x = [model_features(number, numbers[0], seasonal) for number in numbers]
        model = LinearRegression().fit(x, y)
        raw = float(model.predict([model_features(base + 1, numbers[0], seasonal)])[0])
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
        "El error histórico no garantiza resultados futuros; la estimación depende de mantener el ámbito y las pautas del histórico."
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
