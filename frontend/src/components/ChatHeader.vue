<script setup lang="ts">
import { ref } from "vue";
import { APP_NAME } from "../config";

defineProps<{
  availableModels: string[];
  selectedModel: string;
}>();

const emit = defineEmits<{
  "update:selectedModel": [value: string];
  newChat: [];
}>();

const isModelMenuOpen = ref(false);

const selectModel = (model: string) => {
  emit("update:selectedModel", model);
  isModelMenuOpen.value = false;
};

const modelLabel = (model: string) => model.split("/").pop() ?? model;
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
            {{ APP_NAME }}
          </h1>

          <p class="mt-0.5 text-[11px] text-[#8791A5]">
            Your intelligent analysis assistant
          </p>
          <div class="relative mt-2">
            <button
              type="button"
              aria-haspopup="listbox"
              :aria-expanded="isModelMenuOpen"
              class="flex max-w-[230px] cursor-pointer items-center gap-1.5 rounded-xl border border-white/65 bg-white/35 px-2 py-1 shadow-[0_4px_12px_rgba(100,120,160,0.06)] transition-all hover:bg-white/60"
              @click="isModelMenuOpen = !isModelMenuOpen"
            >
            <svg
              viewBox="0 0 24 24"
              class="h-3 w-3 text-[#91A6D7]"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3Z"
                stroke="currentColor"
                stroke-linejoin="round"
                stroke-width="1.25"
              />
            </svg>
            <span class="text-[9px] uppercase tracking-[0.12em] text-[#9AA5B8]">
              Model
            </span>
            <span class="max-w-[155px] truncate text-[10px] font-medium text-[#687895]">
              {{ modelLabel(selectedModel) }}
            </span>
            <svg viewBox="0 0 24 24" class="h-3 w-3 text-[#8D9AB3]" fill="none">
              <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-linecap="round" stroke-width="1.5" />
            </svg>
            </button>

            <Transition name="model-menu">
              <div
                v-if="isModelMenuOpen"
                class="absolute left-0 top-full z-30 mt-2 min-w-[230px] overflow-hidden rounded-2xl border border-white/75 bg-[#F8FAFF]/90 p-1.5 shadow-[0_14px_35px_rgba(80,100,140,0.18)] backdrop-blur-2xl"
                role="listbox"
              >
                <button
                  v-for="model in availableModels"
                  :key="model"
                  type="button"
                  role="option"
                  :aria-selected="model === selectedModel"
                  class="flex w-full cursor-pointer items-center justify-between rounded-xl px-3 py-2 text-left text-[10px] transition-colors hover:bg-white/80"
                  :class="model === selectedModel ? 'bg-white/70 text-[#536FAF]' : 'text-[#687895]'"
                  @click="selectModel(model)"
                >
                  <span class="truncate">{{ modelLabel(model) }}</span>
                  <span v-if="model === selectedModel" class="ml-3 text-[#91A6D7]">✓</span>
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>

      <!-- New chat -->
      <button
        type="button"
        aria-label="New conversation"
        class="group flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-white/70 bg-white/35 text-[#7B869A] shadow-[0_5px_15px_rgba(100,120,160,0.08)] backdrop-blur-xl transition-all duration-300 hover:-translate-y-0.5 hover:bg-white/55 hover:text-[#4D5870] active:translate-y-0"
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
