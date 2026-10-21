import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp()) / "test.db")
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.models import User, LoginSession
from app.security import hash_password
from app.routers.auth import login_attempts
from sqlalchemy.orm import Session
from sqlalchemy import select
import pytest


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    login_attempts.clear()
    with TestClient(app) as c:
        with Session(engine) as db:
            for username, role in [
                ("director", "director"),
                ("analista", "analyst"),
                ("admin", "admin"),
            ]:
                db.add(
                    User(
                        username=username,
                        role=role,
                        password_hash=hash_password("UnaClaveSegura2026"),
                    )
                )
            db.commit()
        c.headers["X-App"] = "1"
        c.post(
            "/api/auth/login",
            json={"username": "director", "password": "UnaClaveSegura2026"},
        )
        yield c


CSV_HEADER = "ID_Registro,Anio,Mes,Categoria,Subcategoria,Concepto,Presupuesto_Estimado,Gasto_Real,Diferencia_Varianza,Porcentaje_Ejecucion,Estado\n"


def enterprise_csv(rows):
    return (CSV_HEADER + rows).encode("utf-8")


def test_financial_dashboard_and_simulation(client):
    financial_login(client)
    content = enterprise_csv(
        "test-1,2026,Enero,TI,Nómina,Salarios,40,50,-10,125,Completado\n"
        "test-2,2026,Enero,TI,Servicios,Operación,60,60,0,100,Completado\n"
    )
    assert import_enterprise(client, content=content, repair=False).status_code == 201
    data = client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()
    assert data["expense"]["budget"] == 100 and data["expense"]["actual"] == 110
    assert data["alerts"][0]["deviation"] == 10
    scenario = client.post(
        "/api/financial/simulations",
        json={
            "period": "2026-01",
            "currency": "MXN",
            "inflation": 10,
            "operating": 0,
            "payroll": 20,
        },
    ).json()
    assert scenario["baseline"] == 110 and scenario["projected"] == 126
    assert import_enterprise(client, content=content, repair=False).status_code == 409


def test_import_is_atomic_and_validated(client):
    financial_login(client)
    row = "test-1,2026,Enero,TI,Servicios,Operación,100,80,20,80,Completado\n"
    assert (
        import_enterprise(
            client, content=enterprise_csv(row + row), repair=False
        ).status_code
        == 422
    )
    assert client.get("/api/financial/entries").json() == []
    invalid = "test-1,2026,Enero,TI,Servicios,Operación,-100,80,-180,0,Completado\n"
    assert (
        import_enterprise(
            client, content=enterprise_csv(invalid), repair=False
        ).status_code
        == 422
    )
    assert client.get("/api/financial/entries").json() == []


def test_zero_budget_and_forecast_horizon(client):
    financial_login(client)
    content = enterprise_csv(
        "test-1,2026,Enero,TI,Servicios,Operación,0,1,-1,0,Completado\n"
        "test-2,2026,Febrero,TI,Servicios,Operación,500,500,0,100,Completado\n"
    )
    assert import_enterprise(client, content=content, repair=False).status_code == 201
    data = client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()
    assert data["expense"]["actual"] == 1 and data["entries"][0]["execution"] is None
    assert data["alerts"][0]["deviation"] == 1
    assert data["prediction"]["next_period"] == "2026-03"
    assert data["prediction"]["amount"] == 250.5


def test_guest_never_reads_real_data(client):
    financial_login(client)
    content = enterprise_csv(
        "private-1,2026,Enero,Confidencial,Servicios,Secreto,100,80,20,80,Completado\n"
    )
    assert import_enterprise(client, content=content, repair=False).status_code == 201
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json() is None
    data = client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()
    assert data["demo"] is True
    assert all(entry["category"] != "Confidencial" for entry in data["entries"])
    assert all(
        entry["source_id"] != "private-1"
        for entry in client.get("/api/financial/entries").json()
    )
    assert import_enterprise(client, content=content, repair=False).status_code == 401
    assert (
        client.post(
            "/api/financial/simulations", json={"period": "2026-01", "currency": "MXN"}
        ).status_code
        == 401
    )


