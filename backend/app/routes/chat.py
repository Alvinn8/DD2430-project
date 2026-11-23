import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from app.models import ChatRequest, ImageInput
from app.config import settings
from app.services.llm_service import LLMService, LLMSession
from app.db.session import get_db
from app.services.ingest import (
    UnsupportedFileError,
    is_dsc_candidate,
    is_sidecar,
    pair_sidecars,
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])
llm_service = LLMService()


def should_send_to_llm_context(mime_type: str) -> bool:
    """Whether a file is sent to the model directly, rather than only through the tools."""
    # The important this here is that raw CSV data files should NOT be sent to
    # the model. This will use a ton of tokens and is not useful.
    return mime_type.startswith("image/") or mime_type == "application/pdf"


async def save_uploads(
    session: LLMSession, files: list[UploadFile]
) -> list[ImageInput] | None:
    if not files:
        return None
    images: list[ImageInput] = []
    data_files: list[tuple[str, bytes]] = []
    for file in files:
        data = await file.read()
        name = file.filename or "uploaded-file"
        mime = file.content_type or ""
        if should_send_to_llm_context(mime):
            images.append(ImageInput(data=data, mime_type=mime))
        elif is_dsc_candidate(name) or is_sidecar(name):
            data_files.append((name, data))

    groups = pair_sidecars(data_files)
    if groups:
        async for db in get_db():
            for name, data, sidecar in groups:
                try:
                    await session.ingest_uploaded_file(db, name, data, sidecar)
                except UnsupportedFileError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
    return images


@router.get("/models")
async def list_models() -> dict[str, list[str]]:
    """List models available through the configured LLM provider."""
    try:
        return {"models": await llm_service.list_models()}
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Unable to list available models: {exc}"
        ) from exc


@router.delete("/{session_id}/files")
async def remove_session_file(session_id: str, filename: str) -> dict[str, str]:
    """Remove an uploaded file from a chat session's analysis context."""
    if not filename.strip():
        raise HTTPException(status_code=400, detail="Filename is required.")

    llm_service.get_session(session_id).remove_uploaded_file(filename)
    return {"status": "removed"}


@router.post("/stream")
async def stream_chat(request: Request):
    """
    Streams LLM text response chunks in real-time.
    """
    content_type = request.headers.get("content-type", "")
    files: list[UploadFile] = []

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        session_id = str(form.get("session_id", ""))
        prompt = str(form.get("prompt", ""))
        files = [
            form_file
            for form_file in form.getlist("file")
            if isinstance(form_file, UploadFile)
        ]
        model_value = form.get("model")
        model = str(model_value) if model_value else settings.DEFAULT_MODEL
    else:
        try:
            payload = ChatRequest.model_validate(await request.json())
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="Invalid chat request."
            ) from exc
        session_id = payload.session_id
        prompt = payload.prompt
        model = payload.model

    if not session_id:
        raise HTTPException(status_code=400, detail="Session id is required.")

    if not prompt.strip() and not files:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        images = await save_uploads(llm_service.get_session(session_id), files)

        return StreamingResponse(
            llm_service.get_session(session_id).stream_chat_response(
                prompt=prompt or "Please analyze the attached file.",
                model=model,
                images=images,
            ),
            media_type="application/x-ndjson",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing Error: {str(e)}")
