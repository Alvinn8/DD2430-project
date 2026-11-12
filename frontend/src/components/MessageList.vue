<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import type { Message } from "../types/chat";
import MessageBubble from "./MessageBubble.vue";

const props = defineProps<{
  messages: Message[];
  isTyping: boolean;
}>();

const container = ref<HTMLElement | null>(null);

const scrollToBottom = async () => {
  await nextTick();

  if (!container.value) {
    return;
  }

  container.value.scrollTo({
    top: container.value.scrollHeight,
    behavior: "smooth",
  });
};

watch(() => [props.messages.length, props.isTyping], scrollToBottom);

onMounted(scrollToBottom);
</script>

<template>
  <section class="relative min-h-0 flex-1 overflow-hidden">
    <!-- Top fade -->
    <div
      class="pointer-events-none absolute inset-x-0 top-0 z-10 h-10 bg-gradient-to-b from-white/15 to-transparent"
    />

    <!--
      ONLY THIS ELEMENT SCROLLS.
      overflow-hidden on all parent elements prevents
      the browser/page from getting its own scrollbar.
    -->
    <div
      ref="container"
      class="chat-scroll-area h-full min-h-0 overflow-x-hidden overflow-y-auto px-4 py-6 sm:px-7 sm:py-8"
    >
      <!-- Conversation label -->
      <div class="mb-8 flex items-center justify-center gap-3">
        <span class="h-px w-8 bg-white/50" />

        <span
          class="text-[9px] font-medium uppercase tracking-[0.18em] text-[#A0A8B8]"
        >
          Conversation
        </span>

        <span class="h-px w-8 bg-white/50" />
      </div>

      <!-- Messages -->
      <TransitionGroup name="message" tag="div" class="flex flex-col space-y-5">
        <MessageBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
        />
      </TransitionGroup>

      <!-- Typing -->
      <Transition name="typing">
        <div v-if="isTyping" class="mt-5 flex items-center gap-3">
          <div
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px] border border-white/70 bg-white/35 shadow-[0_5px_15px_rgba(100,120,160,0.06)] backdrop-blur-xl"
          >
            <div
              class="h-2.5 w-2.5 animate-pulse rounded-full bg-gradient-to-br from-[#98B7FF] to-[#B5A8F5]"
            />
          </div>

          <div
            class="flex items-center gap-1 rounded-[18px] rounded-bl-[7px] border border-white/65 bg-white/38 px-4 py-3 backdrop-blur-xl shadow-[0_8px_25px_rgba(90,110,145,0.06)]"
          >
            <span
              class="h-1.5 w-1.5 animate-bounce rounded-full bg-[#A6B0C3] [animation-delay:-300ms]"
            />

            <span
              class="h-1.5 w-1.5 animate-bounce rounded-full bg-[#A6B0C3] [animation-delay:-150ms]"
            />

            <span
              class="h-1.5 w-1.5 animate-bounce rounded-full bg-[#A6B0C3]"
            />
          </div>
        </div>
      </Transition>
    </div>
  </section>
</template>

<style scoped>
/* These are only animation definitions.
   All visual styling remains Tailwind. */

.message-enter-active,
.message-leave-active {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}

.message-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.985);
}

.message-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.typing-enter-active,
.typing-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.typing-enter-from,
.typing-leave-to {
  opacity: 0;
  transform: translateY(5px);
}

.chat-scroll-area {
  scrollbar-width: thin;
  scrollbar-color: rgba(142, 164, 207, 0.55) transparent;
  scrollbar-gutter: stable;
}

.chat-scroll-area::-webkit-scrollbar {
  width: 10px;
}

.chat-scroll-area::-webkit-scrollbar-track {
  margin: 18px 0;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 0 10px rgba(130, 150, 190, 0.06);
}

.chat-scroll-area::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    rgba(186, 205, 244, 0.9),
    rgba(130, 157, 209, 0.7)
  );
  background-clip: padding-box;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.42),
    0 2px 8px rgba(87, 112, 167, 0.18);
}

.chat-scroll-area::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(
    180deg,
    rgba(170, 194, 239, 0.98),
    rgba(111, 142, 201, 0.86)
  );
  background-clip: padding-box;
}
</style>
