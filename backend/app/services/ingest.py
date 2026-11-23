from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DSCFile, DSCMetadata
from app.db.schemas.dsc import DSCMetadataPayload, DSCMetadataRead
from app.services.dsc_parser import ParsedDSC, decode_text, parse_dsc_file, to_float
from app.services.gcs_storage import (
    compute_sha256,
    download_table_from_gcs,
    upload_bytes_to_gcs,
    upload_table_to_gcs,
)
from app.services.llm_metadata import extract_missing_with_llm
from app.services.metadata_extractor import parse_dsc_header
from app.services.run_params import compare_heating_rate, resolve_run_params

ALLOWED_EXTENSIONS = {".csv", ".txt", ".tsv", ".dat", ".xls", ".xlsx"}
SIDECAR_SUFFIX = "_metadata.csv"

# A value and its unit are one fact: they always come from the same source.
FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "sample_mass": ("sample_mass_value", "sample_mass_unit"),
    "heating_rate": ("heating_rate_value", "heating_rate_unit"),
    "purge_flow": ("purge_flow_value", "purge_flow_unit"),
    "temp_range": ("temp_start_value", "temp_end_value", "temp_range_unit"),
}
PRIORITY = ("header_parser", "sidecar", "llm_extracted")  # best first

SIDECAR_KEYS = {
    "sample_name": "sample_name",
    "name": "sample_name",
    "sample_mass": "sample_mass_value",
    "mass": "sample_mass_value",
    "sample_weight": "sample_mass_value",
    "sample_mass_unit": "sample_mass_unit",
    "mass_unit": "sample_mass_unit",
    "heating_rate": "heating_rate_value",
    "scan_rate": "heating_rate_value",
    "heating_rate_unit": "heating_rate_unit",
    "endothermic_direction": "endothermic_direction",
    "endotherm_direction": "endothermic_direction",
    "endo_direction": "endothermic_direction",
    "crucible": "crucible_type",
    "crucible_type": "crucible_type",
    "purge_gas": "purge_gas",
    "sample_category": "sample_category",
    "category": "sample_category",
    "sample_preparation": "sample_preparation",
    "storage_condition": "storage_condition",
}
NUMERIC_FIELDS = {"sample_mass_value", "heating_rate_value"}


class UnsupportedFileError(ValueError):
    """The file is not a DSC export we can read."""


@dataclass
class IngestResult:
    db_file: DSCFile
    metadata: DSCMetadata
    missing_critical_fields: list[str]
    warnings: list[str] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)
    already_existed: bool = False
    table: pd.DataFrame | None = None  # set on a fresh ingest; else use load_table()

    @property
    def ready_for_analysis(self) -> bool:
        return not self.missing_critical_fields and not self.unconfirmed


# ------------------------------------------------------------------- routing


def is_sidecar(filename: str) -> bool:
    return filename.lower().endswith(SIDECAR_SUFFIX)


def is_dsc_candidate(filename: str) -> bool:
    """Route by extension. The browser's MIME type is unreliable for instrument exports."""
    return PurePath(filename).suffix.lower() in ALLOWED_EXTENSIONS and not is_sidecar(
        filename
    )


def sidecar_stem(filename: str) -> str:
    return filename[: -len(SIDECAR_SUFFIX)].lower()


def pair_sidecars(
    files: list[tuple[str, bytes]],
) -> list[tuple[str, bytes, bytes | None]]:
    """Group uploaded files into (data file name, data bytes, sidecar bytes or None).

    Pairing is by name stem, once, at upload time, so later renames do not matter.
    """
    sidecars = {sidecar_stem(n): b for n, b in files if is_sidecar(n)}
    grouped = []
    for name, data in files:
        if is_dsc_candidate(name):
            stem = PurePath(name).stem.lower()
            grouped.append((name, data, sidecars.get(stem)))
    return grouped


# ------------------------------------------------------------------- sidecar


def _canonical_key(raw: str) -> str | None:
    key = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    return SIDECAR_KEYS.get(key)


