"""Email invitations: no temporary passwords and no raw tokens stored in SQL."""

import hashlib
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.parse import urlsplit

from email_validator import validate_email, EmailNotValidError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from .database import DB
from .models import (
    User,
    UserEmail as Contact,
    UserInvitation as Invitation,
    LoginSession,
)
from .security import Administrator, hash_password

INVITATION_SECONDS = 24 * 60 * 60
attempts = {}


def normalize_email(value):
    try:
        normalized = validate_email(
            value.strip(), check_deliverability=False, allow_smtputf8=False
        ).ascii_email.lower()
        if len(normalized) > 254:
            raise ValueError("Correo demasiado largo")
        return normalized
    except (EmailNotValidError, AttributeError) as exc:
        raise ValueError("Escribe un correo válido, personal o empresarial") from exc


class InviteInput(BaseModel):
    email: str = Field(max_length=254)
    role: str = Field(pattern=r"^(director|analyst|admin)$")

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        return normalize_email(value)


class TokenInput(BaseModel):
    token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")


class ActivateInput(TokenInput):
    password: str = Field(min_length=12, max_length=128)
    confirmation: str = Field(min_length=12, max_length=128)


def throttle(key, limit):
    now = time.time()
    for stale in list(attempts):
        if not attempts[stale] or now - attempts[stale][-1] >= 60:
            attempts.pop(stale, None)
    recent = [t for t in attempts.get(key, []) if now - t < 60]
    if len(recent) >= limit:
        raise HTTPException(429, "Demasiados intentos. Espera un minuto")
    attempts[key] = recent + [now]


def settings():
    mode = os.getenv("INVITE_DELIVERY", "smtp").lower()
    origin = os.getenv("APP_PUBLIC_URL", "").rstrip("/")
    url = urlsplit(origin)
    local = url.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
        or (url.scheme != "https" and not (url.scheme == "http" and local))
    ):
        raise ValueError(
            "Configura APP_PUBLIC_URL con la dirección HTTPS de la plataforma; HTTP solo se admite en localhost."
        )
    if not local and os.getenv("COOKIE_SECURE", "false").lower() != "true":
        raise ValueError(
            "Activa COOKIE_SECURE=true al publicar la plataforma por HTTPS."
        )
    if mode not in ("smtp", "manual"):
        raise ValueError("INVITE_DELIVERY debe ser smtp o manual.")
    if mode == "smtp":
        if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
            raise ValueError(
                "Falta configurar SMTP_HOST y SMTP_FROM para enviar invitaciones por correo."
            )
        normalize_email(os.getenv("SMTP_FROM"))
        if os.getenv("SMTP_SECURITY", "starttls") not in ("starttls", "ssl"):
            raise ValueError("SMTP_SECURITY debe ser starttls o ssl.")
        try:
            if not 1 <= int(os.getenv("SMTP_PORT", "587")) <= 65535:
                raise ValueError()
        except ValueError:
            raise ValueError("SMTP_PORT debe ser un puerto válido.")
        if os.getenv("SMTP_USER") and not os.getenv("SMTP_PASSWORD"):
            raise ValueError("Falta configurar SMTP_PASSWORD.")
    return mode, origin


def send_invitation(email, role, link):
    message = EmailMessage()
    message["From"] = normalize_email(os.environ["SMTP_FROM"])
    message["To"] = email
    message["Subject"] = "Activa tu cuenta · Plataforma de Presupuesto"
    role_name = {
        "admin": "Administrador",
        "director": "Director Financiero",
        "analyst": "Analista Financiero",
    }[role]
    message.set_content(
        f"Te han invitado a la Plataforma de Presupuesto con el rol {role_name}.\n\n"
        f"Abre este enlace y elige tu propia contraseña:\n{link}\n\n"
        "El enlace caduca en 24 horas y solo puede usarse una vez. No lo compartas.\n"
        "Si no esperabas esta invitación, ignora el mensaje y contacta al administrador."
    )
    context = ssl.create_default_context()
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    if os.getenv("SMTP_SECURITY", "starttls") == "ssl":
        transport = smtplib.SMTP_SSL(host, port, timeout=10, context=context)
    else:
        transport = smtplib.SMTP(host, port, timeout=10)
    with transport as smtp:
        if os.getenv("SMTP_SECURITY", "starttls") != "ssl":
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPException("Recipient refused")


router = APIRouter(tags=["Invitaciones"])


@router.get("/api/users/invitation-settings")
def invitation_settings(user: Administrator):
    try:
        mode, _ = settings()
        return dict(
            configured=True,
            mode=mode,
            message=(
                "Envío por correo configurado; la entrega se comprueba al enviar."
                if mode == "smtp"
                else "Modo manual: no se enviarán correos. Comparte el enlace de forma privada."
            ),
        )
    except ValueError as exc:
        return dict(
            configured=False,
            mode=os.getenv("INVITE_DELIVERY", "smtp"),
            message=str(exc),
        )


