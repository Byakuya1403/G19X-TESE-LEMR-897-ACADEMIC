"""All generated histories in this file are test fixtures, never demo API data."""

from copy import copy
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.forecast import predict_budget
from app.models import Entry, ImportBatch


def history(values=None, *, start=(2026, 1), batch_id=1, currency="MXN"):
    values = values if values is not None else [1000, 1100, 1200, 1300, 1400, 1500]
    result = []
    for offset, value in enumerate(values):
        year, month = divmod(start[0] * 12 + start[1] - 1 + offset, 12)
        result.append(
            SimpleNamespace(
                year=year,
                month=month + 1,
                batch_id=batch_id,
                source_id=f"fixture-{year}-{month + 1}",
                currency=currency,
                category="Servicios",
                subcategory="Operación",
                concept="Servicio mensual",
                nature="expense",
                budget=Decimal(str(value)),
                actual=Decimal("99999"),
                status="completado",
            )
        )
    return result


def seed(rows, filename="historia-prueba.csv"):
    with Session(engine) as db:
        batch = ImportBatch(
            sha256=f"test-hash-{filename}",
            filename=filename,
            currency=rows[0].currency,
            username="analista",
            warnings=[],
        )
        db.add(batch)
        db.flush()
        for row in rows:
            values = vars(row).copy()
            values["batch_id"] = batch.id
            db.add(Entry(**values, original={"fixture": True}))
        db.commit()
        return batch.id


def test_linear_budget_is_not_actual_spending_and_changes_year():
    rows = history(start=(2026, 7))
    result = predict_budget(list(reversed(rows)), currency="MXN")
    assert result["disponible"] is True
    assert result["periodo_pronosticado"] == "2027-01"
    assert result["presupuesto_actual"] == 1500
    assert result["presupuesto_estimado"] == 1600
    assert result["variacion_porcentual"] == 6.67
    assert result["meses_analizados"] == 6
    assert result["evaluacion"]["mae"] == 0
    assert result["evaluacion"]["mae_referencia"] == 100
    assert result["evaluacion"]["meses_validacion"] == 3
    assert [p["periodo"] for p in result["historial"]] == [
        f"2026-{m:02}" for m in range(7, 13)
    ]
    assert "confianza" not in result and "r2" not in result


def test_multiple_parts_sum_budgets_without_duplicate_source_rows():
    rows = history()
    other = []
    for row in rows:
        part = copy(row)
        part.source_id += "-b"
        part.budget = Decimal(100)
        other.append(part)
    result = predict_budget(rows + other + [rows[0], other[-1]], currency="MXN")
    assert result["presupuesto_actual"] == 1600
    assert result["presupuesto_estimado"] == 1700
    assert result["historial"][0]["presupuesto"] == 1100
    wrong = copy(rows[0])
    wrong.budget = Decimal(123)
    assert predict_budget(rows + [wrong], currency="MXN")["codigo"] == "datos_invalidos"


def test_future_rows_never_change_historical_forecast():
    rows = history(list(range(1000, 2200, 100)))
    expected = predict_budget(rows, currency="MXN", period="2026-10")
    rows[-1].budget = Decimal(99999999)
    rows[-1].status = "pendiente"
    rows[-2].concept = "Otro concepto futuro"
    assert predict_budget(rows, currency="MXN", period="2026-10") == expected
    assert expected["periodo_pronosticado"] == "2026-11"
    assert expected["presupuesto_estimado"] == 2000
    assert expected["meses_analizados"] == 10


def test_every_validation_fit_uses_only_earlier_months(monkeypatch):
    import app.forecast as module

    real_model = module.LinearRegression
    calls = []

    class Spy(real_model):
        def fit(self, x, y):
            self.last_fit = max(item[0] for item in x)
            calls.append(("fit", len(x)))
            return super().fit(x, y)

        def predict(self, x):
            assert all(item[0] > self.last_fit for item in x)
            return super().predict(x)

    monkeypatch.setattr(module, "LinearRegression", Spy)
    assert predict_budget(history(), currency="MXN")["disponible"]
    assert calls == [("fit", 3), ("fit", 4), ("fit", 5), ("fit", 6)]


