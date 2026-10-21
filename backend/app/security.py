"""Contraseñas, sesión opcional y autorización reutilizable por rol."""

import hashlib
import hmac
import secrets
import time
from typing import Annotated
from fastapi import Depends, HTTPException, Request
from .database import DB
from .models import User, UserEmail, LoginSession


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 600000
    ).hex()
    return f"{salt}${digest}"


def check_password(password, encoded):
    salt, digest = encoded.split("$")
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 600000
    ).hex()
    return hmac.compare_digest(actual, digest)


def public_user(user, session=None):
    contact = session.get(UserEmail, user.id) if session else None
    return {
        "username": user.username,
        "email": contact.email if contact else None,
        "role": user.role,
    }


def optional_user(request: Request, session: DB):
    token = request.cookies.get("finanzas_session")
    if not token:
        return None
    login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not login or login.expires <= time.time():
        return None
    user = session.get(User, login.user_id)
    return user if user and user.active else None


CurrentUser = Annotated[User | None, Depends(optional_user)]


def permitted(*roles):
    def verify(request: Request, user: CurrentUser):
        if not user:
            raise HTTPException(401, "Inicia sesión para continuar")
        if user.role not in roles:
            raise HTTPException(403, "Tu rol no tiene permiso para esta acción")
        if request.method != "GET" and request.headers.get("X-App") != "1":
            raise HTTPException(403, "Solicitud no válida")
        return user

    return verify


Financial = Annotated[User, Depends(permitted("director", "analyst"))]
Director = Annotated[User, Depends(permitted("director"))]
Analyst = Annotated[User, Depends(permitted("analyst"))]
Administrator = Annotated[User, Depends(permitted("admin"))]
