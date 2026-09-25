<script setup lang="ts">
import AuraChatShell from "../components/AuraChatShell.vue";
import { useChat } from "../composables/useChat";

const { inputText, isTyping, messages, sendMessage, clearChat } = useChat();
</script>

<template>
  <AuraChatShell
    :messages="messages"
    :input-text="inputText"
    :is-typing="isTyping"
    @update:input-text="inputText = $event"
    @send="sendMessage"
    @new-chat="clearChat"
  />
</template>
