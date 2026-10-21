"""Modelos persistentes. Cambiar de módulo no cambia tablas ni columnas."""

from decimal import Decimal
from sqlalchemy import (
    Integer,
    Boolean,
    Float,
    ForeignKey,
    Numeric,
    String,
    JSON,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("department", "period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column(String(100))
    period: Mapped[str] = mapped_column(String(7))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    payroll: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    operating: Mapped[Decimal] = mapped_column(Numeric(16, 2))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires: Mapped[float] = mapped_column(Float)


class UserEmail(Base):
    __tablename__ = "user_emails"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class UserInvitation(Base):
    __tablename__ = "user_invitations"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires: Mapped[float] = mapped_column(Float)


class ImportBatch(Base):
    __tablename__ = "financial_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3))
    username: Mapped[str] = mapped_column(String(100))
    warnings: Mapped[list] = mapped_column(JSON)


class Entry(Base):
    __tablename__ = "financial_entries"
    __table_args__ = (
        UniqueConstraint("year", "source_id", "currency"),
        CheckConstraint("month BETWEEN 1 AND 12"),
        CheckConstraint("year BETWEEN 1900 AND 9999"),
        CheckConstraint("budget >= 0"),
        CheckConstraint("actual IS NULL OR actual >= 0"),
        CheckConstraint("nature IN ('income','expense')"),
        CheckConstraint(
            "(status='pendiente' AND actual IS NULL) OR (status='completado' AND actual IS NOT NULL)"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("financial_imports.id"))
    source_id: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(150))
    subcategory: Mapped[str] = mapped_column(String(150))
    concept: Mapped[str] = mapped_column(String(300))
    nature: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    budget: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    actual: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(15))
    original: Mapped[dict] = mapped_column(JSON)
