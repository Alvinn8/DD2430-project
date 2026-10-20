import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from app.models import ChatRequest, ImageInput
from app.config import settings
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/chat", tags=["Chat"])
llm_service = LLMService()

SUPPORTED_INLINE_MIME_TYPES = {
    "application/pdf",
    "application/json",
    "text/csv",
    "text/plain",
}


def is_supported_inline_file(mime_type: str) -> bool:
    return mime_type.startswith("image/") or mime_type in SUPPORTED_INLINE_MIME_TYPES


@router.get("/models")
async def list_models() -> dict[str, list[str]]:
    """List models available through the configured LLM provider."""
    try:
        return {"models": await llm_service.list_models()}
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Unable to list available models: {exc}"
        ) from exc


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
            raise HTTPException(status_code=400, detail="Invalid chat request.") from exc
        session_id = payload.session_id
        prompt = payload.prompt
        model = payload.model

    if not session_id:
        raise HTTPException(status_code=400, detail="Session id is required.")

    if not prompt.strip() and not files:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        images = None
        if files:
            images = []
            for file in files:
                if not file.content_type:
                    raise HTTPException(
                        status_code=400, detail="Attached file has no MIME type."
                    )
                if not is_supported_inline_file(file.content_type):
                    raise HTTPException(
                        status_code=415,
                        detail=(
                            f"Attached file type '{file.content_type}' is not supported. "
                            "Use an image, PDF, CSV, JSON, or plain-text file."
                        ),
                    )
                images.append(
                    ImageInput(data=await file.read(), mime_type=file.content_type)
                )

        return StreamingResponse(
            llm_service.get_session(session_id).stream_chat_response(
                prompt=prompt or "Please analyze the attached file.",
                model=model,
                images=images,
            ),
            media_type="text/plain",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing Error: {str(e)}")
