import base64
import io
from dataclasses import dataclass, field
import pandas as pd
from langchain.tools import tool, ToolRuntime
from matplotlib.figure import Figure
from app.tools.DSCReader import (
    read_standardized_dsc_file,
    read_standardized_dsc_metadata,
)


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


TOOLS = [dsc_file_status, select_dsc_file, plot_dsc]