def parse_sidecar(raw: bytes) -> dict[str, Any]:
    """Read a metadata CSV as `key,value` rows or as one header row plus one value row."""
    text = decode_text(raw)
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return {}
    if (
        len(rows) > 1
        and all(len(r) >= 2 for r in rows)
        and max(len(r) for r in rows) == 2
    ):
        pairs = [(r[0], r[1]) for r in rows]
    elif len(rows) >= 2:
        pairs = list(zip(rows[0], rows[1]))
    else:
        return {}

    out: dict[str, Any] = {}
    for raw_key, raw_value in pairs:
        key, value = _canonical_key(raw_key), raw_value.strip()
        if not key or not value:
            continue
        if key in NUMERIC_FIELDS:
            match = re.match(
                r"^\s*(-?[\d.,]+(?:[eE][-+]?\d+)?)\s*([A-Za-zµ°/]*)\s*$", value
            )
            number = to_float(match.group(1)) if match else None
            if number is None:
                continue
            out[key] = number
            if match.group(2):  # "10 mg" carries its own unit
                out[key.replace("_value", "_unit")] = (
                    match.group(2).replace("µ", "u").replace("°", "")
                )
        elif key == "endothermic_direction":
            low = value.lower()
            if low.startswith("up") or low.startswith("down"):
                out[key] = "up" if low.startswith("up") else "down"
        else:
            out[key] = value
    return out


# --------------------------------------------------------------------- merge


def _group_of(key: str) -> str:
    for group, keys in FIELD_GROUPS.items():
        if key in keys:
            return group
    return key


