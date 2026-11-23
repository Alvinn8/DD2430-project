from __future__ import annotations

import codecs
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePath

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = ("time_min", "temperature_C", "heat_flow_mW")
MIN_TABLE_ROWS = 5
HEADER_LOOKBACK = 15

# unit string (lowercase, no degree sign / spaces) -> conversion
TEMP_UNITS = {
    "c": lambda x: x,
    "degc": lambda x: x,
    "k": lambda x: x - 273.15,
    "f": lambda x: (x - 32.0) * 5.0 / 9.0,
}
TIME_TO_MIN = {"min": 1.0, "s": 1 / 60, "sec": 1 / 60, "ms": 1 / 60000, "h": 60.0}

HEAT_FLOW_UNITS = {
    "mw": (1.0, False),
    "w": (1000.0, False),
    "uw": (1e-3, False),
    "mw/mg": (1.0, True),  # mW/mg == W/g
    "w/g": (1.0, True),
}


@dataclass
class ParsedDSC:
    """A standardized DSC table plus everything learned while parsing it."""

    table: pd.DataFrame
    header_text: str
    temperature_unit: str | None = None  # unit found in the file, e.g. "C", "K"
    time_unit: str | None = None
    heat_flow_unit: str | None = None  # unit found in the file, e.g. "mW", "W/g"
    heat_flow_normalized: bool | None = None  # None = unknown
    fitted_heating_rate: float | None = None  # degC/min, from time vs temperature
    fitted_heating_rate_r2: float | None = None
    segments: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)


# text


