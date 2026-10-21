"""Contratos de entrada conservados para autenticación y formato anterior."""

from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, Field, field_validator


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserInput(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,100}$")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern=r"^(director|analyst|admin)$")


Money = Annotated[
    Decimal,
    Field(ge=0, le=Decimal("99999999999999.99"), max_digits=16, decimal_places=2),
]


class BudgetInput(BaseModel):
    department: str = Field(min_length=1, max_length=100)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Money
    payroll: Money
    operating: Money


class Scenario(BaseModel):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    department: str | None = None
    inflation: float = Field(ge=-10, le=30, default=0)
    operating: float = Field(ge=-50, le=50, default=0)
    payroll: float = Field(ge=-30, le=30, default=0)
