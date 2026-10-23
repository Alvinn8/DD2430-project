<script setup lang="ts">
defineProps<{ darkMode?: boolean }>();
</script>

<template>
  <div
    class="pointer-events-none fixed inset-0 z-0 h-dvh w-full overflow-hidden"
    :class="darkMode ? 'bg-[#0B1220]' : 'bg-[#F3F6FA]'"
  >
    <!-- Soft blue light -->
    <div
      class="absolute -left-32 -top-32 h-[30rem] w-[30rem] rounded-full blur-[100px] animate-pulse"
      :class="darkMode ? 'bg-[#294A83]/35' : 'bg-[#C9DAFF]/60'"
    />

    <!-- Soft lavender light -->
    <div
      class="absolute -right-40 top-[10%] h-[28rem] w-[28rem] rounded-full blur-[110px] animate-pulse [animation-delay:2s]"
      :class="darkMode ? 'bg-[#573D83]/30' : 'bg-[#E7D9FF]/55'"
    />

    <!-- Warm lower light -->
    <div
      class="absolute -bottom-40 left-[25%] h-[30rem] w-[30rem] rounded-full blur-[120px] animate-pulse [animation-delay:4s]"
      :class="darkMode ? 'bg-[#713E50]/22' : 'bg-[#FFE5DC]/45'"
    />

    <!-- Cool lower-right light -->
    <div
      class="absolute bottom-[5%] right-[-10rem] h-[24rem] w-[24rem] rounded-full blur-[110px]"
      :class="darkMode ? 'bg-[#1D5270]/28' : 'bg-[#D9E8FF]/40'"
    />

    <!-- Large white illumination -->
    <div
      class="absolute inset-0"
      :class="darkMode ? 'bg-[radial-gradient(circle_at_50%_0%,rgba(67,91,137,0.25),transparent_58%)]' : 'bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.95),transparent_58%)]'"
    />

    <!-- Very subtle center glow -->
    <div
      class="absolute left-1/2 top-1/2 h-[32rem] w-[32rem] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[150px]"
      :class="darkMode ? 'bg-[#7695D0]/10' : 'bg-white/20'"
    />
  </div>
</template>
<style scoped>
@keyframes float-one {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }

  50% {
    transform: translate3d(30px, 20px, 0);
  }
}

@keyframes float-two {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }

  50% {
    transform: translate3d(-25px, 30px, 0);
  }
}

@keyframes float-three {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }

  50% {
    transform: translate3d(20px, -25px, 0);
  }
}

.animate-float-one {
  animation: float-one 18s ease-in-out infinite;
}

.animate-float-two {
  animation: float-two 22s ease-in-out infinite;
}

.animate-float-three {
  animation: float-three 20s ease-in-out infinite;
}
</style>
