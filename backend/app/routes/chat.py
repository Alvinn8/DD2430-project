import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from app.models import ChatRequest, ImageInput
from app.config import settings
from app.services.llm_service import LLMService, LLMSession

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
    """
    Save uploaded files for the tools. Returns the files to send to the model inline,
    and the names of the data files that the model reaches through the tools instead.
    """
    if not files:
        return None
    images: list[ImageInput] = []
    for file in files:
        if not file.content_type:
            raise HTTPException(
                status_code=400, detail="Attached file has no MIME type."
            )
        file_data = await file.read()
        if file.content_type == "text/csv":
            session.register_uploaded_file(file.filename or "uploaded-file", file_data)
        if should_send_to_llm_context(file.content_type):
            images.append(ImageInput(data=file_data, mime_type=file.content_type))
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
        files = [
            form_file
            for form_file in form.getlist("file")
            if isinstance(form_file, UploadFile)
        ]
        try:
            payload = ChatRequest.model_validate(
                {
                    "session_id": form.get("session_id", ""),
                    "prompt": form.get("prompt", ""),
                    "model": form.get("model") or settings.DEFAULT_MODEL,
                    "exothermic_direction": form.get("exothermic_direction", "unknown"),
                }
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid chat request."
            ) from exc
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
                exothermic_direction=payload.exothermic_direction,
            ),
            media_type="application/x-ndjson",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing Error: {str(e)}")
