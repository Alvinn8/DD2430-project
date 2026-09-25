<script setup lang="ts">
import { computed } from "vue";
import type { Message } from "../types/chat";

const props = defineProps<{
  message: Message;
}>();

const time = computed(() =>
  props.message.timestamp.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  }),
);
</script>

<template>
  <div
    class="flex w-full gap-3"
    :class="message.sender === 'user' ? 'justify-end' : 'justify-start'"
  >
    <!-- Assistant icon -->
    <div
      v-if="message.sender === 'bot'"
      class="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px] border border-white/70 bg-white/35 shadow-[0_5px_15px_rgba(100,120,160,0.06)] backdrop-blur-xl"
    >
      <div
        class="h-2.5 w-2.5 rounded-full bg-gradient-to-br from-[#98B7FF] to-[#B5A8F5] shadow-[0_0_8px_rgba(130,150,230,0.25)]"
      />
    </div>

    <!-- Message + time -->
    <div
      class="max-w-[82%] sm:max-w-[75%]"
      :class="message.sender === 'user' ? 'items-end' : 'items-start'"
    >
      <!-- Bubble -->
      <div
        class="relative overflow-hidden rounded-[20px] border px-4 py-3 text-[13px] leading-[1.65] tracking-[-0.005em] backdrop-blur-xl shadow-[0_8px_25px_rgba(90,110,145,0.06)]"
        :class="
          message.sender === 'user'
            ? [
                'rounded-br-[7px]',
                'border-blue-200/60',
                'bg-[#E7EEFF]/55',
                'text-[#43516B]',
                'shadow-[0_8px_25px_rgba(100,130,180,0.07)]',
              ]
            : [
                'rounded-bl-[7px]',
                'border-white/65',
                'bg-white/38',
                'text-[#4D586B]',
              ]
        "
      >
        <!-- Top glass reflection -->
        <div
          class="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/80 to-transparent"
        />

        <!-- Internal light -->
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-16 w-16 rounded-full bg-white/20 blur-xl"
        />

        <p class="relative whitespace-pre-wrap">
          {{ message.text }}
        </p>
      </div>

      <!-- Time -->
      <div
        class="mt-1.5 px-1 text-[9px] font-medium tracking-[0.10em] text-[#A1A9B8]"
        :class="message.sender === 'user' ? 'text-right' : 'text-left'"
      >
        {{ time }}
      </div>
    </div>
  </div>
</template>