def test_role_permissions_and_session(client):
    assert client.get("/api/users").status_code == 403
    assert import_enterprise(client).status_code == 403  # Director no importa.
    financial_login(client)
    assert import_enterprise(client).status_code == 201
    assert client.get("/api/users").status_code == 403
    client.post(
        "/api/auth/login",
        json={"username": "director", "password": "UnaClaveSegura2026"},
    )
    assert (
        client.post(
            "/api/financial/simulations", json={"period": "2026-01", "currency": "MXN"}
        ).status_code
        == 200
    )
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    assert import_enterprise(client).status_code == 403
    assert (
        client.post(
            "/api/financial/simulations", json={"period": "2026-01", "currency": "MXN"}
        ).status_code
        == 403
    )
    assert client.get("/api/users").status_code == 200
    assert (
        client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()[
            "demo"
        ]
        is True
    )
    with Session(engine) as db:
        for session in db.query(LoginSession).all():
            session.expires = 0
        db.commit()
    assert client.get("/api/auth/me").json() is None
    assert client.get("/api/users").status_code == 401


def test_invalid_login_and_csrf(client):
    assert (
        client.post(
            "/api/auth/login", json={"username": "director", "password": "incorrecta"}
        ).status_code
        == 401
    )
    assert client.get("/api/auth/me").json()["role"] == "director"
    client.headers.pop("X-App")
    assert (
        client.post(
            "/api/financial/simulations", json={"period": "2026-01", "currency": "MXN"}
        ).status_code
        == 403
    )
    assert client.post("/api/auth/logout").status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "director", "password": "UnaClaveSegura2026"},
        ).status_code
        == 403
    )


def test_user_creation_normalization_and_errors(client):
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    payload = {
        "username": "  Yosh.Test  ",
        "password": "UnaClaveNueva2026",
        "role": "analyst",
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 201
    assert response.json()["username"] == "yosh.test"
    assert client.post("/api/users", json=payload).status_code == 409
    assert (
        client.post(
            "/api/users", json={**payload, "username": "otro", "password": "corta"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/users", json={**payload, "username": "nombre con espacios"}
        ).status_code
        == 422
    )
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "YOSH.TEST", "password": payload["password"]},
        ).status_code
        == 200
    )


SAMPLE = Path(__file__).parents[2] / "examples/presupuesto_empresarial_2026.csv"


def financial_login(client):
    client.post(
        "/api/auth/login",
        json={"username": "analista", "password": "UnaClaveSegura2026"},
    )


def import_enterprise(client, content=None, repair=True, currency="MXN"):
    return client.post(
        "/api/financial/imports/csv",
        files={"file": ("presupuesto.csv", content or SAMPLE.read_bytes(), "text/csv")},
        data={"currency": currency, "repair_shifted": str(repair).lower()},
    )


def test_enterprise_import_repair_and_reconciliation(client):
    financial_login(client)
    assert import_enterprise(client, repair=False).status_code == 422
    assert client.get("/api/financial/entries").json() == []
    preview = client.post(
        "/api/financial/imports/preview",
        files={"file": ("p.csv", SAMPLE.read_bytes())},
        data={"repair_shifted": "true"},
    ).json()
    assert (
        preview["count"] == 36
        and len(preview["warnings"]) == 5
        and preview["pending"] == 10
    )
    result = import_enterprise(client)
    assert result.status_code == 201, result.text
    assert result.json()["imported"] == 36
    entries = client.get("/api/financial/entries").json()
    repaired = next(e for e in entries if e["source_id"] == "132")
    assert (
        repaired["period"] == "2026-01"
        and repaired["category"] == "Tecnología e Infraestructura"
    )
    for month, income, expense in [("01", 285600, 189120.5), ("02", 285000, 203110)]:
        d = client.get(
            "/api/financial/dashboard",
            params={"period": "2026-" + month, "currency": "MXN"},
        ).json()
        assert d["income"]["actual"] == income and d["expense"]["actual"] == expense
        assert d["balance"] == income - expense
    march = client.get("/api/financial/dashboard?period=2026-03&currency=MXN").json()
    assert march["expense"]["actual"] is None and march["balance"] is None
    assert march["prediction"]["months"] == 2
    assert march["prediction"]["reference_period"] == "2026-03"
    assert march["prediction"]["next_period"] == "2026-04"
    jan = client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()
    assert jan["prediction"] == march["prediction"]
    assert march["prediction"]["amount"] == 196115.25
    assert (
        client.post(
            "/api/financial/simulations", json={"period": "2026-03", "currency": "MXN"}
        ).status_code
        == 422
    )
    sim = client.post(
        "/api/financial/simulations", json={"period": "2026-01", "currency": "MXN"}
    ).json()
    assert sim["baseline"] == 189120.5 and sim["projected"] == 189120.5
    assert import_enterprise(client).status_code == 409
    assert len(client.get("/api/financial/entries").json()) == 36
    client.post("/api/auth/logout")
    guest = client.get("/api/financial/entries").json()
    assert all(e["source_id"] not in ("101", "132") for e in guest)
    assert (
        client.post(
            "/api/financial/imports/preview",
            files={"file": ("p.csv", SAMPLE.read_bytes())},
        ).status_code
        == 401
    )


