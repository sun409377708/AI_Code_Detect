# 📁 项目结构说明

## 📋 目录

- [目录结构](#目录结构)
- [核心文件](#核心文件)
- [数据库结构](#数据库结构)
- [API 端点](#api-端点)
- [数据流向](#数据流向)
- [依赖关系](#依赖关系)
- [部署配置](#部署配置)

---

## 📂 目录结构

```
pr-agent-dashboard/
├── app.py                      # Flask 应用主文件 (75KB)
├── requirements.txt            # Python 依赖
├── start.sh                    # 启动脚本
├── README.md                   # 项目说明
├── FEATURES.md                 # 功能说明文档
├── PROJECT_STRUCTURE.md        # 本文件
├── templates/                  # HTML 模板目录
│   └── index.html             # 主页面 (60KB)
├── static/                     # 静态资源目录
│   ├── css/                   # 样式文件
│   ├── js/                    # JavaScript 文件
│   └── images/                # 图片资源
├── reviews.db                  # SQLite 数据库
├── history.json               # 审查历史记录
└── prompts.json               # 自定义 Prompt

pr-agent-test/
└── .env                       # 环境配置文件
```

---

## 📄 核心文件

### **app.py - Flask 应用主文件**

| 模块分类 | 函数/端点 | 说明 |
|---------|----------|------|
| **数据库管理** | `init_database()` | 初始化 SQLite 数据库 |
| | `record_review()` | 记录审查到数据库 |
| **配置管理** | `load_env_config()` | 加载 .env 配置 |
| | `get_gitlab_token()` | 获取 GitLab Token |
| | `get_gitlab_url()` | 获取 GitLab URL |
| | `get_china_time()` | 获取中国时区时间 |
| **MR 审查** | `review_mr()` | 手动触发 MR 审查 |
| | `review_mr_from_webhook()` | Webhook 触发 MR 审查 |
| | `has_mr_been_reviewed()` | 检查 MR 是否已审查 |
| | `should_auto_review_mr()` | 判断是否需要审查 MR |
| **Commit 审查** | `review_commit()` | 手动触发 Commit 审查 |
| | `review_commit_from_webhook()` | Webhook 触发 Commit 审查 |
| | `has_commit_been_reviewed()` | 检查 Commit 是否已审查 |
| | `should_auto_review_push()` | 判断是否需要审查 Push |
| **Webhook 处理** | `gitlab_webhook()` | Webhook 入口 |
| | `handle_mr_webhook()` | 处理 MR Webhook 事件 |
| | `handle_push_webhook()` | 处理 Push Webhook 事件 |
| **历史记录** | `save_history()` | 保存审查历史 |

### **index.html - 主页面模板**

| 功能区域 | 组件 | 说明 |
|---------|------|------|
| **导航栏** | 顶部导航 | 项目浏览、Webhook 管理、报表、配置 |
| **Webhook 配置** | `webhookDialog` | 批量配置 Webhook 对话框 |
| | 组选择器 | 选择 GitLab 组 |
| | 项目列表 | 显示组内项目 |
| | 批量操作 | 全选、配置、进度显示 |
| **已配置项目** | `configuredProjectsDialog` | 查看已配置项目对话框 |
| | 项目列表 | 显示已配置的项目 |
| | 状态检测 | Webhook 状态显示 |
| | 批量删除 | 批量删除 Webhook |
| **审查报表** | `reviewReportDialog` | 审查报表对话框 |
| | 时间筛选 | 日期范围选择 |
| | 类型筛选 | MR/Commit 筛选 |
| | 数据展示 | 表格展示审查记录 |
| **自动审查配置** | `autoReviewConfigDialog` | 自动审查配置对话框 |
| | MR 配置 | MR 审查开关和选项 |
| | Push 配置 | Commit 审查开关和选项 |
| | 保存/加载 | 配置保存和加载 |

### **.env - 环境配置文件**

| 配置分类 | 配置项 | 示例值 | 说明 |
|---------|-------|-------|------|
| **GitLab** | `CONFIG__GIT_PROVIDER` | `gitlab` | Git 提供商 |
| | `GITLAB__URL` | `http://gitlab.it.ikang.com` | GitLab 服务器地址 |
| | `GITLAB__PERSONAL_ACCESS_TOKEN` | `glpat-xxx` | GitLab 访问令牌 |
| **AI 配置** | `OPENAI__KEY` | `sk-xxx` | 通义千问 API Key |
| | `OPENAI__API_BASE` | `https://dashscope.aliyuncs.com/...` | API 基础地址 |
| | `CONFIG__MODEL` | `openai/qwen-plus` | AI 模型 |
| | `CONFIG__RESPONSE_LANGUAGE` | `zh-CN` | 响应语言 |
| **MR 审查** | `AUTO_REVIEW_ENABLED` | `true` | 启用 MR 自动审查 |
| | `AUTO_REVIEW_TARGET_BRANCHES` | `*` | 目标分支 |
| | `AUTO_REVIEW_SKIP_DRAFT` | `false` | 跳过 Draft MR |
| | `AUTO_REVIEW_MIN_CHANGES` | `0` | 最小变更行数 |
| **Commit 审查** | `AUTO_REVIEW_PUSH_ENABLED` | `true` | 启用 Commit 审查 |
| | `AUTO_REVIEW_PUSH_BRANCHES` | `*` | 审查分支 |
| | `AUTO_REVIEW_PUSH_NEW_BRANCH_ALL_COMMITS` | `false` | 新分支历史审查 |

---

## 🗄️ 数据库结构

### **reviews.db - SQLite 数据库**

#### **表：review_records**

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| `type` | TEXT | NOT NULL | 审查类型：'mr' 或 'commit' |
| `project_id` | INTEGER | NOT NULL | GitLab 项目 ID |
| `project_name` | TEXT | NOT NULL | 项目名称（路径） |
| `title` | TEXT | NOT NULL | MR 标题或 Commit 消息 |
| `url` | TEXT | NOT NULL | GitLab URL |
| `author` | TEXT | NOT NULL | 作者姓名 |
| `branch` | TEXT | - | 分支名称 |
| `timestamp` | DATETIME | - | 审查时间（中国时区） |
| `details` | TEXT | - | JSON 格式的详细信息 |

#### **索引**

| 索引名 | 字段 | 用途 |
|-------|------|------|
| `idx_project_type` | `project_id, type` | 加快项目审查查询 |
| `idx_timestamp` | `timestamp` | 加快时间范围查询 |

#### **示例数据**

```sql
INSERT INTO review_records VALUES (
    1,                                    -- id
    'mr',                                 -- type
    123,                                  -- project_id
    'dytsh/iosdytsh/new_doctor',        -- project_name
    'Draft: Develop 1.9.3 webhook test', -- title
    'http://gitlab.../merge_requests/3', -- url
    'Unknown',                            -- author
    'develop',                            -- branch
    '2025-11-11 15:30:45',               -- timestamp
    '{"action":"open","iid":3}'          -- details
);
```

### **history.json - 审查历史**

| 字段 | 类型 | 说明 |
|------|------|------|
| `mr_url` | string | MR URL |
| `status` | string | 审查状态：'success' 或 'failed' |
| `output` | string | 审查输出（前 1000 字符） |
| `timestamp` | string | ISO 格式时间戳 |

**示例：**

```json
[
  {
    "mr_url": "http://gitlab.../merge_requests/1",
    "status": "success",
    "output": "审查完成...",
    "timestamp": "2025-11-11T15:30:00+08:00"
  }
]
```

---

## 🔌 API 端点

### **Webhook 管理 API**

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/api/webhook/groups` | GET | 获取 GitLab 组列表 | - |
| `/api/webhook/group-projects/<group_id>` | GET | 获取组内项目 | `webhook_url` (query) |
| `/api/webhook/batch-setup` | POST | 批量配置 Webhook | `project_ids`, `webhook_url`, `webhook_secret` |
| `/api/webhook/batch-delete` | POST | 批量删除 Webhook | `project_ids`, `webhook_url` |
| `/api/webhook/check-config` | POST | 检查 Webhook 配置 | `project_id`, `webhook_url` |

### **审查管理 API**

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/api/review` | POST | 手动触发 MR 审查 | `mr_url`, `mr_id` |
| `/api/review/status/<mr_id>` | GET | 获取审查状态 | - |
| `/api/review/commit` | POST | 手动触发 Commit 审查 | `commit_url`, `commit_id` |
| `/api/review/report` | GET | 获取审查报表 | `date_from`, `date_to`, `type` |

### **配置管理 API**

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/api/config` | GET | 获取配置信息 | - |
| `/api/config` | POST | 更新配置 | 配置键值对 |
| `/api/config/test` | POST | 测试配置连接 | `gitlab_url`, `gitlab_token` |
| `/api/auto-review/config` | GET | 获取自动审查配置 | - |
| `/api/auto-review/config` | POST | 更新自动审查配置 | 配置键值对 |

### **Webhook 接收端点**

| 端点 | 方法 | 说明 | 触发事件 |
|------|------|------|---------|
| `/webhook/gitlab` | POST | 接收 GitLab Webhook | Merge Request Hook, Push Hook |

---

## 🔄 数据流向

### **Webhook 触发流程**

```
┌─────────────┐
│   GitLab    │
└──────┬──────┘
       │ Webhook (POST)
       ↓
┌─────────────────────────────────────┐
│  Flask App (app.py)                 │
│  ┌───────────────────────────────┐  │
│  │ gitlab_webhook()              │  │
│  │   ↓                           │  │
│  │ handle_mr_webhook() /         │  │
│  │ handle_push_webhook()         │  │
│  │   ↓                           │  │
│  │ should_auto_review_*()        │  │
│  │   ↓                           │  │
│  │ record_review()               │  │
│  │   ↓                           │  │
│  │ review_*_from_webhook()       │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────┬───────────┘
       │                  │
       ↓                  ↓
┌─────────────┐    ┌─────────────┐
│ reviews.db  │    │ PR-Agent /  │
│             │    │ AI API      │
└─────────────┘    └──────┬──────┘
                          │
                          ↓
                   ┌─────────────┐
                   │   GitLab    │
                   │ (发布评论)   │
                   └─────────────┘
```

### **Web 界面流程**

```
┌─────────────┐
│   浏览器     │
└──────┬──────┘
       │ HTTP Request
       ↓
┌─────────────────────────────────────┐
│  index.html                         │
│  ┌───────────────────────────────┐  │
│  │ JavaScript (AJAX)             │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────────────────┘
       │ Fetch API
       ↓
┌─────────────────────────────────────┐
│  Flask API (app.py)                 │
│  ┌───────────────────────────────┐  │
│  │ /api/webhook/*                │  │
│  │ /api/review/*                 │  │
│  │ /api/config/*                 │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────┬───────────┘
       │                  │
       ↓                  ↓
┌─────────────┐    ┌─────────────┐
│ reviews.db  │    │ GitLab API  │
└─────────────┘    └─────────────┘
       │
       ↓
┌─────────────────────────────────────┐
│  返回 JSON                           │
└──────┬──────────────────────────────┘
       │
       ↓
┌─────────────┐
│  浏览器显示  │
└─────────────┘
```

---

## 📦 依赖关系

### **Python 依赖**

| 包名 | 版本 | 用途 |
|------|-----|------|
| `Flask` | 2.x | Web 框架 |
| `requests` | 2.x | HTTP 请求库 |
| `sqlite3` | 内置 | 数据库 |
| `subprocess` | 内置 | 执行外部命令 |
| `threading` | 内置 | 多线程处理 |
| `datetime` | 内置 | 时间处理 |
| `json` | 内置 | JSON 处理 |

### **外部服务依赖**

| 服务 | 地址 | 用途 |
|------|------|------|
| **GitLab** | `http://gitlab.it.ikang.com` | 代码托管平台 |
| **通义千问 API** | `https://dashscope.aliyuncs.com` | AI 代码审查 |
| **Docker** | 本地 | 运行 PR-Agent |
| **PR-Agent** | `codiumai/pr-agent:latest` | 代码审查工具 |

### **依赖关系图**

```
Flask App
    ├─ GitLab API (必需)
    │   ├─ 获取项目列表
    │   ├─ 配置 Webhook
    │   ├─ 获取代码 diff
    │   └─ 发布评论
    │
    ├─ 通义千问 API (必需)
    │   └─ AI 代码审查
    │
    ├─ Docker (可选)
    │   └─ PR-Agent 容器
    │
    └─ SQLite (必需)
        └─ 审查记录存储
```

---

## 🚀 部署配置

### **服务端口**

| 服务 | 端口 | 用途 |
|------|-----|------|
| **Flask App** | 8080 | Web 服务 |
| **GitLab** | 80/443 | GitLab 服务器 |

### **访问地址**

| 类型 | 地址 | 说明 |
|------|------|------|
| **Web 界面** | `http://10.108.2.73:8080` | 管理界面 |
| **Webhook** | `http://10.108.2.73:8080/webhook/gitlab` | Webhook 接收地址 |
| **API** | `http://10.108.2.73:8080/api/*` | API 端点 |

### **环境变量**

| 变量 | 必需 | 说明 |
|------|-----|------|
| `GITLAB__URL` | ✅ | GitLab 服务器地址 |
| `GITLAB__PERSONAL_ACCESS_TOKEN` | ✅ | GitLab 访问令牌 |
| `OPENAI__KEY` | ✅ | 通义千问 API Key |
| `OPENAI__API_BASE` | ✅ | API 基础地址 |
| `CONFIG__MODEL` | ✅ | AI 模型名称 |
| `CONFIG__RESPONSE_LANGUAGE` | ✅ | 响应语言 |

### **文件路径**

| 文件 | 路径 | 说明 |
|------|------|------|
| **应用目录** | `/Users/jianqin/pr-agent-dashboard` | Flask 应用 |
| **配置文件** | `/Users/jianqin/pr-agent-test/.env` | 环境配置 |
| **数据库** | `/Users/jianqin/pr-agent-dashboard/reviews.db` | SQLite 数据库 |
| **历史记录** | `/Users/jianqin/pr-agent-dashboard/history.json` | 审查历史 |

---

## 🔧 性能优化

### **已实现的优化**

| 优化项 | 实现方式 | 效果 |
|-------|---------|------|
| **多线程处理** | `threading.Thread` | Webhook 不阻塞主线程 |
| **数据库索引** | `CREATE INDEX` | 加快查询速度 |
| **去重机制** | 数据库 + API 检查 | 避免重复审查 |
| **分页加载** | `LIMIT 1000` | 减少内存占用 |
| **超时控制** | `timeout=30/600` | 防止长时间阻塞 |
| **连接复用** | `requests.Session` | 减少连接开销 |

### **可优化方向**

| 优化项 | 方案 | 预期效果 |
|-------|------|---------|
| **缓存机制** | Redis 缓存 | 减少数据库查询 |
| **异步任务** | Celery 队列 | 提高并发处理能力 |
| **连接池** | SQLAlchemy | 优化数据库连接 |
| **前端优化** | 虚拟滚动 | 提高大数据渲染性能 |
| **CDN 加速** | 静态资源 CDN | 加快资源加载 |

---

## 🔒 安全考虑

### **已实现的安全措施**

| 措施 | 实现方式 | 说明 |
|------|---------|------|
| **Webhook 验证** | Secret Token | 验证 Webhook 来源 |
| **Token 保护** | 环境变量 | 敏感信息不硬编码 |
| **超时控制** | Timeout 设置 | 防止 DoS 攻击 |
| **输入验证** | 参数检查 | 防止注入攻击 |

### **建议的安全措施**

| 措施 | 说明 | 优先级 |
|------|------|-------|
| **HTTPS 部署** | 使用 SSL 证书 | 高 |
| **Token 轮换** | 定期更换 Token | 中 |
| **访问日志** | 记录所有访问 | 中 |
| **IP 白名单** | 限制访问来源 | 低 |
| **Rate Limiting** | API 访问限流 | 中 |

---

## 📋 备份和恢复

### **需要备份的文件**

| 文件 | 路径 | 重要性 |
|------|------|-------|
| **数据库** | `reviews.db` | ⭐⭐⭐ |
| **配置文件** | `.env` | ⭐⭐⭐ |
| **历史记录** | `history.json` | ⭐⭐ |
| **自定义 Prompt** | `prompts.json` | ⭐ |

### **备份命令**

```bash
# 创建备份
tar -czf backup-$(date +%Y%m%d).tar.gz \
  reviews.db history.json prompts.json

# 恢复备份
tar -xzf backup-20251111.tar.gz
```

### **备份策略**

| 策略 | 频率 | 保留时间 |
|------|------|---------|
| **完整备份** | 每天 | 30 天 |
| **增量备份** | 每小时 | 7 天 |
| **异地备份** | 每周 | 永久 |

---

## 📊 监控和日志

### **日志位置**

| 类型 | 位置 | 说明 |
|------|------|------|
| **应用日志** | 终端输出 | 实时日志 |
| **审查记录** | `reviews.db` | 数据库记录 |
| **历史记录** | `history.json` | JSON 文件 |
| **错误日志** | 终端输出 | 异常堆栈 |

### **关键日志**

| 日志内容 | 示例 | 用途 |
|---------|------|------|
| **Webhook 接收** | `收到 Webhook: Merge Request Hook` | 监控 Webhook 触发 |
| **审查开始** | `🚀 开始审查 MR: http://...` | 跟踪审查进度 |
| **审查完成** | `✅ MR 审查完成！` | 确认审查成功 |
| **记录保存** | `✅ 已记录审查: mr - project` | 确认数据保存 |
| **错误信息** | `❌ 审查失败: ...` | 问题排查 |

---

**更新时间：** 2025-11-11  
**维护者：** PR-Agent Dashboard Team
