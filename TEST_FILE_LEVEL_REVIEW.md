# 🧪 文件级审核功能测试指南

## 📋 问题说明

你刚才手动触发了一次 Commit 审核，但发现和之前没有区别。这是因为：

1. ✅ **前端已正确实现** - 复选框和参数传递都正常
2. ✅ **后端已接收参数** - `file_level_review` 参数已添加
3. ⚠️ **审查逻辑已更新** - 但需要验证是否生效

---

## 🔍 已修复的问题

### **1. Commit 审查接口** ✅

**文件：** `app.py` - `review_commit()` 函数

**修改内容：**
```python
# 接收参数
file_level_review = data.get('file_level_review', False)

# 记录日志
review_mode = '文件级审核' if file_level_review else '总体审核'
print(f"📂 Commit 审查模式: {review_mode}")

# 根据模式使用不同的 Prompt
if file_level_review:
    # 文件级审核 - 详细模式（按文件分组、按区块分析）
    prompt = """..."""
else:
    # 总体审核 - 简洁模式
    prompt = """..."""
```

---

### **2. MR 审查接口** ✅

**文件：** `app.py` - `start_review()` 和 `review_mr()` 函数

**修改内容：**
```python
# 接收参数
file_level_review = data.get('file_level_review', False)

# 传递给审查函数
thread = threading.Thread(
    target=review_mr, 
    args=(mr_url, mr_id, gitlab_token, file_level_review)
)

# 在 Docker 命令中添加环境变量
if file_level_review:
    cmd.extend(['-e', 'PR_REVIEWER__ENABLE_FILE_LEVEL_REVIEW=true'])
```

---

## 🧪 如何测试

### **测试步骤：**

1. **打开手动审查页面**
   ```
   http://localhost:8080
   点击左侧菜单 "✋ 手动审查"
   ```

2. **选择项目**
   ```
   选择组：ios
   选择项目：ikangapp
   ```

3. **勾选文件级审核**
   ```
   ☑ 📂 启用文件级审核（详细模式）
   ```

4. **触发审查**
   ```
   点击某个 Commit 的 "审查" 按钮
   ```

5. **查看后端日志**
   ```
   在终端查看是否输出：
   📂 Commit 审查模式: 文件级审核
   ```

6. **查看审查结果**
   ```
   等待审查完成，查看 GitLab Comment
   应该看到按文件分组的详细审查报告
   ```

---

## 📊 预期结果对比

### **总体审核（默认）：**
```
🤖 AI 代码审查

✅ 代码质量评估
- 整体代码结构良好
- 命名规范清晰

⚠️ 潜在问题和建议
- 建议添加错误处理
- 注意性能优化

💡 优化建议
- 可以使用更简洁的语法
- 建议添加注释

📝 其他注意事项
- 测试覆盖率需要提高
```

### **文件级审核（详细）：**
```
🤖 AI 代码审查（文件级详细模式）

┌─────────────────────────────────────────────┐
│ 📁 文件 1/3: AppDelegate.swift              │
│ 变更: +15 行, -3 行                          │
│ 风险等级: 🟡 中风险                          │
│ 文件评分: B                                  │
├─────────────────────────────────────────────┤
│                                              │
│ 🔍 区块 1: 新增网络请求方法 (Line 45-60)    │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 代码片段:                                    │
│   func fetchData() {                        │
│       let url = URL(string: baseURL)        │
│       ...                                    │
│   }                                          │
│                                              │
│ ⚠️ 警告 (2个):                               │
│   1. 缺少错误处理                            │
│      • 网络请求可能失败                      │
│      💡 建议: 添加 do-catch 块               │
│         do {                                 │
│             let data = try await ...        │
│         } catch {                            │
│             print("Error: \(error)")        │
│         }                                    │
│                                              │
│   2. 未处理超时情况                          │
│      💡 建议: 设置请求超时时间               │
│                                              │
│ ✅ 优点:                                     │
│   • 使用了 async/await                       │
│   • 代码结构清晰                             │
│                                              │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 📁 文件 2/3: NetworkManager.swift            │
│ 变更: +8 行, -2 行                           │
│ 风险等级: 🟢 低风险                          │
│ 文件评分: A                                  │
├─────────────────────────────────────────────┤
│ ... (详细分析)                               │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 📊 总体评估                                  │
├─────────────────────────────────────────────┤
│ 🎯 评分明细:                                 │
│   • 安全性: ⚠️ 6/10                          │
│   • 代码质量: ✅ 8/10                         │
│   • 功能完整性: ✅ 9/10                       │
│                                              │
│ 🔴 严重问题: 无                              │
│                                              │
│ ⚠️ 警告 (3个):                               │
│   1. 缺少错误处理 - AppDelegate.swift L45   │
│   2. 未处理超时 - AppDelegate.swift L50      │
│   3. 建议添加日志 - NetworkManager.swift L20 │
│                                              │
│ 📝 审核结论:                                 │
│   ✅ 建议合并（修复警告后更佳）              │
└─────────────────────────────────────────────┘
```

