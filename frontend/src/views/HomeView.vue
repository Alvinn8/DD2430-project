<script setup lang="ts">
import AuraChatShell from "../components/AuraChatShell.vue";
import { useChat } from "../composables/useChat";

const {
  inputText,
  isTyping,
  messages,
  tokenUsage,
  availableModels,
  selectedModel,
  exothermicDirection,
  sessionId,
  sendMessage,
  clearChat,
} = useChat();
</script>

<template>
  <AuraChatShell
    :messages="messages"
    :token-usage="tokenUsage"
    :input-text="inputText"
    :is-typing="isTyping"
    :available-models="availableModels"
    :selected-model="selectedModel"
    :exothermic-direction="exothermicDirection"
    :session-id="sessionId"
    @update:input-text="inputText = $event"
    @update:selected-model="selectedModel = $event"
    @update:exothermic-direction="exothermicDirection = $event"
    @send="sendMessage"
    @new-chat="clearChat"
  />
</template>
