<script setup lang="ts">
import { ref } from "vue";

defineProps<{
  files: File[];
  isTyping: boolean;
}>();

const emit = defineEmits<{
  addFiles: [files: File[]];
  removeFile: [index: number];
  openSettings: [];
}>();

const fileInput = ref<HTMLInputElement | null>(null);

const openFilePicker = () => {
  fileInput.value?.click();
};

const selectFiles = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files?.length) {
    emit("addFiles", Array.from(target.files));
  }
  target.value = "";
};
</script>

<template>
  <aside
    class="flex w-full shrink-0 flex-col border-t border-white/50 bg-white/[0.18] p-4 backdrop-blur-xl sm:p-5 lg:w-[260px] lg:border-l lg:border-t-0"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#8492AD]">
          Analysis
        </p>
        <h2 class="mt-1 text-[14px] font-medium text-[#3D4962]">
          Workspace
        </h2>
      </div>
      <div class="analysis-folder-icon rounded-xl bg-blue-100/40 p-2 text-[#7893CC]">
        <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" aria-hidden="true">
          <path
            d="M4 5.5A1.5 1.5 0 0 1 5.5 4h5l1.5 2h6.5A1.5 1.5 0 0 1 20 7.5v11a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13Z"
            stroke="currentColor"
            stroke-width="1.4"
          />
        </svg>
      </div>
    </div>

    <button
      type="button"
      :disabled="isTyping"
      class="import-file-button mt-5 flex w-full cursor-pointer items-center justify-center gap-2 rounded-2xl border border-white/75 bg-white/45 px-3 py-3 text-[11px] font-medium text-[#6378A5] shadow-[0_6px_18px_rgba(80,100,140,0.08)] transition hover:bg-white/70 disabled:cursor-not-allowed disabled:opacity-50"
      @click="openFilePicker"
    >
      <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" aria-hidden="true">
        <path
          d="M12 5v14M5 12h14"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-width="1.6"
        />
      </svg>
      Import file for analysis
    </button>
    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".csv,.json,.txt,.pdf,text/csv,application/json,text/plain,application/pdf"
      class="hidden"
      @change="selectFiles"
    >

    <div class="mt-5 min-h-0 flex-1">
      <p class="text-[10px] font-medium uppercase tracking-[0.12em] text-[#9AA5B8]">
        Imported files
      </p>
      <p v-if="files.length === 0" class="mt-3 text-[11px] leading-5 text-[#8C98AD]">
        Choose a file here and it will be attached to your next message.
      </p>
      <ul v-else class="mt-3 space-y-2">
        <li
          v-for="(file, index) in files"
          :key="`${file.name}-${file.lastModified}-${index}`"
          class="flex items-center gap-2 rounded-xl border border-white/60 bg-white/35 px-2.5 py-2"
        >
          <span class="min-w-0 flex-1 truncate text-[11px] text-[#596985]">
            {{ file.name }}
          </span>
          <button
            type="button"
            :aria-label="`Remove ${file.name}`"
            class="flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center rounded-full text-sm text-[#8492AD] hover:bg-white/70 hover:text-[#596985]"
            @click="emit('removeFile', index)"
          >
            ×
          </button>
        </li>
      </ul>
    </div>

    <button
      type="button"
      class="mt-5 flex w-full cursor-pointer items-center gap-2 rounded-2xl border border-white/50 bg-white/20 px-3 py-3 text-left text-[11px] text-[#7F8CA4] transition hover:bg-white/45"
      @click="emit('openSettings')"
    >
      <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" aria-hidden="true">
        <path
          d="M12 3.5a2 2 0 0 1 2 2v.4a6.8 6.8 0 0 1 1.7 1l.35-.2a2 2 0 1 1 2 3.46l-.35.2a6.8 6.8 0 0 1 0 2l.35.2a2 2 0 1 1-2 3.46l-.35-.2a6.8 6.8 0 0 1-1.7 1v.4a2 2 0 1 1-4 0v-.4a6.8 6.8 0 0 1-1.7-1l-.35.2a2 2 0 1 1-2-3.46l.35-.2a6.8 6.8 0 0 1 0-2l-.35-.2a2 2 0 1 1 2-3.46l.35.2a6.8 6.8 0 0 1 1.7-1v-.4a2 2 0 0 1 2-2Z"
          stroke="currentColor"
          stroke-width="1.2"
        />
        <circle cx="12" cy="12" r="2.5" stroke="currentColor" stroke-width="1.2" />
      </svg>
      Settings
    </button>
  </aside>
</template>
