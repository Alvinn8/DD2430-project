<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import type { Message } from "../types/chat";
import MarkdownIt from "markdown-it";
import markdownItKatex from "@iktakahiro/markdown-it-katex";
import DOMPurify from "dompurify";

// Import KaTeX stylesheet so the math renders beautifully
import "katex/dist/katex.min.css";

const props = defineProps<{
  message: Message;
}>();

const selectedAttachment = ref<{
  name: string;
  type: string;
  url: string;
} | null>(null);
const selectedText = ref<string | null>(null);
const showTools = ref(false);

// Images produced by tools, such as plots, shown in the bubble
const toolImages = computed(() =>
  (props.message.tools ?? []).flatMap((tool) => tool.images ?? []),
);

const closeAttachment = () => {
  selectedAttachment.value = null;
  selectedText.value = null;
  document.removeEventListener("keydown", onKeydown);
};

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") closeAttachment();
};

const openAttachment = async (attachment: {
  name: string;
  type: string;
  previewUrl?: string;
  contentUrl?: string;
}) => {
  const url = attachment.previewUrl ?? attachment.contentUrl;
  if (!url) return;

  selectedAttachment.value = {
    name: attachment.name,
    type: attachment.type,
    url,
  };
  selectedText.value = null;
  document.addEventListener("keydown", onKeydown);

  if (!attachment.type.includes("pdf") && !attachment.type.startsWith("image/")) {
    selectedText.value = await fetch(url).then((response) => response.text());
  }
};

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
});

// 1. Initialize the Markdown parser with the KaTeX plugin
const md = new MarkdownIt({
  breaks: true, // Converts \n to <br> to respect chat message line breaks
  linkify: true, // Automatically converts URLs into clickable links
}).use(markdownItKatex);

// 2. Parse and sanitize the content dynamically
const parsedContent = computed(() => {
  // Parse markdown and LaTeX to raw HTML
  const rawHtml = md.render(props.message.text);

  // Sanitize the HTML to prevent XSS.
  // We explicitly allow the classes and tags KaTeX uses to draw equations.
  return DOMPurify.sanitize(rawHtml, {
    ADD_TAGS: [
      "math",
      "annotation",
      "semantics",
      "mrow",
      "mi",
      "mo",
      "mn",
      "msup",
      "msubsup",
      "mfrac",
      "msqrt",
      "mstyle",
      "merror",
      "mpadded",
      "mphantom",
      "maligngroup",
      "malignmark",
    ],
    ADD_ATTR: ["display", "mathvariant", "href", "class"],
  });
});
</script>

