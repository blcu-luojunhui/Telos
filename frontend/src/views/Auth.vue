<template>
  <div class="auth-page">
    <!-- page background stars -->
    <span
      v-for="s in bgStars" :key="'bg'+s.id"
      class="star-dot"
      :style="`left:${s.x}%;top:${s.y}%;width:${s.r}px;height:${s.r}px;animation-delay:${s.d}s;animation-duration:${s.t}s;`"
      aria-hidden="true"
    ></span>

    <div class="auth-shell">
      <section class="left-panel">
        <div class="left-copy">
          <p class="brand-tag">BETTERME</p>
          <h1 class="left-title">Build Yourself</h1>
          <p class="left-subtitle">Commitment to a continuous evolution.</p>
        </div>

        <div class="left-canvas-art" aria-hidden="true">
          <!-- left panel stars -->
          <span
            v-for="s in leftStars" :key="'lp'+s.id"
            class="star-dot star-dot--left"
            :style="`left:${s.x}%;top:${s.y}%;width:${s.r}px;height:${s.r}px;animation-delay:${s.d}s;animation-duration:${s.t}s;`"
            aria-hidden="true"
          ></span>
          <div class="heart-stage">
            <div class="heart-ripple ripple-1"></div>
            <div class="heart-ripple ripple-2"></div>
            <div class="heart-ripple ripple-3"></div>
            <img src="/assets/heart-anatomy-user-clean.png" alt="" class="heart-image" />
          </div>
        </div>
      </section>

      <section class="right-panel">
        <div class="tab-row">
          <button type="button" class="tab-btn" :class="{ active: !isRegister }" @click="setMode(false)">Login</button>
          <button type="button" class="tab-btn" :class="{ active: isRegister }" @click="setMode(true)">Register</button>
        </div>

        <h2 class="form-title">{{ isRegister ? 'Register' : 'Login' }}</h2>
        <p class="form-subtitle">{{ isRegister ? 'Create your BetterMe account' : 'Welcome Back to your Agent' }}</p>

        <form class="auth-form" @submit.prevent="submitAuth">
          <label class="field">
            <span class="field-label">Email / Username</span>
            <input
              v-model.trim="userId"
              type="text"
              placeholder="Email / Username"
              required
              autocomplete="username"
            />
          </label>

          <label class="field">
            <div class="field-label-row">
              <span class="field-label">Password</span>
              <button type="button" class="forgot-link">{{ isRegister ? 'At least 6 characters' : 'Forgot Password?' }}</button>
            </div>
            <input
              v-model="password"
              type="password"
              placeholder="Password"
              required
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
            />
          </label>

          <div class="strength-wrap" v-if="password.length > 0">
            <div class="strength-head">
              <span>Password Strength</span>
              <span>{{ strengthLabel }}</span>
            </div>
            <div class="strength-track">
              <div class="strength-fill" :style="{ width: `${strengthPercent}%` }" :class="strengthClass" />
            </div>
          </div>

          <label v-if="isRegister" class="field">
            <span class="field-label">Confirm Password</span>
            <input
              v-model="confirmPassword"
              type="password"
              placeholder="Confirm Password"
              required
              autocomplete="new-password"
            />
          </label>

          <p v-if="errorText" class="error-text">{{ errorText }}</p>

          <button class="submit-btn" type="submit" :disabled="submitDisabled">
            {{ loading ? (isRegister ? 'REGISTERING...' : 'LOGGING IN...') : isRegister ? 'REGISTER' : 'LOGIN' }}
          </button>
        </form>

        <div class="social-block">
          <p class="social-title">Alternative Login</p>
          <div class="social-row">
            <button type="button" class="social-btn" @click="quickLogin('apple')" aria-label="Apple login">
              <svg class="apple-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path fill="currentColor" d="M16.66 3.24c.66-.8 1.12-1.91.99-3.03-1 .04-2.22.67-2.95 1.47-.66.73-1.24 1.85-1.09 2.93 1.11.08 2.24-.56 3.05-1.37ZM20.93 18.16c-.43.98-.64 1.42-1.19 2.3-.77 1.23-1.85 2.78-3.2 2.79-1.2.02-1.52-.78-3.15-.77-1.63.01-1.98.79-3.18.77-1.35-.01-2.38-1.4-3.15-2.62-2.16-3.43-2.39-7.45-1.06-9.47.94-1.44 2.43-2.29 3.84-2.29 1.43 0 2.32.79 3.49.79 1.14 0 1.84-.79 3.48-.79 1.26 0 2.6.69 3.54 1.89-3.1 1.7-2.59 6.15.58 7.4Z"/>
              </svg>
            </button>
            <button type="button" class="social-btn google" @click="quickLogin('google')" aria-label="Google login">
              <svg class="google-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#EA4335" d="M12 10.23v3.9h5.42c-.22 1.26-1.55 3.7-5.42 3.7-3.26 0-5.92-2.69-5.92-6s2.66-6 5.92-6c1.86 0 3.11.79 3.83 1.48l2.61-2.52C16.76 3.27 14.58 2.4 12 2.4 6.93 2.4 2.82 6.51 2.82 11.57S6.93 20.74 12 20.74c5.3 0 8.81-3.73 8.81-8.98 0-.6-.06-1.05-.14-1.53H12Z"/>
                <path fill="#34A853" d="M3.88 7.37l3.21 2.35c.87-1.72 2.67-2.9 4.91-2.9 1.86 0 3.11.79 3.83 1.48l2.61-2.52C16.76 3.27 14.58 2.4 12 2.4 8.47 2.4 5.43 4.39 3.88 7.37Z"/>
                <path fill="#4A90E2" d="M12 20.74c2.52 0 4.64-.83 6.18-2.26l-2.85-2.33c-.76.54-1.79.92-3.33.92-2.24 0-4.14-1.5-4.83-3.57l-3.28 2.53C5.41 18.86 8.47 20.74 12 20.74Z"/>
                <path fill="#FBBC05" d="M3.88 7.37A9.12 9.12 0 0 0 2.82 11.57c0 1.48.35 2.89 1.06 4.16l3.28-2.53a5.9 5.9 0 0 1 0-3.26L3.88 7.37Z"/>
              </svg>
            </button>
          </div>
          <p class="switch-link">
            {{ isRegister ? 'Already have an account?' : "Don't have an account?" }}
            <button type="button" @click="setMode(!isRegister)">
              {{ isRegister ? 'Go to Login' : 'Go to Register' }}
            </button>
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loginWithUserId, registerWithUserId, setAuthSession, startOAuth } from '../api/auth'

