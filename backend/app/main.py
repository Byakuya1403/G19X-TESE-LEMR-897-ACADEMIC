import csv
import io
import os
import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import FastAPI, Depends, File, HTTPException, UploadFile, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import JSON, Integer, Boolean, Float, ForeignKey, Numeric, String, UniqueConstraint, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./finanzas.db"))
class Base(DeclarativeBase):
    pass
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

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"{salt}${digest}"
def check_password(password, encoded):
    salt, digest = encoded.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return hmac.compare_digest(actual, digest)
def public_user(user):
    return {"username": user.username, "role": user.role}

def demo_rows(period=None, department=None):
    data = [("Tecnología", 250000, 140000, 120000), ("Operaciones", 400000, 210000, 250000), ("Comercial", 180000, 98000, 60000)]
    return [Budget(id=i+1, department=n, period=period or "2026-09", amount=Decimal(a), payroll=Decimal(p), operating=Decimal(o)) for i,(n,a,p,o) in enumerate(data) if not department or n==department]

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="Plataforma de Presupuesto · Presupuesto corporativo", version="0.5.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8080"], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-App"], allow_credentials=True)
def db():
    with Session(engine) as session:
        yield session
DB = Annotated[Session, Depends(db)]
def optional_user(request: Request, session: DB):
    token = request.cookies.get("finanzas_session")
    if not token: return None
    login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not login or login.expires <= time.time(): return None
    user = session.get(User, login.user_id)
    return user if user and user.active else None
CurrentUser = Annotated[User | None, Depends(optional_user)]
def permitted(*roles):
    def verify(request: Request, user: CurrentUser):
        if not user: raise HTTPException(401, "Inicia sesión para continuar")
        if user.role not in roles: raise HTTPException(403, "Tu rol no tiene permiso para esta acción")
        if request.method != "GET" and request.headers.get("X-App") != "1":
            raise HTTPException(403, "Solicitud no válida")
        return user
    return verify
Financial = Annotated[User, Depends(permitted("director", "analyst"))]
Director = Annotated[User, Depends(permitted("director"))]
Analyst = Annotated[User, Depends(permitted("analyst"))]
Administrator = Annotated[User, Depends(permitted("admin"))]
class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
# Per-process throttle for local development. Use a shared store before scaling.
login_attempts = {}
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
@app.post("/api/auth/login")
def login(data: LoginInput, request: Request, response: Response, session: DB):
    if request.headers.get("X-App") != "1": raise HTTPException(403, "Solicitud no válida")
    key = request.client.host if request.client else "local"
    now = time.time()
    recent = [t for t in login_attempts.get(key, []) if now-t < 60]
    if len(recent)>=10: raise HTTPException(429, "Demasiados intentos. Espera un minuto")
    login_attempts[key] = recent+[now]
    user = session.scalar(select(User).where(User.username==data.username.strip().lower()))
    valid = check_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not user.active or not valid: raise HTTPException(401, "Usuario o contraseña incorrectos")
    old_token = request.cookies.get("finanzas_session")
    if old_token:
        old = session.get(LoginSession, hashlib.sha256(old_token.encode()).hexdigest())
        if old: session.delete(old)
    token = secrets.token_urlsafe(32)
    session.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires=now+28800))
    session.commit()
    response.set_cookie("finanzas_session", token, max_age=28800, httponly=True, samesite="strict", secure=os.getenv("COOKIE_SECURE", "false").lower()=="true", path="/api")
    return public_user(user)
@app.get("/api/auth/me")
def me(user: CurrentUser): return public_user(user) if user else None
@app.post("/api/auth/logout")
def logout(request: Request, response: Response, session: DB):
    if request.headers.get("X-App") != "1": raise HTTPException(403, "Solicitud no válida")
    token = request.cookies.get("finanzas_session")
    if token:
        login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if login: session.delete(login); session.commit()
    response.delete_cookie("finanzas_session", path="/api")
    return {"ok": True}
@app.get("/api/users")
def list_users(session: DB, user: Administrator):
    return [dict(id=u.id, **public_user(u), active=u.active) for u in session.scalars(select(User)).all()]
class UserInput(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,100}$")
    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value, str) else value
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern=r"^(director|analyst|admin)$")
@app.post("/api/users", status_code=201)
def add_user(data: UserInput, session: DB, user: Administrator):
    if session.scalar(select(User).where(User.username==data.username)): raise HTTPException(409, "El usuario ya existe")
    record = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    session.add(record); session.commit()
    return public_user(record)

Money = Annotated[Decimal, Field(ge=0, le=Decimal("99999999999999.99"), max_digits=16, decimal_places=2)]
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

def rows(session, period=None, department=None):
    q = select(Budget).order_by(Budget.period, Budget.department)
    if period: q = q.where(Budget.period == period)
    if department: q = q.where(Budget.department == department)
    return session.scalars(q).all()
def serial(r):
    spent = r.payroll + r.operating
    return dict(id=r.id, department=r.department, period=r.period, amount=float(r.amount), payroll=float(r.payroll), operating=float(r.operating), spent=float(spent), utilization=float(spent/r.amount*100) if r.amount else None)