def decode_text(raw: bytes) -> str:
    """Decode instrument exports: UTF-16 (BOM), UTF-8, then Windows codepages."""
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = raw.decode("utf-16")
    elif raw.startswith(codecs.BOM_UTF8):
        text = raw.decode("utf-8-sig")
    else:
        for enc in ("utf-8", "cp1252"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("latin-1")
    return text.replace("\x00", "")


def to_float(value) -> float | None:
    """Parse '12.5', '12,5', '1,234.5', '1.234,5', '1e-3'. Returns None if not a number."""
    s = str(value).strip().strip("\"'")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        number = float(s)
    except ValueError:
        return None
    return number if np.isfinite(number) else None


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    return (
        unit.strip()
        .lower()
        .replace("°", "")
        .replace("º", "")
        .replace("µ", "u")
        .replace(" ", "")
        or None
    )


# table location


def _detect_delimiter(lines: list[str]) -> str | None:
    """Tab, semicolon or comma by how consistently it splits lines; None = whitespace."""
    sample = [line for line in lines[:2000] if line.strip()]
    best, best_score = None, 0
    # Order matters on ties: a decimal comma also gives consistent comma counts
    for delim in ("\t", ";", ","):
        counts = Counter(line.count(delim) for line in sample if delim in line)
        if counts:
            score = counts.most_common(1)[0][1]
            if score > best_score:
                best, best_score = delim, score
    return best if best_score >= 5 else None


def _cells(line: str, delim: str | None) -> list[str]:
    parts = line.split() if delim is None else line.split(delim)
    return [p.strip() for p in parts]


def _is_numeric_row(cells: list[str]) -> bool:
    values = [to_float(c) for c in cells]
    found = sum(v is not None for v in values)
    return found >= 2 and all(v is not None or c == "" for v, c in zip(values, cells))


def _locate_table(lines: list[str], delim: str | None) -> tuple[int, int, int]:
    """Return (start, end, width) of the first run of numeric rows (end exclusive)."""
    rows = [_cells(line, delim) if line.strip() else None for line in lines]
    for i in range(len(rows) - MIN_TABLE_ROWS + 1):
        first = rows[i]
        if first is None or not _is_numeric_row(first):
            continue
        width = len(first)
        window = rows[i : i + MIN_TABLE_ROWS]
        if all(
            r is not None and len(r) == width and _is_numeric_row(r) for r in window
        ):
            end = i + MIN_TABLE_ROWS
            while end < len(rows):
                r = rows[end]
                if r is None:  # blank line inside the table
                    end += 1
                    continue
                if len(r) != width or not _is_numeric_row(r):
                    break
                end += 1
            return i, end, width
    raise ValueError("No numeric data table found in the file.")


def _column_header(lines: list[str], start: int, width: int, delim: str | None):
    """Nearest non-numeric line above the table with the same number of cells."""
    found: list[list[str]] = []
    for j in range(start - 1, max(start - 1 - HEADER_LOOKBACK, -1), -1):
        text = lines[j].strip().lstrip("#;/ ").strip()
        if not text:
            continue
        cells = _cells(text, delim)
        if len(cells) == width and not _is_numeric_row(cells):
            found.append(cells)
            if len(found) == 2:
                break
        elif found:
            break
    if not found:
        return None
    if len(found) == 2 and all(len(c) <= 10 for c in found[0]):
        # names line + units line: "Temperature | Time" over "°C | min"
        return [f"{n} [{u}]" for n, u in zip(found[1], found[0])]
    return found[0]


# column mapping


def _classify(name: str) -> str | None:
    n = name.lower()
    if "sensit" in n:
        return None
    if "time" in n or re.match(r"^\s*t\s*[/\[(]\s*(min|s)\b", n):
        return "time_min"
    if "temp" in n or "°c" in n or re.match(r"^\s*(ts|tr|t)\s*[/\[(]\s*°?\s*[ck]\b", n):
        return "temperature_C"
    if any(k in n for k in ("dsc", "heat", "flow", "mw", "w/g", "uv", "µv", "cp")):
        return "heat_flow_mW"
    return None


def _unit_of(name: str) -> str | None:
    brackets = re.findall(r"[\[(]\s*([^\])]+?)\s*[\])]", name)
    if brackets:
        return normalize_unit(brackets[-1])
    slash = re.search(r"/\s*([^/\s]+)\s*$", name)
    if slash:
        return normalize_unit(slash.group(1))
    underscore = re.search(r"_([A-Za-z]+)$", name)
    return normalize_unit(underscore.group(1)) if underscore else None


def _map_columns(header: list[str] | None, width: int, result: ParsedDSC):
    """Return {canonical_name: (column_index, normalized_unit)}."""
    mapping: dict[str, tuple[int, str | None]] = {}
    if header:
        for idx, name in enumerate(header):
            kind = _classify(name)
            if kind and kind not in mapping:
                mapping[kind] = (idx, _unit_of(name))
    if "temperature_C" in mapping and "heat_flow_mW" in mapping:
        return mapping

    # No usable header: positional guess, which must be confirmed by the user
    mapping = {}
    if width == 2:
        mapping = {"temperature_C": (0, None), "heat_flow_mW": (1, None)}
    elif width == 3:
        mapping = {
            "time_min": (0, None),
            "temperature_C": (1, None),
            "heat_flow_mW": (2, None),
        }
    else:
        raise ValueError(
            f"Cannot tell which of the {width} columns are temperature and heat flow "
            "(no recognizable column header)."
        )
    result.unconfirmed.append("column_mapping")
    result.warnings.append(
        "No column header found; assumed the column order "
        + ", ".join(mapping)
        + ". Ask the user to confirm."
    )
    return mapping


# segments


def _find_segments(T: np.ndarray) -> list[dict]:
    """Split a run into heating / cooling / isothermal segments by dT sign."""
    n = len(T)
    if n < 30:
        return [{"start": 0, "end": n, "direction": 0}]
    dT = np.diff(T, prepend=T[0])
    win = max(5, (n // 200) | 1)
    med = pd.Series(dT).rolling(win, center=True, min_periods=1).median().to_numpy()
    tol = 0.05 * float(np.percentile(np.abs(dT), 90)) or 1e-12
    labels = np.where(med > tol, 1, np.where(med < -tol, -1, 0))

    runs, start = [], 0
    for i in range(1, n + 1):
        if i == n or labels[i] != labels[start]:
            runs.append({"start": start, "end": i, "direction": int(labels[start])})
            start = i
    min_len = max(10, n // 100)
    runs = [r for r in runs if r["end"] - r["start"] >= min_len]

    merged: list[dict] = []
    for run in runs:  # re-join a run split by a short noisy blip
        if merged and merged[-1]["direction"] == run["direction"]:
            merged[-1]["end"] = run["end"]
        else:
            merged.append(dict(run))
    return merged or [{"start": 0, "end": n, "direction": 0}]


def _fit_rate(time_min: np.ndarray, temp_c: np.ndarray):
    ok = np.isfinite(time_min) & np.isfinite(temp_c)
    if ok.sum() < 5 or np.ptp(time_min[ok]) <= 0:
        return None, None
    t, y = time_min[ok], temp_c[ok]
    slope, intercept = np.polyfit(t, y, 1)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = (
        1.0 - float(np.sum((y - (slope * t + intercept)) ** 2)) / ss_tot
        if ss_tot
        else None
    )
    return float(slope), r2


# public API


def _excel_to_text(raw: bytes) -> str:
    sheet = pd.read_excel(io.BytesIO(raw), header=None, sheet_name=0, dtype=str)
    return sheet.fillna("").to_csv(sep="\t", header=False, index=False)


def parse_dsc_file(raw: bytes, filename: str) -> ParsedDSC:
    """Parse raw bytes of a DSC export. Raises ValueError when no table is found."""
    suffix = PurePath(filename).suffix.lower()
    text = _excel_to_text(raw) if suffix in (".xls", ".xlsx") else decode_text(raw)
    lines = text.splitlines()

    delim = _detect_delimiter(lines)
    start, end, width = _locate_table(lines, delim)
    header = _column_header(lines, start, width, delim)

    result = ParsedDSC(
        table=pd.DataFrame(),
        header_text="\n".join(lines[:start] + lines[end:]),
    )
    mapping = _map_columns(header, width, result)

    block = [_cells(line, delim) for line in lines[start:end] if line.strip()]
    values = np.full((len(block), width), np.nan)
    for r, cells in enumerate(block):
        for c, cell in enumerate(cells):
            number = to_float(cell)
            if number is not None:
                values[r, c] = number

    # temperature
    t_idx, t_unit = mapping["temperature_C"]
    temp = values[:, t_idx]
    if t_unit in TEMP_UNITS:
        result.temperature_unit = (
            "K" if t_unit == "k" else "F" if t_unit == "f" else "C"
        )
        temp = TEMP_UNITS[t_unit](temp)
    else:
        result.unconfirmed.append("temperature_unit")
        result.warnings.append(
            f"Temperature unit {'unrecognized: ' + t_unit if t_unit else 'not stated'}; "
            "treated as °C until the user confirms."
        )

    # time
    time_min = np.full(len(temp), np.nan)
    if "time_min" in mapping:
        i_time, u_time = mapping["time_min"]
        raw_time = values[:, i_time]
        if u_time in TIME_TO_MIN:
            result.time_unit = u_time if u_time != "sec" else "s"
            time_min = raw_time * TIME_TO_MIN[u_time]
        elif np.isfinite(raw_time).any():
            result.unconfirmed.append("time_unit")
            result.warnings.append(
                "Time unit not stated; treated as minutes until confirmed."
            )
            time_min = raw_time

    # heat flow
    h_idx, h_unit = mapping["heat_flow_mW"]
    heat = values[:, h_idx]
    if h_unit in HEAT_FLOW_UNITS:
        factor, per_gram = HEAT_FLOW_UNITS[h_unit]
        heat = heat * factor
        result.heat_flow_unit = {
            "mw": "mW",
            "w": "W",
            "uw": "uW",
            "mw/mg": "mW/mg",
            "w/g": "W/g",
        }[h_unit]
        result.heat_flow_normalized = per_gram
    else:
        result.unconfirmed.append("heat_flow_unit")
        result.warnings.append(
            f"Heat flow unit {'unrecognized: ' + h_unit if h_unit else 'not stated'}; "
            "values kept as they are. Ask whether they are mW or already per gram."
        )

    table = pd.DataFrame(
        {"time_min": time_min, "temperature_C": temp, "heat_flow_mW": heat}
    )
    table = table.dropna(subset=["temperature_C", "heat_flow_mW"]).reset_index(
        drop=True
    )
    if len(table) < MIN_TABLE_ROWS:
        raise ValueError("Fewer than 5 usable rows after removing empty values.")
    if (
        table["time_min"].notna().all()
        and not table["time_min"].is_monotonic_increasing
    ):
        table = table.sort_values("time_min", kind="mergesort").reset_index(drop=True)

    # keep one monotonic heating scan: the analysis tools assume it
    segments = _find_segments(table["temperature_C"].to_numpy())
    names = {1: "heating", -1: "cooling", 0: "isothermal"}
    T = table["temperature_C"].to_numpy()
    result.segments = [
        {
            "direction": names[s["direction"]],
            "start_index": s["start"],
            "end_index": s["end"],
            "t_start": float(T[s["start"]]),
            "t_end": float(T[s["end"] - 1]),
        }
        for s in segments
    ]
    heating = [s for s in segments if s["direction"] == 1]
    if heating:
        main = max(heating, key=lambda s: s["end"] - s["start"])
        if len([s for s in segments if s["direction"] != 0]) > 1:
            result.warnings.append(
                f"File has {len(segments)} segments "
                f"({', '.join(r['direction'] for r in result.segments)}); only the longest "
                f"heating segment ({T[main['start']]:.1f} to {T[main['end'] - 1]:.1f} °C) is analysed."
            )
        table = table.iloc[main["start"] : main["end"]].reset_index(drop=True)
    else:
        result.warnings.append(
            "No heating segment detected; the whole file is used as it is."
        )

    result.fitted_heating_rate, result.fitted_heating_rate_r2 = _fit_rate(
        table["time_min"].to_numpy(), table["temperature_C"].to_numpy()
    )
    result.table = table
    return result
