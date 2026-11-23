from __future__ import annotations

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from langchain.tools import tool, ToolRuntime

from app.db.session import get_db
from app.services import results_store as store
from app.services.compare import Side, compare_text, overlay_png
from app.services.gcs_storage import download_bytes_from_gcs
from app.services.ingest import load_table
from app.services.run_params import resolve_run_params
from app.services.session_runs import unique_local_name, write_session_files

MAX_IMAGES = 3


# ------------------------------------------------------------------ helpers


async def _with_db(fn):
    """Run fn(db) on one DB session and let get_db() clean up normally."""
    result = None
    async for db in get_db():
        result = await fn(db)
    return result


def _image_block(png: bytes) -> dict:
    return {
        "type": "image",
        "base64": base64.b64encode(png).decode("ascii"),
        "mime_type": "image/png",
    }


def _parse_uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(text).strip())
    except ValueError:
        return None


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        return None


def stash_result(runtime: ToolRuntime, pending: store.PendingResult) -> None:
    """Called by the analysis tools: remember exactly what was computed for the current file."""
    ctx = runtime.context
    if ctx and ctx.current_dsc_file:
        ctx.pending[(ctx.current_dsc_file, pending.tool_name)] = pending


def _pending_for(ctx, file_name: str) -> list[store.PendingResult]:
    return [p for (name, _tool), p in ctx.pending.items() if name == file_name]


def _fmt_rows(rows: list[dict], keys: list[str]) -> str:
    if not rows:
        return "No matches."
    return "\n".join(
        " | ".join(f"{k}={'n/a' if row.get(k) is None else row[k]}" for k in keys)
        for row in rows
    )


def _sidecar_params(ctx, file_name: str) -> dict:
    path = Path(ctx.dsc_file_path(file_name))
    meta_path = path.with_name(path.stem + "_metadata.csv")
    try:
        row = pd.read_csv(meta_path).iloc[0]
    except (OSError, ValueError, IndexError):
        return {}

    def get(key):
        value = row.get(key)
        return None if value is None or pd.isna(value) else value

    return {
        "sample_mass": get("sample_mass"),
        "heating_rate": get("heating_rate"),
        "endo_up": None if get("endo_up") is None else bool(get("endo_up")),
        "heat_flow_normalized": (
            None
            if get("heat_flow_normalized") is None
            else bool(get("heat_flow_normalized"))
        ),
    }


def _pending_as_events(pendings: list[store.PendingResult]) -> list[dict]:
    events = []
    for p in pendings:
        f = p.fields
        events.append(
            {
                "event_type": p.event_type,
                "thermal_direction": p.thermal_direction,
                "temp_unit": "C",
                "enthalpy_unit": "J/g",
                "is_drug_normalized": f.get("is_drug_normalized", False),
                **{
                    k: f.get(k)
                    for k in (
                        "onset_temp_value",
                        "peak_temp_value",
                        "endset_temp_value",
                        "midpoint_temp_value",
                        "inflection_temp_value",
                        "enthalpy_value",
                        "enthalpy_error_value",
                        "delta_cp_value",
                    )
                },
            }
        )
    return events


