"""Retirada de cargas: permisos, confirmación, atomicidad y persistencia."""

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Entry, ImportBatch

COLUMNS = "ID_Registro,Anio,Mes,Categoria,Subcategoria,Concepto,Presupuesto_Estimado,Gasto_Real,Diferencia_Varianza,Porcentaje_Ejecucion,Estado\n"


def login(client, username="analista"):
    return client.post(
        "/api/auth/login", json={"username": username, "password": "UnaClaveSegura2026"}
    )


def upload(client, prefix="one", filename="presupuesto.csv"):
    content = (
        COLUMNS
        + f"{prefix}-1,2026,Enero,Servicios,Operación,Servicio,100,80,20,80,Completado\n"
        + f"{prefix}-2,2026,Febrero,Ingresos,Ventas,Venta,200,200,0,100,Completado\n"
    )
    response = client.post(
        "/api/financial/imports/csv",
        files={"file": (filename, content, "text/csv")},
        data={"currency": "MXN"},
    )
    assert response.status_code == 201
    return content


def remove(client, batch_id, confirmation=None):
    page = client.get("/api/financial/imports").json()
    fingerprint = next(
        (item["sha256"] for item in page.get("items", []) if item["id"] == batch_id),
        "0" * 64,
    )
    return client.request(
        "DELETE",
        f"/api/financial/imports/{batch_id}",
        json={
            "sha256": fingerprint,
            "confirmation": (
                confirmation if confirmation is not None else f"ELIMINAR {batch_id}"
            )
        },
    )


def test_only_analyst_can_list_or_delete_imports(client):
    for username in ["director", "admin", None]:
        if username:
            login(client, username)
        else:
            client.post("/api/auth/logout")
        expected = 403 if username else 401
        assert client.get("/api/financial/imports").status_code == expected
        assert remove(client, 1).status_code == expected
    login(client)
    assert client.get("/api/financial/imports").json()["items"] == []
    client.headers.pop("X-App")
    assert remove(client, 1).status_code == 403


def test_listing_and_delete_target_only_its_entries_even_with_same_filename(client):
    login(client)
    first_content = upload(client)
    upload(client, prefix="two")
    response = client.get("/api/financial/imports")
    assert response.headers["cache-control"] == "no-store"
    page = response.json()
    assert page["total"] == 2
    second, first = page["items"]
    assert first["filename"] == second["filename"]
    assert first["entry_count"] == second["entry_count"] == 2
    assert first["period_from"] == "2026-01" and first["period_to"] == "2026-02"
    assert first["username"] == "analista"
    # Wrong/missing confirmation cannot delete anything.
    for code in ["ELIMINAR", f"ELIMINAR {second['id']}", f"eliminar {first['id']}"]:
        assert remove(client, first["id"], code).status_code == 422
    assert (
        client.request(
            "DELETE", f"/api/financial/imports/{first['id']}", json={}
        ).status_code
        == 422
    )
    assert client.get("/api/financial/imports").json()["total"] == 2
    result = remove(client, first["id"])
    assert result.status_code == 200
    assert result.json()["deleted_entries"] == 2
    with Session(engine) as db:
        assert db.get(ImportBatch, first["id"]) is None
        remaining = db.scalars(select(Entry)).all()
        assert len(remaining) == 2 and all(
            row.batch_id == second["id"] for row in remaining
        )
    assert len(client.get("/api/financial/entries").json()) == 2
    dashboard = client.get("/api/financial/dashboard?period=2026-01").json()
    assert dashboard["expense"]["budget"] == 100
    assert remove(client, first["id"]).status_code == 404
    # Both the source key and file hash are released by deleting that import.
    assert (
        client.post(
            "/api/financial/imports/csv",
            files={"file": ("definitivo.csv", first_content, "text/csv")},
            data={"currency": "MXN"},
        ).status_code
        == 201
    )


def test_last_import_deletion_leaves_no_forecast_or_real_entries(client):
    login(client)
    upload(client)
    batch = client.get("/api/financial/imports").json()["items"][0]
    assert remove(client, batch["id"]).status_code == 200
    assert client.get("/api/financial/imports").json()["total"] == 0
    assert client.get("/api/financial/entries").json() == []
    result = client.get("/api/forecast/budget").json()
    assert result["codigo"] == "sin_datos" and result["presupuesto_estimado"] is None
    assert result["historial"] == []


def test_import_deletion_rolls_back_all_entries_if_batch_delete_fails(client):
    login(client)
    upload(client)
    batch = client.get("/api/financial/imports").json()["items"][0]

    def fail_batch_delete(session, *args):
        if any(isinstance(item, ImportBatch) for item in session.deleted):
            raise RuntimeError("Fallo simulado de transacción")

    event.listen(Session, "before_flush", fail_batch_delete)
    try:
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            remove(client, batch["id"])
    finally:
        event.remove(Session, "before_flush", fail_batch_delete)
    with Session(engine) as db:
        assert db.get(ImportBatch, batch["id"]) is not None
        assert (
            len(db.scalars(select(Entry).where(Entry.batch_id == batch["id"])).all())
            == 2
        )


def test_import_pagination_and_invalid_parameters(client):
    login(client)
    for index in range(3):
        upload(client, prefix=f"page-{index}")
    page = client.get("/api/financial/imports?limit=1&offset=1").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["offset"] == 1 and page["limit"] == 1
    assert page["items"][0]["id"] == 2
    for query in ["limit=0", "limit=101", "offset=-1"]:
        assert client.get("/api/financial/imports?" + query).status_code == 422
    assert remove(client, 99999).status_code == 404
    assert remove(client, 0).status_code == 422


def test_stale_import_fingerprint_cannot_delete_a_different_load(client):
    login(client)
    upload(client)
    batch = client.get("/api/financial/imports").json()["items"][0]
    result = client.request(
        "DELETE",
        f"/api/financial/imports/{batch['id']}",
        json={"confirmation": f"ELIMINAR {batch['id']}", "sha256": "0" * 64},
    )
    assert result.status_code == 409
    assert client.get("/api/financial/imports").json()["items"][0]["entry_count"] == 2
