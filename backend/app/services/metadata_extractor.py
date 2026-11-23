from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.db.schemas.dsc import DSCMetadataPayload
from app.services.dsc_parser import ParsedDSC, decode_text, normalize_unit, to_float

NUM = r"(-?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)"
PREFIX = r"^[#;/\s]*"
SEP = r"\s*[:=\t;,]\s*"

HEADER_PATTERNS: dict[str, re.Pattern[str]] = {
    "sample_name": re.compile(
        PREFIX + r"(?:sample(?:\s*name|\s*id)?|identity|specimen)" + SEP + r"(.+)$",
        re.I,
    ),
    "sample_mass": re.compile(
        PREFIX
        + r"(?:sample\s*)?(?:mass|weight|wt\.?)"
        + SEP
        + NUM
        + r"\s*(mg|µg|ug|g)?\b",
        re.I,
    ),
    "heating_rate": re.compile(
        PREFIX
        + r"(?:heating\s*rate|scan\s*rate|ramp(?:\s*rate)?|rate|slope)"
        + SEP
        + NUM
        + r"\s*([°º]?\s*[CK]\s*/\s*(?:min|s|h))?",
        re.I,
    ),
    "crucible": re.compile(
        PREFIX + r"(?:pan|crucible|pan\s*type)" + SEP + r"(.+)$", re.I
    ),
    "purge_gas": re.compile(
        PREFIX + r"(?:purge\s*)?gas(?:\s*1)?" + SEP + r"([A-Za-z][A-Za-z0-9]*)"
        r"(?:.*?" + NUM + r"\s*(ml/min|cm3/min|l/min))?",
        re.I,
    ),
    "endotherm_dir": re.compile(
        r"endo(?:therm(?:ic)?)?\s*(?:peaks?|direction|heat\s*flow)?\s*(?:point\s*|is\s*|:\s*|=\s*)?"
        r"(up(?:ward)?|down(?:ward)?)",
        re.I,
    ),
    "exo_direction": re.compile(
        r"exo(?:therm(?:ic)?)?\s*(?:peaks?|direction|heat\s*flow)?\s*(?:point\s*|is\s*|:\s*|=\s*)?"
        r"(up(?:ward)?|down(?:ward)?)",
        re.I,
    ),
    "temp_range": re.compile(
        PREFIX
        + r"(?:temperature\s*)?(?:range|program)\b.*?"
        + NUM
        + r"\s*(?:to|-|–|…|\.\.)\s*"
        + NUM
        + r"\s*([°º]?\s*[CK])?",
        re.I,
    ),
}


def _dec(value: str | None) -> Decimal | None:
    number = to_float(value) if value is not None else None
    if number is None:
        return None
    try:
        return Decimal(str(number))
    except InvalidOperation:
        return None


def _rate_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    return (
        raw.replace("°", "")
        .replace("º", "")
        .replace(" ", "")
        .replace("c", "C")
        .replace("k", "K")
    )


def extract_from_header_text(header_text: str, filename: str) -> dict[str, Any]:
    """Pull run conditions out of the free-text header. Only fields that are present are set."""
    out: dict[str, Any] = {}
    raw_header: dict[str, str] = {}

    for line in header_text.splitlines()[:200]:
        stripped = line.strip()
        if not stripped:
            continue

        key_value = re.match(r"^[#;/\s]*([^:=\t]{1,60}?)\s*[:=\t]\s*(.+)$", stripped)
        if key_value and not key_value.group(1).strip().replace(".", "").isdigit():
            raw_header.setdefault(
                key_value.group(1).strip(), key_value.group(2).strip()
            )

        if m := HEADER_PATTERNS["endotherm_dir"].search(stripped):
            out["endothermic_direction"] = (
                "up" if m.group(1).lower().startswith("up") else "down"
            )
        elif m := HEADER_PATTERNS["exo_direction"].search(stripped):
            # "exo up" means endotherm points down
            out["endothermic_direction"] = (
                "down" if m.group(1).lower().startswith("up") else "up"
            )

        if m := HEADER_PATTERNS["sample_name"].match(stripped):
            out["sample_name"] = m.group(1).strip()
        if m := HEADER_PATTERNS["sample_mass"].match(stripped):
            out["sample_mass_value"] = _dec(m.group(1))
            out["sample_mass_unit"] = (m.group(2) or "mg").lower().replace("µ", "u")
        if m := HEADER_PATTERNS["heating_rate"].match(stripped):
            out["heating_rate_value"] = _dec(m.group(1))
            out["heating_rate_unit"] = _rate_unit(m.group(2)) or "C/min"
        if m := HEADER_PATTERNS["crucible"].match(stripped):
            text = m.group(1).strip()
            out["crucible_type"] = text
            lower = text.lower()
            for config in ("pinhole", "hermetic", "open"):
                if config in lower:
                    out["crucible_lid_config"] = config
                    break
        if m := HEADER_PATTERNS["purge_gas"].match(stripped):
            out["purge_gas"] = m.group(1).strip()
            if m.group(2):
                out["purge_flow_value"] = _dec(m.group(2))
                out["purge_flow_unit"] = m.group(3).lower().replace("cm3", "cm3")
        if m := HEADER_PATTERNS["temp_range"].match(stripped):
            out["temp_start_value"], out["temp_end_value"] = _dec(m.group(1)), _dec(
                m.group(2)
            )
            temp_unit = normalize_unit(m.group(3) or "C")
            if temp_unit is not None:
                out["temp_range_unit"] = temp_unit.upper()

    out["raw_header_json"] = raw_header
    out.setdefault("sample_name", filename.rsplit(".", 1)[0])
    return out


def parse_dsc_header(
    raw_bytes: bytes, filename: str, parsed: ParsedDSC | None = None
) -> DSCMetadataPayload:
    """Header metadata as a payload. Pass ``parsed`` to reuse an existing parse."""
    header_text = parsed.header_text if parsed else decode_text(raw_bytes)
    fields = extract_from_header_text(header_text, filename)

    if parsed:
        # axis units come from the column header, which the parser already read
        if parsed.temperature_unit:
            fields["temperature_unit"] = parsed.temperature_unit
        if parsed.time_unit:
            fields["time_unit"] = parsed.time_unit
        fields["has_time_axis"] = bool(parsed.table["time_min"].notna().any())
        if parsed.heat_flow_unit:
            fields["heat_flow_unit"] = parsed.heat_flow_unit
        if parsed.heat_flow_normalized is not None:
            fields["is_mass_normalized"] = parsed.heat_flow_normalized

    fields["extraction_source"] = "header_parser"
    return DSCMetadataPayload(**fields)
