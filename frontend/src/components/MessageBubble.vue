<script setup lang="ts">
import { computed } from "vue";
import type { Message } from "../types/chat";
import MarkdownIt from "markdown-it";
import markdownItKatex from "@iktakahiro/markdown-it-katex";
import DOMPurify from "dompurify";

// Import KaTeX stylesheet so the math renders beautifully
import "katex/dist/katex.min.css";

const props = defineProps<{
  message: Message;
}>();

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
      <!-- 3. Replace {{ message.text }} with v-html -->
      <div class="markdown-body" v-html="parsedContent"></div>
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
</template>

<style scoped>
/* 
  4. Styling the injected HTML 
  Because v-html content is injected dynamically, standard scoped CSS won't affect it.
  You must use Vue's :deep() selector to target the markdown elements.
*/
.markdown-body :deep(p) {
  margin-bottom: 0.75em;
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
  line-height: normal !important;
}

/* Protect fraction lines from Tailwind's global border removal */
.markdown-body :deep(.katex .mfrac .frac-line) {
  border-bottom-style: solid !important;
}

/* Ensure display math has enough vertical breathing room */
.markdown-body :deep(.katex-display) {
  margin: 1em 0;
  padding: 0.5em 0;
}
</style>
