# app/services/llm_service.py
import asyncio
from typing import AsyncGenerator, List, Optional
import google.genai
import google.genai.types
from app.config import settings
from app.models import ImageInput


class LLMService:
    def __init__(self):
        # Initializes using Application Default Credentials or GCP_PROJECT_ID
        self.client = google.genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
        )

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

    async def stream_chat_response(
        self,
        prompt: str,
        model: str | None = settings.DEFAULT_MODEL,
        images: Optional[List[ImageInput]] = None,
    ) -> AsyncGenerator[str, None]:
        """Sends a message and yields streaming response chunks asynchronously."""

        contents: list[str | google.genai.types.Part] = [prompt]

        if images:
            for img in images:
                contents.append(
                    google.genai.types.Part.from_bytes(
                        data=img.data, mime_type=img.mime_type
                    )
                )

        # Execute blocking SDK calls in an async thread pool
        loop = asyncio.get_running_loop()

        def get_stream():
            chat = self.client.chats.create(
                model=model if model else settings.DEFAULT_MODEL
            )
            return chat.send_message_stream(contents)

        stream = await loop.run_in_executor(None, get_stream)

        for chunk in stream:
            if chunk.text:
                yield chunk.text
                await asyncio.sleep(0)  # Yield execution back to event loop