// deterministic pseudo-random (no Math.random so values are stable across renders)
function seededRand(seed) {
  let s = seed
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280 }
}

function makeStars(count, seed) {
  const rand = seededRand(seed)
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    x: rand() * 100,
    y: rand() * 100,
    r: rand() * 2.2 + 0.8,
    d: rand() * 5,
    t: rand() * 2.5 + 2,
  }))
}

const bgStars   = makeStars(520, 1337)  // page background (ultra dense full-screen)
const leftStars = makeStars(220, 4219)  // left panel canvas (ultra dense)

const route = useRoute()
const router = useRouter()

const isRegister = ref(route.path === '/register')
const userId = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorText = ref('')

watch(
  () => route.path,
  (next) => {
    isRegister.value = next === '/register'
    errorText.value = ''
  }
)

const strengthScore = computed(() => {
  const value = password.value
  let score = 0
  if (value.length >= 8) score += 25
  if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 25
  if (/\d/.test(value)) score += 25
  if (/[^A-Za-z0-9]/.test(value)) score += 25
  if (value.length >= 14) score += 10
  return Math.min(score, 100)
})

const strengthPercent = computed(() => Math.max(8, strengthScore.value))

const strengthLabel = computed(() => {
  if (strengthScore.value < 35) return 'Weak'
  if (strengthScore.value < 65) return 'Medium'
  if (strengthScore.value < 85) return 'Strong'
  return 'Very Strong'
})

const strengthClass = computed(() => {
  if (strengthScore.value < 35) return 'level-1'
  if (strengthScore.value < 65) return 'level-2'
  if (strengthScore.value < 85) return 'level-3'
  return 'level-4'
})

