"""Contratos de entrada para autenticación y administración de cuentas."""

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
