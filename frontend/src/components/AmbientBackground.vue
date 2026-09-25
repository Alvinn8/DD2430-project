<template>
  <div
    class="pointer-events-none fixed inset-0 z-0 h-dvh w-full overflow-hidden bg-[#F3F6FA]"
  >
    <!-- Soft blue light -->
    <div
      class="absolute -left-32 -top-32 h-[30rem] w-[30rem] rounded-full bg-[#C9DAFF]/60 blur-[100px] animate-pulse"
    />

    <!-- Soft lavender light -->
    <div
      class="absolute -right-40 top-[10%] h-[28rem] w-[28rem] rounded-full bg-[#E7D9FF]/55 blur-[110px] animate-pulse [animation-delay:2s]"
    />

    <!-- Warm lower light -->
    <div
      class="absolute -bottom-40 left-[25%] h-[30rem] w-[30rem] rounded-full bg-[#FFE5DC]/45 blur-[120px] animate-pulse [animation-delay:4s]"
    />

    <!-- Cool lower-right light -->
    <div
      class="absolute bottom-[5%] right-[-10rem] h-[24rem] w-[24rem] rounded-full bg-[#D9E8FF]/40 blur-[110px]"
    />

    <!-- Large white illumination -->
    <div
      class="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.95),transparent_58%)]"
    />

    <!-- Very subtle center glow -->
    <div
      class="absolute left-1/2 top-1/2 h-[32rem] w-[32rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/20 blur-[150px]"
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
