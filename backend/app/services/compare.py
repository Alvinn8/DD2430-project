from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from matplotlib.figure import Figure

TEMP_FIELDS = (
    ("onset_temp_value", "onset"),
    ("peak_temp_value", "peak"),
    ("midpoint_temp_value", "midpoint (Tg)"),
    ("endset_temp_value", "endset"),
)


@dataclass
class Side:
    label: str  # file name shown to the user
    source: str  # "stored run 2026-11-20 14:03" or "this session, not saved"
    events: list[dict[str, Any]]
    params: dict[str, Any] = field(
        default_factory=dict
    )  # heating_rate, sample_mass, endo_up ...
    table: pd.DataFrame | None = None


def _key_temp(event: dict) -> float:
    for key in ("midpoint_temp_value", "peak_temp_value", "onset_temp_value"):
        if event.get(key) is not None:
            return float(event[key])
    return float("inf")


def pair_events(a: list[dict], b: list[dict]):
    """Pair events of the same type by nearest characteristic temperature."""
    pairs, only_a, only_b = [], [], []
    for event_type in sorted(
        {e["event_type"] for e in a} | {e["event_type"] for e in b}
    ):
        left = sorted((e for e in a if e["event_type"] == event_type), key=_key_temp)
        right = sorted((e for e in b if e["event_type"] == event_type), key=_key_temp)
        while left and right:
            best = min(
                ((i, j) for i in range(len(left)) for j in range(len(right))),
                key=lambda ij: abs(_key_temp(left[ij[0]]) - _key_temp(right[ij[1]])),
            )
            pairs.append((left.pop(best[0]), right.pop(best[1])))
        only_a += left
        only_b += right
    return pairs, only_a, only_b


def comparability_warnings(a: Side, b: Side) -> list[str]:
    warnings = []
    ra, rb = a.params.get("heating_rate"), b.params.get("heating_rate")
    if ra and rb and abs(ra - rb) / max(ra, rb) > 0.05:
        warnings.append(
            f"Heating rates differ ({ra:g} vs {rb:g} °C/min). Peak and onset temperatures shift "
            "with heating rate, so temperature differences are not purely a material effect."
        )
    elif not ra or not rb:
        warnings.append(
            "A heating rate is unknown for one side, so rate effects cannot be ruled out."
        )
    norm_a = {
        e["is_drug_normalized"] for e in a.events if e.get("enthalpy_value") is not None
    }
    norm_b = {
        e["is_drug_normalized"] for e in b.events if e.get("enthalpy_value") is not None
    }
    if norm_a and norm_b and norm_a != norm_b:
        warnings.append(
            "One enthalpy is normalized to the drug fraction and the other to total sample mass; "
            "do not compare them directly."
        )
    units_a = {
        e.get("enthalpy_unit") for e in a.events if e.get("enthalpy_value") is not None
    }
    units_b = {
        e.get("enthalpy_unit") for e in b.events if e.get("enthalpy_value") is not None
    }
    if units_a and units_b and units_a != units_b:
        warnings.append(
            f"Enthalpy units differ ({', '.join(map(str, units_a))} vs {', '.join(map(str, units_b))})."
        )
    return warnings


def _fmt(value, digits=2):
    return "n/a" if value is None else f"{value:.{digits}f}"


def _delta(x, y, digits=2):
    return "n/a" if x is None or y is None else f"{y - x:+.{digits}f}"


def compare_text(a: Side, b: Side) -> str:
    """Plain-text comparison. Differences are B minus A."""
    pairs, only_a, only_b = pair_events(a.events, b.events)
    lines = [
        f"A = {a.label} ({a.source})",
        f"B = {b.label} ({b.source})",
        "Differences are B minus A.",
    ]
    if not a.events or not b.events:
        side = a if not a.events else b
        lines.append(
            f"No results found for {side.label}; run the analysis on it first."
        )
    for ea, eb in pairs:
        lines.append(f"\n{ea['event_type']}:")
        for field_name, label in TEMP_FIELDS:
            x, y = ea.get(field_name), eb.get(field_name)
            if x is not None or y is not None:
                lines.append(
                    f"  {label}: A {_fmt(x)} °C, B {_fmt(y)} °C, Δ {_delta(x, y)} °C"
                )
        x, y = ea.get("enthalpy_value"), eb.get("enthalpy_value")
        if x is not None or y is not None:
            ex, ey = ea.get("enthalpy_error_value"), eb.get("enthalpy_error_value")
            lines.append(
                f"  enthalpy: A {_fmt(x)}{f' ± {ex:.2f}' if ex else ''} {ea.get('enthalpy_unit') or 'J/g'}, "
                f"B {_fmt(y)}{f' ± {ey:.2f}' if ey else ''} {eb.get('enthalpy_unit') or 'J/g'}, "
                f"Δ {_delta(x, y)}"
                + (f" ({(y - x) / x:+.1%})" if x and y is not None else "")
            )
    for side, rest in ((a, only_a), (b, only_b)):
        for event in rest:
            lines.append(
                f"\nOnly in {side.label}: {event['event_type']} near {_fmt(_key_temp(event) if _key_temp(event) != float('inf') else None, 1)} °C"
            )
    warnings = comparability_warnings(a, b)
    if warnings:
        lines.append("\nCaution:")
        lines += [f"  - {w}" for w in warnings]
    return "\n".join(lines)


def overlay_png(a: Side, b: Side) -> bytes | None:
    """Both heat-flow curves on one plot, per mg when masses are known and endotherm up."""
    if a.table is None or b.table is None:
        return None
    fig = Figure(figsize=(8, 5), dpi=100)
    ax = fig.add_subplot()
    notes = []
    per_mg = bool(a.params.get("sample_mass") and b.params.get("sample_mass"))
    for side, color in ((a, "#2b6cb0"), (b, "#c05621")):
        if side.table is None:
            continue
        data = side.table.dropna(subset=["temperature_C", "heat_flow_mW"]).sort_values(
            "temperature_C"
        )
        y = data["heat_flow_mW"].to_numpy(dtype=float)
        if per_mg and not side.params.get("heat_flow_normalized"):
            y = y / side.params["sample_mass"]
        endo_up = side.params.get("endo_up")
        if endo_up is False:
            y = -y  # show endotherms up on every curve
        ax.plot(data["temperature_C"], y, color=color, linewidth=1, label=side.label)
    if per_mg:
        notes.append("per mg of sample")
    if a.params.get("endo_up") is None or b.params.get("endo_up") is None:
        notes.append("endotherm direction unknown for one curve, shown as exported")
    else:
        notes.append("endotherms up")
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Heat flow (mW/mg)" if per_mg else "Heat flow (mW)")
    ax.set_title("Overlay" + (f" ({'; '.join(notes)})" if notes else ""), fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.legend()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    return buf.getvalue()