def test_enterprise_validation_is_atomic_and_role_enforced(client):
    assert import_enterprise(client).status_code == 403
    financial_login(client)
    content = SAMPLE.read_bytes().replace(b"6500.0,6500.0", b"-6500.0,6500.0", 1)
    assert import_enterprise(client, content=content).status_code == 422
    assert client.get("/api/financial/entries").json() == []
    assert import_enterprise(client, currency="pesos").status_code == 422
    assert import_enterprise(client, currency="USD").status_code == 201
    mxn = client.get("/api/financial/dashboard?period=2026-01&currency=MXN").json()
    usd = client.get("/api/financial/dashboard?period=2026-01&currency=USD").json()
    assert mxn["entries"] == [] and usd["income"]["actual"] == 285600
    assert (
        client.post(
            "/api/financial/simulations",
            json={"period": "2026-01", "currency": "USD", "inflation": 1000},
        ).status_code
        == 422
    )


def test_forecast_orders_months_and_changes_year():
    from app.financial import forecast_expenses
    from types import SimpleNamespace
    from decimal import Decimal

    rows = [
        SimpleNamespace(
            year=y,
            month=m,
            nature="expense",
            category="Operación",
            actual=Decimal(v) if v is not None else None,
        )
        for y, m, v in [(2026, 12, None), (2026, 1, 100), (2026, 11, 300)]
    ]
    forecast = forecast_expenses(rows)
    assert forecast["reference_period"] == "2026-12"
    assert forecast["next_period"] == "2027-01"
    assert forecast["periods_available"] == ["2026-01", "2026-11", "2026-12"]
    assert forecast["periods_used"] == ["2026-01", "2026-11"]
    assert forecast["amount"] == 200
    assert forecast_expenses(list(reversed(rows))) == forecast
    rows.append(
        SimpleNamespace(
            year=2027,
            month=1,
            nature="expense",
            category="Operación",
            actual=Decimal(500),
        )
    )
    assert forecast_expenses(rows)["next_period"] == "2027-02"
    assert forecast_expenses(rows)["amount"] == 300
    # A category filter cannot move the dataset's horizon to another month.
    assert forecast_expenses(rows, category="Sin datos")["next_period"] == "2027-02"
    assert forecast_expenses(rows, category="Sin datos")["amount"] is None
    assert forecast_expenses([])["next_period"] is None
    pending = [
        SimpleNamespace(
            year=2026, month=3, nature="expense", category="Operación", actual=None
        )
    ]
    assert forecast_expenses(pending)["next_period"] == "2026-04"
    assert forecast_expenses(pending)["amount"] is None


@pytest.fixture()
def invitation_client(client, monkeypatch):
    from app.invitations import attempts

    attempts.clear()
    monkeypatch.setenv("INVITE_DELIVERY", "manual")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://localhost:8080")
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    return client


def invitation(client, email="persona@gmail.com"):
    response = client.post(
        "/api/users/invitations", json={"email": email, "role": "analyst"}
    )
    assert response.status_code == 201, response.text
    return response.json()["activation_url"].split("#activar=")[1]


