from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

MASS_TO_MG = {"mg": 1.0, "g": 1000.0, "ug": 1e-3, "kg": 1e6}
# value in unit -> degC/min (a rate of K/min equals degC/min)
RATE_TO_C_PER_MIN = {
    "c/min": 1.0,
    "k/min": 1.0,
    "c/s": 60.0,
    "k/s": 60.0,
    "c/h": 1 / 60,
    "k/h": 1 / 60,
}

# Fields the analysis cannot be trusted without
CRITICAL_FIELDS = ("sample_mass", "heating_rate", "endothermic_direction")


def _get(meta: Any, key: str):
    if isinstance(meta, Mapping):
        return meta.get(key)
    return getattr(meta, key, None)


def _number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_unit(unit) -> str:
    return (
        str(unit or "")
        .strip()
        .lower()
        .replace("°", "")
        .replace("º", "")
        .replace("µ", "u")
        .replace(" ", "")
    )


def to_mg(value, unit) -> float | None:
    """Mass to mg. A missing unit is treated as mg, the DSC convention."""
    number = _number(value)
    if number is None or number <= 0:
        return None
    factor = MASS_TO_MG.get(_clean_unit(unit) or "mg")
    return None if factor is None else number * factor


def to_c_per_min(value, unit) -> float | None:
    """Heating rate to degC/min. A missing unit is treated as degC/min."""
    number = _number(value)
    if number is None or number <= 0:
        return None
    factor = RATE_TO_C_PER_MIN.get(_clean_unit(unit) or "c/min")
    return None if factor is None else number * factor


@dataclass
class RunParams:
    sample_mass_mg: float | None = None
    heating_rate_c_per_min: float | None = None
    endo_up: bool | None = None  # None = unknown, ask the user
    heat_flow_normalized: bool | None = None
    temp_start_c: float | None = None
    temp_end_c: float | None = None
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "sample_mass": self.sample_mass_mg,
            "heating_rate": self.heating_rate_c_per_min,
            "endo_up": self.endo_up,
            "heat_flow_normalized": self.heat_flow_normalized,
            "temp_start": self.temp_start_c,
            "temp_end": self.temp_end_c,
            "missing": self.missing,
            "problems": self.problems,
        }


def resolve_run_params(meta: Any) -> RunParams:
    """Build RunParams from a DSCMetadata row or a dict with the same field names."""
    params = RunParams()

    mass_value, mass_unit = _get(meta, "sample_mass_value"), _get(
        meta, "sample_mass_unit"
    )
    params.sample_mass_mg = to_mg(mass_value, mass_unit)
    if params.sample_mass_mg is None:
        params.missing.append("sample_mass")
        if mass_value is not None:
            params.problems.append(
                f"Unusable sample mass: {mass_value} {mass_unit or ''}".strip()
            )

    rate_value, rate_unit = _get(meta, "heating_rate_value"), _get(
        meta, "heating_rate_unit"
    )
    params.heating_rate_c_per_min = to_c_per_min(rate_value, rate_unit)
    if params.heating_rate_c_per_min is None:
        params.missing.append("heating_rate")
        if rate_value is not None:
            params.problems.append(
                f"Unusable heating rate: {rate_value} {rate_unit or ''}".strip()
            )

    direction = str(_get(meta, "endothermic_direction") or "").lower()
    if direction in ("up", "down"):
        params.endo_up = direction == "up"
    else:
        params.missing.append("endothermic_direction")

    params.heat_flow_normalized = _get(meta, "is_mass_normalized")

    start, end = _number(_get(meta, "temp_start_value")), _number(
        _get(meta, "temp_end_value")
    )
    range_unit = _clean_unit(_get(meta, "temp_range_unit")) or "c"
    if range_unit == "k":
        start = None if start is None else start - 273.15
        end = None if end is None else end - 273.15
    params.temp_start_c, params.temp_end_c = start, end
    return params


def compare_heating_rate(
    stated_c_per_min: float | None,
    fitted_c_per_min: float | None,
    tolerance: float = 0.05,
) -> str | None:
    """Warning text when the header rate and the rate fitted from the data disagree."""
    if not stated_c_per_min or not fitted_c_per_min:
        return None
    relative = abs(stated_c_per_min - fitted_c_per_min) / stated_c_per_min
    if relative <= tolerance:
        return None
    return (
        f"Heating rate in the metadata is {stated_c_per_min:.3g} °C/min but the data "
        f"gives {fitted_c_per_min:.3g} °C/min ({relative:.0%} apart). One of them is wrong."
    )
