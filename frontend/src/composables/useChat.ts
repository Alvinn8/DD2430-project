// src/composables/useChat.ts
import { ref } from "vue";
import type { Message } from "../types/chat";

export function useChat() {
  const inputText = ref("");
  const isTyping = ref(false);
  const messages = ref<Message[]>([]);

  const sendMessage = async () => {
    const text = inputText.value.trim();
    if (!text || isTyping.value) return;

    // 1. Push user message
    const userMsg: Message = {
      id: Date.now(),
      text,
      sender: "user",
      timestamp: new Date(),
    };
    messages.value.push(userMsg);
    inputText.value = "";

    // 2. Show the animated typing dots while waiting for the server's first byte
    isTyping.value = true;

    const botMsgId = Date.now() + 1;
    let botMsgCreated = false;

    try {
      const response = await fetch("http://localhost:8000/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text }),
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

  const clearChat = () => {
    messages.value = [];
  };

  return {
    inputText,
    isTyping,
    messages,
    sendMessage,
    clearChat,
  };
}
