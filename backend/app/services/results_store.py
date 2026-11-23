from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AnalysisRun, DSCFile, DSCMetadata, ThermalEvent
from app.services.gcs_storage import delete_blobs, upload_plot_png, upload_report_md

log = logging.getLogger(__name__)

AGENT_VERSION = "dsc-agent-1"
EVENT_TYPES = (
    "melting",
    "glass_transition",
    "crystallization",
    "decomposition",
    "moisture_loss",
)
DIRECTIONS = ("endothermic", "exothermic", "step_change")


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return (
        Decimal(str(round(number, 5)))
        if number == number and abs(number) != float("inf")
        else None
    )


@dataclass
class PendingResult:
    """One analysis outcome waiting to be saved. `fields` uses ThermalEvent column names."""

    tool_name: str
    event_type: str
    thermal_direction: str
    fields: dict[str, Any]
    params: dict[
        str, Any
    ]  # inputs that produced it: window, baseline, mass, heating rate...
    summary: str
    png: bytes | None = None
    confidence: float | None = None
    notes: str | None = None
    created: datetime = field(default_factory=datetime.utcnow)


# ------------------------------------------------------------------- save


async def save_pending(
    db: AsyncSession,
    file_id: uuid.UUID,
    pendings: list[PendingResult],
    event_type_overrides: dict[str, str] | None = None,
    input_snapshot: dict[str, Any] | None = None,
) -> AnalysisRun:
    """Store pendings as one AnalysisRun with its ThermalEvents, plots and a Markdown report."""
    if not pendings:
        raise ValueError("Nothing to save.")
    overrides = event_type_overrides or {}

    run = AnalysisRun(
        file_id=file_id,
        agent_version=AGENT_VERSION,
        status="completed",
        tool_name=", ".join(sorted({p.tool_name for p in pendings})),
        preprocessing_params={p.tool_name: p.params for p in pendings},
        input_snapshot=input_snapshot or {},  # field_sources + unconfirmed at save time
    )
    db.add(run)
    await db.flush()

    plot_uris: list[str] = []
    for pending in pendings:
        event_type = overrides.get(pending.tool_name, pending.event_type)
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of {EVENT_TYPES}, got '{event_type}'."
            )
        f = pending.fields
        db.add(
            ThermalEvent(
                run_id=run.run_id,
                event_type=event_type,
                thermal_direction=pending.thermal_direction,
                onset_temp_value=_dec(f.get("onset_temp_value")),
                peak_temp_value=_dec(f.get("peak_temp_value")),
                endset_temp_value=_dec(f.get("endset_temp_value")),
                midpoint_temp_value=_dec(f.get("midpoint_temp_value")),
                inflection_temp_value=_dec(f.get("inflection_temp_value")),
                enthalpy_value=_dec(f.get("enthalpy_value")),
                enthalpy_error_value=_dec(f.get("enthalpy_error_value")),
                is_drug_normalized=bool(f.get("is_drug_normalized", False)),
                delta_cp_value=_dec(f.get("delta_cp_value")),
                delta_cp_unit=f.get("delta_cp_unit"),
                confidence_score=_dec(pending.confidence),
                notes=pending.notes,
            )
        )
        if pending.png:
            plot_uris.append(await upload_plot_png(run.run_id, pending.png))

    run.plot_uris = plot_uris
    run.summary_report = "\n\n".join(p.summary for p in pendings)
    run.report_uri = await upload_report_md(
        run.run_id, f"# Analysis run {run.run_id}\n\n{run.summary_report}\n"
    )
    await db.commit()
    await db.refresh(run)
    return run


# ------------------------------------------------------------------ lookup