async def _resolve_side(ctx, ref: str) -> Side | str:
    """A side is a file loaded in this session (by name) or a stored file (by file_id)."""
    ref = ref.strip()
    if ref in ctx.dsc_files_available:  # loaded or just uploaded in this session
        pendings = _pending_for(ctx, ref)
        params = _sidecar_params(ctx, ref)
        table = pd.read_csv(ctx.dsc_file_path(ref))
        file_id = ctx.file_ids.get(ref)
        if pendings:
            return Side(
                ref,
                "this session, results not saved",
                _pending_as_events(pendings),
                params,
                table,
            )
        if file_id is not None:

            async def _latest(db):
                return await store.latest_run_events(db, file_id)

            run, events = await _with_db(_latest)
            if run is not None:
                return Side(
                    ref,
                    f"stored run {run.created_at:%Y-%m-%d %H:%M}",
                    events,
                    params,
                    table,
                )
        return Side(ref, "no analysis yet", [], params, table)

    file_id = _parse_uuid(ref)
    if file_id is None:
        return f"'{ref}' is neither a file loaded in this session nor a file_id."

    async def _stored(db):
        db_file = await store.get_file(db, file_id)
        if db_file is None:
            return None
        run, events = await store.latest_run_events(db, file_id)
        table = await load_table(db_file) if db_file.table_uri else None
        params = (
            resolve_run_params(db_file.metadata_record).as_dict()
            if db_file.metadata_record
            else {}
        )
        return db_file.original_filename, run, events, params, table

    found = await _with_db(_stored)
    if found is None:
        return f"No stored file with id {file_id}."
    name, run, events, params, table = found
    source = f"stored run {run.created_at:%Y-%m-%d %H:%M}" if run else "no analysis yet"
    return Side(name, source, events, params, table)


# ------------------------------------------------------------------- tools


@tool(
    "save_analysis_results",
    description=(
        "Save the analysis results just computed for the currently selected file to the "
        "database (thermal events, parameters used, plots, report). The values saved are the "
        "ones the analysis tools computed; you do not pass numbers. Call it when the user "
        "accepts the results or asks to save them, never before. Optional event_types maps a "
        "tool name to the event type when the default is wrong, e.g. "
        "{'enthalpy_analysis': 'decomposition'}; allowed: melting, glass_transition, "
        "crystallization, decomposition, moisture_loss."
    ),
)
async def save_analysis_results(
    runtime: ToolRuntime, event_types: dict[str, str] | None = None
) -> str:
    ctx = runtime.context
    name = ctx.current_dsc_file
    file_id = ctx.file_ids.get(name) if name else None
    if file_id is None:
        return "No stored DSC file is currently selected."
    pendings = _pending_for(ctx, name)
    if not pendings:
        return "There are no new analysis results for this file. Run an analysis first."

    async def _save(db):
        db_file = await store.get_file(db, file_id)
        meta = db_file.metadata_record if db_file else None
        snapshot = {
            "field_sources": dict(meta.field_sources or {}) if meta else {},
            "unconfirmed": list(meta.unconfirmed_fields or []) if meta else [],
        }
        return (
            await store.save_pending(db, file_id, pendings, event_types, snapshot),
            snapshot,
        )

    try:
        run, snapshot = await _with_db(_save)
    except ValueError as error:
        return f"Not saved: {error}"
    for p in pendings:
        ctx.pending.pop((name, p.tool_name), None)
    note = ""
    if snapshot["unconfirmed"]:
        note = f" Note: these inputs were still unconfirmed when saving: {', '.join(snapshot['unconfirmed'])}."
    return f"Saved run {run.run_id} for '{name}' with {len(pendings)} event(s) and {len(run.plot_uris or [])} plot(s).{note}"


@tool(
    "search_files",
    description=(
        "Search files uploaded earlier (by anyone using this system). All filters are optional: "
        "name_contains matches the file name or sample name; category is pure_drug, excipient, "
        "mixture or reference; uploaded_after / uploaded_before are YYYY-MM-DD; has_results "
        "filters to files with (true) or without (false) saved analyses. Returns file_id, "
        "metadata and how many analysis runs are stored."
    ),
)
async def search_files(
    runtime: ToolRuntime,
    name_contains: str | None = None,
    category: str | None = None,
    uploaded_after: str | None = None,
    uploaded_before: str | None = None,
    has_results: bool | None = None,
    limit: int = 20,
) -> str:
    async def _q(db):
        return await store.search_files(
            db,
            name_contains,
            category,
            _parse_date(uploaded_after),
            _parse_date(uploaded_before),
            has_results,
            limit,
        )

    rows = await _with_db(_q)
    return _fmt_rows(
        rows,
        [
            "file_id",
            "filename",
            "sample_name",
            "category",
            "uploaded",
            "sample_mass",
            "heating_rate",
            "analysis_runs",
        ],
    )


