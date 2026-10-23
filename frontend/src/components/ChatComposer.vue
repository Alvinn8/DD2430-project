<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { APP_NAME } from "../config";

const props = defineProps<{
  modelValue: string;
  isTyping: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  send: [files: File[]];
}>();

const textarea = ref<HTMLTextAreaElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const previewUrls = ref<string[]>([]);
const dragDepth = ref(0);
const isDraggingFiles = computed(() => dragDepth.value > 0 && !props.isTyping);
const hasFiles = computed(() => selectedFiles.value.length > 0);

const canSend = computed(
  () =>
    (props.modelValue.trim().length > 0 || hasFiles.value) &&
    !props.isTyping,
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

  emit("send", [...selectedFiles.value]);
  selectedFiles.value = [];

  nextTick(() => {
    if (textarea.value) {
      textarea.value.style.height = "auto";
    }
  });
};

const openFilePicker = () => {
  fileInput.value?.click();
};

const addFiles = (files: FileList | File[]) => {
  selectedFiles.value = [
    ...selectedFiles.value,
    ...Array.from(files),
  ];
};

const selectFile = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    addFiles(target.files);
  }
  target.value = "";
};

const hasDraggedFiles = (event: DragEvent) =>
  Array.from(event.dataTransfer?.types ?? []).includes("Files");

const onDragEnter = (event: DragEvent) => {
  if (!props.isTyping && hasDraggedFiles(event)) {
    event.preventDefault();
    dragDepth.value += 1;
  }
};

const onDragOver = (event: DragEvent) => {
  if (!props.isTyping && hasDraggedFiles(event)) {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy";
    }
  }
};

const onDragLeave = (event: DragEvent) => {
  if (hasDraggedFiles(event)) {
    event.preventDefault();
    dragDepth.value = Math.max(0, dragDepth.value - 1);
  }
};

const onDrop = (event: DragEvent) => {
  if (!props.isTyping && hasDraggedFiles(event)) {
    event.preventDefault();
    if (event.dataTransfer?.files.length) {
      addFiles(event.dataTransfer.files);
    }
  }
  dragDepth.value = 0;
};

watch(selectedFiles, (files) => {
  for (const url of previewUrls.value) {
    if (url) URL.revokeObjectURL(url);
  }
  previewUrls.value = files.map((file) =>
    file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
  );
});

const removeFile = (index: number) => {
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== index);
};

onBeforeUnmount(() => {
  for (const url of previewUrls.value) {
    if (url) URL.revokeObjectURL(url);
  }
});

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
      :class="isDraggingFiles ? 'border-blue-300/90 bg-blue-50/45 shadow-[0_12px_35px_rgba(90,140,220,0.20)]' : ''"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <!-- Top reflection -->
      <div
        class="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/90 to-transparent"
      />

      <!-- Little refraction -->
      <div
        class="pointer-events-none absolute -right-4 -top-4 h-16 w-16 rounded-full bg-blue-100/20 blur-2xl"
      />

      <div
        v-if="isDraggingFiles"
        class="pointer-events-none absolute inset-2 z-20 flex items-center justify-center rounded-[20px] border-2 border-dashed border-blue-300/80 bg-white/60 text-[12px] font-medium text-[#6378A5] backdrop-blur-sm"
      >
        Drop files to attach
      </div>

      <!-- Text -->
      <textarea
        ref="textarea"
        :value="modelValue"
        rows="1"
        maxlength="4000"
        :placeholder="`Ask ${APP_NAME} something...`"
        class="relative block max-h-[140px] min-h-[48px] w-full resize-none bg-transparent px-4 pb-14 pt-3 text-[13px] leading-6 text-[#43516B] outline-none placeholder:text-[#9DA6B6]"
        :class="hasFiles ? 'min-h-[220px] pt-[96px]' : ''"
        @input="updateValue"
        @keydown="onKeydown"
      />

      <input
        ref="fileInput"
        type="file"
        multiple
        class="hidden"
        @change="selectFile"
      />

      <div
        v-if="hasFiles"
        class="pointer-events-none absolute inset-x-3 top-1.5 flex items-center gap-2 rounded-2xl border border-white/65 bg-white/35 p-2 shadow-[0_5px_15px_rgba(80,100,140,0.08)] backdrop-blur-xl transition-all duration-300"
      >
        <TransitionGroup
          name="attachment"
          tag="div"
          class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto"
        >
          <div
            v-for="(file, index) in selectedFiles"
            :key="`${file.name}-${file.lastModified}`"
            class="pointer-events-auto relative h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-white/70 bg-white/40 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md"
          >
            <img
              v-if="file.type.startsWith('image/') && previewUrls[index]"
              :src="previewUrls[index]"
              alt="Attached image"
              class="h-full w-full object-cover"
            >
            <span
              v-else
              class="flex h-full w-full items-center justify-center text-xl"
              aria-label="Attached file"
            >
              📎
            </span>
            <button
              type="button"
              :aria-label="`Remove ${file.name}`"
              class="absolute right-0.5 top-0.5 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-[#43516B]/75 text-[11px] leading-none text-white transition-transform hover:scale-110"
              @click="removeFile(index)"
            >
              ×
            </button>
          </div>
        </TransitionGroup>
      </div>

      <!-- Controls -->
      <div
        class="absolute inset-x-3 bottom-2.5 flex items-center justify-between"
        :class="hasFiles ? 'pt-1' : ''"
      >
        <!-- Attachment and counter -->
        <div class="flex min-w-0 items-center gap-3 px-2">
          <button
            type="button"
            aria-label="Attach a file"
            :disabled="isTyping"
            class="attach-button flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-[#8795B0] transition-colors hover:bg-white/50 hover:text-[#6378A5] disabled:cursor-not-allowed disabled:opacity-50"
            @click="openFilePicker"
          >
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none">
              <path
                d="M16.5 5.5 8.4 13.6a3 3 0 0 0 4.2 4.2l7-7a4.5 4.5 0 0 0-6.4-6.4l-7.1 7.1a6 6 0 0 0 8.5 8.5l6.2-6.2"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.5"
              />
            </svg>
          </button>

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
          class="send-button group flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-white/60 transition-all duration-300"
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
      {{ APP_NAME }} can make mistakes. Verify important scientific information.
    </div>
  </div>
</template>

<style scoped>
.attachment-enter-active,
.attachment-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease,
    width 0.22s ease;
}

.attachment-enter-from,
.attachment-leave-to {
  opacity: 0;
  transform: scale(0.78) translateY(-4px);
}

.attachment-leave-active {
  position: absolute;
}
</style>