def event_dict(event: ThermalEvent) -> dict[str, Any]:
    def num(value):
        return None if value is None else float(value)

    return {
        "event_type": event.event_type,
        "thermal_direction": event.thermal_direction,
        "onset_temp_value": num(event.onset_temp_value),
        "peak_temp_value": num(event.peak_temp_value),
        "endset_temp_value": num(event.endset_temp_value),
        "midpoint_temp_value": num(getattr(event, "midpoint_temp_value", None)),
        "inflection_temp_value": num(getattr(event, "inflection_temp_value", None)),
        "temp_unit": event.temp_unit,
        "enthalpy_value": num(event.enthalpy_value),
        "enthalpy_error_value": num(getattr(event, "enthalpy_error_value", None)),
        "enthalpy_unit": event.enthalpy_unit,
        "is_drug_normalized": event.is_drug_normalized,
        "delta_cp_value": num(event.delta_cp_value),
        "delta_cp_unit": event.delta_cp_unit,
        "confidence_score": num(event.confidence_score),
    }


async def count_runs(db: AsyncSession, file_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count(AnalysisRun.run_id)).where(AnalysisRun.file_id == file_id)
        )
    ).scalar_one()


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> DSCFile | None:
    stmt = (
        select(DSCFile)
        .where(DSCFile.file_id == file_id)
        .options(
            selectinload(DSCFile.metadata_record), selectinload(DSCFile.analysis_runs)
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def search_files(
    db: AsyncSession,
    name_contains: str | None = None,
    category: str | None = None,
    uploaded_after: datetime | None = None,
    uploaded_before: datetime | None = None,
    has_results: bool | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    stmt = (
        select(DSCFile, DSCMetadata, func.count(AnalysisRun.run_id).label("n_runs"))
        .join(DSCMetadata, DSCMetadata.file_id == DSCFile.file_id, isouter=True)
        .join(AnalysisRun, AnalysisRun.file_id == DSCFile.file_id, isouter=True)
        .group_by(DSCFile.file_id, DSCMetadata.metadata_id)
        .order_by(DSCFile.created_at.desc())
        .limit(min(max(limit, 1), 50))
    )
    if name_contains:
        like = f"%{name_contains.strip()}%"  # bound parameter, not string-built SQL
        stmt = stmt.where(
            or_(
                DSCFile.original_filename.ilike(like),
                DSCMetadata.sample_name.ilike(like),
            )
        )
    if category:
        stmt = stmt.where(DSCMetadata.sample_category == category)
    if uploaded_after:
        stmt = stmt.where(DSCFile.created_at >= uploaded_after)
    if uploaded_before:
        stmt = stmt.where(DSCFile.created_at <= uploaded_before)
    if has_results is True:
        stmt = stmt.having(func.count(AnalysisRun.run_id) > 0)
    elif has_results is False:
        stmt = stmt.having(func.count(AnalysisRun.run_id) == 0)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "file_id": str(f.file_id),
            "filename": f.original_filename,
            "uploaded": f.created_at.strftime("%Y-%m-%d %H:%M"),
            "sample_name": m.sample_name if m else None,
            "category": m.sample_category if m else None,
            "sample_mass": (
                f"{m.sample_mass_value} {m.sample_mass_unit}"
                if m and m.sample_mass_value
                else None
            ),
            "heating_rate": (
                f"{m.heating_rate_value} {m.heating_rate_unit}"
                if m and m.heating_rate_value
                else None
            ),
            "analysis_runs": n_runs,
        }
        for f, m, n_runs in rows
    ]


async def search_events(
    db: AsyncSession,
    sample_name: str | None = None,
    event_type: str | None = None,
    temp_min: float | None = None,
    temp_max: float | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Stored thermal events, newest run first. The temperature filter matches the event's
    characteristic temperature (midpoint for Tg, otherwise peak, otherwise onset)."""
    characteristic = func.coalesce(
        ThermalEvent.midpoint_temp_value,
        ThermalEvent.peak_temp_value,
        ThermalEvent.onset_temp_value,
    )
    stmt = (
        select(ThermalEvent, AnalysisRun, DSCFile, DSCMetadata)
        .join(AnalysisRun, AnalysisRun.run_id == ThermalEvent.run_id)
        .join(DSCFile, DSCFile.file_id == AnalysisRun.file_id)
        .join(DSCMetadata, DSCMetadata.file_id == DSCFile.file_id, isouter=True)
        .order_by(AnalysisRun.created_at.desc())
        .limit(min(max(limit, 1), 100))
    )
    if sample_name:
        like = f"%{sample_name.strip()}%"
        stmt = stmt.where(
            or_(
                DSCFile.original_filename.ilike(like),
                DSCMetadata.sample_name.ilike(like),
            )
        )
    if event_type:
        stmt = stmt.where(ThermalEvent.event_type == event_type)
    if temp_min is not None:
        stmt = stmt.where(characteristic >= temp_min)
    if temp_max is not None:
        stmt = stmt.where(characteristic <= temp_max)

    out = []
    for event, run, db_file, meta in (await db.execute(stmt)).all():
        row = event_dict(event)
        row.update(
            run_id=str(run.run_id),
            run_date=run.created_at.strftime("%Y-%m-%d %H:%M"),
            file_id=str(db_file.file_id),
            filename=db_file.original_filename,
            sample_name=meta.sample_name if meta else None,
        )
        out.append(row)
    return out


async def get_run(
    db: AsyncSession, run_id: uuid.UUID
) -> tuple[AnalysisRun, list[dict]] | None:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.run_id == run_id)
        .options(selectinload(AnalysisRun.thermal_events))
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    return None if run is None else (run, [event_dict(e) for e in run.thermal_events])


async def latest_run_events(
    db: AsyncSession, file_id: uuid.UUID
) -> tuple[AnalysisRun | None, list[dict]]:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.file_id == file_id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
        .options(selectinload(AnalysisRun.thermal_events))
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    return (
        (None, [])
        if run is None
        else (run, [event_dict(e) for e in run.thermal_events])
    )


# ------------------------------------------------------------------ delete


async def describe_deletion(
    db: AsyncSession, file_id: uuid.UUID
) -> dict[str, Any] | None:
    """What deleting a file would remove, so the user can confirm with full information."""
    db_file = await get_file(db, file_id)
    if db_file is None:
        return None
    run_ids = [r.run_id for r in db_file.analysis_runs]
    n_events = 0
    if run_ids:
        n_events = (
            await db.execute(
                select(func.count(ThermalEvent.event_id)).where(
                    ThermalEvent.run_id.in_(run_ids)
                )
            )
        ).scalar_one()
    referencing = (
        (
            await db.execute(
                select(DSCFile.original_filename)
                .join(DSCMetadata, DSCMetadata.file_id == DSCFile.file_id)
                .where(DSCMetadata.reference_file_id == file_id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "file_id": str(file_id),
        "filename": db_file.original_filename,
        "analysis_runs": len(run_ids),
        "thermal_events": n_events,
        "plots": sum(len(r.plot_uris or []) for r in db_file.analysis_runs),
        "used_as_reference_by": list(referencing),
    }


async def delete_file(db: AsyncSession, file_id: uuid.UUID) -> dict[str, Any]:
    """Delete the DB rows first (cascade), then the GCS objects. Returns a report."""
    db_file = await get_file(db, file_id)
    if db_file is None:
        raise LookupError("File not found.")
    uris = [u for u in (db_file.storage_uri, getattr(db_file, "table_uri", None)) if u]
    for run in db_file.analysis_runs:
        uris += list(run.plot_uris or [])
        if getattr(run, "report_uri", None):
            uris.append(run.report_uri)
    name = db_file.original_filename

    await db.delete(db_file)
    await db.commit()

    failed = await delete_blobs(uris)
    if failed:
        log.error("GCS objects left behind after deleting %s: %s", file_id, failed)
    return {
        "filename": name,
        "objects_deleted": len(uris) - len(failed),
        "objects_left_behind": failed,
    }