@tool(
    "search_results",
    description=(
        "Search stored analysis results (thermal events) across all files. Filters are optional: "
        "sample_name (file or sample name), event_type (melting, glass_transition, crystallization, "
        "decomposition, moisture_loss), temp_min and temp_max in °C on the event's characteristic "
        "temperature (Tg midpoint, else peak, else onset). Each result has its units, run date and "
        "file_id. Report enthalpies together with their units and say when a value is normalized."
    ),
)
async def search_results(
    runtime: ToolRuntime,
    sample_name: str | None = None,
    event_type: str | None = None,
    temp_min: float | None = None,
    temp_max: float | None = None,
    limit: int = 30,
) -> str:
    async def _q(db):
        return await store.search_events(
            db, sample_name, event_type, temp_min, temp_max, limit
        )

    rows = await _with_db(_q)
    return _fmt_rows(
        rows,
        [
            "filename",
            "run_date",
            "event_type",
            "onset_temp_value",
            "peak_temp_value",
            "midpoint_temp_value",
            "endset_temp_value",
            "enthalpy_value",
            "enthalpy_error_value",
            "enthalpy_unit",
            "is_drug_normalized",
            "run_id",
            "file_id",
        ],
    )


@tool(
    "load_file",
    description=(
        "Load a previously uploaded file (by file_id from search_files) into this session and "
        "select it, so the plotting and analysis tools can use it. Its stored metadata comes with it."
    ),
)
async def load_file(runtime: ToolRuntime, file_id: str) -> str:
    ctx = runtime.context
    fid = _parse_uuid(file_id)
    if fid is None:
        return "file_id must be a UUID from search_files."
    for name, known in ctx.file_ids.items():
        if known == fid:
            ctx.current_dsc_file = name
            return f"'{name}' is already loaded; selected it."

    async def _load(db):
        db_file = await store.get_file(db, fid)
        if db_file is None or db_file.metadata_record is None:
            return None
        return db_file, await load_table(db_file)

    try:
        found = await _with_db(_load)
    except LookupError as error:
        return str(error)
    if found is None:
        return f"No stored file with id {fid}."
    db_file, table = found
    meta = db_file.metadata_record
    local = unique_local_name(ctx.dsc_files_available, db_file.original_filename)
    write_session_files(
        Path(ctx.upload_dir),
        local,
        table,
        meta,
        list(meta.unconfirmed_fields or []),
        list(meta.parse_warnings or []),
    )
    ctx.file_ids[local] = fid
    ctx.dsc_files_available.append(local)
    ctx.current_dsc_file = local
    return f"Loaded '{db_file.original_filename}' as '{local}' ({len(table)} points) and selected it."


@tool(
    "get_run",
    description=(
        "Get a stored analysis run: its report text, events and saved plots. Pass run_id (from "
        "search_results) or file_id for that file's latest run."
    ),
)
async def get_run(
    runtime: ToolRuntime, run_id: str | None = None, file_id: str | None = None
) -> str | list[dict]:
    rid, fid = _parse_uuid(run_id or ""), _parse_uuid(file_id or "")
    if rid is None and fid is None:
        return "Give a run_id or a file_id."

    async def _get(db):
        if rid is not None:
            return await store.get_run(db, rid)
        run, events = await store.latest_run_events(db, fid)
        return None if run is None else (run, events)

    found = await _with_db(_get)
    if found is None:
        return "No stored run found."
    run, events = found
    text = f"Run {run.run_id} from {run.created_at:%Y-%m-%d %H:%M} ({run.tool_name}).\n{run.summary_report or ''}\nEvents:\n"
    text += _fmt_rows(
        events,
        [
            "event_type",
            "onset_temp_value",
            "peak_temp_value",
            "midpoint_temp_value",
            "endset_temp_value",
            "enthalpy_value",
            "enthalpy_unit",
        ],
    )
    blocks: list[dict] = [{"type": "text", "text": text}]
    for uri in (run.plot_uris or [])[:MAX_IMAGES]:
        try:
            blocks.append(_image_block(await download_bytes_from_gcs(uri)))
        except Exception:  # a missing plot must not hide the numbers
            blocks.append({"type": "text", "text": f"(plot {uri} could not be loaded)"})
    return blocks