@pytest.mark.parametrize("length", [1, 2, 3, 4, 5])
def test_insufficient_history_has_no_invented_estimate(length):
    result = predict_budget(history()[:length], currency="MXN")
    assert not result["disponible"] and result["codigo"] == "historico_insuficiente"
    assert result["presupuesto_estimado"] is None
    assert result["evaluacion"] is None


def test_gaps_pending_coverage_and_missing_base_are_rejected():
    rows = history()
    assert (
        predict_budget(rows[:2] + rows[3:], currency="MXN")["codigo"]
        == "meses_faltantes"
    )
    rows[1].status = "pendiente"
    assert predict_budget(rows, currency="MXN")["codigo"] == "meses_pendientes"
    rows[1].status = "completado"
    rows[1].concept = "Concepto distinto"
    assert predict_budget(rows, currency="MXN")["codigo"] == "cobertura_variable"
    assert (
        predict_budget(history(), currency="MXN", period="2026-07")["codigo"]
        == "sin_mes_base"
    )


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1e400"])
def test_invalid_budgets_have_no_forecast(bad):
    rows = history()
    rows[2].budget = Decimal(bad)
    result = predict_budget(rows, currency="MXN")
    assert (
        result["codigo"] == "datos_invalidos" and result["presupuesto_estimado"] is None
    )


def test_income_currency_category_and_imports_are_separate():
    rows = history()
    income = history()
    income[0].nature = "income"
    assert predict_budget(income[:1], currency="MXN")["codigo"] == "sin_datos"
    assert predict_budget(rows, currency="USD")["codigo"] == "sin_datos"
    assert (
        predict_budget(rows, currency="MXN", category="Otra")["codigo"] == "sin_datos"
    )
    assert (
        predict_budget(rows + history(batch_id=2), currency="MXN")["codigo"]
        == "conjuntos_distintos"
    )


def test_error_threshold_and_naive_reference_reject_bad_models():
    result = predict_budget(history([100, 1000, 100, 1000, 100, 1000]), currency="MXN")
    assert not result["disponible"] and result["codigo"] == "error_elevado"
    result = predict_budget(history([100, 110, 120, 120, 120, 120]), currency="MXN")
    assert not result["disponible"] and result["codigo"] == "referencia_mejor"
    assert result["evaluacion"] is not None


def test_zero_baseline_and_negative_trend_are_explicit():
    zero = predict_budget(history([0] * 6), currency="MXN")
    assert zero["disponible"] and zero["presupuesto_estimado"] == 0
    assert zero["variacion_porcentual"] is None
    declining = predict_budget(history([61, 51, 41, 31, 21, 11, 1]), currency="MXN")
    assert declining["disponible"] and declining["presupuesto_estimado"] == 0
    assert declining["ajuste_no_negativo"] is True


def test_maximum_window_and_last_supported_year():
    result = predict_budget(
        history(list(range(100, 3100, 100)), start=(2024, 1)), currency="MXN"
    )
    assert result["disponible"] and result["meses_analizados"] == 24
    assert result["periodo_pronosticado"] == "2026-07"
    result = predict_budget(history(start=(9999, 7)), currency="MXN")
    assert result["codigo"] == "periodo_fuera_rango"


def test_endpoint_requires_financial_role_and_never_uses_guest_data(client):
    client.post("/api/auth/logout")
    assert client.get("/api/forecast/budget").status_code == 401
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    assert client.get("/api/forecast/budget").status_code == 403
    client.post(
        "/api/auth/login",
        json={"username": "analista", "password": "UnaClaveSegura2026"},
    )
    empty = client.get("/api/forecast/budget").json()
    assert empty["codigo"] == "sin_datos" and empty["historial"] == []


