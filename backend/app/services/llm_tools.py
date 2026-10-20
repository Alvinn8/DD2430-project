from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime


@dataclass
class SessionContext:
    """Per-session state, passed to every tool call. Changes made by tools persist."""

    session_id: str
    current_dsc_file: str | None = None


@tool(
    "example_tool",
    description="Example tool function that gives session information.",
)
def example_tool(runtime: ToolRuntime[SessionContext]) -> str:
    context = runtime.context
    return f"Session ID: {context.session_id}, Current DSC File: {context.current_dsc_file}"


TOOLS = [example_tool]
