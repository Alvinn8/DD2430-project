<script setup lang="ts">
import { ref } from "vue";

type SettingsTab = "general" | "knowledge" | "inspect" | "execution";

defineProps<{ darkMode: boolean }>();

const emit = defineEmits<{
  close: [];
  "update:darkMode": [value: boolean];
}>();

const activeTab = ref<SettingsTab>("general");
const tabs: Array<{ id: SettingsTab; label: string }> = [
  { id: "general", label: "General" },
  { id: "knowledge", label: "Knowledge agent" },
  { id: "inspect", label: "Inspect agent" },
  { id: "execution", label: "Execution agent" },
];
const tabDescription: Record<Exclude<SettingsTab, "general">, string> = {
  knowledge: "The knowledge agent will manage background information and source context.",
  inspect: "The inspect agent will review data quality, structure, and analysis details.",
  execution: "The execution agent will coordinate analysis tools and perform requested actions.",
};
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-[#25324A]/20 p-4 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-labelledby="settings-title"
    @click.self="emit('close')"
  >
    <section
      class="flex max-h-[min(620px,calc(100dvh-32px))] w-full max-w-[720px] overflow-hidden rounded-[28px] border shadow-[0_25px_80px_rgba(50,70,110,0.24)] backdrop-blur-2xl"
      :class="darkMode ? 'border-white/15 bg-[#202A3D]/95' : 'border-white/75 bg-[#F8FAFF]/90'"
    >
      <nav class="settings-nav w-[175px] shrink-0 border-r border-white/60 bg-white/25 p-3">
        <div class="px-3 pb-4 pt-2">
          <p class="text-[9px] font-semibold uppercase tracking-[0.16em] text-[#8A98B3]">Configuration</p>
          <h2 id="settings-title" class="mt-1 text-[15px] font-medium text-[#3D4962]">Settings</h2>
        </div>
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="settings-tab mb-1 w-full rounded-xl px-3 py-2.5 text-left text-[11px] transition"
          :class="activeTab === tab.id ? 'bg-white/75 font-medium text-[#5B73AA] shadow-sm' : 'text-[#7F8CA4] hover:bg-white/45'"
          :aria-current="activeTab === tab.id ? 'page' : undefined"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="settings-content min-w-0 flex-1 overflow-y-auto p-5 sm:p-7">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#91A0BA]">
              {{ tabs.find((tab) => tab.id === activeTab)?.label }}
            </p>
            <h3 class="mt-1 text-[20px] font-medium tracking-tight text-[#35415A]">
              {{ activeTab === "general" ? "General settings" : "Behaviour prompt" }}
            </h3>
          </div>
          <button type="button" aria-label="Close settings" class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-white/50 text-lg text-[#7F8CA4] hover:bg-white/80" @click="emit('close')">×</button>
        </div>

        <div v-if="activeTab === 'general'" class="mt-8">
          <div class="flex items-center justify-between rounded-2xl border border-white/70 bg-white/40 p-4">
            <div>
              <p class="text-[12px] font-medium text-[#52627E]">Appearance</p>
              <p class="mt-1 text-[11px] text-[#8A96AA]">Choose how the workspace should look.</p>
            </div>
            <div class="flex rounded-xl border border-white/70 bg-white/45 p-1">
              <button type="button" class="rounded-lg px-3 py-1.5 text-[10px] transition" :class="!darkMode ? 'bg-white/80 text-[#5B73AA] shadow-sm' : 'text-[#8A96AA]'" @click="emit('update:darkMode', false)">Light</button>
              <button type="button" class="rounded-lg px-3 py-1.5 text-[10px] transition" :class="darkMode ? 'bg-[#53627D] text-white shadow-sm' : 'text-[#8A96AA]'" @click="emit('update:darkMode', true)">Dark</button>
            </div>
          </div>
          <div class="mt-3 rounded-2xl border border-dashed border-white/75 bg-white/20 p-4 text-[11px] text-[#8A96AA]">More general settings are coming soon.</div>
        </div>

        <div v-else class="mt-8 rounded-2xl border border-dashed border-white/75 bg-white/25 p-5">
          <p class="text-[12px] font-medium text-[#52627E]">{{ tabs.find((tab) => tab.id === activeTab)?.label }} behaviour</p>
          <p class="mt-2 text-[11px] leading-5 text-[#8A96AA]">{{ tabDescription[activeTab as Exclude<SettingsTab, "general">] }}</p>
          <p class="mt-5 rounded-xl bg-white/35 px-3 py-2.5 text-[10px] uppercase tracking-[0.08em] text-[#A0AABD]">Prompt editing coming soon</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-nav,
.settings-content {
  transition: background-color 180ms ease, color 180ms ease;
}
</style>