def test_endpoint_reads_persisted_budgets_and_refreshes_after_new_import(client):
    batch = seed(history())
    response = client.get(
        "/api/forecast/budget", params={"period": "2026-06", "currency": "MXN"}
    )
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    data = response.json()
    assert data["presupuesto_estimado"] == 1600 and data["batch_id"] == batch
    # A later independent import requires selection instead of being added to the first.
    second = seed(
        history([2000, 2100, 2200, 2300, 2400, 2500], start=(2025, 1)),
        filename="otra-serie.csv",
    )
    result = client.get("/api/forecast/budget").json()
    assert (
        result["codigo"] == "seleccion_requerida"
        and len(result["conjuntos_disponibles"]) == 2
    )
    first_result = client.get("/api/forecast/budget", params={"batch_id": batch}).json()
    second_result = client.get(
        "/api/forecast/budget", params={"batch_id": second}
    ).json()
    assert first_result["presupuesto_estimado"] == 1600
    assert second_result["presupuesto_estimado"] == 2600
    # A new monthly entry in the same persisted series is immediately considered (no cache).
    with Session(engine) as db:
        row = history([1600], start=(2026, 7))[0]
        values = vars(row).copy()
        values["batch_id"] = batch
        db.add(Entry(**values, original={"fixture": True}))
        db.commit()
    updated = client.get("/api/forecast/budget", params={"batch_id": batch}).json()
    assert (
        updated["periodo_pronosticado"] == "2026-08"
        and updated["presupuesto_estimado"] == 1700
    )


def test_endpoint_filters_and_input_validation(client):
    batch = seed(history())
    assert (
        client.get("/api/forecast/budget?period=2026-04").json()["codigo"]
        == "historico_insuficiente"
    )
    assert (
        client.get("/api/forecast/budget?currency=USD").json()["codigo"] == "sin_datos"
    )
    assert (
        client.get("/api/forecast/budget?category=Ingresos").json()["codigo"]
        == "sin_datos"
    )
    assert client.get("/api/forecast/budget?batch_id=9999").status_code == 404
    for query in ["period=2026-13", "period=2026-01-01", "currency=mxn", "batch_id=0"]:
        assert client.get("/api/forecast/budget?" + query).status_code == 422
    # Asking for a missing base does not silently compare another month.
    result = client.get(
        "/api/forecast/budget", params={"period": "2026-07", "batch_id": batch}
    ).json()
    assert result["codigo"] == "sin_mes_base"


def test_real_csv_import_flow_recomputes_datasets_without_summing_them(client):
    client.post(
        "/api/auth/login",
        json={"username": "analista", "password": "UnaClaveSegura2026"},
    )
    columns = "ID_Registro,Anio,Mes,Categoria,Subcategoria,Concepto,Presupuesto_Estimado,Gasto_Real,Diferencia_Varianza,Porcentaje_Ejecucion,Estado\n"
    months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio"]

    def upload(prefix, base):
        # Actual spending is zero in these fixtures; budgets are nonzero and increasing.
        rows = [
            f"{prefix}-{i},2026,{month},Servicios,Operación,Servicio mensual,{base+i*100},0,{base+i*100},0,Completado"
            for i, month in enumerate(months)
        ]
        response = client.post(
            "/api/financial/imports/csv",
            files={
                "file": (f"{prefix}.csv", columns + "\n".join(rows) + "\n", "text/csv")
            },
            data={"currency": "MXN"},
        )
        assert response.status_code == 201

    upload("fixture-a", 1000)
    first = client.get("/api/forecast/budget?period=2026-06").json()
    assert first["disponible"] and first["presupuesto_estimado"] == 1600
    upload("fixture-b", 2000)
    ambiguous = client.get("/api/forecast/budget?period=2026-06").json()
    assert ambiguous["codigo"] == "seleccion_requerida"
    selected = next(
        batch["id"]
        for batch in ambiguous["conjuntos_disponibles"]
        if batch["nombre"] == "fixture-b.csv"
    )
    new = client.get(
        "/api/forecast/budget", params={"period": "2026-06", "batch_id": selected}
    ).json()
    assert new["presupuesto_estimado"] == 2600
    old = client.get(
        "/api/forecast/budget",
        params={"period": "2026-06", "batch_id": first["batch_id"]},
    ).json()
    assert old["presupuesto_estimado"] == 1600
