# app/services/llm_service.py
import asyncio
import base64
import json
import tempfile
from os import path
from pathlib import Path
from typing import AsyncGenerator, List, Optional
import google.genai
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    AnyMessage,
)
from app.config import settings
from app.models import ImageInput
from app.services.llm_tools import TOOLS, SessionContext
from app.services.ingest import ingest_file, load_table
from app.services.session_runs import unique_local_name, write_session_files
from app.services.results_store import count_runs

basepath = path.dirname(__file__)
with open(
    path.join(basepath, "..", "..", "prompts", "main.md"), "r", encoding="utf-8"
) as f:
    SYSTEM_PROMPT = f.read()


class LLMService:
    def __init__(self):
        # Initializes using Application Default Credentials or GCP_PROJECT_ID.
        # LangChain has no API for listing models :(
        # Use Google GenAI directly
        self.client = google.genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
        )
        self._agents: dict[str, object] = {}
        self._sessions: dict[str, LLMSession] = {}

    def get_session(self, session_id: str) -> "LLMSession":
        """Return the session with the given id, creating it if it does not exist."""
        if session_id not in self._sessions:
            self._sessions[session_id] = LLMSession(self, session_id)
        return self._sessions[session_id]

    def get_agent(self, model: str):
        """Return a cached tool-calling agent for the given model name."""
        if model not in self._agents:
            chat_model = init_chat_model(
                model,
                model_provider="google_genai",
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_LOCATION,
            )
            self._agents[model] = create_agent(
                model=chat_model, tools=TOOLS, context_schema=SessionContext
            )
        return self._agents[model]

    async def list_models(self) -> list[str]:
        """Return model names available through the configured Vertex project."""
        loop = asyncio.get_running_loop()
        excluded_model_tokens = (
            "embedding",
            "segmentation",
            "tts",
            "live",
            "audio",
        )

        def get_models() -> list[str]:
            models: list[str] = []
            for model in self.client.models.list():
                if model.name is None:
                    continue

                model_name = model.name.lower()
                if any(token in model_name for token in excluded_model_tokens):
                    continue

                supported_actions = model.supported_actions or []
                if supported_actions:
                    if "generateContent" not in supported_actions:
                        continue

                models.append(model.name)

            return models

        return await loop.run_in_executor(None, get_models)


def _event(event_type: str, **fields) -> str:
    """Encode a stream event as one line of JSON."""
    return json.dumps({"type": event_type, **fields}) + "\n"


def _tool_result_event(message: ToolMessage) -> str:
    """Encode a tool result, splitting its content into text and images."""
    if isinstance(message.content, str):
        return _event(
            "tool_result", id=message.tool_call_id, text=message.content, images=[]
        )

    texts: list[str] = []
    images: list[str] = []
    for block in message.content:
        if isinstance(block, str):
            texts.append(block)
        elif block.get("type") == "text":
            texts.append(block["text"])
        elif block.get("type") == "image" and "base64" in block:
            images.append(f"data:{block['mime_type']};base64,{block['base64']}")
    return _event(
        "tool_result", id=message.tool_call_id, text="\n".join(texts), images=images
    )


class LLMSession:
    def __init__(self, service: LLMService, session_id: str):
        self._service = service
        self._upload_dir = Path(tempfile.mkdtemp(prefix="dd2430-session-"))
        # State that tools can read and update, such as the current DSC file
        self.context = SessionContext(
            session_id=session_id, upload_dir=self._upload_dir
        )
        self.messages: list[AnyMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        self._lock = asyncio.Lock()

    async def ingest_uploaded_file(
        self, db, filename: str, data: bytes, sidecar: bytes | None = None
    ) -> str:
        """Ingest through the shared path and expose the result to the tools. Returns the local name."""
        result = await ingest_file(db, data, filename, sidecar_bytes=sidecar)

        if result.already_existed:
            n = await count_runs(db, result.db_file.file_id)
            self.context.notices.append(
                f"'{filename}' was already uploaded on {result.db_file.created_at:%Y-%m-%d} "
                f"with {n} saved analysis run(s); the stored copy is used."
            )

        table = (
            result.table
            if result.table is not None
            else await load_table(result.db_file)
        )
        ctx = self.context
        local = next(
            (n for n, fid in ctx.file_ids.items() if fid == result.db_file.file_id),
            None,
        ) or unique_local_name(ctx.dsc_files_available, filename)
        write_session_files(
            self._upload_dir,
            local,
            table,
            result.metadata,
            result.unconfirmed,
            result.warnings,
        )
        ctx.file_ids[local] = result.db_file.file_id
        if local not in ctx.dsc_files_available:
            ctx.dsc_files_available.append(local)
        ctx.current_dsc_file = local
        return local

    def remove_uploaded_file(self, filename: str) -> None:
        name = Path(filename).name
        (self._upload_dir / name).unlink(missing_ok=True)
        (self._upload_dir / (name.removesuffix(".csv") + "_metadata.csv")).unlink(
            missing_ok=True
        )
        self.context.file_ids.pop(name, None)
        if name in self.context.dsc_files_available:
            self.context.dsc_files_available.remove(name)
        if self.context.current_dsc_file == name:
            self.context.current_dsc_file = None

    async def stream_chat_response(
        self,
        prompt: str,
        model: str | None = settings.DEFAULT_MODEL,
        images: Optional[List[ImageInput]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Sends a message and yields the response as lines of JSON, one per event:
        - {"type": "text", "text": ...}: a chunk of the model's reply
        - {"type": "tool_call", "id": ..., "name": ..., "args": {...}}: a tool is called
        - {"type": "tool_result", "id": ..., "text": ..., "images": [data URLs]}: its result
        """

        self.context.turn += 1

        content: list[str | dict] = [{"type": "text", "text": prompt}]

        if images:
            for img in images:
                content.append(
                    {
                        "type": "image",
                        "base64": base64.b64encode(img.data).decode("ascii"),
                        "mime_type": img.mime_type,
                    }
                )

        agent = self._service.get_agent(model if model else settings.DEFAULT_MODEL)

        async with self._lock:
            messages = [*self.messages, HumanMessage(content=content)]
            seen = len(messages)

            # "messages" streams model tokens, "values" gives the full state after each step
            async for mode, data in agent.astream(
                {"messages": messages},
                context=self.context,
                stream_mode=["messages", "values"],
            ):
                if mode == "messages":
                    chunk, _metadata = data
                    if isinstance(chunk, AIMessage) and chunk.text:
                        yield _event("text", text=chunk.text)
                else:
                    # Includes the new user message, tool calls, tool results and replies
                    messages = data["messages"]
                    for message in messages[seen:]:
                        if isinstance(message, AIMessage):
                            for call in message.tool_calls:
                                yield _event(
                                    "tool_call",
                                    id=call["id"],
                                    name=call["name"],
                                    args=call["args"],
                                )
                        elif isinstance(message, ToolMessage):
                            yield _tool_result_event(message)
                    seen = len(messages)

            self.messages = messages
