import argparse
import getpass
from sqlalchemy.orm import Session
from sqlalchemy import select
from .main import Base, engine, User, hash_password
parser = argparse.ArgumentParser(description="Crear cuenta inicial local")
parser.add_argument("username")
parser.add_argument("role", choices=["director", "analyst", "admin"])
args = parser.parse_args()
username = args.username.strip().lower()
import re
if not re.fullmatch(r"[a-z0-9._-]{3,100}", username): parser.error("Usuario: 3 a 100 letras minúsculas, números, punto, guión o guión bajo")
password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
if not 12 <= len(password) <= 128: parser.error("Contraseña de 12 a 128 caracteres")
if password != getpass.getpass("Confirmar contraseña: "): parser.error("No coinciden")
Base.metadata.create_all(engine)
with Session(engine) as session:
    if session.scalar(select(User).where(User.username==username)): parser.error("Ya existe")
    session.add(User(username=username, role=args.role, password_hash=hash_password(password)))
    session.commit()
print("Cuenta creada:", username, args.role)
