import base64
import io
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from langchain.tools import tool, ToolRuntime
from matplotlib.figure import Figure
from app.tools.DSCReader import (
    read_standardized_dsc_file,
    read_standardized_dsc_metadata,
)
from app.tools.MeltingPointAnalysis import find_melting_point


@dataclass
class SessionContext:
    """Per-session state, passed to every tool call. Changes made by tools persist."""

    session_id: str
    current_dsc_file: str | None = None
    dsc_files_available: list[str] = field(default_factory=list)


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
    file_path = runtime.context.current_dsc_file
    if file_path is None:
        return "No DSC file is currently selected."

    try:
        df = read_standardized_dsc_file(file_path)
        metadata = read_standardized_dsc_metadata(file_path)
    except (OSError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_path}': {exc}"

    # Plot with the object-oriented API, since pyplot is not thread-safe
    fig = Figure(figsize=(8, 5), dpi=100)
    ax = fig.add_subplot()
    ax.plot(df["temperature_C"], df["heat_flow_mW"], linewidth=1)
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Heat flow (mW)")
    ax.grid(True, alpha=0.3)
    if metadata:
        ax.set_title(
            f"{metadata['sample_name']} ({metadata['heating_rate_C_per_min']} °C/min)"
        )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")

    summary = (
        f"Plot of heat flow against temperature for '{file_path}'. "
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
    file_path = runtime.context.current_dsc_file
    if file_path is None:
        return "No DSC file is currently selected."

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_path}': {exc}"

    # Find the closest temperature in the DataFrame
    closest_idx = (df["temperature_C"] - temperature).abs().idxmin()
    closest_temp = df.loc[closest_idx, "temperature_C"]
    heat_flow = df.loc[closest_idx, "heat_flow_mW"]

    return (
        f"At {closest_temp:.2f} °C, the heat flow is {heat_flow:.4f} mW "
        f"in the DSC file '{file_path}'."
    )


def extreme_value_in_range(
    runtime: ToolRuntime[SessionContext], start_t: float, end_t: float, find_max: bool
) -> str:
    file_path = runtime.context.current_dsc_file
    if file_path is None:
        return "No DSC file is currently selected."

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_path}': {exc}"

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

    return f"{extreme_type} heat flow in the range [{start_t}, {end_t}] °C is {extreme_heat_flow:.4f} mW at {extreme_temp:.2f} °C."


@tool(
    "max_value_in_range",
    description=(
        "Get the maximum value in the range [start_t, end_t]. The interval is a range in temperature and the return value is a tuple of (t, y) where t is the temperature of the maximum and y is the maximum heat flow value itself."
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
    file_path = runtime.context.current_dsc_file
    if file_path is None:
        return "No DSC file is currently selected."

    try:
        df = read_standardized_dsc_file(file_path)
    except (OSError, pd.errors.ParserError) as exc:
        return f"Could not read DSC file '{file_path}': {exc}"

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
        return f"Melting point analysis failed for '{file_path}': {exc}"

    melting_t, melting_heat_flow = result["melting_point"]
    plateau_start, plateau_end = result["plateau_region"]
    decline_start, decline_end = result["decline_region"]
    temperature = data["Temperature"]

    return (
        f"Melting point of '{file_path}': {melting_t:.2f} °C "
        f"(heat flow {melting_heat_flow:.4f} mW). "
        f"Baseline fitted over {temperature[plateau_start]:.2f} to "
        f"{temperature[plateau_end]:.2f} °C, slope {result['baseline_fit'][0]:.4f} mW/°C. "
        f"Decline fitted over {temperature[decline_start]:.2f} to "
        f"{temperature[decline_end]:.2f} °C, slope {result['decline_fit'][0]:.4f} mW/°C."
    )


TOOLS = [
    dsc_file_status,
    select_dsc_file,
    plot_dsc,
    get_heat_flow_at_temperature,
    max_value_in_range,
    min_value_in_range,
    melting_point_analysis,
]
