from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/chat", tags=["Chat"])
llm_service = LLMService()


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Streams LLM text response chunks in real-time.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        return StreamingResponse(
            llm_service.stream_chat_response(
                prompt=request.prompt, model=request.model
            ),
            media_type="text/plain",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing Error: {str(e)}")
