"""Consulta y retirada explícita de cargas del espacio financiero compartido."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select

from .database import DB
from .forecast import period_label
from .models import Entry, ImportBatch
from .security import Analyst

router = APIRouter(tags=["Gestión de importaciones"])


class ImportSummary(BaseModel):
    id: int
    filename: str
    sha256: str
    currency: str
    username: str
    entry_count: int
    period_from: str | None
    period_to: str | None


class ImportsPage(BaseModel):
    items: list[ImportSummary]
    total: int
    limit: int
    offset: int


class DeleteImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str = Field(min_length=1, max_length=50)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DeletedImport(BaseModel):
    id: int
    filename: str
    deleted_entries: int


@router.get("/api/financial/imports", response_model=ImportsPage)
def list_imports(
    db: DB,
    user: Analyst,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    response.headers["Cache-Control"] = "no-store"
    month = Entry.year * 12 + Entry.month - 1
    rows = db.execute(
        select(ImportBatch, func.count(Entry.id), func.min(month), func.max(month))
        .outerjoin(Entry, Entry.batch_id == ImportBatch.id)
        .group_by(ImportBatch.id)
        .order_by(ImportBatch.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ImportsPage(
        items=[
            ImportSummary(
                id=batch.id,
                filename=batch.filename,
                sha256=batch.sha256,
                currency=batch.currency,
                username=batch.username,
                entry_count=count,
                period_from=period_label(first) if first is not None else None,
                period_to=period_label(last) if last is not None else None,
            )
            for batch, count, first, last in rows
        ],
        total=db.scalar(select(func.count()).select_from(ImportBatch)),
        limit=limit,
        offset=offset,
    )


@router.delete("/api/financial/imports/{batch_id}", response_model=DeletedImport)
def delete_import(
    batch_id: Annotated[int, Path(gt=0)],
    data: DeleteImportInput,
    db: DB,
    user: Analyst,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    if data.confirmation != f"ELIMINAR {batch_id}":
        raise HTTPException(
            422, "Escribe el código de confirmación exacto de esta carga."
        )
    # Imports are immutable. Serialize competing deletions on PostgreSQL.
    batch = db.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(404, "La importación ya no existe. Actualiza el listado.")
    if data.sha256 != batch.sha256:
        raise HTTPException(
            409, "La carga cambió. Actualiza el listado y vuelve a confirmarla."
        )
    filename = batch.filename
    try:
        removed = db.execute(delete(Entry).where(Entry.batch_id == batch_id))
        count = removed.rowcount
        db.delete(batch)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return DeletedImport(id=batch_id, filename=filename, deleted_entries=count)
