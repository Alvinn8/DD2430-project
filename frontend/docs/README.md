# Aura — Liquid Glass Vue Chatbot UI

A modular, light-themed chatbot interface built with **Vue 3 Composition API**, **TypeScript**, and **Tailwind CSS**.

The design is intentionally closer to a **soft liquid-glass application** than a conventional dark-mode AI dashboard. It uses translucent white surfaces, blurred ambient color, subtle reflections, rounded organic geometry, restrained motion, and a small amount of blue/lavender emphasis for interactive elements.

The project is structured so that the main view is responsible for composing the application, while the individual UI pieces live in separate Vue components. Chat state and behavior are kept in a composable instead of being mixed into presentation markup.

---

## Table of Contents

1. [Overview](#overview)
2. [Design Goals](#design-goals)
3. [Technology](#technology)
4. [Project Structure](#project-structure)
5. [Quick Start](#quick-start)
6. [Architecture](#architecture)
7. [Component Overview](#component-overview)
8. [AuraChatView](#aurachatview)
9. [AuraChatShell](#aurachatshell)
10. [AmbientBackground](#ambientbackground)
11. [ChatHeader](#chatheader)
12. [MessageList](#messagelist)
13. [MessageBubble](#messagebubble)
14. [ChatComposer](#chatcomposer)
15. [useChat Composable](#usechat-composable)
16. [Message Type](#message-type)
17. [Props API](#props-api)
18. [Events API](#events-api)
19. [Data Flow](#data-flow)
20. [Scrolling Behavior](#scrolling-behavior)
21. [Liquid Glass Styling](#liquid-glass-styling)
22. [Color System](#color-system)
23. [Animations and Micro-interactions](#animations-and-micro-interactions)
24. [Responsive Behavior](#responsive-behavior)
25. [Keyboard Behavior](#keyboard-behavior)
26. [Accessibility](#accessibility)
27. [Connecting a Real Backend or LLM API](#connecting-a-real-backend-or-llm-api)
28. [Streaming Responses](#streaming-responses)
29. [Adding Rich Scientific Messages](#adding-rich-scientific-messages)
30. [Customizing the Theme](#customizing-the-theme)
31. [Adding Features](#adding-features)
32. [Performance Considerations](#performance-considerations)
33. [Common Problems and Fixes](#common-problems-and-fixes)
34. [Deployment Notes](#deployment-notes)
35. [Recommended Extension Roadmap](#recommended-extension-roadmap)
36. [Summary](#summary)

---

## Overview

Aura is a single-page chatbot UI intended to be embedded into a larger Vue application.

The interface consists of:

- a soft, ambient background;
- a translucent liquid-glass application window;
- a compact assistant header;
- an independently scrollable message area;
- bot and user message bubbles;
- a typing indicator;
- an auto-growing message composer;
- a glass send button;
- a new-conversation action.

The current implementation simulates the assistant response. The simulated response can later be replaced by a request to an application backend, an LLM gateway, or another service without having to redesign the UI component hierarchy.

The most important architectural decision is the separation between **visual presentation** and **chat behavior**.

The main page does not directly implement the chatbot internals. Instead, it imports the `AuraChatShell` component and the `useChat` composable.

---

## Design Goals

The interface intentionally follows these principles.

### 1. Light first

The page is based on an off-white background rather than a dark interface. The glass effect is visible because the surface is lighter than the background while still being translucent.

### 2. Glass instead of opaque cards

Most visible surfaces use combinations of:

```text
bg-white/[opacity]
border-white/[opacity]
backdrop-blur-*
shadow-[...]
ring-1 ring-inset
```

The result is a translucent layered surface rather than a collection of opaque panels.

### 3. Color is an accent, not the entire design

The primary UI is neutral. Blue, lavender, and warm peach tones are mainly used in ambient background lighting, the small assistant identity mark, and the send button.

### 4. Animation stays subtle

Animation is used for:

- ambient background movement/pulsing;
- message appearance;
- typing feedback;
- button hover states;
- icon rotation;
- send-button movement.

The UI should feel alive without looking like a science-fiction dashboard.

### 5. Only the conversation scrolls

The page is explicitly locked to the viewport. The message list is the only component permitted to create vertical scrolling.

### 6. Modular Vue architecture

Each visual responsibility has its own component:

```text
AuraChatView
    ↓
AuraChatShell
    ├── AmbientBackground
    ├── ChatHeader
    ├── MessageList
    │      └── MessageBubble
    └── ChatComposer
```

Chat state lives in:

```text
useChat.ts
```

The message data model lives in:

```text
chat.ts
```

---

## Technology

The implementation assumes the following stack:

- Vue 3
- Vue Composition API
- `<script setup lang="ts">`
- TypeScript
- Tailwind CSS
- Vue `<Transition>` / `<TransitionGroup>`

No component library is required.

No separate UI framework is required.

No custom icon package is required because the current implementation uses inline SVG for the small icons.

---

## Project Structure

A recommended project structure is:

```text
src/
├── components/
│   ├── AmbientBackground.vue
│   ├── AuraChatShell.vue
│   ├── ChatComposer.vue
│   ├── ChatHeader.vue
│   ├── MessageBubble.vue
│   └── MessageList.vue
│
├── composables/
│   └── useChat.ts
│
├── types/
│   └── chat.ts
│
├── views/
│   └── AuraChatView.vue
│
├── App.vue
├── main.ts
└── assets/
    └── ...
```

The precise location of `AuraChatView.vue` depends on how the router is organized. The important requirement is that the imports point to the actual component locations.

---

# Quick Start

## 1. Install Vue and Tailwind

Use the normal Vue + Vite setup for your project.

For example, a typical project will already contain:

```text
Vue 3
Vite
TypeScript
Tailwind CSS
```

The exact Tailwind installation procedure depends on the Tailwind version and build setup used by the application. This UI only relies on ordinary utility classes and arbitrary values, so it does not require a custom component library.

## 2. Add the folders

Create:

```text
src/components
src/composables
src/types
src/views
```

Then place the files into those directories.

## 3. Make the view your route

With Vue Router, for example:

```ts
import { createRouter, createWebHistory } from "vue-router";
import AuraChatView from "../views/AuraChatView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "chat",
      component: AuraChatView,
    },
  ],
});

export default router;
```

## 4. Render the application

The normal Vue application bootstrap remains unchanged.

```ts
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./style.css";

createApp(App)
  .use(router)
  .mount("#app");
```

## 5. Run the project

```bash
npm run dev
```

Open the local development URL printed by Vite.

---

# Architecture

There are three conceptual layers.

## Presentation layer

Components:

```text
AmbientBackground.vue
AuraChatShell.vue
ChatHeader.vue
MessageList.vue
MessageBubble.vue
ChatComposer.vue
```

These components are primarily responsible for rendering UI and emitting user interactions.

## State / behavior layer

```text
useChat.ts
```

This handles:

- current input text;
- messages;
- typing state;
- sending messages;
- generating simulated replies;
- clearing the conversation;
- scrolling indirectly through reactive changes.

## Data model layer

```text
types/chat.ts
```

This defines the `Message` interface shared between the components and composable.

---

# Component Overview

| Component | Responsibility | Owns state? | Scrollable? |
|---|---|---:|---:|
| `AuraChatView` | Page-level composition | Uses composable | No |
| `AuraChatShell` | Layout/composition | No | No |
| `AmbientBackground` | Ambient visual background | No | No |
| `ChatHeader` | Branding and new-chat button | No | No |
| `MessageList` | Renders conversation and typing indicator | Local DOM ref only | **Yes** |
| `MessageBubble` | Renders one message | No | No |
| `ChatComposer` | User text entry and send interaction | Local textarea ref | No |
| `useChat` | Chat behavior/state | **Yes** | No |

The design intentionally keeps state out of the presentational child components wherever practical.

---

# AuraChatView

File:

```text
src/views/AuraChatView.vue
```

This is the main view used by the router.

Current implementation:

```vue
<script setup lang="ts">
import AuraChatShell from "../components/AuraChatShell.vue";
import { useChat } from "../composables/useChat";

const {
  inputText,
  isTyping,
  messages,
  sendMessage,
  clearChat,
} = useChat();
</script>

<template>
  <AuraChatShell
    :messages="messages"
    :input-text="inputText"
    :is-typing="isTyping"
    @update:input-text="inputText = $event"
    @send="sendMessage"
    @new-chat="clearChat"
  />
</template>
```

## Responsibility

`AuraChatView` is intentionally thin.

It does not contain:

- message bubble markup;
- input markup;
- glass styling;
- scrolling implementation;
- response generation logic.

Instead, it connects the state layer to the visual shell.

## Why keep the view this small?

The page becomes easy to replace with another route or layout without rewriting the chat implementation.

For example, an application could later use:

```text
DashboardView
    ├── Sidebar
    └── AuraChatShell
```

without moving all chat logic into the dashboard.

---

# AuraChatShell

File:

```text
src/components/AuraChatShell.vue
```

This is the main visual composition component.

Its job is to provide:

- viewport sizing;
- overflow containment;
- glass application window;
- component arrangement;
- communication between child components.

## Props

### `messages`

Type:

```ts
Message[]
```

Required.

Passed to `MessageList`.

### `inputText`

Type:

```ts
string
```

Required.

Passed to `ChatComposer` as `model-value`.

### `isTyping`

Type:

```ts
boolean
```

Required.

Passed to both `MessageList` and `ChatComposer`.

## Events emitted

### `update:inputText`

Payload:

```ts
string
```

Emitted by forwarding the same event from `ChatComposer`.

### `send`

No payload.

Forwarded when the composer requests a send operation.

### `newChat`

No payload.

Forwarded from the `ChatHeader` new-conversation button.

## Layout responsibility

The outermost element uses:

```text
fixed
inset-0
h-dvh
w-full
overflow-hidden
```

This is deliberate.

The component is designed to occupy the entire viewport without creating a page-level scrollbar.

The main glass panel then uses `overflow-hidden` so none of its children can accidentally create an outer scroll region.

---

# AmbientBackground

File:

```text
src/components/AmbientBackground.vue
```

The background is purely visual. It accepts no props and emits no events.

## Visual layers

There are several layers.

### Base surface

```text
bg-[#F3F6FA]
```

This supplies the neutral daylight-like background.

### Blue ambient light

```text
bg-[#C9DAFF]/60
blur-[100px]
```

This produces the cool light source in the upper-left area.

### Lavender ambient light

```text
bg-[#E7D9FF]/55
blur-[110px]
```

This supplies a softer purple refraction toward the upper-right.

### Warm ambient light

```text
bg-[#FFE5DC]/45
blur-[120px]
```

This gives the lower part of the screen a subtle warm contrast.

### White illumination

A large radial gradient creates the impression that the center/top of the environment is naturally illuminated.

## Animation

The current background uses Tailwind's `animate-pulse` utility on some ambient shapes.

The goal is not to animate the shapes aggressively. The motion should be almost subconscious.

If more physical liquid movement is desired, the ambient elements can later be changed to custom `transform` keyframes. The current implementation intentionally avoids heavy animation complexity.

---

# ChatHeader

File:

```text
src/components/ChatHeader.vue
```

The header contains:

1. the Aura identity mark;
2. the application title;
3. a small subtitle;
4. the new conversation action.

## Props

None.

## Events

### `newChat`

Emitted when the circular plus button is clicked.

Payload:

```text
none
```

The shell forwards the event to the view, which maps it to `clearChat()` from the composable.

## Logo construction

The logo is made entirely from HTML/Tailwind shapes:

- outer translucent rounded square;
- blue blurred circle;
- purple blurred circle;
- small gradient core.

This is intentionally not an image asset.

It can therefore be recolored and scaled without introducing an additional asset pipeline.

## New-chat interaction

The plus icon uses:

```text
group-hover:rotate-90
```

The icon rotates only during hover. The intent is to add a small tactile interaction without making the UI feel animated everywhere.

---

# MessageList

File:

```text
src/components/MessageList.vue
```

This component is responsible for the conversation viewport.

It is the **only intentionally scrollable component in the entire interface**.

## Props

### `messages`

Type:

```ts
Message[]
```

Required.

### `isTyping`

Type:

```ts
boolean
```

Required.

When `true`, a typing indicator is displayed at the bottom of the conversation.

## Internal reference

The component uses:

```ts
const container = ref<HTMLElement | null>(null);
```

This reference points to the actual scrolling element.

## Auto-scroll

After the message list changes, the component calls:

```ts
container.value.scrollTo({
  top: container.value.scrollHeight,
  behavior: "smooth",
});
```

`nextTick()` is used first so that Vue has time to render the new message before calculating the new scroll height.

## Why `min-h-0` matters

The scroll region uses:

```text
min-h-0
flex-1
h-full
overflow-y-auto
```

`min-h-0` is particularly important inside a flex column.

Without it, the flex child may refuse to shrink below its content height. When that happens, the entire page can become taller than the viewport and a browser-level scrollbar appears.

## Scroll axis

The element explicitly uses:

```text
overflow-y-auto
overflow-x-hidden
```

Therefore:

- vertical scrolling appears when messages overflow;
- horizontal scrolling is disabled.

## Scrollbar styling

The current implementation does not style the scrollbar with custom CSS. This is deliberate because the requirement was to prefer Tailwind styling and keep vanilla CSS to a minimum.

If a custom scrollbar plugin is added later, it should be applied only to this element.

---

# MessageBubble

File:

```text
src/components/MessageBubble.vue
```

This component renders exactly one message.

## Props

### `message`

Type:

```ts
Message
```

Required.

Example:

```ts
{
  id: 1,
  text: "Hello!",
  sender: "bot",
  timestamp: new Date(),
}
```

## Sender-dependent styling

The bubble checks:

```ts
message.sender === "user"
```

and changes alignment and appearance accordingly.

### Bot message

The bot message:

- stays on the left;
- has a rounded bottom-left corner that is slightly less rounded;
- uses translucent white glass;
- uses neutral text.

### User message

The user message:

- moves to the right;
- has a slightly blue/lavender translucent surface;
- uses a slightly stronger blue-tinted shadow;
- uses a rounded bottom-right corner.

The goal is to distinguish the sender without creating two completely unrelated visual systems.

## Assistant identity mark

Bot messages include a small liquid-glass circular identity mark. It deliberately uses the same blue/lavender gradient found in the main logo.

## Timestamp

The message timestamp is formatted through:

```ts
message.timestamp.toLocaleTimeString([], {
  hour: "2-digit",
  minute: "2-digit",
});
```

Therefore the displayed format follows the browser's locale settings.

## Content rendering

The message text uses:

```text
whitespace-pre-wrap
```

This preserves line breaks supplied by the assistant or user.

The current renderer treats the message as plain text.

It does **not** render Markdown or HTML.

That is an intentional safety and simplicity choice. Markdown rendering can be introduced later with a dedicated parser and sanitization strategy.

---

# ChatComposer

File:

```text
src/components/ChatComposer.vue
```

The composer is the user input area at the bottom of the glass panel.

## Props

### `modelValue`

Type:

```ts
string
```

Required.

This is the current text inside the textarea.

The component follows the Vue `v-model` convention by accepting `modelValue` and emitting `update:modelValue`.

### `isTyping`

Type:

```ts
boolean
```

Required.

When the assistant is generating a response, the send action is disabled.

## Computed `canSend`

The composer calculates:

```ts
const canSend = computed(
  () => props.modelValue.trim().length > 0 && !props.isTyping,
);
```

Therefore the send button is enabled only when:

1. the message is not empty after trimming whitespace;
2. the assistant is not currently typing.

## Events

### `update:modelValue`

Payload:

```ts
string
```

Emitted on every input change.

### `send`

No payload.

Emitted when:

- the send button is clicked; or
- Enter is pressed without Shift.

## Auto-growing textarea

The textarea starts at one visible row and dynamically increases in height.

The component performs:

```ts
target.style.height = "auto";
target.style.height = `${Math.min(target.scrollHeight, 140)}px`;
```

This is one of the few places where direct DOM manipulation is intentionally used. Tailwind cannot calculate the rendered text height of a textarea by itself.

The maximum dynamic height is 140 pixels.

## Enter behavior

The current keyboard behavior is:

```text
Enter       → send message
Shift+Enter → insert a new line
```

The default Enter action is prevented when sending.

## Character limit

The textarea uses:

```html
maxlength="4000"
```

and displays:

```text
current characters / 4000
```

The UI therefore supports up to 4000 characters per message at the input level.

The backend can still enforce its own limits.

## Send button appearance

When disabled, the button is a very subtle translucent white shape.

When enabled, it becomes a gradient glass button:

```text
#AFC8FF → #B9AAFF
```

The stronger color intentionally appears only when the interaction is available.

---

# useChat Composable

File:

```text
src/composables/useChat.ts
```

This is the state and behavior layer.

## Exposed state

### `inputText`

```ts
Ref<string>
```

Contains the current composer text.

### `isTyping`

```ts
Ref<boolean>
```

Indicates whether the assistant is currently generating a simulated response.

### `messages`

```ts
Ref<Message[]>
```

Contains the complete message history for the current in-memory session.

## Exposed methods

### `sendMessage()`

Validates the current input, appends a user message, clears the input, and creates a delayed simulated bot reply.

### `clearChat()`

Replaces the current message list with an empty array.

## Simulated response

The current code uses a `setTimeout` delay to simulate assistant latency.

A real application should replace this with a network request.

---

# Message Type

File:

```text
src/types/chat.ts
```

The shared message type is:

```ts
export interface Message {
  id: number;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
}
```

## Field reference

### `id`

Unique identifier used as the Vue `key` in `v-for`.

The current example uses `Date.now()` when creating messages.

For a production application with persistent server-side messages, prefer the backend's stable message identifier or use a UUID.

### `text`

The plain-text message body.

### `sender`

Allowed values:

```text
user
bot
```

This controls alignment and visual styling.

### `timestamp`

A JavaScript `Date` representing the message creation time.

---

# Props API

## `AuraChatShell`

| Prop | Type | Required | Purpose |
|---|---|---:|---|
| `messages` | `Message[]` | Yes | Conversation history |
| `inputText` | `string` | Yes | Current composer value |
| `isTyping` | `boolean` | Yes | Whether assistant is generating |

## `MessageList`

| Prop | Type | Required | Purpose |
|---|---|---:|---|
| `messages` | `Message[]` | Yes | Messages to display |
| `isTyping` | `boolean` | Yes | Show typing indicator |

## `MessageBubble`

| Prop | Type | Required | Purpose |
|---|---|---:|---|
| `message` | `Message` | Yes | Message to render |

## `ChatComposer`

| Prop | Type | Required | Purpose |
|---|---|---:|---|
| `modelValue` | `string` | Yes | Current input text |
| `isTyping` | `boolean` | Yes | Controls send availability |

## `ChatHeader`

No props.

## `AmbientBackground`

No props.

---

# Events API

## `AuraChatShell`

| Event | Payload | Origin |
|---|---|---|
| `update:inputText` | `string` | `ChatComposer` |
| `send` | none | `ChatComposer` |
| `newChat` | none | `ChatHeader` |

## `ChatHeader`

| Event | Payload | Trigger |
|---|---|---|
| `newChat` | none | New conversation button |

## `ChatComposer`

| Event | Payload | Trigger |
|---|---|---|
| `update:modelValue` | `string` | Textarea input |
| `send` | none | Click or Enter |

## `MessageBubble`

No events.

## `MessageList`

No custom events.

## `AmbientBackground`

No events.

---

# Data Flow

The current flow is deliberately unidirectional.

```text
User types
    ↓
ChatComposer
    ↓
update:modelValue
    ↓
AuraChatView
    ↓
inputText ref
```

When sending:

```text
User presses Enter / clicks Send
    ↓
ChatComposer emits `send`
    ↓
AuraChatShell forwards `send`
    ↓
AuraChatView calls `sendMessage()`
    ↓
useChat pushes user Message
    ↓
messages changes
    ↓
MessageList re-renders
    ↓
MessageList scrolls to bottom
```

After the simulated delay:

```text
setTimeout
    ↓
useChat pushes bot Message
    ↓
isTyping becomes false
    ↓
MessageList updates
    ↓
auto-scroll
```

This same flow can be reused when replacing the simulated backend with a real API.

---

# Scrolling Behavior

Scrolling is one of the most important implementation details in the UI.

## Requirement

The page itself must not scroll.

Only the conversation should scroll.

## How it works

The top-level shell uses:

```text
fixed
inset-0
h-dvh
overflow-hidden
```

The application wrapper uses:

```text
h-dvh
overflow-hidden
```

The glass panel uses:

```text
flex
flex-col
overflow-hidden
```

The content wrapper uses:

```text
flex-1
min-h-0
flex-col
overflow-hidden
```

The message viewport uses:

```text
flex-1
min-h-0
h-full
overflow-y-auto
overflow-x-hidden
```

This creates one bounded scroll container.

## Why `min-h-0` is important

In a CSS flex column, a child can otherwise maintain its minimum content height. That can cause the entire parent to expand with message content instead of allowing the message region to become scrollable.

Therefore the combination:

```text
flex-1 min-h-0 overflow-y-auto
```

is intentional.

## Avoid adding `overflow-auto` to parents

Do not casually change a parent into:

```text
overflow-auto
```

because that can reintroduce the outer scrollbar that this architecture is designed to prevent.

---

# Liquid Glass Styling

The liquid-glass effect is built from several ingredients rather than one CSS property.

## 1. Translucent white surfaces

Examples:

```text
bg-white/35
bg-white/38
bg-white/40
bg-white/[0.42]
bg-white/[0.48]
```

The opacity allows the ambient background to remain visible through the surface.

## 2. Backdrop blur

Examples:

```text
backdrop-blur-xl
backdrop-blur-2xl
backdrop-blur-[35px]
```

This blurs the background behind the translucent glass while keeping the foreground interface readable.

## 3. White edge highlights

Examples:

```text
border-white/60
border-white/65
border-white/70
border-white/75
```

These provide the visual edge of the glass.

## 4. Inset rings

Examples:

```text
ring-1 ring-inset ring-white/40
ring-1 ring-inset ring-white/25
```

They provide a thin secondary highlight inside the surface.

## 5. Soft shadows

The shadows use low-opacity blue-gray values instead of black.

For example:

```text
shadow-[0_25px_80px_rgba(80,100,140,0.12)]
```

This is important for the light theme. Heavy black shadows would make the interface feel like stacked boxes instead of translucent glass.

## 6. Internal refraction

The main panel contains large blurred shapes that are partly hidden behind it.

These provide the feeling that light exists inside/through the glass.

## 7. Rounded organic geometry

The application uses large corner radii such as:

```text
rounded-[36px]
rounded-[24px]
rounded-[20px]
rounded-[16px]
```

This makes the surfaces feel softer and more physical.

---

# Color System

The design does not require CSS variables to function, but the following palette describes the intended visual system.

| Role | Value |
|---|---|
| Main background | `#F3F6FA` |
| Cool ambient blue | `#C9DAFF` |
| Lavender ambient | `#E7D9FF` |
| Warm ambient | `#FFE5DC` |
| Primary text | `#293246` |
| Secondary text | `#8791A5` |
| User bubble | `#E7EEFF` |
| Primary accent | `#AFC8FF` |
| Secondary accent | `#B9AAFF` |

The important design rule is that the colors should remain **washed out**.

Avoid replacing them with fully saturated colors such as:

```text
#0000FF
#FF00FF
#00FFFF
```

because this immediately turns the visual language into a neon/cyber interface.

---

# Animations and Micro-interactions

Animation should support the interface rather than dominate it.

## Background pulse

Ambient background blobs use Tailwind's:

```text
animate-pulse
```

They have low visual contrast and large blur radii, so the animation is intentionally soft.

## New-chat button

The plus icon rotates using:

```text
group-hover:rotate-90
```

The button itself also lifts slightly:

```text
hover:-translate-y-0.5
```

## Send button

When active:

```text
hover:scale-[1.04]
active:scale-95
```

The arrow shifts slightly on hover:

```text
group-hover:-translate-y-0.5
group-hover:translate-x-0.5
```

## Message entry

`MessageList` uses Vue's `TransitionGroup`.

Messages appear with a small combination of:

```text
opacity
translateY
scale
```

The movement is only a few pixels so the messages do not look like they are flying into the interface.

## Typing indicator

The typing indicator uses three small Tailwind `animate-bounce` dots with staggered delays.

The visual rhythm suggests activity without displaying a conventional animated spinner.

---

# Responsive Behavior

The interface is designed for both desktop and mobile widths.

## Desktop

At larger widths:

- the glass window is capped at roughly 900px;
- the content receives larger horizontal padding;
- helper text such as `Enter to send` can be displayed.

## Mobile

At smaller widths:

- the glass window takes essentially the full available width;
- the surrounding page padding is reduced;
- the message area uses smaller horizontal padding;
- the interface remains inside the viewport;
- the chat region remains the only scrolling area.

The `sm:` Tailwind breakpoint is used to increase spacing once the viewport becomes wider.

---

# Keyboard Behavior

Current behavior:

| Key | Result |
|---|---|
| `Enter` | Sends the message |
| `Shift + Enter` | Inserts a newline |
| Mouse click on Send | Sends the message |

This is suitable for a conversational assistant where Enter-to-send is expected.

If multiline-first behavior is desired, reverse the rules so that Enter creates a newline and `Ctrl+Enter` or `Cmd+Enter` sends.

---

# Accessibility

The current implementation already includes several basic accessibility considerations.

## Semantic elements

The UI uses elements such as:

```html
<header>
<section>
<main>
<button>
<textarea>
```

rather than building the whole interface out of generic `div` elements.

## Button labels

The new-chat and send buttons use `aria-label` because they primarily contain iconography.

Examples:

```html
aria-label="New conversation"
```

and:

```html
aria-label="Send message"
```

## Focus

The textarea uses browser focus behavior rather than manually moving focus.

The glass background does not prevent the controls from being keyboard reachable.

## Recommended future improvements

For production use, consider adding:

- explicit visible focus rings;
- `aria-live="polite"` around assistant response announcements;
- a label associated with the textarea for screen readers;
- reduced-motion support;
- keyboard-accessible alternatives for every icon-only action.

---

# Connecting a Real Backend or LLM API

The visual components should not call the LLM directly.

A preferred architecture is:

```text
Vue frontend
    ↓
Your application API
    ↓
LLM / analysis service
```

Do not put secret provider API keys directly in the Vue frontend.

The browser should generally call your own backend endpoint instead.

For example:

```text
POST /api/chat
```

with:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the melting point?"
    }
  ]
}
```

The backend can then forward the request to the selected AI provider or scientific analysis service.

## Replacing the simulated response

The current composable conceptually does:

```ts
setTimeout(() => {
  messages.value.push(...);
}, 1200);
```

Replace this with a real asynchronous request.

For example:

```ts
const sendMessage = async () => {
  const text = inputText.value.trim();

  if (!text || isTyping.value) {
    return;
  }

  messages.value.push({
    id: crypto.randomUUID(),
    text,
    sender: "user",
    timestamp: new Date(),
  });

  inputText.value = "";
  isTyping.value = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: text,
      }),
    });

    if (!response.ok) {
      throw new Error("Chat request failed");
    }

    const data = await response.json();

    messages.value.push({
      id: crypto.randomUUID(),
      text: data.reply,
      sender: "bot",
      timestamp: new Date(),
    });
  } finally {
    isTyping.value = false;
  }
};
```

The UI components do not have to change for this basic integration.

---

# Streaming Responses

For an AI assistant, streaming is often preferable to waiting for the entire answer before updating the interface.

The recommended architecture is:

```text
User message
    ↓
POST /api/chat
    ↓
Backend starts LLM request
    ↓
Backend streams tokens/chunks
    ↓
Vue progressively updates one bot Message
```

Instead of pushing a complete response only once, create the assistant message first:

```ts
const botMessage: Message = {
  id: crypto.randomUUID(),
  text: "",
  sender: "bot",
  timestamp: new Date(),
};

messages.value.push(botMessage);
```

Then append received chunks to its `text` property.

This allows `MessageBubble` to update naturally because the underlying reactive `messages` data changed.

For example:

```ts
botMessage.text += chunk;
```

The same `MessageBubble` component can then render a streaming response without modification.

---

# Adding Rich Scientific Messages

For a scientific application, plain text will eventually become limiting.

A strong next step is to extend the message type.

For example:

```ts
export type MessageContent =
  | {
      type: "text";
      text: string;
    }
  | {
      type: "analysis";
      title: string;
      value: string;
      unit?: string;
      confidence?: number;
    }
  | {
      type: "chart";
      title: string;
      series: Array<{
        x: number;
        y: number;
      }>;
    };
```

Then:

```ts
export interface Message {
  id: string;
  sender: "user" | "bot";
  timestamp: Date;
  content: MessageContent[];
}
```

The message renderer can dispatch to components such as:

```text
MessageBubble
    ├── TextBlock
    ├── AnalysisCard
    ├── ChartCard
    └── DataTable
```

This would be particularly appropriate for a scientific/DSC workflow where an assistant may return:

```text
Melting point
123.86 °C

Confidence
94.2 %

Thermal event
Endothermic transition
```

alongside a DSC curve.

The same liquid-glass visual language can be reused for these cards.

---

# Customizing the Theme

The easiest way to modify the appearance is to change the Tailwind classes directly.

## Background

Change:

```text
bg-[#F3F6FA]
```

to another neutral background.

## Ambient blue

Change:

```text
bg-[#C9DAFF]/60
```

## Ambient lavender

Change:

```text
bg-[#E7D9FF]/55
```

## User bubble

Change:

```text
bg-[#E7EEFF]/55
```

## Send button

Change:

```text
from-[#AFC8FF]/80
```

and:

```text
to-[#B9AAFF]/75
```

## Main glass

The main surface is:

```text
bg-white/[0.42]
backdrop-blur-[35px]
border-white/60
```

Increasing the white opacity makes it more opaque and less glass-like.

Reducing it makes the background more visible.

Increasing blur produces a more frosted appearance.

Reducing blur exposes more background detail.

---

# Adding Features

Because state and presentation are separate, common features can be added without restructuring the entire interface.

## Conversation history

Store `messages` on the backend or in local storage.

The UI already accepts a complete `Message[]`, so persistent loading only requires populating that array.

## Loading previous sessions

Add an endpoint such as:

```text
GET /api/conversations/:id
```

Then load the returned messages into the composable before rendering.

## Conversation IDs

Extend the composable state with:

```ts
const conversationId = ref<string | null>(null);
```

This allows the backend to distinguish multiple sessions.

## Regenerate response

A future `MessageBubble` could expose:

```text
Regenerate
```

through an event such as:

```text
regenerate(messageId)
```

The view would forward the event to a composable method.

## Copy message

Add a small copy action to the message bubble.

Use the Clipboard API:

```ts
await navigator.clipboard.writeText(message.text);
```

The action can remain hidden until the user hovers the message to preserve the minimal design.

## Attachments

The composer can be extended with:

- file upload;
- image upload;
- PDF upload;
- drag and drop.

For a scientific application this could eventually be used to submit DSC files directly.

The attachment metadata should be represented separately from the simple `text` field.

---

# Performance Considerations

## Large message histories

The current implementation renders every message in the array.

For ordinary conversations this is acceptable.

For very large sessions, consider:

- virtual scrolling;
- paginating older messages;
- loading previous messages on demand;
- limiting the in-memory message window.

## Blur performance

Backdrop blur can be GPU-intensive on weaker devices.

The main glass panel currently uses:

```text
backdrop-blur-[35px]
```

and the composer uses:

```text
backdrop-blur-2xl
```

If performance is poor on mobile devices, reduce the blur amount before removing the glass effect entirely.

## Background blur

The ambient circles use large blur radii such as:

```text
blur-[100px]
blur-[110px]
blur-[120px]
```

These are visually effective but can be expensive on low-power devices.

Reducing their size or blur radius is a straightforward optimization.

## Animation

The animations are deliberately slow and low-contrast. Avoid adding many simultaneous transforms, especially to large translucent surfaces.

---

# Common Problems and Fixes

## Problem: Browser scrollbar appears

Check that the outer application is still using:

```text
fixed
inset-0
h-dvh
overflow-hidden
```

and that the main wrapper still has:

```text
h-dvh
overflow-hidden
```

The glass panel should also remain:

```text
overflow-hidden
```

Only `MessageList` should use:

```text
overflow-y-auto
```

## Problem: MessageList does not scroll

Ensure its parent flex hierarchy includes:

```text
flex
flex-1
min-h-0
```

The most common missing utility is `min-h-0`.

## Problem: Composer is pushed out of the glass panel

The likely cause is a missing `min-h-0` on the message area or an ancestor that is not a flex column.

The desired structure is:

```text
panel
└── content wrapper (flex-1 min-h-0 flex-col)
    ├── header
    ├── message list (flex-1 min-h-0)
    └── composer
```

## Problem: Glass looks too opaque

Reduce the white background opacity.

For example:

```text
bg-white/[0.42]
```

to:

```text
bg-white/[0.32]
```

## Problem: Glass looks too transparent

Increase the white opacity, for example:

```text
bg-white/[0.50]
```

## Problem: Design looks too colorful

Lower the opacity of the ambient circles.

The interface should primarily read as white/frosted glass, with color appearing through the glass rather than becoming the main UI surface.

## Problem: Design looks too flat

Increase:

- backdrop blur;
- the subtle white border;
- the internal highlight;
- the soft shadow.

Do not solve flatness by adding stronger saturated colors.

## Problem: Design feels too “robotic”

Remove technical labels, neon colors, heavy dark shadows, and dashboard-like metadata.

The current design is intentionally conversational and calm.

---

# Deployment Notes

The UI is a normal Vue frontend and can be deployed using any hosting platform compatible with the chosen Vue/Vite build pipeline.

For a real chatbot, the frontend normally needs access to an HTTPS backend endpoint.

Do not place private model-provider secrets in the built Vue application.

Environment variables prefixed for frontend exposure should be considered public unless the build system explicitly guarantees otherwise.

The recommended deployment structure is:

```text
Browser
   ↓ HTTPS
Frontend host
   ↓ HTTPS API request
Your backend
   ↓
LLM / scientific analysis service
```

---

# Recommended Extension Roadmap

A practical development order is:

## Stage 1 — UI

Already represented by the current component set:

- liquid-glass shell;
- responsive layout;
- message bubbles;
- typing state;
- composer;
- auto-scroll.

## Stage 2 — Backend

Add:

```text
POST /api/chat
```

and replace the simulated response.

## Stage 3 — Persistence

Add conversation IDs and persistent message history.

## Stage 4 — Streaming

Stream LLM output into an existing assistant message.

## Stage 5 — Rich scientific content

Add:

- charts;
- analysis cards;
- confidence indicators;
- tables;
- downloadable results.

## Stage 6 — Scientific file workflow

Potential workflow:

```text
Upload DSC file
      ↓
Python analysis service
      ↓
Extract thermal events
      ↓
LLM interprets analysis
      ↓
Vue renders scientific result
```

The current UI architecture is suitable for this because the message renderer can eventually support richer content types without requiring a complete rewrite of the application shell.

---

# Example Integration Contract

A useful future backend response could be:

```json
{
  "conversationId": "c_12345",
  "message": {
    "id": "m_98765",
    "sender": "bot",
    "text": "The main endothermic transition begins around 121.4 °C and reaches its maximum near 123.9 °C.",
    "timestamp": "2026-09-25T20:30:00.000Z"
  }
}
```

The frontend would transform that into the local `Message` type:

```ts
messages.value.push({
  id: response.message.id,
  text: response.message.text,
  sender: "bot",
  timestamp: new Date(response.message.timestamp),
});
```

The UI does not need to know how the model generated the response.

That separation is important.

---

# Component Contract Summary

The entire current interface can be understood as this contract:

```text
AuraChatView
│
├── owns application-level chat connection
│
└── AuraChatShell
    │
    ├── messages: Message[]
    ├── inputText: string
    ├── isTyping: boolean
    │
    ├── ChatHeader
    │      └── emits newChat
    │
    ├── MessageList
    │      ├── messages
    │      ├── isTyping
    │      └── MessageBubble × N
    │
    └── ChatComposer
           ├── modelValue
           ├── isTyping
           ├── emits update:modelValue
           └── emits send
```

This makes the responsibilities clear:

- the **view** connects application state;
- the **shell** composes the page;
- the **header** provides navigation-level chat actions;
- the **message list** controls the conversation viewport;
- the **message bubble** renders one message;
- the **composer** handles user input;
- the **composable** owns chat behavior.

---

# Final Notes

The key to preserving the visual quality of this interface is restraint.

The liquid-glass look depends on the interaction of:

```text
transparency
+ backdrop blur
+ soft light
+ low-contrast color
+ white highlights
+ large radii
+ gentle shadows
+ restrained motion
```

Increasing every value does not make the design more premium. In particular, stronger colors, heavier shadows, and more animation can quickly turn the interface into a generic “AI dashboard.”

For future scientific functionality, keep the same visual language for data-heavy UI elements. A DSC curve, melting-point result, confidence value, analysis explanation, or downloadable result can all be represented as translucent cards inside the same visual system.

The current architecture is deliberately small enough to understand, but modular enough to grow into a full scientific AI application.
