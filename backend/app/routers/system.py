"""Estado de la aplicación y de la integración pendiente de Power BI."""

from fastapi import APIRouter

router = APIRouter(tags=["Estado"])


@router.get("/api/health")
def health():
    return {"status": "ok", "mode": "development"}


@router.get("/api/powerbi/status")
def powerbi():
    return {
        "configured": False,
        "message": "Pendiente: autenticación, Microsoft Entra, workspace, reporte y capacidad. La generación de tokens está deshabilitada hasta implementar autorización.",
    }