def issue(session, account, contact):
    try:
        mode, origin = settings()
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    token = secrets.token_urlsafe(32)
    expires = time.time() + INVITATION_SECONDS
    old = session.get(Invitation, account.id)
    if old:
        session.delete(old)
        session.flush()
    session.add(
        Invitation(
            user_id=account.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires=expires,
        )
    )
    session.flush()
    link = f"{origin}/#activar={token}"
    if mode == "smtp":
        try:
            send_invitation(contact.email, account.role, link)
        except (OSError, smtplib.SMTPException):
            session.rollback()
            raise HTTPException(
                502,
                "El servidor de correo no aceptó el envío. Revisa la configuración SMTP y vuelve a intentarlo; no se cambió la invitación anterior.",
            )
    session.commit()
    return dict(
        email=contact.email,
        role=account.role,
        delivery=mode,
        expires=expires,
        **({"activation_url": link} if mode == "manual" else {}),
    )


@router.post("/api/users/invitations", status_code=201)
def invite(data: InviteInput, session: DB, user: Administrator):
    throttle(("invite", user.id), 10)
    if session.scalar(select(Contact).where(Contact.email == data.email)):
        raise HTTPException(
            409,
            "Ese correo ya está registrado. Usa Reenviar invitación si sigue pendiente.",
        )
    try:
        account = User(
            username="invitado_" + secrets.token_hex(16),
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=data.role,
            active=False,
        )
        session.add(account)
        session.flush()
        contact = Contact(user_id=account.id, email=data.email, verified=False)
        session.add(contact)
        session.flush()
        return issue(session, account, contact)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Ese correo ya está registrado.")


@router.post("/api/users/{user_id}/invitation")
def resend(user_id: int, session: DB, user: Administrator):
    throttle(("invite", user.id), 10)
    account = session.scalar(select(User).where(User.id == user_id).with_for_update())
    contact = session.get(Contact, user_id)
    if not account or not contact:
        raise HTTPException(404, "No hay una invitación para esta cuenta.")
    if account.active or contact.verified:
        raise HTTPException(
            409,
            "La cuenta ya está activada; no se cambia su contraseña con una invitación.",
        )
    return issue(session, account, contact)


def protect(request):
    if request.headers.get("X-App") != "1":
        raise HTTPException(403, "Solicitud no válida")
    throttle(("activate", request.client.host if request.client else "local"), 20)


def lookup(session, token, lock=False):
    invitation = session.scalar(
        select(Invitation).where(
            Invitation.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            Invitation.expires > time.time(),
        )
    )
    account = (
        session.scalar(
            select(User)
            .where(User.id == invitation.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if invitation and lock
        else session.get(User, invitation.user_id) if invitation else None
    )
    if invitation and lock:
        invitation = session.scalar(
            select(Invitation)
            .where(
                Invitation.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                Invitation.expires > time.time(),
            )
            .execution_options(populate_existing=True)
        )
    contact = session.get(Contact, invitation.user_id) if invitation else None
    if (
        not invitation
        or not account
        or not contact
        or account.active
        or contact.verified
    ):
        raise HTTPException(
            400,
            "El enlace no es válido, ya se usó o ha caducado. Pide al administrador una nueva invitación.",
        )
    return invitation, account, contact


@router.post("/api/auth/invitation/validate")
def validate(data: TokenInput, request: Request, response: Response, session: DB):
    protect(request)
    response.headers["Cache-Control"] = "no-store"
    invitation, account, contact = lookup(session, data.token)
    return dict(email=contact.email, role=account.role, expires=invitation.expires)


@router.post("/api/auth/activate")
def activate(data: ActivateInput, request: Request, response: Response, session: DB):
    protect(request)
    response.headers["Cache-Control"] = "no-store"
    if data.password != data.confirmation:
        raise HTTPException(422, "Las contraseñas no coinciden.")
    invitation, account, contact = lookup(session, data.token, lock=True)
    password_hash = hash_password(data.password)
    # Atomic consumption: competing submissions cannot reuse this invitation.
    consumed = session.execute(
        delete(Invitation).where(
            Invitation.user_id == invitation.user_id,
            Invitation.token_hash == hashlib.sha256(data.token.encode()).hexdigest(),
            Invitation.expires > time.time(),
        ),
        execution_options={"synchronize_session": False},
    )
    if consumed.rowcount != 1:
        session.rollback()
        raise HTTPException(400, "El enlace ya se usó o ha caducado.")
    account.password_hash = password_hash
    account.active = True
    contact.verified = True
    session.execute(delete(LoginSession).where(LoginSession.user_id == account.id))
    session.commit()
    return dict(ok=True, email=contact.email)
