// src/composables/useChat.ts
import { onMounted, ref } from "vue";
import { DEFAULT_MODEL } from "../config";
import type { Message } from "../types/chat";

function randomSessionId() {
  return Math.random().toString(36).substring(2, 15);
}

export function useChat() {
  const inputText = ref("");
  const isTyping = ref(false);
  const messages = ref<Message[]>([]);
  const availableModels = ref<string[]>([DEFAULT_MODEL]);
  const selectedModel = ref(DEFAULT_MODEL);
  // Generate random session ID
  const sessionId = ref(randomSessionId());

  const loadModels = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/chat/models");
      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const payload = (await response.json()) as { models?: string[] };
      if (payload.models?.length) {
        availableModels.value = payload.models;
        if (!payload.models.includes(selectedModel.value)) {
          selectedModel.value = payload.models[0];
        }
      }
    } catch (error) {
      console.error("Model listing error:", error);
    }
  };

  const sendMessage = async (files: File[] = []) => {
    const text = inputText.value.trim();
    if ((!text && files.length === 0) || isTyping.value) return;

    const attachments = await Promise.all(
      files.map(async (file) => ({
        name: file.name,
        type: file.type,
        ...(file.type.startsWith("image/")
          ? { previewUrl: await readFileAsDataUrl(file) }
          : { contentUrl: await readFileAsDataUrl(file) }),
      })),
    );

    // 1. Push user message
    const userMsg: Message = {
      id: Date.now(),
      text,
      sender: "user",
      timestamp: new Date(),
      ...(attachments.length > 0 ? { attachments } : {}),
    };
    messages.value.push(userMsg);
    inputText.value = "";

    // 2. Show the animated typing dots while waiting for the server's first byte
    isTyping.value = true;

    const botMsgId = Date.now() + 1;
    let botMsgCreated = false;

    try {
      const body = new FormData();
      body.append("session_id", sessionId.value);
      body.append("prompt", text);
      body.append("model", selectedModel.value);
      for (const file of files) {
        body.append("file", file);
      }

      const response = await fetch("http://localhost:8000/api/chat/stream", {
        method: "POST",
        body,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        if (!botMsgCreated) {
          // 3. The first chunk arrived! Hide the animated dots.
          isTyping.value = false;

          // 4. Create the actual message bubble containing this first chunk
          messages.value.push({
            id: botMsgId,
            text: chunk,
            sender: "bot",
            timestamp: new Date(),
          });
          botMsgCreated = true;
        } else {
          // 5. Append subsequent chunks to the existing bubble
          const target = messages.value.find((m) => m.id === botMsgId);
          if (target) {
            target.text += chunk;
          }
        }
      }
    } catch (error) {
      console.error("Streaming error:", error);
      if (!botMsgCreated) {
        messages.value.push({
          id: botMsgId,
          text: "⚠️ Error communicating with the assistant.",
          sender: "bot",
          timestamp: new Date(),
        });
      } else {
        const target = messages.value.find((m) => m.id === botMsgId);
        if (target) target.text += "\n\n⚠️ Connection lost.";
      }
    } finally {
      isTyping.value = false;
    }
  };

  const readFileAsDataUrl = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });

  const clearChat = () => {
    messages.value = [];
    sessionId.value = randomSessionId();
  };

  onMounted(loadModels);

  return {
    inputText,
    isTyping,
    messages,
    availableModels,
    selectedModel,
    sendMessage,
    clearChat,
  };
}
