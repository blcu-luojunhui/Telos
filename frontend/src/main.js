import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')

// Force dark theme globally.
document.documentElement.setAttribute('data-theme', 'dark')
localStorage.setItem('betterme_theme', 'dark')
