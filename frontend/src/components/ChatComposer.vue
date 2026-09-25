<script setup lang="ts">
import { computed, nextTick, ref } from "vue";

const props = defineProps<{
  modelValue: string;
  isTyping: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  send: [];
}>();

const textarea = ref<HTMLTextAreaElement | null>(null);

const canSend = computed(
  () => props.modelValue.trim().length > 0 && !props.isTyping,
);

const updateValue = (event: Event) => {
  const target = event.target as HTMLTextAreaElement;

  emit("update:modelValue", target.value);

  target.style.height = "auto";
  target.style.height = `${Math.min(target.scrollHeight, 140)}px`;
};

const send = () => {
  if (!canSend.value) {
    return;
  }

  emit("send");

  nextTick(() => {
    if (textarea.value) {
      textarea.value.style.height = "auto";
    }
  });
};

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    send();
  }
};
</script>

<template>
  <div class="relative shrink-0 px-4 pb-4 pt-3 sm:px-5">
    <!-- Input glass -->
    <div
      class="relative overflow-hidden rounded-[24px] border border-white/75 bg-white/[0.48] shadow-[0_10px_30px_rgba(80,100,140,0.10)] backdrop-blur-2xl transition-all duration-300 focus-within:border-blue-200/80 focus-within:bg-white/[0.58] focus-within:shadow-[0_12px_35px_rgba(90,120,180,0.12)]"
    >
      <!-- Top reflection -->
      <div
        class="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/90 to-transparent"
      />

      <!-- Little refraction -->
      <div
        class="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full bg-blue-100/20 blur-2xl"
      />

      <!-- Text -->
      <textarea
        ref="textarea"
        :value="modelValue"
        rows="1"
        maxlength="4000"
        placeholder="Ask Aura something..."
        class="relative block max-h-[140px] min-h-[48px] w-full resize-none bg-transparent px-4 pb-14 pt-3 text-[13px] leading-6 text-[#43516B] outline-none placeholder:text-[#9DA6B6]"
        @input="updateValue"
        @keydown="onKeydown"
      />

      <!-- Controls -->
      <div
        class="absolute inset-x-3 bottom-2.5 flex items-center justify-between"
      >
        <!-- Counter -->
        <div class="flex items-center gap-3 px-2">
          <span
            class="hidden text-[9px] font-medium tracking-[0.04em] text-[#A1A9B8] sm:block"
          >
            Enter to send
          </span>

          <span class="hidden h-3 w-px bg-[#CBD2DE] sm:block" />

          <span class="text-[9px] tabular-nums text-[#B0B7C5]">
            {{ modelValue.length }}/4000
          </span>
        </div>

        <!-- Send button -->
        <button
          type="button"
          aria-label="Send message"
          :disabled="!canSend"
          class="group flex h-10 w-10 items-center justify-center rounded-full border border-white/60 transition-all duration-300"
          :class="
            canSend
              ? [
                  'bg-gradient-to-br from-[#AFC8FF]/80 to-[#B9AAFF]/75',
                  'text-white',
                  'shadow-[0_6px_18px_rgba(110,140,220,0.22)]',
                  'hover:scale-[1.04]',
                  'hover:shadow-[0_8px_24px_rgba(110,140,220,0.30)]',
                  'active:scale-95',
                ]
              : ['cursor-not-allowed', 'bg-white/30', 'text-[#B7BFCC]']
          "
          @click="send"
        >
          <svg
            viewBox="0 0 24 24"
            class="h-[17px] w-[17px] transition-transform duration-200"
            :class="
              canSend
                ? 'group-hover:-translate-y-0.5 group-hover:translate-x-0.5'
                : ''
            "
            fill="none"
          >
            <path
              d="M4 12L20 4L14 20L11 13L4 12Z"
              stroke="currentColor"
              stroke-width="1.35"
              stroke-linejoin="round"
            />

            <path
              d="M11 13L20 4"
              stroke="currentColor"
              stroke-width="1.35"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Disclaimer -->
    <div
      class="mt-2.5 flex items-center justify-center px-2 text-center text-[9px] leading-4 text-[#AAB2C0]"
    >
      Aura can make mistakes. Verify important scientific information.
    </div>
  </div>
</template>
