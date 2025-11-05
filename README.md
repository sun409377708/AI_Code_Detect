# PR-Agent AI 代码审查平台

> 基于通义千问 AI 的 GitLab MR/Commit 自动审查平台

## 📋 目录

1. [快速开始](#快速开始)
2. [功能特性](#功能特性)
3. [架构方案](#架构方案)
4. [配置说明](#配置说明)
5. [常见问题](#常见问题)

---

## 🚀 快速开始

### **访问地址**

```bash
# 自己访问
http://localhost:8080

# 内网访问（局域网）
http://10.108.2.73:8080
```

### **默认项目**

```
http://gitlab.it.ikang.com/ios/ikangapp
```

### **基本使用**

1. 打开浏览器访问平台
2. 输入项目 URL（默认已填写）
3. 选择 MR 状态（Open/Merged/Closed/All）
4. 点击"加载 MR 列表"
5. 选择 MR 进行审查

---

## ✨ 功能特性

- ✅ **MR 审查** - 支持所有状态（Open/Merged/Closed），实时进度，自动发布评论
- ✅ **Commit 审查** - 单个 Commit 审查，评论发布到 GitLab
- ✅ **自定义 Prompt** - 6 种内置模板（默认、iOS、后端、前端、安全、性能）
- ✅ **彩色结果** - 🟢 成功 🔴 错误 🟡 警告 🔵 优化，支持 Markdown

---

## 🏗️ 架构方案

### **当前方案：本地 Flask 服务器 + Web UI** ⭐

```
你的 Mac 运行 Flask 服务
  ↓
Web UI (http://localhost:8080)
  ↓
手动点击按钮触发审查
  ↓
调用通义千问 AI API
  ↓
发布评论到 GitLab
```

**优点**：
- ✅ 简单快速，无需配置 CI/CD
- ✅ 可视化界面，操作直观
- ✅ 灵活控制，想审查哪个就审查哪个
- ✅ 支持历史 MR 和 Commit 审查
- ✅ 局域网可访问（`http://10.108.2.73:8080`）

**缺点**：
- ⚠️ 需要手动触发
- ⚠️ Mac 必须开机
- ⚠️ 不适合大规模团队

**适用场景**：
- 个人使用或小团队（< 10 人）
- 需要灵活控制审查时机
- 快速验证和测试

---

### **方案对比**

| 特性 | 本地 Flask 服务器 | GitLab Runner | Webhook |
|------|------------------|---------------|---------|
| **触发方式** | 手动点击 | 自动（Push/MR） | 自动（事件） |
| **部署难度** | ⭐ 简单 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 复杂 |
| **配置要求** | 本地运行 | 配置 Runner | 配置服务器 + Webhook |
| **灵活性** | ✅ 高 | ⚠️ 中 | ⚠️ 低 |
| **自动化** | ❌ 手动 | ✅ 自动 | ✅ 自动 |
| **历史审查** | ✅ 支持 | ❌ 不支持 | ❌ 不支持 |
| **可视化** | ✅ Web UI | ❌ 仅日志 | ❌ 仅评论 |
| **团队使用** | ⚠️ 小团队 | ✅ 适合 | ✅ 适合 |

---

### **方案 2：GitLab Runner（CI/CD 自动化）**

```
开发者 Push 代码或创建 MR
  ↓
触发 GitLab CI/CD Pipeline
  ↓
GitLab Runner 执行 .gitlab-ci.yml
  ↓
运行 PR-Agent Docker 容器
  ↓
AI 审查并发布评论
```

**配置示例**：

```yaml
# .gitlab-ci.yml
stages:
  - review

pr_agent_review:
  stage: review
  image: codiumai/pr-agent:latest
  script:
    - pr-agent review --pr_url=$CI_MERGE_REQUEST_PROJECT_URL/-/merge_requests/$CI_MERGE_REQUEST_IID
  only:
    - merge_requests
  variables:
    GITLAB__PERSONAL_ACCESS_TOKEN: $GITLAB_TOKEN
    OPENAI__KEY: $QWEN_API_KEY
```

**优点**：
- ✅ 完全自动化，无需手动触发
- ✅ 每次 Push/MR 都自动审查
- ✅ 与 GitLab 深度集成
- ✅ 适合团队使用

**缺点**：
- ⚠️ 需要配置 GitLab Runner
- ⚠️ 需要在项目中添加 `.gitlab-ci.yml`
- ⚠️ 每次 Push 都触发，可能频繁
- ⚠️ 不支持历史 MR 审查
- ⚠️ 调试困难，只能看日志

**适用场景**：
- 团队协作，需要自动化
- 每次提交都需要审查
- 有 GitLab Runner 资源

**潜在问题**：
- 并发限制（多个 MR 同时触发）
- Token 权限管理
- CI/CD 配额消耗

---

### **方案 3：Webhook（事件驱动）**

```
开发者创建/更新 MR
  ↓
GitLab 发送 Webhook 到你的服务器
  ↓
服务器接收事件并解析
  ↓
调用 PR-Agent 进行审查
  ↓
发布评论到 GitLab
```

**实现示例**：

```python
# webhook_server.py
from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def gitlab_webhook():
    data = request.json
    
    # 只处理 MR 事件
    if data['object_kind'] == 'merge_request':
        mr_url = data['object_attributes']['url']
        
        # 触发审查
        subprocess.Popen([
            'docker', 'run', '--rm',
            '--env-file', '.env',
            'codiumai/pr-agent:latest',
            '--pr_url', mr_url,
            'review'
        ])
    
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**GitLab Webhook 配置**：
```
Settings → Webhooks
URL: http://your-server:5000/webhook
Trigger: Merge request events
Secret Token: (可选)
```

**优点**：
- ✅ 完全自动化
- ✅ 实时响应 MR 事件
- ✅ 灵活控制逻辑
- ✅ 可以处理多种事件

**缺点**：
- ⚠️ 需要公网服务器或内网穿透
- ⚠️ 需要配置 Webhook
- ⚠️ 需要处理并发和队列
- ⚠️ 安全性需要考虑（验证 Secret Token）

**适用场景**：
- 需要高度自定义
- 需要处理多种 GitLab 事件
- 有稳定的服务器资源

---

### **方案选择建议**

#### **个人使用 / 小团队（< 5 人）**
→ **本地 Flask 服务器**（当前方案）
- 简单快速
- 灵活控制
- 无需额外配置

#### **团队协作 / 中等规模（5-20 人）**
→ **GitLab Runner**
- 自动化审查
- 与 CI/CD 集成
- 团队共享

#### **大型团队 / 高度定制**
→ **Webhook**
- 完全控制
- 灵活扩展
- 支持复杂逻辑

#### **混合方案**（推荐）
```
日常开发：GitLab Runner 自动审查
历史分析：本地 Flask Web UI 手动审查
特殊需求：Webhook 自定义处理
```

---

### **迁移到其他方案**

#### **从本地服务器迁移到 GitLab Runner**

1. **准备 `.gitlab-ci.yml`**
   ```yaml
   pr_agent_review:
     stage: review
     image: codiumai/pr-agent:latest
     script:
       - pr-agent review --pr_url=$CI_MERGE_REQUEST_PROJECT_URL/-/merge_requests/$CI_MERGE_REQUEST_IID
     only:
       - merge_requests
   ```

2. **配置 CI/CD 变量**
   - Settings → CI/CD → Variables
   - 添加 `GITLAB_TOKEN` 和 `QWEN_API_KEY`

3. **测试**
   - 创建测试 MR
   - 查看 Pipeline 日志
   - 验证评论是否发布

#### **从本地服务器迁移到 Webhook**

1. **部署 Webhook 服务器**
   ```bash
   # 在服务器上
   git clone <your-repo>
   cd webhook-server
   python3 webhook_server.py
   ```

2. **配置 GitLab Webhook**
   - Settings → Webhooks
   - URL: `http://your-server:5000/webhook`
   - 选择 Merge request events

3. **测试**
   - 创建测试 MR
   - 查看服务器日志
   - 验证评论是否发布

---

## 🎯 使用说明

### **MR 审查**
```
加载 MR 列表 → 选择 MR → 点击"立即审查" → 查看彩色结果
```

### **Commit 审查**
```
查看 Commits → 选择 Commit → 点击"AI 审查" → 结果发布到 GitLab
```

### **自定义 Prompt**
```
页面底部 → 编辑 Prompt → 选择模板（推荐：iOS 项目） → 保存
```

**内置模板**：默认、iOS、后端、前端、安全、性能

### **结果颜色**
- 🟢 绿色 - 成功/通过
- 🔴 红色 - 错误/问题（优先处理）
- 🟡 黄色 - 警告/建议
- 🔵 蓝色 - 提示/优化

---

## ⚙️ 配置说明

**配置文件**：`/Users/jianqin/pr-agent-test/.env`

```bash
# GitLab
GITLAB__URL=http://gitlab.it.ikang.com
GITLAB__PERSONAL_ACCESS_TOKEN=glpat-xxx

# 通义千问 AI
OPENAI__KEY=sk-xxx
CONFIG__MODEL=openai/qwen-plus
```

**获取 Token**：
- GitLab Token：Settings → Access Tokens（权限：api, read_api, read_repository）
- 通义千问 API Key：阿里云控制台 → 通义千问

---

## ❓ 常见问题

### **服务启动**
```bash
# 启动服务
cd ~/pr-agent-dashboard && source venv/bin/activate && python3 app.py

# 检查服务
lsof -i:8080

# 查看 IP
ifconfig | grep "inet "
```

### **审查失败**

**API Key 错误**：检查 `.env` 中的 `OPENAI__KEY` 是否正确

**代理错误**：已禁用代理，如仍有问题执行 `unset HTTP_PROXY HTTPS_PROXY`

**评论未发布**：检查 GitLab Token 是否有 `api` 权限

### **同事无法访问**

1. 确认服务运行：`lsof -i:8080`
2. 检查防火墙：系统偏好设置 → 安全性与隐私
3. 测试连接：`ping 10.108.2.73`

### **IP 地址变化**

设置静态 IP：系统偏好设置 → 网络 → 高级 → TCP/IP → 手动

---

## 🎉 总结

**当前方案**：本地 Flask 服务器 + Web UI
- ✅ 简单快速，无需配置 CI/CD
- ✅ 可视化界面，灵活控制
- ✅ 支持历史 MR 和 Commit 审查
- ✅ 局域网可访问

**访问地址**：
- 你：`http://localhost:8080`
- 同事：`http://10.108.2.73:8080`

**推荐配置**：
- 项目：ikangapp
- Prompt：iOS 项目模板
- 审查：每个 Commit + 每个 MR

---

*最后更新：2025-11-05*