<template>
  <!-- Keep your existing Aura theme outer wrapper -->
  <div
    class="flex flex-col max-w-[85%]"
    :class="[
      message.sender === 'user'
        ? 'self-end items-end'
        : 'self-start items-start',
    ]"
  >
    <div
      class="px-5 py-3.5 shadow-sm ring-1 ring-inset"
      :class="[
        message.sender === 'user'
          ? 'bg-[#E7EEFF]/55 rounded-[20px] rounded-br-[6px] text-[#293246] ring-white/40 shadow-[0_8px_20px_rgba(80,100,140,0.08)]'
          : 'bg-white/[0.42] backdrop-blur-[35px] rounded-[20px] rounded-bl-[6px] text-[#293246] ring-white/60 shadow-[0_8px_20px_rgba(80,100,140,0.06)]',
      ]"
    >
      <div v-if="message.tools?.length" class="mb-2 text-xs text-[#8791A5]">
        <button
          type="button"
          class="cursor-pointer hover:text-[#43516B]"
          @click="showTools = !showTools"
        >
          🔧 {{ message.tools.length }}
          {{ message.tools.length === 1 ? "tool" : "tools" }} used
          {{ showTools ? "▾" : "▸" }}
        </button>
        <div v-if="showTools" class="mt-2 flex flex-col gap-2">
          <div
            v-for="tool in message.tools"
            :key="tool.id"
            class="rounded-lg bg-white/40 p-2 ring-1 ring-white/60"
          >
            <div class="font-medium text-[#43516B]">{{ tool.name }}</div>
            <pre
              v-if="Object.keys(tool.args).length"
              class="mt-1 whitespace-pre-wrap break-words"
            >{{ JSON.stringify(tool.args, null, 2) }}</pre>
            <pre class="mt-1 whitespace-pre-wrap break-words">{{ tool.result ?? "Running…" }}</pre>
          </div>
        </div>
      </div>

      <!-- 3. Replace {{ message.text }} with v-html -->
      <div v-if="message.text" class="markdown-body" v-html="parsedContent"></div>

      <div v-if="toolImages.length" class="mt-3 flex flex-wrap gap-2">
        <img
          v-for="(image, index) in toolImages"
          :key="index"
          :src="image"
          alt="Image from tool"
          class="max-h-64 cursor-pointer rounded-xl bg-white shadow-sm ring-1 ring-white/70"
          @click="openAttachment({ name: 'Tool image', type: 'image/png', previewUrl: image })"
        />
      </div>
      <div v-if="message.attachments" class="mt-3 flex flex-wrap gap-2">
        <template
          v-for="attachment in message.attachments"
          :key="attachment.name"
        >
          <img
            v-if="attachment.previewUrl"
            :src="attachment.previewUrl"
            alt="Attached image"
            class="h-24 w-24 cursor-pointer rounded-xl object-cover shadow-sm ring-1 ring-white/70 transition-transform hover:scale-[1.03]"
            @click="openAttachment(attachment)"
          />
          <span
            v-else
            class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl bg-white/40 text-lg ring-1 ring-white/70 transition-transform hover:scale-[1.05]"
            aria-label="Attached file"
            :title="`View ${attachment.name}`"
            @click="openAttachment(attachment)"
          >
            📎
          </span>
        </template>
      </div>
    </div>

    <span class="text-xs text-[#8791A5] mt-1.5 px-1">
      {{
        message.timestamp.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      }}
    </span>
  </div>

  <Teleport to="body">
    <Transition name="attachment-dialog">
      <div
        v-if="selectedAttachment"
        class="fixed inset-0 z-50 flex cursor-pointer items-center justify-center bg-[#293246]/55 p-4 backdrop-blur-md sm:p-6"
        role="dialog"
        aria-modal="true"
        :aria-label="`Preview of ${selectedAttachment.name}`"
        @click.self="closeAttachment"
      >
        <button
          type="button"
          aria-label="Close attachment preview"
          class="absolute right-5 top-5 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full bg-white/20 text-2xl text-white transition-colors hover:bg-white/35"
          @click="closeAttachment"
        >
          ×
        </button>
        <img
          v-if="selectedAttachment.type.startsWith('image/')"
          :src="selectedAttachment.url"
          alt="Expanded attachment"
          class="max-h-[90vh] max-w-[92vw] cursor-default rounded-2xl object-contain shadow-[0_20px_70px_rgba(0,0,0,0.28)]"
        />
        <iframe
          v-else-if="selectedAttachment.type === 'application/pdf'"
          :src="selectedAttachment.url"
          :title="selectedAttachment.name"
          class="h-[88vh] w-[min(92vw,900px)] cursor-default rounded-2xl bg-white shadow-[0_20px_70px_rgba(0,0,0,0.28)]"
        />
        <div
          v-else
          class="flex h-[min(82vh,720px)] w-[min(92vw,900px)] cursor-default flex-col overflow-hidden rounded-2xl bg-[#F8FAFF] shadow-[0_20px_70px_rgba(0,0,0,0.28)]"
        >
          <div class="border-b border-[#DCE3F0] px-5 py-3 text-sm font-medium text-[#43516B]">
            {{ selectedAttachment.name }}
          </div>
          <pre class="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words p-5 text-left text-xs leading-6 text-[#43516B]">{{ selectedText ?? "Loading preview..." }}</pre>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 
  4. Styling the injected HTML 
  Because v-html content is injected dynamically, standard scoped CSS won't affect it.
  You must use Vue's :deep() selector to target the markdown elements.
*/
.markdown-body :deep(p) {
  margin-bottom: 0.75em;
  line-height: 1.75;
  white-space: normal; /* Override whitespace-pre-wrap for normal markdown wrapping */
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

/* Style inline code block */
.markdown-body :deep(code:not(.language-math)) {
  background: rgba(255, 255, 255, 0.4);
  padding: 0.15em 0.3em;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
}

/* Style multiline code blocks */
.markdown-body :deep(pre) {
  background: rgba(255, 255, 255, 0.4);
  padding: 0.85rem;
  border-radius: 8px;
  overflow-x: auto;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.5);
}

/* Ensure display math scrolls horizontally if it overflows on mobile */
.markdown-body :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding-top: 0.2em;
  padding-bottom: 0.2em;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 0.75em;
}

.markdown-body :deep(ul) {
  list-style-type: disc;
}

.markdown-body :deep(ol) {
  list-style-type: decimal;
}

.markdown-body :deep(a) {
  color: #afc8ff;
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* Protect KaTeX math from Tailwind's global box-sizing reset */
.markdown-body :deep(.katex),
.markdown-body :deep(.katex *) {
  box-sizing: content-box !important;
}

/* Reset line-height so vertical fractions and exponents don't collapse */
.markdown-body :deep(.katex) {
  display: inline-block;
  font-size: 1.08em;
  line-height: normal !important;
  vertical-align: middle;
  white-space: nowrap;
}

/* Protect fraction lines from Tailwind's global border removal */
.markdown-body :deep(.katex .mfrac .frac-line) {
  border-bottom-style: solid !important;
}

/* Ensure display math has enough vertical breathing room */
.markdown-body :deep(.katex-display) {
  margin: 1em 0;
  min-height: 2.5em;
  padding: 0.75em 0;
  line-height: 1.5 !important;
}

.markdown-body :deep(.katex-display > .katex) {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.15em 0.25em;
}

.markdown-body :deep(.katex .vlist-t) {
  vertical-align: middle;
}

.attachment-dialog-enter-active,
.attachment-dialog-leave-active {
  transition: opacity 0.2s ease;
}

.attachment-dialog-enter-from,
.attachment-dialog-leave-to {
  opacity: 0;
}
</style>
