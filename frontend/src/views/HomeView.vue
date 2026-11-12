<script setup lang="ts">
import AuraChatShell from "../components/AuraChatShell.vue";
import { useChat } from "../composables/useChat";

const {
  inputText,
  isTyping,
  messages,
  availableModels,
  selectedModel,
  sessionId,
  sendMessage,
  clearChat,
} = useChat();
</script>

<template>
  <AuraChatShell
    :messages="messages"
    :input-text="inputText"
    :is-typing="isTyping"
    :available-models="availableModels"
    :selected-model="selectedModel"
    :session-id="sessionId"
    @update:input-text="inputText = $event"
    @update:selected-model="selectedModel = $event"
    @send="sendMessage"
    @new-chat="clearChat"
  />
</template>