def activate_payload(token, **extra):
    return dict(
        token=token,
        password="MiContraseñaPersonal2026",
        confirmation="MiContraseñaPersonal2026",
        **extra,
    )


def test_email_invitation_activation_and_single_use(invitation_client):
    from app.models import UserEmail, UserInvitation
    import hashlib

    c = invitation_client
    token = invitation(c, "  Persona@GMAIL.com ")
    user = next(
        u for u in c.get("/api/users").json() if u["email"] == "persona@gmail.com"
    )
    assert user["status"] == "pending" and not user["active"]
    with Session(engine) as db:
        stored = db.get(UserInvitation, user["id"])
        assert (
            stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
            and token not in stored.token_hash
        )
        assert db.get(UserEmail, user["id"]).verified is False
    c.post("/api/auth/logout")
    assert (
        c.post(
            "/api/auth/login",
            json={
                "username": "persona@gmail.com",
                "password": "MiContraseñaPersonal2026",
            },
        ).status_code
        == 401
    )
    # Mail scanners and page previews do not consume the invitation.
    for _ in range(2):
        preview = c.post("/api/auth/invitation/validate", json={"token": token})
        assert (
            preview.status_code == 200
            and preview.headers["cache-control"] == "no-store"
        )
    activated = c.post("/api/auth/activate", json=activate_payload(token))
    assert activated.status_code == 200
    assert c.get("/api/auth/me").json() is None  # no automatic login
    assert c.post("/api/auth/activate", json=activate_payload(token)).status_code == 400
    assert (
        c.post("/api/auth/invitation/validate", json={"token": token}).status_code
        == 400
    )
    signed = c.post(
        "/api/auth/login",
        json={"username": "PERSONA@GMAIL.COM", "password": "MiContraseñaPersonal2026"},
    )
    assert (
        signed.status_code == 200
        and signed.json()["role"] == "analyst"
        and signed.json()["email"] == "persona@gmail.com"
    )
    assert c.get("/api/users").status_code == 403


def test_invitation_expiry_resend_and_password_policy(invitation_client):
    from app.models import UserInvitation

    c = invitation_client
    old = invitation(c)
    user = next(
        u for u in c.get("/api/users").json() if u["email"] == "persona@gmail.com"
    )
    with Session(engine) as db:
        db.get(UserInvitation, user["id"]).expires = 0
        db.commit()
    assert c.post("/api/auth/activate", json=activate_payload(old)).status_code == 400
    new = (
        c.post(f"/api/users/{user['id']}/invitation")
        .json()["activation_url"]
        .split("#activar=")[1]
    )
    assert new != old
    assert (
        c.post("/api/auth/invitation/validate", json={"token": old}).status_code == 400
    )
    wrong = activate_payload(new)
    wrong["confirmation"] = "OtraContraseña2026"
    assert c.post("/api/auth/activate", json=wrong).status_code == 422
    wrong = activate_payload(new)
    wrong["password"] = wrong["confirmation"] = "corta"
    assert c.post("/api/auth/activate", json=wrong).status_code == 422
    assert c.post("/api/auth/activate", json=activate_payload(new)).status_code == 200
    assert c.post(f"/api/users/{user['id']}/invitation").status_code == 409


def test_invitation_permissions_email_validation_and_config(
    invitation_client, monkeypatch
):
    c = invitation_client
    for email in [
        "sin-correo",
        "persona@gmail.com\r\nBcc: otro@gmail.com",
        "Nombre <persona@gmail.com>",
    ]:
        assert (
            c.post(
                "/api/users/invitations", json={"email": email, "role": "analyst"}
            ).status_code
            == 422
        )
    invitation(c)
    assert (
        c.post(
            "/api/users/invitations",
            json={"email": "PERSONA@gmail.com", "role": "director"},
        ).status_code
        == 409
    )
    monkeypatch.setenv("APP_PUBLIC_URL", "http://empresa.com")
    assert (
        c.post(
            "/api/users/invitations",
            json={"email": "otra@gmail.com", "role": "analyst"},
        ).status_code
        == 503
    )
    assert not any(u["email"] == "otra@gmail.com" for u in c.get("/api/users").json())
    c.post(
        "/api/auth/login",
        json={"username": "director", "password": "UnaClaveSegura2026"},
    )
    assert (
        c.post(
            "/api/users/invitations",
            json={"email": "otra@gmail.com", "role": "analyst"},
        ).status_code
        == 403
    )
    c.post("/api/auth/logout")
    assert (
        c.post(
            "/api/users/invitations",
            json={"email": "otra@gmail.com", "role": "analyst"},
        ).status_code
        == 401
    )
    c.headers.pop("X-App")
    assert (
        c.post("/api/auth/activate", json=activate_payload("a" * 43)).status_code == 403
    )


