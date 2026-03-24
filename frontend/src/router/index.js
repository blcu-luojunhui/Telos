import { createRouter, createWebHistory } from 'vue-router'
import Auth from '../views/Auth.vue'
import Chat from '../views/Chat.vue'
import Monitor from '../views/Monitor.vue'
import OAuthCallback from '../views/OAuthCallback.vue'
import { getAuthToken, getAuthUserId } from '../api/auth'

const routes = [
  {
    path: '/',
    name: 'Login',
    component: Auth
  },
  {
    path: '/register',
    name: 'Register',
    component: Auth
  },
  {
    path: '/oauth/callback',
    name: 'OAuthCallback',
    component: OAuthCallback
  },
  {
    path: '/chat',
    name: 'Chat',
    component: Chat,
    meta: { requiresAuth: true }
  },
  {
    path: '/monitor',
    name: 'Monitor',
    component: Monitor,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userId = getAuthUserId()
  const token = getAuthToken()
  const authed = Boolean(userId && token)
  if (to.meta.requiresAuth && !authed) {
    next('/')
  } else if ((to.path === '/' || to.path === '/register') && authed) {
    next('/chat')
  } else {
    next()
  }
})

export default router
