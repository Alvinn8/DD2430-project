<script setup lang="ts">
defineEmits<{
  newChat: [];
}>();
</script>

<template>
  <header class="relative shrink-0 px-5 pb-4 pt-5 sm:px-6">
    <div class="flex items-center justify-between">
      <!-- Left -->
      <div class="flex items-center gap-3">
        <!-- Liquid glass logo -->
        <div
          class="relative flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-[16px] border border-white/70 bg-white/40 shadow-[0_8px_25px_rgba(100,120,160,0.10)] backdrop-blur-xl"
        >
          <!-- Internal refraction -->
          <div
            class="absolute -left-2 -top-2 h-7 w-7 rounded-full bg-blue-200/60 blur-md"
          />

          <div
            class="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-purple-200/50 blur-md"
          />

          <!-- Core -->
          <div
            class="relative h-3 w-3 rounded-full bg-gradient-to-br from-[#8FB4FF] to-[#B1A2F5] shadow-[0_0_14px_rgba(120,150,255,0.35)]"
          />
        </div>

        <!-- Text -->
        <div>
          <h1 class="text-[15px] font-medium tracking-tight text-[#293246]">
            Aura
          </h1>

          <p class="mt-0.5 text-[11px] text-[#8791A5]">
            Your intelligent analysis assistant
          </p>
        </div>
      </div>

      <!-- New chat -->
      <button
        type="button"
        aria-label="New conversation"
        class="group flex h-9 w-9 items-center justify-center rounded-full border border-white/70 bg-white/35 text-[#7B869A] shadow-[0_5px_15px_rgba(100,120,160,0.08)] backdrop-blur-xl transition-all duration-300 hover:-translate-y-0.5 hover:bg-white/55 hover:text-[#4D5870] active:translate-y-0"
        @click="$emit('newChat')"
      >
        <svg
          viewBox="0 0 24 24"
          class="h-4 w-4 transition-transform duration-300 group-hover:rotate-90"
          fill="none"
        >
          <path
            d="M12 5v14M5 12h14"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>
  </header>
</template>
