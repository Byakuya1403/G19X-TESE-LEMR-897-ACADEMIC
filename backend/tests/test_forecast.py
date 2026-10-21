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


def test_income_currency_and_category_are_separate():
    rows = history()
    income = history()
    income[0].nature = "income"
    assert predict_budget(income[:1], currency="MXN")["codigo"] == "sin_datos"
    assert predict_budget(rows, currency="USD")["codigo"] == "sin_datos"
    assert (
        predict_budget(rows, currency="MXN", category="Otra")["codigo"] == "sin_datos"
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


def test_endpoint_accumulates_persisted_history_across_imports(client):
    seed(history()[:3], filename="primer-trimestre.csv")
    early = client.get("/api/forecast/budget").json()
    assert early["codigo"] == "historico_insuficiente"
    seed(history()[3:], filename="segundo-trimestre.csv")
    response = client.get("/api/forecast/budget")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["presupuesto_estimado"] == 1600
    assert data["importaciones_analizadas"] == 2
    assert data["registros_analizados"] == 6
    assert data["origen"] == "base_de_datos"
    assert "batch_id" not in data and "conjuntos_disponibles" not in data
    seed(history([1600], start=(2026, 7)), filename="julio.csv")
    updated = client.get("/api/forecast/budget").json()
    assert updated["periodo_pronosticado"] == "2026-08"
    assert updated["presupuesto_estimado"] == 1700
    assert updated["importaciones_analizadas"] == 3
    # The selected month remains a true temporal cutoff even after later imports.
    assert client.get("/api/forecast/budget?period=2026-06").json() == data


def test_endpoint_filters_and_input_validation(client):
    seed(history())
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
    for query in ["period=2026-13", "period=2026-01-01", "currency=mxn"]:
        assert client.get("/api/forecast/budget?" + query).status_code == 422
    # Asking for a missing base does not silently compare another month.
    result = client.get("/api/forecast/budget", params={"period": "2026-07"}).json()
    assert result["codigo"] == "sin_mes_base"


def test_monthly_csv_uploads_persist_and_forecast_without_reading_files(
    client, monkeypatch
):
    client.post(
        "/api/auth/login",
        json={"username": "analista", "password": "UnaClaveSegura2026"},
    )
    columns = "ID_Registro,Anio,Mes,Categoria,Subcategoria,Concepto,Presupuesto_Estimado,Gasto_Real,Diferencia_Varianza,Porcentaje_Ejecucion,Estado\n"
    months = ["Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    files = {}
    # Out-of-order uploads, one file per month, same shared financial history.
    for i in [4, 0, 5, 1, 3, 2]:
        amount = 1000 + i * 100
        content = (
            columns
            + f"monthly-{i},2026,{months[i]},Servicios,Operación,Servicio mensual,{amount},0,{amount},0,Completado\n"
        )
        files[i] = content
        response = client.post(
            "/api/financial/imports/csv",
            files={"file": (f"mes-{i}.csv", content, "text/csv")},
            data={"currency": "MXN"},
        )
        assert response.status_code == 201
    # A fresh SQL session observes six committed entries, irrespective of upload order.
    with Session(engine) as db:
        assert len(db.scalars(select(Entry)).all()) == 6
        assert len(db.scalars(select(ImportBatch)).all()) == 6
    duplicate = client.post(
        "/api/financial/imports/csv",
        files={"file": ("copia.csv", files[0], "text/csv")},
        data={"currency": "MXN"},
    )
    assert duplicate.status_code == 409
    conflicting = files[0].replace(
        "Servicio mensual,1000", "Servicio mensual corregido,1000"
    )
    conflict = client.post(
        "/api/financial/imports/csv",
        files={"file": ("mismo-id.csv", conflicting, "text/csv")},
        data={"currency": "MXN"},
    )
    assert conflict.status_code == 409

    def forbid_csv_read(*args, **kwargs):
        raise AssertionError("El forecast no debe abrir ni parsear archivos CSV")

    monkeypatch.setattr("app.financial.parse_file", forbid_csv_read)
    data = client.get("/api/forecast/budget").json()
    assert data["disponible"] and data["presupuesto_estimado"] == 1600
    assert data["presupuesto_actual"] == 1500
    assert data["periodo_pronosticado"] == "2027-01"
    assert data["registros_analizados"] == 6
    assert data["importaciones_analizadas"] == 6
    assert [p["periodo"] for p in data["historial"]] == [
        f"2026-{month:02}" for month in range(7, 13)
    ]
    # Nothing is retained from request uploads; subsequent SQL changes are the source.
    with Session(engine) as db:
        for row in db.scalars(select(Entry)):
            row.budget += 100
        db.commit()
    updated = client.get("/api/forecast/budget").json()
    assert updated["presupuesto_estimado"] == 1700


def test_complementary_imports_sum_distinct_parts_in_the_same_month(client):
    first = history()
    second = history([100] * 6)
    for row in second:
        row.source_id += "-other"
        row.concept = "Otro servicio"
    seed(first, filename="servicio-a.csv")
    seed(second, filename="servicio-b.csv")
    data = client.get("/api/forecast/budget").json()
    assert data["presupuesto_estimado"] == 1700
    assert data["presupuesto_actual"] == 1600
    assert data["importaciones_analizadas"] == 2
    assert data["registros_analizados"] == 12


def test_duplicate_identity_is_global_not_per_import():
    rows = history()
    duplicate = copy(rows[0])
    duplicate.batch_id = 42
    result = predict_budget(rows + [duplicate], currency="MXN")
    assert result["presupuesto_estimado"] == 1600
    assert result["registros_analizados"] == 6
    duplicate.budget += 1
    assert (
        predict_budget(rows + [duplicate], currency="MXN")["codigo"]
        == "datos_invalidos"
    )


def test_forecast_filters_currency_and_category_over_all_imports(client):
    seed(history()[:3], filename="a.csv")
    seed(history()[3:], filename="b.csv")
    others = history([5000] * 6, currency="USD")
    seed(others, filename="usd.csv")
    extras = history([100] * 6)
    for row in extras:
        row.source_id += "-extra"
        row.category = "Licencias"
    seed(extras, filename="licencias.csv")
    data = client.get("/api/forecast/budget?category=Servicios&currency=MXN").json()
    assert data["presupuesto_estimado"] == 1600
    assert data["importaciones_analizadas"] == 2
    assert (
        client.get("/api/forecast/budget?currency=USD").json()["presupuesto_estimado"]
        == 5000
    )
    assert (
        client.get("/api/forecast/budget?currency=MXN").json()["presupuesto_estimado"]
        == 1700
    )


def test_forecast_contract_has_no_import_selector(client):
    parameters = client.get("/openapi.json").json()["paths"]["/api/forecast/budget"][
        "get"
    ]["parameters"]
    assert {p["name"] for p in parameters} == {"currency", "category", "period"}
