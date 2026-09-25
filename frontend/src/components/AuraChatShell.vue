<script setup lang="ts">
import type { Message } from "../types/chat";

import AmbientBackground from "./AmbientBackground.vue";
import ChatComposer from "./ChatComposer.vue";
import ChatHeader from "./ChatHeader.vue";
import MessageList from "./MessageList.vue";

defineProps<{
  messages: Message[];
  inputText: string;
  isTyping: boolean;
}>();

const emit = defineEmits<{
  "update:inputText": [value: string];
  send: [];
  newChat: [];
}>();
</script>

<template>
  <!--
    fixed + inset-0 means this can NEVER create a page scrollbar.
  -->
  <div class="fixed inset-0 h-dvh w-full overflow-hidden">
    <!-- Background -->
    <AmbientBackground />

    <!-- Main application -->
    <main
      class="relative z-10 flex h-dvh w-full items-center justify-center overflow-hidden p-3 sm:p-6"
    >
      <!-- Glass window -->
      <section
        class="relative flex h-full max-h-[calc(100dvh-24px)] w-full max-w-[900px] flex-col overflow-hidden rounded-[36px] border border-white/60 bg-white/[0.42] shadow-[0_25px_80px_rgba(80,100,140,0.12)] backdrop-blur-[35px] ring-1 ring-inset ring-white/40 sm:max-h-[calc(100dvh-48px)]"
      >
        <!-- Main reflection -->
        <div
          class="pointer-events-none absolute -left-[20%] -top-[35%] h-[70%] w-[70%] rotate-[-20deg] rounded-full bg-white/20 blur-[45px]"
        />

        <!-- Lower refraction -->
        <div
          class="pointer-events-none absolute -bottom-[25%] -right-[15%] h-[45%] w-[45%] rounded-full bg-blue-200/10 blur-[70px]"
        />

        <!-- Glass edge -->
        <div
          class="pointer-events-none absolute inset-0 rounded-[36px] ring-1 ring-inset ring-white/25"
        />

        <!-- Content -->
        <div class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <ChatHeader @new-chat="emit('newChat')" />

          <!-- THE ONLY SCROLLABLE AREA -->
          <MessageList :messages="messages" :is-typing="isTyping" />

          <ChatComposer
            :model-value="inputText"
            :is-typing="isTyping"
            @update:model-value="emit('update:inputText', $event)"
            @send="emit('send')"
          />
        </div>
      </section>
    </main>
  </div>
</template>