@tool(
    "compare_results",
    description=(
        "Compare analysis results of two files: onset, peak, Tg and enthalpy differences (B minus A) "
        "plus an overlay plot. Each of file_a and file_b is either the name of a file loaded in this "
        "session (including one uploaded just now, whose unsaved results are used) or a stored file_id. "
        "Both need analysis results. Pass what the caution lines say to the user; do not hide them."
    ),
)
async def compare_results(
    runtime: ToolRuntime, file_a: str, file_b: str
) -> str | list[dict]:
    ctx = runtime.context
    a, b = await _resolve_side(ctx, file_a), await _resolve_side(ctx, file_b)
    for side in (a, b):
        if isinstance(side, str):
            return side
    text = compare_text(a, b)
    png = overlay_png(a, b)
    return [{"type": "text", "text": text}] + ([_image_block(png)] if png else [])


@tool(
    "request_delete_file",
    description=(
        "Step 1 of deleting a stored file: shows what would be removed (file, analysis runs, "
        "events, plots, files that use it as reference). It deletes nothing. Then ask the user "
        "to confirm in plain words, listing what will be lost. Use only when the user asks to delete."
    ),
)
async def request_delete_file(runtime: ToolRuntime, file_id: str) -> str:
    ctx = runtime.context
    fid = _parse_uuid(file_id)
    if fid is None:
        return "file_id must be a UUID from search_files."

    async def _d(db):
        return await store.describe_deletion(db, fid)

    info = await _with_db(_d)
    if info is None:
        return f"No stored file with id {fid}."
    ctx.delete_request = {"file_id": fid, "turn": ctx.turn}
    text = (
        f"Deleting '{info['filename']}' would permanently remove the raw file, its processed data, "
        f"{info['analysis_runs']} analysis run(s), {info['thermal_events']} event(s) and {info['plots']} plot(s). "
        "This cannot be undone."
    )
    if info["used_as_reference_by"]:
        text += f" It is the reference for: {', '.join(info['used_as_reference_by'])} (they lose that link)."
    return text + " Nothing has been deleted yet. Ask the user to confirm."


@tool(
    "confirm_delete_file",
    description=(
        "Step 2 of deleting a stored file. Only call it after request_delete_file, in a LATER "
        "turn, after the user explicitly said yes to deleting that file. The system rejects it "
        "otherwise."
    ),
)
async def confirm_delete_file(runtime: ToolRuntime, file_id: str) -> str:
    ctx = runtime.context
    fid = _parse_uuid(file_id)
    request = ctx.delete_request
    if fid is None or not request or request["file_id"] != fid:
        return "Not deleted: call request_delete_file for this file first."
    if ctx.turn <= request["turn"]:
        return "Not deleted: the user has not answered yet. Ask them to confirm, then wait for their reply."
    ctx.delete_request = None

    async def _del(db):
        return await store.delete_file(db, fid)

    try:
        report = await _with_db(_del)
    except LookupError:
        return "That file no longer exists."
    for name, known in list(ctx.file_ids.items()):  # drop it from this session too
        if known == fid:
            ctx.file_ids.pop(name)
            if name in ctx.dsc_files_available:
                ctx.dsc_files_available.remove(name)
            if ctx.current_dsc_file == name:
                ctx.current_dsc_file = None
            for key in [k for k in ctx.pending if k[0] == name]:
                ctx.pending.pop(key)
    text = f"Deleted '{report['filename']}' and {report['objects_deleted']} stored object(s)."
    if report["objects_left_behind"]:
        text += f" {len(report['objects_left_behind'])} object(s) could not be removed from storage and were logged."
    return text


RESULT_TOOLS = [
    save_analysis_results,
    search_files,
    search_results,
    load_file,
    get_run,
    compare_results,
    request_delete_file,
    confirm_delete_file,
]
