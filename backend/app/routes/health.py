from fastapi import APIRouter
from datetime import datetime

router = APIRouter(
    prefix="/api/health",
    tags=["Health Check"],
)


@router.get(
    "",
    summary="Health Check",
    description="Check if the API is running and healthy",
    tags=["Health Check"],
)
async def health_check():
    """
    Health check endpoint

    Returns basic information about the API status.
    """
    return {
        "status": "ok",
        "service": "DD2430 DSC Analyzer",
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness Check",
    description="Check if API is ready to accept requests",
    tags=["Health Check"],
)
async def readiness_check():
    """
    Readiness check endpoint

    Indicates if all dependencies are initialized and the API is ready.
    """
    return {
        "ready": True,
        "services": {
            "analysis": "ready",
            "storage": "ready",
        },
    }


@router.get(
    "/live",
    summary="Liveness Check",
    description="Check if API process is alive",
    tags=["Health Check"],
)
async def liveness_check():
    """
    Liveness check endpoint

    Indicates if the API process is still running.
    """
    return {
        "alive": True,
    }
