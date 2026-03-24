<template>
  <div class="app">
    <router-view />
  </div>
</template>

<style>
:root {
  --bg-gradient: radial-gradient(ellipse at top, #1c1d25 0%, #0f0f12 100%);
  --header-bg: rgba(24, 24, 28, 0.6);
  --header-border: rgba(255, 255, 255, 0.05);
  --text-primary: #f3f4f6;
  --text-secondary: #9ca3af;
  
  --user-bubble-bg: linear-gradient(135deg, #10b981 0%, #059669 100%);
  --user-bubble-text: #ffffff;
  
  --bot-bubble-bg: rgba(31, 41, 55, 0.7);
  --bot-bubble-border: rgba(255, 255, 255, 0.05);
  --bot-bubble-text: #e5e7eb;
  --bot-avatar-bg: linear-gradient(135deg, #047857 0%, #064e3b 100%);
  --bot-avatar-text: #ffffff;
  --bot-bubble-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);

  --user-avatar-bg: #374151;
  --user-avatar-text: #ffffff;

  --input-bg: rgba(31, 41, 55, 0.8);
  --input-border: rgba(255, 255, 255, 0.1);
  --input-text: #f3f4f6;
  --input-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);

  --btn-bg: rgba(55, 65, 81, 0.5);
  --btn-text: #9ca3af;
  
  --id-wrap-bg: rgba(0, 0, 0, 0.2);
  --id-wrap-border: rgba(255, 255, 255, 0.1);
}

* {
  box-sizing: border-box;
}

html, body, #app, .app {
  margin: 0;
  height: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg-gradient);
  color: var(--text-primary);
  transition: background 0.3s ease, color 0.3s ease;
}
</style>
