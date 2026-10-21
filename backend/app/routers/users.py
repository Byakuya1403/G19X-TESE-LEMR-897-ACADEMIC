"""Administración de cuentas. Las invitaciones viven en invitations.py."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, delete
from ..database import DB
from ..models import User, UserEmail, UserInvitation, LoginSession
from ..schemas import UserInput
from ..security import Administrator, hash_password, public_user

router = APIRouter(tags=["Usuarios"])


@router.get("/api/users")
def list_users(session: DB, user: Administrator):
    result = []
    for u in session.scalars(select(User)).all():
        contact = session.get(UserEmail, u.id)
        invitation = session.get(UserInvitation, u.id)
        status = (
            "active"
            if u.active
            else "pending" if contact and not contact.verified else "disabled"
        )
        result.append(
            dict(
                id=u.id,
                **public_user(u, session),
                active=u.active,
                status=status,
                invitation_expires=invitation.expires if invitation else None
            )
        )
    return result


@router.delete("/api/users/{user_id}")
def delete_user(user_id: int, session: DB, user: Administrator):
    if user_id == user.id:
        raise HTTPException(409, "No puedes eliminar tu propia cuenta administrativa.")
    # Serialize administrator deletions on PostgreSQL, including competing admins.
    administrators = session.scalars(
        select(User)
        .where(User.role == "admin", User.active == True)
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if not any(a.id == user.id for a in administrators):
        raise HTTPException(403, "Tu cuenta ya no tiene acceso administrativo.")
    target = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if not target:
        raise HTTPException(404, "El usuario ya no existe.")
    if target.role == "admin" and target.active and len(administrators) <= 1:
        raise HTTPException(409, "Debe quedar al menos un administrador activo.")
    for model in (LoginSession, UserInvitation, UserEmail):
        session.execute(
            delete(model).where(model.user_id == user_id),
            execution_options={"synchronize_session": False},
        )
    session.delete(target)
    session.commit()
    return {"ok": True, "deleted_id": user_id}


@router.post("/api/users", status_code=201)
def add_user(data: UserInput, session: DB, user: Administrator):
    if session.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "El usuario ya existe")
    record = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    session.add(record)
    session.commit()
    return public_user(record)
