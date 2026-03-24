<template>
  <div class="lobster-avatar" :class="[`action-${currentAction}`]">
    <img
      src="/assets/lobster-avatar.png"
      alt=""
      class="lobster-img"
      aria-hidden="true"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({
  /** 动作类型: idle | sway | tap | pause | poke */
  action: { type: String, default: 'idle' },
})

const currentAction = ref(props.action)

function scheduleIdleReset() {
  if (!['tap', 'pause', 'poke'].includes(currentAction.value)) return
  const t = setTimeout(() => {
    currentAction.value = 'idle'
  }, 800)
  return () => clearTimeout(t)
}

watch(
  () => props.action,
  (next) => {
    currentAction.value = next
    scheduleIdleReset()
  },
  { immediate: false }
)

onMounted(() => {
  scheduleIdleReset()
})
</script>

<style scoped>
.lobster-avatar {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transform-origin: center center;
}

.lobster-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

/* 默认：轻微晃动 */
.lobster-avatar.action-idle .lobster-img {
  animation: lobster-idle 2.5s ease-in-out infinite;
}

/* 懒洋洋晃了晃 */
.lobster-avatar.action-sway .lobster-img {
  animation: lobster-sway 1.2s ease-in-out 2;
}

/* 不耐烦地敲了敲 */
.lobster-avatar.action-tap .lobster-img {
  animation: lobster-tap 0.25s ease-out 3;
}

/* 顿了一下 */
.lobster-avatar.action-pause .lobster-img {
  animation: lobster-pause 0.8s ease-in-out 1;
}

/* 戳了戳屏幕 */
.lobster-avatar.action-poke .lobster-img {
  animation: lobster-poke 0.6s ease-in-out 1;
}

@keyframes lobster-idle {
  0%, 100% { transform: translateY(0) rotate(-2deg); }
  50% { transform: translateY(-2px) rotate(2deg); }
}

@keyframes lobster-sway {
  0%, 100% { transform: translateX(0) rotate(0deg); }
  25% { transform: translateX(3px) rotate(8deg); }
  75% { transform: translateX(-3px) rotate(-8deg); }
}

@keyframes lobster-tap {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(0.92); }
}

@keyframes lobster-pause {
  0% { transform: scale(1); }
  15% { transform: scale(0.95); }
  30%, 70% { transform: scale(0.95); }
  100% { transform: scale(1); }
}

@keyframes lobster-poke {
  0% { transform: translateX(0); }
  40% { transform: translateX(8px); }
  100% { transform: translateX(0); }
}
</style>
