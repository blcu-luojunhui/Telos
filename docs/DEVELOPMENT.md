# Telos 开发文档

[English Version](DEVELOPMENT_EN.md)

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                   Telos - Personal Life Agent               │
├─────────────────────────────────────────────────────────────┤
│  五层生命框架                                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  自我 → 爱 · 孤独 · 勇敢 · 意志 · 恐惧              │  │
│  │  生活 → 健康 · 学习 · 工作 · 习惯                   │  │
│  │  世界 → 观察 · 关系 · 现实 · 规律                   │  │
│  │  认知 → 反思 · 模型 · 信念 · 原则                   │  │
│  │  秩序 → 节律 · 原则 · 框架 · 方向                   │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Agent 层                                                   │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ 交互 → 决策 → 记忆 → 进化                           │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  个人画像                                                   │
│  价值观 · 目标 · 行为模式 · 认知 · 秩序                    │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

**后端**
- Python 3.11+
- Quart - 异步 Web 框架（异步版 Flask）
- LangChain - Agent 编排
- DeepSeek / OpenAI - LLM 服务

**数据存储**
- MySQL - 结构化数据
- Redis - 缓存层（规划中）
- Vector DB - 向量存储（规划中）

**前端**
- React Native - 跨平台移动端（规划中）

**部署**
- Docker - 容器化
- Docker Compose - 本地开发
- Kubernetes - 生产部署（规划中）

---

## 环境配置

### 前置要求

- Python 3.11+
- MySQL 8.0+
- Docker & Docker Compose（可选）
- Git

### 本地开发环境

1. **克隆项目**

```bash
git clone https://github.com/yourusername/telos.git
cd telos
```

2. **创建虚拟环境**

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```env
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=telos

# LLM API 配置
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key

# 应用配置
APP_ENV=development
LOG_LEVEL=INFO
```

5. **初始化数据库**

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE telos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 运行迁移（如果有）
python -m alembic upgrade head
```

6. **启动服务**

```bash
python -m src.main
```

服务将在 `http://localhost:8000` 启动。

---

## Docker 容器化

### 使用 Docker Compose（推荐）

最简单的方式是使用 Docker Compose 一键启动所有服务：

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 单独构建 Docker 镜像

```bash
# 构建镜像
docker build -t telos:latest .

# 运行容器
docker run -d \
  --name telos \
  -p 8000:8000 \
  --env-file .env \
  telos:latest
```

### Docker Compose 配置说明

`docker-compose.yml` 包含以下服务：

- **app**: Telos 主应用
- **mysql**: MySQL 数据库
- **redis**: Redis 缓存（规划中）

---

## 开发指南

### 项目结构

```
telos/
├── src/                    # 源代码
│   ├── main.py            # 应用入口
│   ├── api/               # API 路由
│   ├── core/              # 核心业务逻辑
│   ├── models/            # 数据模型
│   ├── services/          # 服务层
│   └── utils/             # 工具函数
├── tests/                 # 测试代码
├── docs/                  # 文档
├── assets/                # 静态资源
├── .env.example           # 环境变量模板
├── requirements.txt       # Python 依赖
├── Dockerfile            # Docker 镜像构建
├── docker-compose.yml    # Docker Compose 配置
└── README.md             # 项目说明
```

### 代码规范

- 遵循 PEP 8 Python 代码规范
- 使用 Black 进行代码格式化
- 使用 isort 管理导入顺序
- 使用 mypy 进行类型检查

```bash
# 格式化代码
black src/

# 排序导入
isort src/

# 类型检查
mypy src/
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_health.py

# 查看覆盖率
pytest --cov=src tests/
```

### Git 工作流

1. 从 `master` 分支创建功能分支
2. 开发并提交代码
3. 推送到远程仓库
4. 创建 Pull Request
5. 代码审查通过后合并

```bash
# 创建功能分支
git checkout -b feature/your-feature-name

# 提交代码
git add .
git commit -m "feat: add your feature"

# 推送到远程
git push origin feature/your-feature-name
```

---

## 部署

### 生产环境部署

（待补充：Kubernetes 部署配置）

### 环境变量配置

生产环境需要配置以下环境变量：

```env
APP_ENV=production
LOG_LEVEL=WARNING
MYSQL_HOST=your_production_db_host
# ... 其他生产配置
```

---

## 常见问题

### 数据库连接失败

检查 MySQL 服务是否启动，以及 `.env` 中的数据库配置是否正确。

### LLM API 调用失败

确认 API Key 是否正确配置，以及网络是否可以访问 API 服务。

### Docker 容器启动失败

查看容器日志：`docker-compose logs app`

---

## 贡献指南

这是一个个人项目，主要为自己服务。但如果你有兴趣参考或借鉴，欢迎：

- 提出 Issue 讨论想法
- Fork 项目进行自己的定制
- 分享你的使用心得

---

## 许可证

MIT License