---

## 🔧 调试方法

### **1. 查看后端日志**

在运行 `python3 app.py` 的终端中查看：

```bash
# 应该看到类似输出：
📂 Commit 审查模式: 文件级审核
使用 AI 模型: qwen-plus
API Key 前缀: sk-xxxxx...
```

### **2. 查看浏览器控制台**

按 `F12` 打开开发者工具，查看 Network 标签：

```javascript
// 查找 /api/commit/review 请求
// 查看 Request Payload:
{
  "commit_url": "http://gitlab.it.ikang.com/...",
  "commit_id": "7dea2117...",
  "file_level_review": true  // 应该是 true
}
```

### **3. 测试 API**

使用 `curl` 命令测试：

```bash
curl -X POST http://localhost:8080/api/commit/review \
  -H "Content-Type: application/json" \
  -H "X-GitLab-Token: YOUR_TOKEN" \
  -d '{
    "commit_url": "http://gitlab.it.ikang.com/ios/ikangapp/-/commit/7dea2117e44351a3e9308d20a2341ba30208bcc6",
    "commit_id": "7dea2117e44351a3e9308d20a2341ba30208bcc6",
    "file_level_review": true
  }'
```

---

## 📝 验证清单

- [x] **前端复选框** - 已添加到手动审查页面
- [x] **前端参数传递** - `manual-review.js` 和 `commits.js` 已修改
- [x] **后端参数接收** - `review_commit()` 已接收 `file_level_review`
- [x] **审查模式日志** - 已添加 `print(f"📂 Commit 审查模式: {review_mode}")`
- [x] **Prompt 差异化** - 文件级审核使用详细 Prompt
- [x] **MR 审查支持** - `review_mr()` 也已支持文件级审核

---

## 🎯 下一步测试

### **重新测试之前的 Commit：**

1. **访问手动审查页面**
   ```
   http://localhost:8080
   ```

2. **强制刷新页面**
   ```
   Mac: Cmd + Shift + R
   Windows: Ctrl + Shift + R
   ```

3. **选择项目并勾选文件级审核**
   ```
   项目: ios/ikangapp
   ☑ 📂 启用文件级审核（详细模式）
   ```

4. **审查同一个 Commit**
   ```
   http://gitlab.it.ikang.com/ios/ikangapp/-/commit/7dea2117e44351a3e9308d20a2341ba30208bcc6
   ```

5. **对比结果**
   ```
   - 查看后端日志是否显示 "文件级审核"
   - 查看 GitLab Comment 是否按文件分组
   - 查看是否有详细的区块分析
   ```

---

## ⚠️ 注意事项

### **1. AI 模型支持**

文件级审核需要 AI 模型能够理解和遵循复杂的格式要求。如果 AI 模型不能很好地遵循格式，可能需要：

- 调整 Prompt 的复杂度
- 使用更强大的模型（如 GPT-4）
- 分多次调用 AI（每个文件单独调用）

### **2. Token 限制**

文件级审核的 Prompt 更长，可能会超出 AI 模型的 Token 限制。建议：

- 限制每次审查的文件数量（当前已限制为 10 个）
- 限制每个文件的 diff 长度（当前已限制为 2000 字符）

### **3. 审查时间**

文件级审核需要更多的 AI 处理时间：

- 总体审核：5-10 秒
- 文件级审核：20-40 秒（取决于文件数量）

---

## 📖 相关文档

- [文件级审核功能说明](./FILE_LEVEL_REVIEW.md)
- [手动审查使用指南](./README.md)

---

**最后更新：2025-11-13 18:15**

**测试 Commit：** http://gitlab.it.ikang.com/ios/ikangapp/-/commit/7dea2117e44351a3e9308d20a2341ba30208bcc6
