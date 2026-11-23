from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(
    prefix="/api/health",
    tags=["Health Check"],
)


@router.get(
    "",
    summary="Health Check",
    description="Check if the API is running and healthy",
)
async def health_check() -> dict[str, str]:
    """Return basic information about the API status."""
    return {
        "status": "ok",
        "service": "DD2430 DSC Analyzer",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness Check",
    description="Check if API and Cloud SQL dependencies are ready to accept requests",
)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """Verify database connectivity before marking the service ready."""
    db_status = "ready"
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_status = "unavailable"

    is_ready = db_status == "ready"
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ready": False,
                "services": {
                    "analysis": "ready",
                    "database": db_status,
                },
            },
        )

    return {
        "ready": True,
        "services": {
            "analysis": "ready",
            "database": db_status,
        },
    }


@router.get(
    "/live",
    summary="Liveness Check",
    description="Check if API process is alive",
)
async def liveness_check() -> dict[str, bool]:
    """Indicate if the API process is still running."""
    return {
        "alive": True,
    }


@router.get(
    "/db",
    summary="Database Schema & Connection Check",
    description="Verify Cloud SQL Proxy connection, DB user, and DSC table presence",
)
async def database_health_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Return detailed PostgreSQL and DSC schema diagnostics."""
    try:
        result = await db.execute(text("""
                SELECT
                    current_database() AS db_name,
                    current_user AS db_user,
                    version() AS pg_version,
                    (
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name IN ('dsc_files', 'dsc_metadata', 'analysis_runs', 'thermal_events')
                    ) AS dsc_table_count
                """))
        row = result.mappings().one()

        return {
            "status": "ok",
            "database": row["db_name"],
            "user": row["db_user"],
            "postgres_version": row["pg_version"].split(",")[0],
            "dsc_tables_ready": row["dsc_table_count"] == 4,
            "dsc_table_count": row["dsc_table_count"],
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {exc.__class__.__name__}: {exc}",
        ) from exc