const submitDisabled = computed(() => {
  if (loading.value) return true
  if (!userId.value || !password.value) return true
  if (!isRegister.value) return false
  return !confirmPassword.value
})

const setMode = (nextRegister) => {
  if (loading.value) return
  const path = nextRegister ? '/register' : '/'
  if (path === route.path) return
  router.push(path)
}

const submitAuth = async () => {
  if (submitDisabled.value) return
  errorText.value = ''
  if (isRegister.value && password.value !== confirmPassword.value) {
    errorText.value = 'Passwords do not match'
    return
  }
  loading.value = true
  try {
    const data = isRegister.value
      ? await registerWithUserId(userId.value, password.value)
      : await loginWithUserId(userId.value, password.value)
    setAuthSession({
      userId: data.user_id || userId.value,
      token: data.token || '',
    })
    router.push('/chat')
  } catch (e) {
    if (isRegister.value && e && e.status === 409) {
      errorText.value = e.message || 'User ID already exists, please log in directly'
    } else {
      errorText.value = e.message || (isRegister.value ? 'Registration failed, please try again later' : 'Login failed, please try again later')
    }
  } finally {
    loading.value = false
  }
}

const quickLogin = (provider) => {
  if (loading.value) return
  const redirectUri = `${window.location.origin}/oauth/callback?provider=${provider}`
  startOAuth(provider, redirectUri)
    .then((payload) => {
      const stateKey = `betterme_oauth_state_${provider}`
      localStorage.setItem(stateKey, payload.state || '')
      window.location.href = payload.authorize_url
    })
    .catch((e) => {
      alert(e.message || 'Failed to start OAuth, please try again later')
    })
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  min-height: 100dvh;
  background:
    radial-gradient(ellipse at 68% 32%, rgba(30, 88, 176, 0.28), transparent 48%),
    radial-gradient(ellipse at 18% 72%, rgba(16, 54, 136, 0.16), transparent 40%),
    linear-gradient(145deg, #070f24 0%, #0a1530 56%, #0c1a38 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: #cbd5e1;
  position: relative;
  overflow: hidden;
}

/* ── twinkling star dots (generated by script) ── */
@keyframes twinkle {
  0%, 100% { opacity: 0.15; transform: scale(0.75); }
  50%       { opacity: 1;    transform: scale(1.35); }
}

.star-dot {
  position: absolute;
  border-radius: 50%;
  background: rgba(200, 225, 255, 0.85);
  pointer-events: none;
  z-index: 0;
  animation: twinkle linear infinite;
  will-change: opacity, transform;
}

.star-dot--left {
  position: absolute;
  background: rgba(170, 210, 255, 0.9);
  z-index: 1;
}

.auth-shell {
  width: min(1210px, calc(100vw - 20px));
  min-height: clamp(700px, 88vh, 820px);
  background: transparent;
  border: none;
  border-radius: 30px;
  overflow: hidden;
  box-shadow: none;
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  position: relative;
  z-index: 1;
}

.left-panel {
  padding: clamp(30px, 3.2vw, 44px);
  border-bottom: 1px solid transparent;
  background: #13224a;
  border-radius: 30px 0 0 30px;
  border: none;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  position: relative;
  overflow: hidden;
}

.left-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 54% 64%, rgba(98, 142, 255, 0.13), transparent 52%),
    radial-gradient(ellipse at 46% 58%, rgba(136, 88, 230, 0.1), transparent 44%);
  pointer-events: none;
  z-index: 1;
}

.left-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  background: transparent;
  pointer-events: none;
}

.left-copy {
  max-width: 430px;
  position: relative;
  z-index: 3;
}

.brand-tag {
  margin: 0 0 14px;
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(198, 214, 244, 0.68);
}

.left-title {
  margin: 0;
  font-size: clamp(2.06rem, 3.1vw, 2.6rem);
  line-height: 1.15;
  letter-spacing: -0.015em;
  color: #f6f8ff;
  font-family: "Playfair Display", "Cormorant Garamond", "Times New Roman", serif;
  font-weight: 650;
  text-shadow: 0 5px 14px rgba(96, 120, 211, 0.16);
}

