# BetterMe 前端（Vue 3）

前后端分离的 Chat 对话页面，对接后端 `POST /v1/api/chat`。

## 开发

1. 安装依赖：

   ```bash
   cd frontend && npm install
   ```

2. 启动后端（在项目根目录）：

   ```bash
   # 端口需为 6666，与 vite.config.js 中 proxy 一致
   hypercorn app:app -c app.toml
   # 或
   python app.py  # 若已配置为 6666
   ```

3. 启动前端开发服务器：

   ```bash
   npm run dev
   ```

4. 浏览器打开：**http://localhost:5173**

前端会把 `/v1` 的请求代理到 `http://127.0.0.1:6666`，无需后端开 CORS。

## 构建

```bash
npm run build
```

产物在 `frontend/dist`，可部署到任意静态托管或由 Nginx 等反向代理到后端同一域名下。

## 生产环境

若前端与后端部署在不同域名，需在后端为 Quart 配置 CORS，允许前端源访问 `/v1/api/*`。
