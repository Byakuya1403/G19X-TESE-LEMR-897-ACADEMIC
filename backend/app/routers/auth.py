"""Inicio y cierre de sesión con el mismo contrato y controles existentes."""

import hashlib
import os
import secrets
import time
from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from ..database import DB
from ..models import User, UserEmail, LoginSession
from ..schemas import LoginInput
from ..security import CurrentUser, check_password, hash_password, public_user

router = APIRouter(tags=["Autenticación"])
# Límite por proceso para desarrollo; compartir el almacén antes de escalar.
login_attempts = {}
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


@router.post("/api/auth/login")
def login(data: LoginInput, request: Request, response: Response, session: DB):
    if request.headers.get("X-App") != "1":
        raise HTTPException(403, "Solicitud no válida")
    key = request.client.host if request.client else "local"
    now = time.time()
    recent = [t for t in login_attempts.get(key, []) if now - t < 60]
    if len(recent) >= 10:
        raise HTTPException(429, "Demasiados intentos. Espera un minuto")
    login_attempts[key] = recent + [now]
    identifier = data.username.strip().lower()
    if "@" in identifier:
        from ..invitations import normalize_email

        try:
            identifier = normalize_email(identifier)
        except ValueError:
            pass
        user = session.scalar(
            select(User)
            .join(UserEmail)
            .where(UserEmail.email == identifier, UserEmail.verified == True)
            .with_for_update(of=User)
        )
    else:
        user = session.scalar(
            select(User).where(User.username == identifier).with_for_update()
        )
    valid = check_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.active or not valid:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    old_token = request.cookies.get("finanzas_session")
    if old_token:
        old = session.get(LoginSession, hashlib.sha256(old_token.encode()).hexdigest())
        if old:
            session.delete(old)
    token = secrets.token_urlsafe(32)
    session.add(
        LoginSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires=now + 28800,
        )
    )
    session.commit()
    response.set_cookie(
        "finanzas_session",
        token,
        max_age=28800,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        path="/api",
    )
    return public_user(user, session)


@router.get("/api/auth/me")
def me(user: CurrentUser, session: DB):
    return public_user(user, session) if user else None


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, session: DB):
    if request.headers.get("X-App") != "1":
        raise HTTPException(403, "Solicitud no válida")
    token = request.cookies.get("finanzas_session")
    if token:
        login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if login:
            session.delete(login)
            session.commit()
    response.delete_cookie("finanzas_session", path="/api")
    return {"ok": True}
