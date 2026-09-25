import { nextTick, ref } from "vue";
import type { Message } from "../types/chat";

export function useChat() {
  const inputText = ref("");
  const isTyping = ref(false);

  const messages = ref<Message[]>([
    {
      id: 1,
      text: "Hello. I'm Aura, your scientific analysis assistant. How can I help?",
      sender: "bot",
      timestamp: new Date(),
    },
  ]);

  const generateResponse = (input: string): string => {
    return `I received your request:

"${input}"

This is a simulated response from the analysis layer. In the real application, this would be connected to your backend or LLM service.`;
  };

  const sendMessage = async () => {
    const text = inputText.value.trim();

    if (!text || isTyping.value) {
      return;
    }

    messages.value.push({
      id: Date.now(),
      text,
      sender: "user",
      timestamp: new Date(),
    });

    inputText.value = "";
    isTyping.value = true;

    await nextTick();

    window.setTimeout(() => {
      messages.value.push({
        id: Date.now(),
        text: generateResponse(text),
        sender: "bot",
        timestamp: new Date(),
      });

      isTyping.value = false;
    }, 1200);
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