def normalized(data):
    name = data.department.strip()
    if not name: raise ValueError("Departamento vacío")
    # SQL Numeric caps components individually; their sum remains Decimal.
    return dict(department=name, period=data.period, amount=data.amount, payroll=data.payroll, operating=data.operating)

@app.get("/api/health")
def health(): return {"status": "ok", "mode": "development"}
@app.get("/api/budgets")
def budgets(session: DB, user: CurrentUser):
    return [serial(r) for r in (rows(session) if user and user.role in ("director", "analyst") else demo_rows())]
@app.post("/api/budgets", status_code=201)
def create_budget(data: BudgetInput, session: DB, user: Director):
    try: values = normalized(data)
    except ValueError as e: raise HTTPException(422, str(e))
    if rows(session, data.period, values["department"]): raise HTTPException(409, "Ya existe ese departamento y periodo")
    record = Budget(**values)
    session.add(record)
    session.commit()
    session.refresh(record)
    return serial(record)

@app.get("/api/dashboard")
def dashboard(session: DB, user: CurrentUser, period: str, department: str | None = None):
    real = bool(user and user.role in ("director", "analyst"))
    selected = rows(session, period, department) if real else demo_rows(period, department)
    total = sum((r.amount for r in selected), Decimal(0))
    spent = sum((r.payroll+r.operating for r in selected), Decimal(0))
    alerts = []
    for r in selected:
        used = r.payroll+r.operating
        if used > r.amount or (r.amount and used/r.amount >= Decimal("0.9")):
            severity = "critical" if used > r.amount*Decimal("1.1") else "warning" if used > r.amount else "info"
            alerts.append(dict(department=r.department, severity=severity, message="Sobrepresupuesto" if used>r.amount else "Consumo igual o mayor al 90%", deviation=float(used-r.amount)))
    history = rows(session, department=department) if real else selected
    monthly = {}
    # Exclude future periods and use matching departments to avoid scope drift.
    names = {r.department for r in selected}
    for r in history:
        if r.period <= period and r.department in names:
            monthly.setdefault(r.period, {})[r.department] = r.payroll+r.operating
    complete = [sum(v.values()) for p,v in sorted(monthly.items()) if set(v)==names][-3:]
    prediction = float(sum(complete)/len(complete)) if complete else None
    return dict(demo=not real, budgets=[serial(r) for r in selected], kpis=dict(budget=float(total), spent=float(spent), available=float(total-spent), utilization=float(spent/total*100) if total else None), alerts=alerts, prediction=dict(amount=prediction, method="Media de hasta 3 meses completos. Referencia estadística, no modelo IA validado.", months=len(complete), reliable=False))

@app.post("/api/simulations")
def simulate(data: Scenario, session: DB, user: Financial):
    selected = rows(session, data.period, data.department)
    if not selected: raise HTTPException(404, "No hay datos para ese periodo")
    payroll = sum((r.payroll for r in selected), Decimal(0))
    operating = sum((r.operating for r in selected), Decimal(0))
    # Inflation affects operations only; salary adjustment is separate to avoid double counting.
    projected = payroll*(1+Decimal(str(data.payroll))/100) + operating*(1+Decimal(str(data.operating))/100)*(1+Decimal(str(data.inflation))/100)
    baseline = payroll+operating
    return dict(baseline=float(baseline), projected=float(projected.quantize(Decimal("0.01"))), difference=float((projected-baseline).quantize(Decimal("0.01"))), formula="Nómina × (1 + ajuste salarial) + operación × (1 + ajuste operativo) × (1 + inflación)")

@app.post("/api/imports/csv")
async def import_csv(session: DB, user: Analyst, file: UploadFile = File(...)):
    content = await file.read(2*1024*1024+1)
    if len(content)>2*1024*1024: raise HTTPException(413, "Máximo 2 MB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        required = {"department", "period", "amount", "payroll", "operating"}
        if not reader.fieldnames or set(reader.fieldnames)!=required: raise ValueError("Columnas requeridas: department,period,amount,payroll,operating")
        records=[]; seen=set()
        existing={(r.department,r.period) for r in rows(session)}
        for line, row in enumerate(reader, start=2):
            if line>10001: raise ValueError("Máximo 10000 filas")
            try:
                values=normalized(BudgetInput(**row))
                key=(values["department"],values["period"])
                if key in seen or key in existing: raise ValueError("Departamento/periodo duplicado")
                seen.add(key); records.append(Budget(**values))
            except (ValueError, InvalidOperation) as e: raise ValueError(f"Fila {line}: {e}")
        if not records: raise ValueError("Archivo vacío")
    except (ValueError, UnicodeError, csv.Error) as e: raise HTTPException(422, str(e))
    session.add_all(records)
    session.commit()
    return {"imported":len(records)}

@app.get("/api/powerbi/status")
def powerbi():
    return {"configured":False, "message":"Pendiente: autenticación, Microsoft Entra, workspace, reporte y capacidad. La generación de tokens está deshabilitada hasta implementar autorización."}

from .financial import install_financial
install_financial(app, Base, engine, DB, CurrentUser, Analyst, Financial)
