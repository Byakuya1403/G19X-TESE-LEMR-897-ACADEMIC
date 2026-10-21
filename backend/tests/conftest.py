import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp()) / "test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import Base, engine
from app.models import User
from app.security import hash_password
from app.routers.auth import login_attempts


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
