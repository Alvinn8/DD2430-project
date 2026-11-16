# pylint: disable=too-many-arguments,too-many-locals

import base64
import io
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import pandas as pd
from langchain.tools import tool, ToolRuntime
from matplotlib.figure import Figure
from app.tools.DSCReader import (
    read_standardized_dsc_file,
    read_standardized_dsc_metadata,
)
from app.tools.GlassTransitionAnalysis import find_glass_transition
from app.tools.MeltingPointAnalysis import find_melting_point
from app.tools.EnthalpyAnalysis import analyze_enthalpy, plot_enthalpy


@dataclass
class SessionContext:
    """Per-session state, passed to every tool call. Changes made by tools persist."""

    session_id: str
    # Directory where the session's uploaded files are stored
    upload_dir: Path | None = None
    # File names (not paths) of the uploaded DSC files, relative to upload_dir
    current_dsc_file: str | None = None
    dsc_files_available: list[str] = field(default_factory=list)

    def dsc_file_path(self, file_name: str) -> str:
        """Construct the full path of an uploaded DSC file from its name."""
        if self.upload_dir is None:
            return file_name
        return str(self.upload_dir / file_name)


def _meta_float(metadata, *keys):
    """Read a numeric metadata value, returning None if missing or NaN."""
    for key in keys:
        try:
            value = float((metadata or {}).get(key))
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            return value
    return None


