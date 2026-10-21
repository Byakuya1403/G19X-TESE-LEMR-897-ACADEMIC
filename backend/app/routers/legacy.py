"""API del formato anterior: se mantiene aislada para clientes existentes."""

import csv
import io
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select
from ..database import DB
from ..models import Budget
from ..schemas import BudgetInput, Scenario
from ..security import CurrentUser, Director, Financial, Analyst

router = APIRouter(tags=["Compatibilidad (obsoleto)"], deprecated=True)


def demo_rows(period=None, department=None):
    data = [
        ("Tecnología", 250000, 140000, 120000),
        ("Operaciones", 400000, 210000, 250000),
        ("Comercial", 180000, 98000, 60000),
    ]
    return [
        Budget(
            id=i + 1,
            department=n,
            period=period or "2026-09",
            amount=Decimal(a),
            payroll=Decimal(p),
            operating=Decimal(o),
        )
        for i, (n, a, p, o) in enumerate(data)
        if not department or n == department
    ]


def rows(session, period=None, department=None):
    q = select(Budget).order_by(Budget.period, Budget.department)
    if period:
        q = q.where(Budget.period == period)
    if department:
        q = q.where(Budget.department == department)
    return session.scalars(q).all()


def serial(r):
    spent = r.payroll + r.operating
    return dict(
        id=r.id,
        department=r.department,
        period=r.period,
        amount=float(r.amount),
        payroll=float(r.payroll),
        operating=float(r.operating),
        spent=float(spent),
        utilization=float(spent / r.amount * 100) if r.amount else None,
    )


def normalized(data):
    name = data.department.strip()
    if not name:
        raise ValueError("Departamento vacío")
    # SQL Numeric caps components individually; their sum remains Decimal.
    return dict(
        department=name,
        period=data.period,
        amount=data.amount,
        payroll=data.payroll,
        operating=data.operating,
    )


@router.get("/api/budgets")
def budgets(session: DB, user: CurrentUser):
    return [
        serial(r)
        for r in (
            rows(session)
            if user and user.role in ("director", "analyst")
            else demo_rows()
        )
    ]


@router.post("/api/budgets", status_code=201)
def create_budget(data: BudgetInput, session: DB, user: Director):
    try:
        values = normalized(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if rows(session, data.period, values["department"]):
        raise HTTPException(409, "Ya existe ese departamento y periodo")
    record = Budget(**values)
    session.add(record)
    session.commit()
    session.refresh(record)
    return serial(record)


@router.get("/api/dashboard")
def dashboard(
    session: DB, user: CurrentUser, period: str, department: str | None = None
):
    real = bool(user and user.role in ("director", "analyst"))
    selected = (
        rows(session, period, department) if real else demo_rows(period, department)
    )
    total = sum((r.amount for r in selected), Decimal(0))
    spent = sum((r.payroll + r.operating for r in selected), Decimal(0))
    alerts = []
    for r in selected:
        used = r.payroll + r.operating
        if used > r.amount or (r.amount and used / r.amount >= Decimal("0.9")):
            severity = (
                "critical"
                if used > r.amount * Decimal("1.1")
                else "warning" if used > r.amount else "info"
            )
            alerts.append(
                dict(
                    department=r.department,
                    severity=severity,
                    message=(
                        "Sobrepresupuesto"
                        if used > r.amount
                        else "Consumo igual o mayor al 90%"
                    ),
                    deviation=float(used - r.amount),
                )
            )
    history = rows(session, department=department) if real else selected
    monthly = {}
    # Exclude future periods and use matching departments to avoid scope drift.
    names = {r.department for r in selected}
    for r in history:
        if r.period <= period and r.department in names:
            monthly.setdefault(r.period, {})[r.department] = r.payroll + r.operating
    complete = [sum(v.values()) for p, v in sorted(monthly.items()) if set(v) == names][
        -3:
    ]
    prediction = float(sum(complete) / len(complete)) if complete else None
    return dict(
        demo=not real,
        budgets=[serial(r) for r in selected],
        kpis=dict(
            budget=float(total),
            spent=float(spent),
            available=float(total - spent),
            utilization=float(spent / total * 100) if total else None,
        ),
        alerts=alerts,
        prediction=dict(
            amount=prediction,
            method="Media de hasta 3 meses completos. Referencia estadística, no modelo IA validado.",
            months=len(complete),
            reliable=False,
        ),
    )


@router.post("/api/simulations")
def simulate(data: Scenario, session: DB, user: Financial):
    selected = rows(session, data.period, data.department)
    if not selected:
        raise HTTPException(404, "No hay datos para ese periodo")
    payroll = sum((r.payroll for r in selected), Decimal(0))
    operating = sum((r.operating for r in selected), Decimal(0))
    # Inflation affects operations only; salary adjustment is separate to avoid double counting.
    projected = payroll * (1 + Decimal(str(data.payroll)) / 100) + operating * (
        1 + Decimal(str(data.operating)) / 100
    ) * (1 + Decimal(str(data.inflation)) / 100)
    baseline = payroll + operating
    return dict(
        baseline=float(baseline),
        projected=float(projected.quantize(Decimal("0.01"))),
        difference=float((projected - baseline).quantize(Decimal("0.01"))),
        formula="Nómina × (1 + ajuste salarial) + operación × (1 + ajuste operativo) × (1 + inflación)",
    )


@router.post("/api/imports/csv")
async def import_csv(session: DB, user: Analyst, file: UploadFile = File(...)):
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Máximo 2 MB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        required = {"department", "period", "amount", "payroll", "operating"}
        if not reader.fieldnames or set(reader.fieldnames) != required:
            raise ValueError(
                "Columnas requeridas: department,period,amount,payroll,operating"
            )
        records = []
        seen = set()
        existing = {(r.department, r.period) for r in rows(session)}
        for line, row in enumerate(reader, start=2):
            if line > 10001:
                raise ValueError("Máximo 10000 filas")
            try:
                values = normalized(BudgetInput(**row))
                key = (values["department"], values["period"])
                if key in seen or key in existing:
                    raise ValueError("Departamento/periodo duplicado")
                seen.add(key)
                records.append(Budget(**values))
            except (ValueError, InvalidOperation) as e:
                raise ValueError(f"Fila {line}: {e}")
        if not records:
            raise ValueError("Archivo vacío")
    except (ValueError, UnicodeError, csv.Error) as e:
        raise HTTPException(422, str(e))
    session.add_all(records)
    session.commit()
    return {"imported": len(records)}
