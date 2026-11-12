<script setup lang="ts">
import { ref } from "vue";
import type { Message } from "../types/chat";

import AmbientBackground from "./AmbientBackground.vue";
import ChatComposer from "./ChatComposer.vue";
import ChatHeader from "./ChatHeader.vue";
import MessageList from "./MessageList.vue";
import AnalysisSidebar from "./AnalysisSidebar.vue";
import SettingsModal from "./SettingsModal.vue";

type SendPayload = File[];

const props = defineProps<{
  messages: Message[];
  inputText: string;
  isTyping: boolean;
  availableModels: string[];
  selectedModel: string;
  sessionId: string;
}>();

const emit = defineEmits<{
  "update:inputText": [value: string];
  "update:selectedModel": [value: string];
  send: [files: SendPayload];
  newChat: [];
}>();

const importedFiles = ref<File[]>([]);
const sentImportedFileKeys = ref(new Set<string>());
const isSettingsOpen = ref(false);
const isDarkMode = ref(false);

const fileKey = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;

const addImportedFiles = (files: File[]) => {
  importedFiles.value = [...importedFiles.value, ...files];
};

const removeImportedFile = (index: number) => {
  const removedFile = importedFiles.value[index];
  if (removedFile) {
    sentImportedFileKeys.value.delete(fileKey(removedFile));
    void fetch(
      `http://localhost:8000/api/chat/${encodeURIComponent(props.sessionId)}/files?filename=${encodeURIComponent(removedFile.name)}`,
      { method: "DELETE" },
    )
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server returned status ${response.status}`);
        }
      })
      .catch((error) => console.error("File removal error:", error));
  }
  importedFiles.value = importedFiles.value.filter(
    (_, fileIndex) => fileIndex !== index,
  );
};

const sendMessage = (files: File[]) => {
  const newImportedFiles = importedFiles.value.filter(
    (file) => !sentImportedFileKeys.value.has(fileKey(file)),
  );
  emit("send", [...newImportedFiles, ...files]);
  for (const file of newImportedFiles) {
    sentImportedFileKeys.value.add(fileKey(file));
  }
};

const clearChat = () => {
  importedFiles.value = [];
  sentImportedFileKeys.value.clear();
  emit("newChat");
};
</script>

<template>
  <!--
    fixed + inset-0 means this can NEVER create a page scrollbar.
  -->
  <div class="fixed inset-0 h-dvh w-full overflow-hidden" :class="{ dark: isDarkMode }">
    <!-- Background -->
    <AmbientBackground :dark-mode="isDarkMode" />

    <!-- Main application -->
    <main
      class="relative z-10 flex h-dvh w-full items-center justify-center overflow-hidden p-3 sm:p-6"
    >
      <!-- Glass window -->
      <section
        class="relative flex h-full max-h-[calc(100dvh-24px)] w-full max-w-[1160px] flex-col overflow-hidden rounded-[36px] border shadow-[0_25px_80px_rgba(80,100,140,0.12)] backdrop-blur-[35px] ring-1 ring-inset ring-white/40 sm:max-h-[calc(100dvh-48px)] lg:flex-row"
        :class="isDarkMode ? 'border-white/20 bg-[#202A3D]/80' : 'border-white/60 bg-white/[0.42]'"
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
        <div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <ChatHeader
            :available-models="props.availableModels"
            :selected-model="props.selectedModel"
            @update:selected-model="emit('update:selectedModel', $event)"
            @new-chat="clearChat"
          />

          <!-- THE ONLY SCROLLABLE AREA -->
          <MessageList :messages="props.messages" :is-typing="props.isTyping" />

          <ChatComposer
            :model-value="props.inputText"
            :is-typing="props.isTyping"
            @update:model-value="emit('update:inputText', $event)"
            @send="sendMessage"
          />
        </div>

        <AnalysisSidebar
          :files="importedFiles"
          :is-typing="props.isTyping"
          @add-files="addImportedFiles"
          @remove-file="removeImportedFile"
          @open-settings="isSettingsOpen = true"
        />
      </section>

      <SettingsModal
        v-if="isSettingsOpen"
        :dark-mode="isDarkMode"
        @close="isSettingsOpen = false"
        @update:dark-mode="isDarkMode = $event"
      />
    </main>
  </div>
</template>

<style>
.dark [class~="text-[#293246]"] { color: #E7EDF9; }
.dark [class~="text-[#35415A]"],
.dark [class~="text-[#3D4962]"] { color: #E5ECFA; }
.dark [class~="text-[#43516B]"] { color: #C2CEE4; }
.dark [class~="text-[#4D5870]"] { color: #D5DDF0; }
.dark [class~="text-[#52627E]"] { color: #D0DBEF; }
.dark [class~="text-[#596985]"] { color: #CBD7ED; }
.dark [class~="text-[#6378A5]"] { color: #B8C9F1; }
.dark [class~="text-[#687895]"] { color: #B1C0DD; }
.dark [class~="text-[#7F8CA4]"],
.dark [class~="text-[#8492AD]"],
.dark [class~="text-[#8791A5]"],
.dark [class~="text-[#8A98B3]"],
.dark [class~="text-[#8A96AA]"],
.dark [class~="text-[#8C98AD]"],
.dark [class~="text-[#91A0BA]"],
.dark [class~="text-[#9AA5B8]"],
.dark [class~="text-[#A0A8B8]"],
.dark [class~="text-[#A0AABD]"],
.dark [class~="text-[#A4ADBC]"],
.dark [class~="text-[#AAB2C0]"],
.dark [class~="text-[#9DA6B6]"] { color: #9FAFCB; }

.dark [class~="bg-white/40"],
.dark [class~="bg-white/35"],
.dark [class~="bg-white/30"],
.dark [class~="bg-white/25"],
.dark [class~="bg-white/20"],
.dark [class~="bg-white/[0.48]"],
.dark [class~="bg-white/[0.42]"] {
  background-color: rgba(31, 45, 70, 0.62);
}

.dark [class~="bg-white/45"],
.dark [class~="bg-white/50"],
.dark [class~="bg-white/60"],
.dark [class~="bg-white/70"] {
  background-color: rgba(70, 88, 122, 0.56);
}

.dark [class~="border-white/75"],
.dark [class~="border-white/70"],
.dark [class~="border-white/65"],
.dark [class~="border-white/60"],
.dark [class~="border-white/50"] {
  border-color: rgba(177, 198, 237, 0.22);
}

.dark textarea { color: #D7E1F4; }
.dark textarea::placeholder { color: #7789AA; }
.dark .attach-button,
.dark .new-chat-button {
  color: #AFC4E8;
  border-color: rgba(182, 207, 250, 0.28);
}
.dark .attach-button:hover,
.dark .new-chat-button:hover {
  color: #E1EBFF;
  background-color: rgba(99, 128, 184, 0.35);
}
.dark .model-selector {
  background-color: rgba(32, 48, 77, 0.72);
  border-color: rgba(167, 192, 237, 0.25);
  color: #b9cbed;
}
.dark .model-selector:hover {
  background-color: rgba(57, 78, 119, 0.8);
}
.dark .model-menu {
  background-color: rgba(25, 38, 63, 0.97);
  border-color: rgba(167, 192, 237, 0.24);
  box-shadow: 0 16px 36px rgba(1, 6, 18, 0.42);
}
.dark .model-option {
  color: #aebfdf;
}
.dark .model-option:hover {
  background-color: rgba(73, 98, 149, 0.5);
  color: #e2ebff;
}
.dark .model-option[aria-selected="true"] {
  background-color: rgba(67, 91, 139, 0.72);
  color: #e8f0ff;
}
.dark .settings-tab[aria-current="page"] {
  background-color: rgba(67, 91, 139, 0.72);
  color: #dce8ff;
  box-shadow: inset 0 1px 0 rgba(202, 220, 255, 0.1);
}
.dark .settings-tab {
  color: #91a5ca;
}
.dark .settings-tab:hover {
  background-color: rgba(55, 77, 119, 0.55);
  color: #c9d8f4;
}
.dark .analysis-folder-icon {
  background-color: rgba(62, 86, 132, 0.58);
  color: #a9c2f1;
}
.dark .import-file-button {
  background-color: rgba(47, 67, 105, 0.64);
  border-color: rgba(167, 192, 237, 0.24);
  color: #b9cbed;
}
.dark .import-file-button:hover {
  background-color: rgba(68, 92, 143, 0.72);
  color: #e2ebff;
}
.dark .send-button:not(:disabled) {
  color: #FFFFFF;
  border-color: rgba(205, 220, 255, 0.38);
}
.dark .send-button:disabled {
  color: #7185A8;
  border-color: rgba(170, 195, 238, 0.2);
  background-color: rgba(47, 65, 98, 0.56);
}
.dark aside svg,
.dark header svg {
  color: #AFC4E8;
}
.dark .chat-scroll-area { scrollbar-color: rgba(130, 161, 225, 0.68) transparent; }
.dark .chat-scroll-area::-webkit-scrollbar-track {
  background: rgba(14, 24, 42, 0.35);
  border-color: rgba(180, 201, 240, 0.12);
}
.dark .chat-scroll-area::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(142, 174, 239, 0.88), rgba(78, 110, 177, 0.8));
  background-clip: padding-box;
}
</style>