.left-subtitle {
  margin: 14px 0 0;
  color: rgba(170, 189, 225, 0.74);
  font-size: 0.95rem;
  font-weight: 350;
  line-height: 1.6;
  max-width: 360px;
}

.left-canvas-art {
  position: relative;
  margin-top: clamp(34px, 6vh, 62px);
  min-height: clamp(250px, 40vh, 360px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

/* .left-stars removed – replaced by .star-dot--left spans */

.heart-stage {
  position: relative;
  width: clamp(306px, 39vw, 468px);
  aspect-ratio: 1024 / 1000;
  border-radius: 26px;
  border: none;
  background: #13224a;
  box-shadow: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.heart-stage::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 2;
  background: transparent;
  pointer-events: none;
}

.heart-stage::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 4;
  background: transparent;
  pointer-events: none;
}

.heart-ripple {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid rgba(155, 224, 255, 0.34);
  box-shadow: 0 0 14px rgba(95, 170, 255, 0.12);
  z-index: 3;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.4) 18%, rgba(0, 0, 0, 1) 35%, rgba(0, 0, 0, 1) 65%, rgba(0, 0, 0, 0.4) 82%, transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.4) 18%, rgba(0, 0, 0, 1) 35%, rgba(0, 0, 0, 1) 65%, rgba(0, 0, 0, 0.4) 82%, transparent 100%);
}

.ripple-1 {
  width: 48%;
  height: 48%;
}

.ripple-2 {
  width: 66%;
  height: 66%;
  opacity: 0.58;
}

.ripple-3 {
  width: 84%;
  height: 84%;
  opacity: 0.4;
}

.heart-image {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  max-width: none;
  user-select: none;
  pointer-events: none;
  object-fit: contain;
  object-position: center;
  filter:
    saturate(0.95)
    brightness(0.99)
    contrast(0.96)
    drop-shadow(0 0 10px rgba(122, 177, 255, 0.2));
}


