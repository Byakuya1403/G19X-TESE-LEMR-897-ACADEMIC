"""Base declarativa, conexión y sesión compartida por los módulos de la API."""

import os
from typing import Annotated
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./finanzas.db"))


class Base(DeclarativeBase):
    pass


def db():
    with Session(engine) as session:
        yield session


DB = Annotated[Session, Depends(db)]