def test_smtp_failure_retains_old_link_and_new_creation_is_atomic(
    invitation_client, monkeypatch
):
    import smtplib
    import app.invitations as module

    c = invitation_client
    old = invitation(c)
    user = next(
        u for u in c.get("/api/users").json() if u["email"] == "persona@gmail.com"
    )
    monkeypatch.setenv("INVITE_DELIVERY", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "presupuesto@example.com")

    def fail(*args):
        raise smtplib.SMTPException("private server error")

    monkeypatch.setattr(module, "send_invitation", fail)
    assert c.post(f"/api/users/{user['id']}/invitation").status_code == 502
    assert (
        c.post("/api/auth/invitation/validate", json={"token": old}).status_code == 200
    )
    response = c.post(
        "/api/users/invitations", json={"email": "otra@gmail.com", "role": "director"}
    )
    assert response.status_code == 502 and "private server error" not in response.text
    assert not any(u["email"] == "otra@gmail.com" for u in c.get("/api/users").json())


def test_smtp_delivery_does_not_expose_token_to_admin(invitation_client, monkeypatch):
    import app.invitations as module

    c = invitation_client
    captured = []
    monkeypatch.setenv("INVITE_DELIVERY", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM", "presupuesto@example.com")
    monkeypatch.setattr(
        module,
        "send_invitation",
        lambda email, role, link: captured.append((email, role, link)),
    )
    response = c.post(
        "/api/users/invitations", json={"email": "otra@gmail.com", "role": "director"}
    )
    assert response.status_code == 201 and response.json()["delivery"] == "smtp"
    assert "activation_url" not in response.json() and len(captured) == 1
    token = captured[0][2].split("#activar=")[1]
    assert c.post("/api/auth/activate", json=activate_payload(token)).status_code == 200


def test_invitation_activation_rate_limited(invitation_client):
    c = invitation_client
    for _ in range(20):
        assert (
            c.post(
                "/api/auth/invitation/validate", json={"token": "a" * 43}
            ).status_code
            == 400
        )
    assert (
        c.post("/api/auth/invitation/validate", json={"token": "a" * 43}).status_code
        == 429
    )


def test_smtp_uses_tls_and_only_sends_activation_link(monkeypatch):
    import app.invitations as module
    import ssl

    sent = []
    steps = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            steps.append("ehlo")

        def starttls(self, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            steps.append("tls")

        def login(self, user, password):
            assert (user, password) == ("env-user", "smtp-secret")
            steps.append("auth")

        def send_message(self, message):
            sent.append(message)
            return {}

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "presupuesto@example.com")
    monkeypatch.setenv("SMTP_SECURITY", "starttls")
    monkeypatch.setenv("SMTP_USER", "env-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setattr(module.smtplib, "SMTP", SMTP)
    module.send_invitation(
        "persona@gmail.com", "analyst", "https://presupuesto.example.com/#activar=token"
    )
    assert steps == ["ehlo", "tls", "ehlo", "auth"] and len(sent) == 1
    assert sent[0]["To"] == "persona@gmail.com"
    assert (
        "#activar=token" in sent[0].get_content()
        and "smtp-secret" not in sent[0].as_string()
    )


def test_delete_user_permissions_and_self_protection(client):
    with Session(engine) as db:
        target = db.scalar(select(User).where(User.username == "analista")).id
        admin = db.scalar(select(User).where(User.username == "admin")).id
    assert client.delete(f"/api/users/{target}").status_code == 403
    client.post("/api/auth/logout")
    assert client.delete(f"/api/users/{target}").status_code == 401
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    assert client.delete(f"/api/users/{admin}").status_code == 409
    assert client.get("/api/auth/me").json()["username"] == "admin"
    assert client.delete("/api/users/999999").status_code == 404
    client.headers.pop("X-App")
    assert client.delete(f"/api/users/{target}").status_code == 403


def test_delete_active_user_revokes_sessions_preserves_financial_data(client):
    import hashlib

    financial_login(client)
    assert import_enterprise(client).status_code == 201
    session_token = client.cookies.get("finanzas_session")
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    # Include a second outstanding session, not just the cookie replaced at login.
    with Session(engine) as db:
        target = db.scalar(select(User).where(User.username == "analista")).id
        db.add(
            LoginSession(
                token_hash=hashlib.sha256(session_token.encode()).hexdigest(),
                user_id=target,
                expires=9999999999,
            )
        )
        db.commit()
    assert client.delete(f"/api/users/{target}").status_code == 200
    assert not any(u["id"] == target for u in client.get("/api/users").json())
    with Session(engine) as db:
        assert db.get(User, target) is None
        assert (
            db.scalar(select(LoginSession).where(LoginSession.user_id == target))
            is None
        )
    assert client.delete(f"/api/users/{target}").status_code == 404
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "analista", "password": "UnaClaveSegura2026"},
        ).status_code
        == 401
    )
    client.post(
        "/api/auth/login",
        json={"username": "director", "password": "UnaClaveSegura2026"},
    )
    assert len(client.get("/api/financial/entries").json()) == 36
    # Removed session cannot regain real financial access.
    client.cookies.clear()
    client.cookies.set("finanzas_session", session_token, path="/api")
    assert client.get("/api/auth/me").json() is None


