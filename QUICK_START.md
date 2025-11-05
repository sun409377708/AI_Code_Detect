# 快速开始 - 5 分钟上手

## 🚀 访问地址

```bash
你自己：http://localhost:8080
同事：  http://10.108.2.73:8080
```

## 📋 基本操作

### **1. 审查 MR**
```
输入项目 URL → 加载 MR 列表 → 点击"立即审查" → 查看结果
```

### **2. 审查 Commit**
```
查看 Commits → 选择 Commit → 点击"AI 审查" → 查看结果
```

### **3. 切换 Prompt**
```
滚动到底部 → 编辑 Prompt → 选择"iOS 项目" → 保存
```

## 🎨 结果颜色

- 🟢 **绿色** - 成功/通过
- 🔴 **红色** - 错误/问题（优先处理）
- 🟡 **黄色** - 警告/建议（重要关注）
- 🔵 **蓝色** - 提示/优化（可选）

## ⚙️ 配置文件

```bash
/Users/jianqin/pr-agent-test/.env
```

## 🔧 常用命令

```bash
# 启动服务
cd ~/pr-agent-dashboard
source venv/bin/activate
python3 app.py

# 检查服务
lsof -i:8080

# 查看 IP
ifconfig | grep "inet "
```

## ❓ 遇到问题？

查看完整文档：`README.md`

---

**就这么简单！开始使用吧！** 🎉
