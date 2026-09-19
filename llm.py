from collections.abc import Generator
from dataclasses import dataclass
import mimetypes
import google.genai
import google.genai.chats
import google.genai.types

@dataclass
class Image:
    data: bytes
    mime_type: str

    @staticmethod
    def from_file(path: str) -> "Image":
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None:
            raise ValueError(f"Could not guess mime type for {path}")
        with open(path, "rb") as f:
            return Image(f.read(), mime_type)

class LLMProvider:
    def list_models(self) -> list[str]:
        raise NotImplementedError("Abstract method.")
    def new_chat(self, model: str) -> LLMChat:
        raise NotImplementedError("Abstract method.")

class LLMChat:
    def send(self, prompt: str, images: list[Image] | None = None) -> Generator[str]:
        raise NotImplementedError("Abstract method.")

# Google Cloud

class GoogleCloudProvider(LLMProvider):
    # TODO have a way to choose the location, since we might need EU location?
    def __init__(self, project: str, location: str = "global"):
        # Application Default Credentials:
        # file referenced by the GOOGLE_APPLICATION_CREDENTIALS env var.
        # TODO instead store this and project ID so the user does not have
        # to set the env var themselves or enter the project ID each time.
        self.client = google.genai.Client(vertexai=True, project=project, location=location)

    def list_models(self) -> list[str]:
        return list(model.name for model in self.client.models.list() if model.name is not None)

    def new_chat(self, model: str) -> LLMChat:
        chat = self.client.chats.create(model=model)
        return GoogleCloudChat(chat)

class GoogleCloudChat(LLMChat):
    def __init__(self, chat: google.genai.chats.Chat):
        self.chat = chat

    def send(self, prompt: str, images: list[Image] | None = None) -> Generator[str]:
        message: list[str | google.genai.types.Part] = [prompt]
        for image in images or []:
            message.append(google.genai.types.Part.from_bytes(data=image.data, mime_type=image.mime_type))
        stream = self.chat.send_message_stream(message)
        return (chunk.text for chunk in stream if chunk.text is not None)