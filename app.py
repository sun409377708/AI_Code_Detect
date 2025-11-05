#!/usr/bin/env python3
"""
PR-Agent 可视化管理平台
提供 Web 界面来管理和审查 GitLab Merge Requests
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import subprocess
import os
import json
from datetime import datetime
from pathlib import Path
import threading

app = Flask(__name__)

# 配置文件路径
ENV_FILE = os.path.expanduser("~/pr-agent-test/.env")
HISTORY_FILE = os.path.expanduser("~/pr-agent-dashboard/history.json")
PROMPT_FILE = os.path.expanduser("~/pr-agent-dashboard/prompts.json")

# 全局变量存储审查状态
review_status = {}

def load_env_config():
    """加载 .env 配置"""
    config = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
    return config

def get_gitlab_token():
    """获取 GitLab Token"""
    config = load_env_config()
    return config.get('GITLAB__PERSONAL_ACCESS_TOKEN', '')

def get_gitlab_url():
    """获取 GitLab URL"""
    config = load_env_config()
    return config.get('GITLAB__URL', 'http://gitlab.it.ikang.com')

def get_project_mrs(project_url, state='opened'):
    """获取项目的 MR 列表
    
    Args:
        project_url: 项目 URL
        state: MR 状态 - opened, merged, closed, all
    """
    try:
        # 从 URL 提取项目路径
        # 例如: http://gitlab.it.ikang.com/ios/IKStaff -> ios/IKStaff
        gitlab_url = get_gitlab_url()
        project_path = project_url.replace(gitlab_url + '/', '').strip('/')
        
        # 调用 GitLab API
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests"
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        params = {'per_page': 100, 'order_by': 'updated_at', 'sort': 'desc'}
        
        # 设置状态参数
        if state != 'all':
            params['state'] = state
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        mrs = response.json()
        
        # 检查每个 MR 是否已审查
        for mr in mrs:
            mr['reviewed'] = check_if_reviewed(mr['web_url'])
            mr['project_url'] = project_url
        
        return mrs
    except Exception as e:
        print(f"获取 MR 列表失败: {e}")
        return []

def check_if_reviewed(mr_url):
    """检查 MR 是否已被 AI 审查"""
    try:
        # 从 URL 提取项目和 MR ID
        parts = mr_url.split('/')
        project_path = '/'.join(parts[3:-2])
        mr_iid = parts[-1]
        
        gitlab_url = get_gitlab_url()
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests/{mr_iid}/notes"
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        notes = response.json()
        
        # 检查是否有 AI 的评论
        for note in notes:
            body = note.get('body', '')
            if 'PR Reviewer Guide' in body or 'Code feedback' in body or '代码审查' in body:
                return True
        
        return False
    except Exception as e:
        print(f"检查审查状态失败: {e}")
        return False

def review_mr(mr_url, mr_id):
    """审查单个 MR"""
    try:
        review_status[mr_id] = {
            'status': 'running',
            'progress': 0,
            'message': '正在启动审查...',
            'start_time': datetime.now().isoformat()
        }
        
        # 更新进度
        review_status[mr_id]['progress'] = 20
        review_status[mr_id]['message'] = '正在连接 GitLab...'
        
        # 运行 Docker 命令
        cmd = [
            'docker', 'run', '--rm',
            '--env-file', ENV_FILE,
            'codiumai/pr-agent:latest',
            '--pr_url', mr_url,
            'review'
        ]
        
        review_status[mr_id]['progress'] = 40
        review_status[mr_id]['message'] = '正在调用 AI 模型审查代码...'
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            review_status[mr_id]['status'] = 'success'
            review_status[mr_id]['progress'] = 100
            review_status[mr_id]['message'] = '审查完成！'
            review_status[mr_id]['output'] = result.stdout
            
            # 保存到历史记录
            save_history(mr_url, 'success', result.stdout)
        else:
            review_status[mr_id]['status'] = 'failed'
            review_status[mr_id]['progress'] = 100
            review_status[mr_id]['message'] = f'审查失败: {result.stderr}'
            review_status[mr_id]['error'] = result.stderr
            
            save_history(mr_url, 'failed', result.stderr)
        
        review_status[mr_id]['end_time'] = datetime.now().isoformat()
        
    except subprocess.TimeoutExpired:
        review_status[mr_id]['status'] = 'failed'
        review_status[mr_id]['message'] = '审查超时（10分钟）'
    except Exception as e:
        review_status[mr_id]['status'] = 'failed'
        review_status[mr_id]['message'] = f'审查失败: {str(e)}'

def save_history(mr_url, status, output):
    """保存审查历史"""
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        
        history.append({
            'mr_url': mr_url,
            'status': status,
            'output': output[:1000],  # 只保存前1000字符
            'timestamp': datetime.now().isoformat()
        })
        
        # 只保留最近100条记录
        history = history[-100:]
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"保存历史记录失败: {e}")

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/projects/mrs', methods=['POST'])
def get_mrs():
    """获取项目的 MR 列表"""
    data = request.json
    project_url = data.get('project_url', '')
    state = data.get('state', 'opened')  # opened, merged, closed, all
    
    if not project_url:
        return jsonify({'error': '请输入项目 URL'}), 400
    
    mrs = get_project_mrs(project_url, state)
    return jsonify({'mrs': mrs})

@app.route('/api/review', methods=['POST'])
def start_review():
    """开始审查 MR"""
    data = request.json
    mr_url = data.get('mr_url', '')
    mr_id = data.get('mr_id', '')
    
    if not mr_url or not mr_id:
        return jsonify({'error': '缺少参数'}), 400
    
    # 在后台线程中执行审查
    thread = threading.Thread(target=review_mr, args=(mr_url, mr_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': '审查已启动', 'mr_id': mr_id})

@app.route('/api/review/status/<mr_id>')
def get_review_status(mr_id):
    """获取审查状态"""
    status = review_status.get(mr_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/api/config')
def get_config():
    """获取配置信息"""
    config = load_env_config()
    # 返回完整配置（用于编辑）和安全配置（用于显示）
    full_config = {
        'gitlab_url': config.get('GITLAB__URL', ''),
        'gitlab_token': config.get('GITLAB__PERSONAL_ACCESS_TOKEN', ''),
        'openai_key': config.get('OPENAI__KEY', ''),
        'openai_api_base': config.get('OPENAI__API_BASE', ''),
        'model': config.get('CONFIG__MODEL', ''),
        'language': config.get('CONFIG__RESPONSE_LANGUAGE', '')
    }
    
    # 用于显示的安全配置
    safe_config = {
        'gitlab_url': full_config['gitlab_url'],
        'gitlab_token_masked': full_config['gitlab_token'][:10] + '...' if full_config['gitlab_token'] else '',
        'openai_key_masked': full_config['openai_key'][:10] + '...' if full_config['openai_key'] else '',
        'openai_api_base': full_config['openai_api_base'],
        'model': full_config['model'],
        'language': full_config['language']
    }
    
    return jsonify({
        'full': full_config,
        'safe': safe_config
    })

@app.route('/api/history')
def get_history():
    """获取审查历史"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            return jsonify({'history': history})
        return jsonify({'history': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        data = request.json
        
        # 读取现有配置
        config_lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'r') as f:
                config_lines = f.readlines()
        
        # 更新配置项
        config_map = {
            'gitlab_url': 'GITLAB__URL',
            'gitlab_token': 'GITLAB__PERSONAL_ACCESS_TOKEN',
            'openai_key': 'OPENAI__KEY',
            'openai_api_base': 'OPENAI__API_BASE',
            'model': 'CONFIG__MODEL',
            'language': 'CONFIG__RESPONSE_LANGUAGE'
        }
        
        # 构建新的配置内容
        new_config = {}
        for key, env_key in config_map.items():
            if key in data and data[key]:
                new_config[env_key] = data[key]
        
        # 更新或添加配置行
        updated_lines = []
        updated_keys = set()
        
        for line in config_lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key = line.split('=', 1)[0]
                if key in new_config:
                    updated_lines.append(f"{key}={new_config[key]}\n")
                    updated_keys.add(key)
                else:
                    updated_lines.append(line + '\n')
            else:
                updated_lines.append(line + '\n')
        
        # 添加新的配置项
        for key, value in new_config.items():
            if key not in updated_keys:
                updated_lines.append(f"{key}={value}\n")
        
        # 写入文件
        with open(ENV_FILE, 'w') as f:
            f.writelines(updated_lines)
        
        return jsonify({'message': '配置已更新', 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/config/test', methods=['POST'])
def test_config():
    """测试配置连接"""
    try:
        data = request.json
        gitlab_url = data.get('gitlab_url', '')
        gitlab_token = data.get('gitlab_token', '')
        
        # 测试 GitLab 连接
        headers = {'PRIVATE-TOKEN': gitlab_token}
        response = requests.get(f"{gitlab_url}/api/v4/user", headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                'success': True,
                'message': f'连接成功！当前用户: {user_data.get("name", "未知")}'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'连接失败: {response.status_code} - {response.text}'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'连接失败: {str(e)}'
        }), 500

@app.route('/api/prompts')
def get_prompts():
    """获取 Prompt 配置"""
    try:
        # 默认 Prompt 模板
        default_prompts = {
            'current': 'default',
            'templates': {
                'default': {
                    'name': '默认审查',
                    'description': 'PR-Agent 默认的代码审查 Prompt',
                    'prompt': '请对这个 Merge Request 进行全面的代码审查，包括：\n1. 代码质量和最佳实践\n2. 潜在的 bug 和安全问题\n3. 性能优化建议\n4. 代码可读性和维护性'
                },
                'ios': {
                    'name': 'iOS 项目',
                    'description': '专注于 iOS/Swift 开发的审查',
                    'prompt': '请对这个 iOS Merge Request 进行审查，重点关注：\n1. Swift 代码规范和最佳实践\n2. 内存管理（ARC、循环引用）\n3. UI 性能和响应式设计\n4. iOS API 使用是否正确\n5. 线程安全和并发处理\n6. 是否遵循 Apple 的设计指南'
                },
                'backend': {
                    'name': '后端 API',
                    'description': '专注于后端服务的审查',
                    'prompt': '请对这个后端 API Merge Request 进行审查，重点关注：\n1. API 设计是否 RESTful\n2. 数据库查询性能和 N+1 问题\n3. 安全性（SQL 注入、XSS、认证授权）\n4. 错误处理和日志记录\n5. 接口文档是否完整\n6. 是否有适当的单元测试'
                },
                'frontend': {
                    'name': '前端项目',
                    'description': '专注于前端开发的审查',
                    'prompt': '请对这个前端 Merge Request 进行审查，重点关注：\n1. 组件设计和复用性\n2. 状态管理是否合理\n3. 性能优化（懒加载、代码分割）\n4. 响应式设计和浏览器兼容性\n5. 用户体验和可访问性\n6. 是否遵循项目的代码规范'
                },
                'security': {
                    'name': '安全审查',
                    'description': '专注于安全问题的审查',
                    'prompt': '请对这个 Merge Request 进行安全审查，重点关注：\n1. 输入验证和数据清理\n2. 认证和授权机制\n3. 敏感数据处理（加密、脱敏）\n4. SQL 注入、XSS、CSRF 等漏洞\n5. 依赖包的安全性\n6. 日志中是否泄露敏感信息'
                },
                'performance': {
                    'name': '性能优化',
                    'description': '专注于性能问题的审查',
                    'prompt': '请对这个 Merge Request 进行性能审查，重点关注：\n1. 算法复杂度和时间复杂度\n2. 数据库查询优化\n3. 缓存策略\n4. 资源加载和网络请求\n5. 内存使用和泄漏\n6. 并发和异步处理'
                }
            }
        }
        
        # 读取用户保存的配置
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                user_prompts = json.load(f)
                # 合并用户配置和默认配置
                default_prompts['current'] = user_prompts.get('current', 'default')
                if 'custom' in user_prompts:
                    default_prompts['templates']['custom'] = user_prompts['custom']
        
        return jsonify(default_prompts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts', methods=['POST'])
def save_prompt():
    """保存 Prompt 配置"""
    try:
        data = request.json
        
        # 保存到文件
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Prompt 已保存'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mr/commits', methods=['POST'])
def get_mr_commits():
    """获取 MR 的 Commit 列表"""
    try:
        data = request.json
        mr_url = data.get('mr_url', '')
        
        if not mr_url:
            return jsonify({'error': '请提供 MR URL'}), 400
        
        # 解析 MR URL
        # 例如: http://gitlab.it.ikang.com/ios/IKStaff/-/merge_requests/123
        gitlab_url = get_gitlab_url()
        parts = mr_url.replace(gitlab_url, '').strip('/').split('/')
        
        # 找到项目路径和 MR ID
        mr_index = parts.index('merge_requests') if 'merge_requests' in parts else -1
        if mr_index == -1:
            return jsonify({'error': '无效的 MR URL'}), 400
        
        project_path = '/'.join(parts[:mr_index-1])  # -/merge_requests 前面的部分
        mr_iid = parts[mr_index + 1]
        
        # 调用 GitLab API 获取 Commits
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests/{mr_iid}/commits"
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        commits = response.json()
        
        # 简化返回的数据
        simplified_commits = []
        for commit in commits:
            simplified_commits.append({
                'id': commit['id'],
                'short_id': commit['short_id'],
                'title': commit['title'],
                'message': commit['message'],
                'author_name': commit['author_name'],
                'created_at': commit['created_at'],
                'web_url': commit.get('web_url', f"{gitlab_url}/{project_path}/-/commit/{commit['id']}")
            })
        
        return jsonify({'commits': simplified_commits})
    except Exception as e:
        print(f"获取 Commit 列表失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/commit/review', methods=['POST'])
def review_commit():
    """审查单个 Commit"""
    try:
        data = request.json
        commit_url = data.get('commit_url', '')
        commit_id = data.get('commit_id', '')
        
        if not commit_url or not commit_id:
            return jsonify({'error': '请提供 Commit URL 和 ID'}), 400
        
        # 生成唯一的审查 ID
        review_id = f"commit-{commit_id[:8]}-{int(datetime.now().timestamp())}"
        
        # 初始化状态
        review_status[review_id] = {
            'status': 'running',
            'progress': 0,
            'message': '准备审查 Commit...',
            'commit_id': commit_id
        }
        
        # 在后台线程中执行审查
        def run_review():
            try:
                review_status[review_id]['progress'] = 10
                review_status[review_id]['message'] = '获取 Commit 信息...'
                
                # 解析 Commit URL 获取项目和 SHA
                # 例如: http://gitlab.it.ikang.com/ios/IKStaff/-/commit/abc123
                gitlab_url = get_gitlab_url()
                parts = commit_url.replace(gitlab_url, '').strip('/').split('/')
                commit_index = parts.index('commit') if 'commit' in parts else -1
                
                if commit_index == -1:
                    raise Exception('无效的 Commit URL')
                
                project_path = '/'.join(parts[:commit_index-1])
                commit_sha = parts[commit_index + 1]
                
                review_status[review_id]['progress'] = 20
                review_status[review_id]['message'] = '获取 Commit 变更...'
                
                # 获取 Commit 的 diff
                headers = {'PRIVATE-TOKEN': get_gitlab_token()}
                api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/diff"
                diff_response = requests.get(api_url, headers=headers, timeout=30)
                diff_response.raise_for_status()
                diffs = diff_response.json()
                
                # 构建审查内容
                review_status[review_id]['progress'] = 30
                review_status[review_id]['message'] = '使用 AI 分析代码...'
                
                # 准备 diff 文本
                diff_text = ""
                for diff in diffs[:10]:  # 限制最多10个文件，避免内容过多
                    diff_text += f"\n\n文件: {diff['new_path']}\n"
                    diff_text += f"变更: +{diff.get('added_lines', 0)} -{diff.get('removed_lines', 0)}\n"
                    diff_text += diff.get('diff', '')[:2000]  # 每个文件最多2000字符
                
                # 调用 AI API 进行审查（使用通义千问）
                config = load_env_config()
                ai_api_key = config.get('OPENAI__KEY', '')
                ai_model = config.get('CONFIG__MODEL', 'qwen-plus')
                
                # 如果 model 包含 openai/ 前缀，去掉它
                if ai_model.startswith('openai/'):
                    ai_model = ai_model.replace('openai/', '')
                
                # 验证 API Key
                if not ai_api_key:
                    raise Exception('未配置 AI API Key，请在 .env 文件中设置 OPENAI__KEY')
                
                print(f"使用 AI 模型: {ai_model}")
                print(f"API Key 前缀: {ai_api_key[:10]}...")
                
                review_status[review_id]['progress'] = 50
                
                # 构建审查 prompt
                prompt = f"""请对以下 Git Commit 的代码变更进行审查：

代码变更：
{diff_text}

请提供：
1. ✅ 代码质量评估
2. ⚠️ 潜在问题和建议
3. 💡 优化建议
4. 📝 其他注意事项

请使用中文回复，并使用 ✅ ⚠️ ❌ 💡 等图标标注不同类型的反馈。"""

                # 调用 AI API（禁用代理）
                import json as json_module
                
                # 禁用代理，直接连接
                proxies = {
                    'http': None,
                    'https': None
                }
                
                ai_response = requests.post(
                    'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                    headers={
                        'Authorization': f'Bearer {ai_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': ai_model,
                        'input': {'messages': [{'role': 'user', 'content': prompt}]},
                        'parameters': {'result_format': 'message'}
                    },
                    proxies=proxies,
                    timeout=120
                )
                
                review_status[review_id]['progress'] = 80
                review_status[review_id]['message'] = '发布审查结果到 GitLab...'
                
                if ai_response.status_code == 200:
                    ai_result = ai_response.json()
                    review_content = ai_result['output']['choices'][0]['message']['content']
                    
                    # 发布评论到 GitLab Commit
                    comment_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/comments"
                    comment_data = {'note': f"🤖 AI 代码审查\n\n{review_content}"}
                    
                    comment_response = requests.post(
                        comment_url,
                        headers=headers,
                        json=comment_data,
                        timeout=30
                    )
                    
                    review_status[review_id]['progress'] = 100
                    review_status[review_id]['status'] = 'success'
                    review_status[review_id]['message'] = 'Commit 审查完成'
                    review_status[review_id]['output'] = review_content
                    
                    # 保存历史记录
                    save_history(commit_url, 'commit', 'success')
                else:
                    raise Exception(f'AI 审查失败: {ai_response.text}')
                    
            except Exception as e:
                review_status[review_id]['status'] = 'failed'
                review_status[review_id]['message'] = f'审查失败: {str(e)}'
                review_status[review_id]['output'] = str(e)
        
        thread = threading.Thread(target=run_review)
        thread.start()
        
        return jsonify({'review_id': review_id, 'message': '开始审查 Commit'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/commit/review/status/<review_id>')
def get_commit_review_status(review_id):
    """获取 Commit 审查状态"""
    status = review_status.get(review_id, {'status': 'not_found'})
    return jsonify(status)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 PR-Agent 可视化管理平台")
    print("=" * 60)
    print(f"📂 配置文件: {ENV_FILE}")
    print(f"📊 历史记录: {HISTORY_FILE}")
    print(f"🌐 访问地址: http://localhost:8080")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=8080)