.right-panel {
  background:
    radial-gradient(ellipse at 50% 0%, rgba(72, 148, 238, 0.36), transparent 54%),
    linear-gradient(180deg, rgba(28, 68, 148, 0.78) 0%, rgba(14, 36, 88, 0.72) 100%);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  border-radius: 0 30px 30px 0;
  border: 1px solid rgba(156, 202, 255, 0.22);
  border-left: 1px solid rgba(156, 202, 255, 0.18);
  padding: clamp(30px, 3.2vw, 44px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow-y: auto;
  box-shadow:
    inset 1px 0 0 rgba(180, 218, 255, 0.14),
    inset 0 1px 0 rgba(200, 228, 255, 0.16),
    0 0 60px rgba(20, 60, 160, 0.2);
}

.tab-row {
  display: flex;
  gap: 8px;
  margin-bottom: 22px;
}

.tab-btn {
  border: 1px solid rgba(180, 214, 255, 0.28);
  background: rgba(150, 196, 255, 0.12);
  color: #d8ecff;
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn.active {
  background: linear-gradient(90deg, #3574e2, #5060d4);
  border-color: rgba(160, 195, 255, 0.8);
  color: #fff;
  box-shadow: 0 6px 18px rgba(48, 96, 210, 0.36);
}

.form-title {
  margin: 0;
  font-size: clamp(2rem, 2.4vw, 2.3rem);
  line-height: 1.08;
  color: #f4f8ff;
  font-family: "Playfair Display", "Cormorant Garamond", "Times New Roman", serif;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.form-subtitle {
  margin: 6px 0 22px;
  color: rgba(166, 186, 221, 0.92);
  font-size: 0.875rem;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  color: rgba(194, 213, 247, 0.82);
  font-size: 12px;
  font-weight: 600;
}

.forgot-link {
  border: none;
  background: transparent;
  color: #8eb7ff;
  cursor: pointer;
  padding: 0;
  font-size: 12px;
  text-decoration: none;
}

.field input {
  width: 100%;
  background: rgba(180, 212, 255, 0.1);
  border: 1px solid rgba(170, 210, 255, 0.3);
  border-radius: 12px;
  color: #eaf3ff;
  padding: 12px 14px;
  font-size: 14px;
  outline: none;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.22s ease;
}

.field input::placeholder {
  color: rgba(190, 218, 248, 0.52);
}

.field input:focus {
  border-color: rgba(148, 196, 255, 0.82);
  box-shadow:
    0 0 0 2px rgba(80, 148, 255, 0.3),
    0 0 18px rgba(80, 148, 255, 0.16);
}

.strength-wrap {
  border-radius: 10px;
  padding: 8px 10px 10px;
  border: 1px solid rgba(52, 91, 70, 0.65);
  background: rgba(10, 31, 23, 0.55);
}

.strength-head {
  display: flex;
  justify-content: space-between;
  color: #b0d9c0;
  font-size: 12px;
  margin-bottom: 7px;
}

.strength-track {
  height: 7px;
  border-radius: 999px;
  background: rgba(18, 47, 35, 0.9);
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.25s ease;
}

.strength-fill.level-1 {
  background: linear-gradient(90deg, #14532d, #1c6c3a);
  box-shadow: 0 0 12px rgba(27, 106, 58, 0.55);
}

.strength-fill.level-2 {
  background: linear-gradient(90deg, #17653a, #20864a);
  box-shadow: 0 0 14px rgba(35, 125, 68, 0.6);
}

.strength-fill.level-3 {
  background: linear-gradient(90deg, #1f8a4d, #2cb05f);
  box-shadow: 0 0 15px rgba(46, 165, 92, 0.62);
}

.strength-fill.level-4 {
  background: linear-gradient(90deg, #2aa861, #39d07a);
  box-shadow: 0 0 17px rgba(72, 207, 120, 0.65);
}

.error-text {
  margin: 0;
  color: #ff7f7f;
  font-size: 13px;
}

.submit-btn {
  margin-top: 4px;
  width: 100%;
  border: none;
  border-radius: 12px;
  padding: 12px 0;
  color: #e2e8f0;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 13px;
  background: linear-gradient(90deg, #2d6be0, #4d5ed4 55%, #5648cc 100%);
  cursor: pointer;
  box-shadow: 0 12px 28px rgba(36, 88, 220, 0.4);
  transition: opacity 0.2s ease, transform 0.2s ease;
  flex-shrink: 0;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.social-block {
  margin-top: 20px;
  text-align: center;
  flex-shrink: 0;
}

.social-title {
  margin: 0 0 14px;
  color: rgba(191, 210, 244, 0.62);
  font-size: 12px;
}

.social-row {
  display: flex;
  justify-content: center;
  gap: 14px;
}

.social-btn {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  border: 1px solid rgba(168, 204, 255, 0.28);
  background: linear-gradient(180deg, rgba(180, 212, 255, 0.18), rgba(140, 178, 240, 0.08));
  color: #e2e8f0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.social-btn svg {
  width: 19px;
  height: 19px;
}

.apple-icon {
  color: #f8fafc;
}

.google-icon {
  width: 20px;
  height: 20px;
}

.social-btn:hover {
  background: linear-gradient(180deg, rgba(200, 224, 255, 0.26), rgba(164, 192, 248, 0.12));
  transform: translateY(-1px);
  border-color: rgba(191, 219, 254, 0.5);
}

.switch-link {
  margin: 20px 0 0;
  color: rgba(198, 214, 242, 0.72);
  font-size: 12px;
  line-height: 1.5;
}

.switch-link button {
  border: none;
  background: transparent;
  color: #f3f7ff;
  cursor: pointer;
  font-weight: 700;
}

@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
    width: min(960px, calc(100vw - 20px));
    min-height: auto;
  }

  .left-panel {
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    border-bottom: none;
    border-radius: 30px 30px 0 0;
    padding: 28px 22px;
  }

  .right-panel {
    border-radius: 0 0 30px 30px;
    border-top: 1px solid rgba(156, 202, 255, 0.18);
  }

  .left-canvas-art {
    margin-top: 22px;
    min-height: 230px;
  }

  .heart-stage {
    width: min(420px, 88vw);
  }

  .heart-image {
    width: 100%;
    height: 100%;
    transform: none;
  }

  .right-panel {
    padding: 28px 22px;
    overflow-y: visible;
  }

  .form-title,
  .left-title {
    font-size: 2rem;
  }
}
</style>