def test_delete_pending_invitation_and_reinvite(invitation_client):
    from app.models import UserEmail, UserInvitation

    c = invitation_client
    token = invitation(c)
    target = next(
        u["id"] for u in c.get("/api/users").json() if u["email"] == "persona@gmail.com"
    )
    assert c.delete(f"/api/users/{target}").status_code == 200
    with Session(engine) as db:
        assert (
            db.get(UserEmail, target) is None and db.get(UserInvitation, target) is None
        )
    assert c.post("/api/auth/activate", json=activate_payload(token)).status_code == 400
    new = invitation(c)
    assert new != token


def test_delete_other_admin_keeps_current_admin(client):
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "UnaClaveSegura2026"}
    )
    assert (
        client.post(
            "/api/users",
            json={
                "username": "admin_dos",
                "role": "admin",
                "password": "OtraClaveSegura2026",
            },
        ).status_code
        == 201
    )
    target = next(
        u["id"] for u in client.get("/api/users").json() if u["username"] == "admin_dos"
    )
    assert client.delete(f"/api/users/{target}").status_code == 200
    assert client.get("/api/auth/me").json()["username"] == "admin"
    assert (
        len(
            [
                u
                for u in client.get("/api/users").json()
                if u["role"] == "admin" and u["active"]
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/budgets"),
        ("post", "/api/budgets"),
        ("get", "/api/dashboard"),
        ("post", "/api/simulations"),
        ("post", "/api/imports/csv"),
    ],
)
def test_removed_legacy_routes_return_404_and_are_absent_from_openapi(
    client, method, path
):
    assert getattr(client, method)(path).status_code == 404
    assert path not in client.get("/openapi.json").json()["paths"]


def test_existing_budget_data_survives_startup(client):
    from app.models import Budget
    from decimal import Decimal

    with Session(engine) as db:
        budget = Budget(
            department="Histórico",
            period="2026-01",
            amount=Decimal(100),
            payroll=Decimal(40),
            operating=Decimal(20),
        )
        db.add(budget)
        db.commit()
        budget_id = budget.id
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert db.get(Budget, budget_id).amount == Decimal(100)
    assert client.get("/api/financial/entries").json() == []