@tool(
    "enthalpy_analysis",
    description=(
        "Calculate the enthalpy (J/g) of one thermal event, e.g. the enthalpy of fusion, "
        "in the currently selected DSC file. Two independent estimates are returned: "
        "(1) a fit of the analytical DSC_N(T) model (Ghanbari et al. 2023), and "
        "(2) baseline-corrected numerical integration. Also returns the equilibrium "
        "melting temperature Tm0, peak, onset and endset temperatures, fit quality and "
        "warnings. You MUST know whether endothermic peaks point up (endo_up=True) or "
        "down; ask the user if unclear. The sample mass (mg) is needed unless the heat "
        "flow is already normalized; it is read from the file metadata when available, "
        "otherwise ask the user. Use t_min/t_max to isolate the event and to exclude a "
        "decomposition exotherm that follows melting. event is 'endothermic' for melting "
        "and 'exothermic' for crystallization or decomposition. baseline is 'linear' or "
        "'sigmoidal' (use sigmoidal if the baseline steps across the peak)."
    ),
)
def enthalpy_analysis(
    runtime: ToolRuntime[SessionContext],
    endo_up: bool,
    sample_mass: float | None = None,
    heat_flow_normalized: bool = False,
    heating_rate: float | None = None,
    event: str = "endothermic",
    t_min: float | None = None,
    t_max: float | None = None,
    fit_dcp: bool = True,
) -> str | list[dict]:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
        metadata = read_standardized_dsc_metadata(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    if heating_rate is None:
        heating_rate = _meta_float(metadata, "heating_rate", "heating_rate_C_per_min")
    if heating_rate is None:
        return (
            "The heating rate is not in the metadata and was not given. "
            "Ask the user for it (°C/min)."
        )
    if sample_mass is None and not heat_flow_normalized:
        sample_mass = _meta_float(metadata, "sample_mass", "sample_mass_mg")
    if sample_mass is None and not heat_flow_normalized:
        return (
            "The sample mass is not in the metadata and was not given. Ask the user for "
            "the sample mass (mg), or whether the heat flow is already per gram."
        )

    data = df.dropna(subset=["temperature_C", "heat_flow_mW"]).sort_values(
        "temperature_C"
    )
    try:
        result = analyze_enthalpy(
            data["temperature_C"].to_numpy(),
            data["heat_flow_mW"].to_numpy(),
            heating_rate=heating_rate,
            sample_mass=sample_mass,
            already_normalized=heat_flow_normalized,
            endo_up=endo_up,
            event=event,
            t_min=t_min,
            t_max=t_max,
            fit_dcp=fit_dcp,
        )
    except (ValueError, TypeError, IndexError, np.linalg.LinAlgError) as exc:
        return f"Enthalpy analysis failed for '{file_name}': {exc}"

    fit = result.fit

    def fmt(value):
        return "n/a" if value is None else f"{value:.2f} °C"

    summary = (
        f"Enthalpy analysis of '{file_name}' ({event} event, window "
        f"{result.window[0]:.1f} to {result.window[1]:.1f} °C, "
        f"{heating_rate:g} °C/min). "
        f"DSC_N(T) fit: dH = {fit.dH_J_per_g:.2f} ± {fit.dH_J_per_g_err:.2f} J/g, "
        f"Tm0 = {fit.Tm0:.2f} ± {fit.Tm0_err:.2f} °C, peak {fmt(fit.t_peak)}, "
        f"onset {fmt(fit.t_onset)}, endset {fmt(fit.t_endset)}, R² = {fit.r_squared:.4f}, "
        f"alpha = {fit.params['alpha']:.3g} 1/K, beta = {fit.params['beta']:.3g} 1/K², "
        f"dCp = {fit.params['dCp']:.3g} W/(g·K). "
        f"Quality check: {'passed' if result.ok else 'NOT passed'}."
    )
    if result.warnings:
        summary += " Warnings: " + "; ".join(result.warnings) + "."

    fig = plot_enthalpy(result)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    return [
        {"type": "text", "text": summary},
        {
            "type": "image",
            "base64": base64.b64encode(buf.getvalue()).decode("ascii"),
            "mime_type": "image/png",
        },
    ]


@tool(
    "dsc_file_status",
    description="List which DSC files are available and which one is currently selected.",
)
def dsc_file_status(runtime: ToolRuntime[SessionContext]) -> str:
    context = runtime.context
    return f"Available DSC Files: {', '.join(context.dsc_files_available)}, Current: {context.current_dsc_file}"


@tool(
    "select_dsc_file",
    description="Select a DSC file to be the current one for subsequent operations.",
)
def select_dsc_file(runtime: ToolRuntime[SessionContext], file_name: str) -> str:
    context = runtime.context
    if file_name not in context.dsc_files_available:
        return f"File '{file_name}' is not available. Available files: {', '.join(context.dsc_files_available)}"
    context.current_dsc_file = file_name
    return f"Selected DSC file: {file_name}"


@tool(
    "plot_dsc",
    description=(
        "Plot heat flow against temperature for the currently selected DSC file "
        "and return the plot as an image, together with a short numeric summary."
    ),
)
def plot_dsc(runtime: ToolRuntime[SessionContext]) -> str | list[dict]:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
        metadata = read_standardized_dsc_metadata(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    # Plot with the object-oriented API, since pyplot is not thread-safe
    fig = Figure(figsize=(8, 5), dpi=100)
    ax = fig.add_subplot()
    ax.plot(df["temperature_C"], df["heat_flow_mW"], linewidth=1)
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Heat flow (mW)")
    ax.grid(True, alpha=0.3)
    if metadata:
        sample_name = metadata.get("sample_name", file_name)
        heating_rate = metadata.get(
            "heating_rate", metadata.get("heating_rate_C_per_min")
        )
        title = str(sample_name)
        if heating_rate is not None and not pd.isna(heating_rate):
            title += f" ({heating_rate} °C/min)"
        ax.set_title(title)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")

    summary = (
        f"Plot of heat flow against temperature for '{file_name}'. "
        f"{len(df)} data points, temperature range "
        f"{df['temperature_C'].min():.2f} to {df['temperature_C'].max():.2f} °C, "
        f"heat flow range {df['heat_flow_mW'].min():.4f} to "
        f"{df['heat_flow_mW'].max():.4f} mW."
    )
    if metadata:
        summary += f" Metadata: {metadata}"

    return [
        {"type": "text", "text": summary},
        {
            "type": "image",
            "base64": base64.b64encode(buf.getvalue()).decode("ascii"),
            "mime_type": "image/png",
        },
    ]


@tool(
    "get_heat_flow_at_temperature",
    description=(
        "Get the heat flow value at a specific temperature from the currently selected DSC file."
    ),
)
def get_heat_flow_at_temperature(
    runtime: ToolRuntime[SessionContext], temperature: float
) -> str:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    # Find the closest temperature in the DataFrame
    closest_idx = (df["temperature_C"] - temperature).abs().idxmin()
    closest_temp = df.loc[closest_idx, "temperature_C"]
    heat_flow = df.loc[closest_idx, "heat_flow_mW"]

    return (
        f"At {closest_temp:.2f} °C, the heat flow is {heat_flow:.4f} mW "
        f"in the DSC file '{file_name}'."
    )


def extreme_value_in_range(
    runtime: ToolRuntime[SessionContext], start_t: float, end_t: float, find_max: bool
) -> str:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    # Filter the DataFrame to the specified temperature range
    filtered_df = df[(df["temperature_C"] >= start_t) & (df["temperature_C"] <= end_t)]

    if filtered_df.empty:
        return f"No data points found in the range [{start_t}, {end_t}] °C."

    # Find the extreme heat flow value and its corresponding temperature
    if find_max:
        extreme_row = filtered_df.loc[filtered_df["heat_flow_mW"].idxmax()]
        extreme_type = "Maximum"
    else:
        extreme_row = filtered_df.loc[filtered_df["heat_flow_mW"].idxmin()]
        extreme_type = "Minimum"

    extreme_temp = extreme_row["temperature_C"]
    extreme_heat_flow = extreme_row["heat_flow_mW"]

    return f"""{extreme_type} heat flow in the range [{start_t}, {end_t}]
    °C is {extreme_heat_flow:.4f} mW at {extreme_temp:.2f} °C."""


@tool(
    "max_value_in_range",
    description=(
        """Get the maximum value in the range [start_t, end_t]. 
        The interval is a range in temperature and the return value is a tuple of (t, y)
        where t is the temperature of the maximum and y is the maximum heat flow value itself."""
    ),
)
def max_value_in_range(
    runtime: ToolRuntime[SessionContext], start_t: float, end_t: float
) -> str:
    return extreme_value_in_range(runtime, start_t, end_t, find_max=True)


@tool(
    "min_value_in_range",
    description=("Same as max_value_in_range but returns the minimum value instead."),
)
def min_value_in_range(
    runtime: ToolRuntime[SessionContext], start_t: float, end_t: float
) -> str:
    return extreme_value_in_range(runtime, start_t, end_t, find_max=False)


@tool(
    "melting_point_analysis",
    description=(
        "Perform a melting point analysis on the currently selected DSC file. "
        "The melting point is found as the intersection of a baseline fitted to "
        "the plateau before the melting peak and a line fitted to the rapid "
        "decline into the peak. Returns the melting point temperature and heat "
        "flow, together with the temperature ranges used for the fits."
    ),
)
def melting_point_analysis(
    runtime: ToolRuntime[SessionContext], smoothing_window: int = 11
) -> str:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    # The analysis expects sorted 'Temperature' and 'HeatFlow' columns without gaps
    data = (
        df.rename(columns={"temperature_C": "Temperature", "heat_flow_mW": "HeatFlow"})
        .dropna(subset=["Temperature", "HeatFlow"])
        .sort_values("Temperature")
        .reset_index(drop=True)
    )

    try:
        result = find_melting_point(data, smoothing_window)
    except (ValueError, TypeError, IndexError, np.linalg.LinAlgError) as exc:
        return f"Melting point analysis failed for '{file_name}': {exc}"

    melting_t, melting_heat_flow = result["melting_point"]
    plateau_start, plateau_end = result["plateau_region"]
    decline_start, decline_end = result["decline_region"]
    temperature = data["Temperature"]

    return (
        f"Melting point of '{file_name}': {melting_t:.2f} °C "
        f"(heat flow {melting_heat_flow:.4f} mW). "
        f"Baseline fitted over {temperature[plateau_start]:.2f} to "
        f"{temperature[plateau_end]:.2f} °C, slope {result['baseline_fit'][0]:.4f} mW/°C. "
        f"Decline fitted over {temperature[decline_start]:.2f} to "
        f"{temperature[decline_end]:.2f} °C, slope {result['decline_fit'][0]:.4f} mW/°C."
    )


@tool(
    "glass_transition_analysis",
    description=(
        "Perform a glass transition analysis on the currently selected DSC file. "
        "The glass transition is located as the most pronounced step in heat flow "
        "with a width of 3 to 15 °C. Horizontal baselines are placed at the levels "
        "before and after the step, and a tangent is fitted at the inflection point. "
        "Returns the glass transition temperature Tg (midpoint between onset and "
        "endset), the onset, endset and inflection temperatures, and the baseline "
        "heat flow levels."
    ),
)
def glass_transition_analysis(runtime: ToolRuntime[SessionContext]) -> str:
    file_name = runtime.context.current_dsc_file
    if file_name is None:
        return "No DSC file is currently selected."
    file_path = runtime.context.dsc_file_path(file_name)

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_name}': {exc}"

    # The analysis expects data sorted by temperature without gaps
    data = df.dropna(subset=["temperature_C", "heat_flow_mW"]).sort_values(
        "temperature_C"
    )

    try:
        gt = find_glass_transition(
            data["temperature_C"].to_numpy(), data["heat_flow_mW"].to_numpy()
        )
    except (ValueError, TypeError, IndexError, np.linalg.LinAlgError) as exc:
        return f"Glass transition analysis failed for '{file_name}': {exc}"

    return (
        f"Glass transition of '{file_name}': Tg = {gt.tg:.2f} °C "
        f"(midpoint between onset and endset). "
        f"Onset {gt.t_onset:.2f} °C, endset {gt.t_endset:.2f} °C, "
        f"inflection point {gt.t_inflection:.2f} °C. "
        f"Pre-transition baseline {gt.hf_pre:.4f} mW (level at {gt.t_pre:.2f} °C), "
        f"post-transition baseline {gt.hf_post:.4f} mW (level at {gt.t_post:.2f} °C), "
        f"step height {gt.hf_pre - gt.hf_post:.4f} mW. "
        f"Tangent slope at inflection {gt.slope:.4f} mW/°C."
    )


TOOLS = [
    dsc_file_status,
    select_dsc_file,
    plot_dsc,
    get_heat_flow_at_temperature,
    max_value_in_range,
    min_value_in_range,
    melting_point_analysis,
    glass_transition_analysis,
    enthalpy_analysis,
]
