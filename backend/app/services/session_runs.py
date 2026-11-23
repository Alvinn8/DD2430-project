from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.services.run_params import resolve_run_params


def safe_stem(file_name: str) -> str:
    stem = Path(file_name).stem
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "dsc_file"


def write_session_files(
    upload_dir: Path,
    local_name: str,
    table: pd.DataFrame,
    meta,
    unconfirmed: list[str],
    warnings: list[str],
) -> None:
    """(Re)write <local_name> and its _metadata.csv from the table and the DB metadata row."""
    params = resolve_run_params(meta)
    table.to_csv(upload_dir / local_name, index=False)

    row = {
        "sample_name": getattr(meta, "sample_name", None),
        "sample_mass": params.sample_mass_mg,  # mg
        "heating_rate": params.heating_rate_c_per_min,  # degC/min
        "endothermic_direction": getattr(meta, "endothermic_direction", None),
        "endo_up": params.endo_up,
        "heat_flow_normalized": params.heat_flow_normalized,
        "heat_flow_unit": getattr(meta, "heat_flow_unit", None),
        "missing": ";".join(params.missing),
        "unconfirmed": ";".join(unconfirmed),
        "warnings": " | ".join(warnings),
    }
    metadata_name = local_name.removesuffix(".csv") + "_metadata.csv"
    pd.DataFrame([row]).to_csv(upload_dir / metadata_name, index=False)


def unique_local_name(taken: list[str], file_name: str) -> str:
    """<stem>.csv, or <stem>-2.csv when this session already has that name."""
    name = safe_stem(file_name) + ".csv"
    n = 1
    while name in taken:
        n += 1
        name = f"{safe_stem(file_name)}-{n}.csv"
    return name
