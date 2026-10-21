"""Punto de entrada: composición de la aplicación, middleware y routers."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import auth, users, system
from . import financial, invitations, forecast


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Plataforma de Presupuesto · Presupuesto corporativo",
    version="0.15.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-App"],
    allow_credentials=True,
)


@app.middleware("http")
async def private_auth_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/auth/", "/api/users")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


for router in (
    auth.router,
    users.router,
    financial.router,
    forecast.router,
    invitations.router,
    system.router,
):
    app.include_router(router)