def merge_sources(
    layers: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Combine {source: fields} by PRIORITY. Returns (merged fields, {group: source})."""
    merged: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for source in reversed(PRIORITY):  # worst first, so better sources overwrite
        fields = layers.get(source) or {}
        by_group: dict[str, dict[str, Any]] = {}
        for key, value in fields.items():
            if value is None or key == "raw_header_json":
                continue
            by_group.setdefault(_group_of(key), {})[key] = value
        for group, values in by_group.items():
            for stale in FIELD_GROUPS.get(
                group, ()
            ):  # replace the whole value+unit pair
                merged.pop(stale, None)
            merged.update(values)
            sources[group] = source
    return merged, sources


# --------------------------------------------------------------- validation


def check_consistency(parsed: ParsedDSC, merged: dict[str, Any]) -> list[str]:
    """Warnings only. These never block ingestion."""
    warnings = list(parsed.warnings)
    params = resolve_run_params(merged)

    rate_warning = compare_heating_rate(
        params.heating_rate_c_per_min, parsed.fitted_heating_rate
    )
    if rate_warning:
        warnings.append(rate_warning)

    temp = parsed.table["temperature_C"]
    if params.temp_start_c is not None and params.temp_end_c is not None:
        if (
            abs(temp.min() - params.temp_start_c) > 20
            or abs(temp.max() - params.temp_end_c) > 20
        ):
            warnings.append(
                f"Data covers {temp.min():.0f} to {temp.max():.0f} °C but the metadata says "
                f"{params.temp_start_c:.0f} to {params.temp_end_c:.0f} °C."
            )
    if parsed.table["temperature_C"].duplicated().mean() > 0.2:
        warnings.append(
            "Many repeated temperature values; the file may have isothermal holds."
        )
    if parsed.heat_flow_normalized is None and parsed.heat_flow_unit is None:
        magnitude = float(parsed.table["heat_flow_mW"].abs().median())
        if magnitude > 20:
            warnings.append(
                "Heat flow values are large; they may already be per gram. Confirm the unit."
            )
    return warnings


# -------------------------------------------------------------------- ingest


async def _read_result(db: AsyncSession, db_file: DSCFile) -> IngestResult:
    await db.refresh(db_file, attribute_names=["metadata_record"])
    meta = db_file.metadata_record
    missing = DSCMetadataRead.model_validate(meta).missing_critical_fields()
    return IngestResult(
        db_file=db_file,
        metadata=meta,
        missing_critical_fields=missing,
        warnings=list(getattr(meta, "parse_warnings", None) or []),
        unconfirmed=list(getattr(meta, "unconfirmed_fields", None) or []),
        already_existed=True,
    )


async def load_table(db_file: DSCFile) -> pd.DataFrame:
    """The canonical table of an already-ingested file."""
    if not db_file.table_uri:
        raise LookupError(
            f"'{db_file.original_filename}' has no processed table; upload it again."
        )
    return await download_table_from_gcs(db_file.table_uri)


async def ingest_file(
    db: AsyncSession,
    raw_bytes: bytes,
    filename: str,
    content_type: str | None = None,
    sidecar_bytes: bytes | None = None,
    uploaded_by: str | None = None,
    use_llm: bool = True,
) -> IngestResult:
    if not is_dsc_candidate(filename):
        raise UnsupportedFileError(
            f"'{filename}' is not a supported DSC file type "
            f"({', '.join(sorted(ALLOWED_EXTENSIONS))})."
        )

    file_hash = compute_sha256(raw_bytes)
    existing = (
        await db.execute(
            select(DSCFile)
            .options(selectinload(DSCFile.metadata_record))
            .where(DSCFile.file_hash_sha256 == file_hash)
        )
    ).scalar_one_or_none()
    if existing and existing.metadata_record:
        return await _read_result(db, existing)

    try:
        parsed = parse_dsc_file(raw_bytes, filename)
    except ValueError as error:
        raise UnsupportedFileError(f"Could not read '{filename}': {error}") from error

    header_fields = parse_dsc_header(raw_bytes, filename, parsed).model_dump(
        exclude_unset=True
    )
    layers: dict[str, dict[str, Any]] = {"header_parser": header_fields}
    if sidecar_bytes:
        layers["sidecar"] = parse_sidecar(sidecar_bytes)

    merged, sources = merge_sources(layers)
    missing = resolve_run_params(merged).missing
    llm_used = False
    if use_llm and missing:
        llm_fields = await extract_missing_with_llm(parsed.header_text, missing)
        if llm_fields:
            layers["llm_extracted"] = llm_fields
            merged, sources = merge_sources(layers)
            llm_used = True

    warnings = check_consistency(parsed, merged)
    if llm_used:
        warnings.append(
            "Some metadata was read from the header by a language model "
            f"({', '.join(g for g, s in sources.items() if s == 'llm_extracted')}). Please confirm it."
        )

    # fields that stay unconfirmed until the user answers
    unconfirmed = list(parsed.unconfirmed)
    if llm_used:
        unconfirmed += [g for g, s in sources.items() if s == "llm_extracted"]

    # store raw bytes, then the canonical table, then the rows
    storage_uri = await upload_bytes_to_gcs(
        raw_bytes, filename, content_type or "application/octet-stream"
    )
    db_file = DSCFile(
        original_filename=filename,
        storage_uri=storage_uri,
        file_hash_sha256=file_hash,
        file_format=PurePath(filename).suffix.lower().lstrip(".") or "txt",
        uploaded_by=uploaded_by,
    )
    db.add(db_file)
    await db.flush()
    db_file.table_uri = await upload_table_to_gcs(parsed.table, db_file.file_id)

    payload = DSCMetadataPayload(
        **{**merged, "raw_header_json": header_fields.get("raw_header_json", {})}
    )
    meta_dict = payload.model_dump()
    meta_dict["isothermal_holds"] = [h.model_dump() for h in payload.isothermal_holds]
    meta_dict["composition"] = [c.model_dump() for c in payload.composition]
    meta_dict["extraction_source"] = next(
        (s for s in PRIORITY if s in set(sources.values())), "header_parser"
    )
    meta_dict["field_sources"] = sources
    meta_dict["parse_warnings"] = warnings
    meta_dict["unconfirmed_fields"] = unconfirmed

    db_meta = DSCMetadata(file_id=db_file.file_id, **meta_dict)
    db.add(db_meta)
    await db.commit()
    await db.refresh(db_meta)

    missing_final = DSCMetadataRead.model_validate(db_meta).missing_critical_fields()
    return IngestResult(
        db_file=db_file,
        metadata=db_meta,
        missing_critical_fields=missing_final,
        warnings=warnings,
        unconfirmed=unconfirmed,
        table=parsed.table,
    )


# ------------------------------------------------------------ user answers


async def apply_user_metadata(
    db: AsyncSession,
    db_file: DSCFile,
    changes: dict[str, Any],
    confirm: list[str] | None = None,
) -> IngestResult:
    """Write values the user gave (highest priority) and mark them as confirmed.

    ``changes`` uses DB field names (sample_mass_value, endothermic_direction, ...).
    ``confirm`` lists unconfirmed items the user accepted as they are, e.g.
    ["temperature_unit"] or ["column_mapping"].
    """
    await db.refresh(db_file, attribute_names=["metadata_record"])
    meta = db_file.metadata_record

    sources = dict(meta.field_sources or {})
    unconfirmed = list(meta.unconfirmed_fields or [])
    for key, value in changes.items():
        if key in ("isothermal_holds", "composition") and value is not None:
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(meta, key, value)
        group = _group_of(key)
        sources[group] = "user_verified"
        # "heat_flow_unit" confirms the heat-flow question, and so on
        unconfirmed = [u for u in unconfirmed if u not in (group, key)]
    unconfirmed = [u for u in unconfirmed if u not in (confirm or [])]

    meta.field_sources = sources
    meta.unconfirmed_fields = unconfirmed
    meta.extraction_source = "user_verified"
    await db.commit()
    await db.refresh(meta)

    missing = DSCMetadataRead.model_validate(meta).missing_critical_fields()
    return IngestResult(
        db_file=db_file,
        metadata=meta,
        missing_critical_fields=missing,
        warnings=list(meta.parse_warnings or []),
        unconfirmed=unconfirmed,
        already_existed=True,
    )
