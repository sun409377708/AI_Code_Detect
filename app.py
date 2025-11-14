#!/usr/bin/env python3
"""
PR-Agent 可视化管理平台
提供 Web 界面来管理和审查 GitLab Merge Requests
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import subprocess
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import sqlite3

# 中国时区 (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国时区的当前时间"""
    return datetime.now(CHINA_TZ)

app = Flask(__name__)

# 启用 CORS（允许跨域请求）
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # 允许所有来源，生产环境建议指定具体域名
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Content-Type", 
            "Authorization", 
            "PRIVATE-TOKEN",
            "X-GitLab-Token",      # 用户 Token（前端传递）
            "X-Gitlab-Token",      # Webhook 验证 Token
            "X-Gitlab-Event"       # Webhook 事件类型
        ],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# 配置文件路径
ENV_FILE = os.path.expanduser("~/pr-agent-test/.env")
HISTORY_FILE = os.path.expanduser("~/pr-agent-dashboard/history.json")
PROMPT_FILE = os.path.expanduser("~/pr-agent-dashboard/prompts.json")
DB_FILE = os.path.expanduser("~/pr-agent-dashboard/reviews.db")

# 全局变量存储审查状态
review_status = {}

# 初始化数据库
def init_database():
    """初始化审查记录数据库"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            project_id INTEGER NOT NULL,
            project_name TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            author TEXT NOT NULL,
            branch TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"数据库已初始化: {DB_FILE}")

# 记录审查
def record_review(review_type, project_id, project_name, title, url, author, branch='', details=''):
    """记录审查到数据库"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # 使用中国时区的当前时间
        china_time = get_china_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO review_records 
            (type, project_id, project_name, title, url, author, branch, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (review_type, project_id, project_name, title, url, author, branch, china_time, details))
        conn.commit()
        conn.close()
        print(f"✅ 已记录审查: {review_type} - {project_name} - {title}")
    except Exception as e:
        print(f"❌ 记录审查失败: {e}")

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
    """获取 GitLab Token - 优先从请求头获取，否则从配置文件"""
    # 优先使用前端传来的 Token
    from flask import request
    token = request.headers.get('X-GitLab-Token')
    if token:
        return token
    # 否则使用配置文件中的 Token（向后兼容）
    config = load_env_config()
    return config.get('GITLAB__PERSONAL_ACCESS_TOKEN', '')

def get_gitlab_url():
    """获取 GitLab URL"""
    config = load_env_config()
    return config.get('GITLAB__URL', 'http://gitlab.it.ikang.com')

def get_project_mrs(project_url, state='opened', target_branch=''):
    """获取项目的 MR 列表
    
    Args:
        project_url: 项目 URL
        state: MR 状态 - opened, merged, closed, all
        target_branch: 目标分支过滤（可选）
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
        
        # 设置目标分支过滤
        if target_branch:
            params['target_branch'] = target_branch
        
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
        # 例如: http://gitlab.it.ikang.com/ios/ikangapp/-/merge_requests/8
        parts = mr_url.split('/')
        
        # 找到 merge_requests 的位置
        mr_index = parts.index('merge_requests') if 'merge_requests' in parts else -1
        if mr_index == -1:
            return False
        
        # 项目路径是 merge_requests 前面的部分（排除 '-'）
        project_parts = parts[3:mr_index]
        if project_parts and project_parts[-1] == '-':
            project_parts = project_parts[:-1]
        project_path = '/'.join(project_parts)
        
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

def review_mr(mr_url, mr_id, gitlab_token=None, file_level_review=False):
    """审查单个 MR"""
    try:
        review_mode = '文件级审核' if file_level_review else '总体审核'
        review_status[mr_id] = {
            'status': 'running',
            'progress': 0,
            'message': f'正在启动审查（{review_mode}）...',
            'start_time': get_china_time().isoformat(),
            'review_mode': review_mode
        }
        
        # 更新进度
        review_status[mr_id]['progress'] = 20
        review_status[mr_id]['message'] = '正在连接 GitLab...'
        
        # 运行 Docker 命令
        cmd = [
            'docker', 'run', '--rm',
            '--env-file', ENV_FILE,
        ]
        
        # 如果提供了用户的 Token，覆盖环境变量
        if gitlab_token:
            cmd.extend(['-e', f'GITLAB__PERSONAL_ACCESS_TOKEN={gitlab_token}'])
        
        # 如果启用文件级审核，添加相应的环境变量或参数
        # 注意：这里需要根据 pr-agent 的实际支持情况调整
        # 当前先通过环境变量传递
        if file_level_review:
            cmd.extend(['-e', 'PR_REVIEWER__ENABLE_FILE_LEVEL_REVIEW=true'])
            review_status[mr_id]['message'] = '正在进行文件级详细审查...'
        
        cmd.extend([
            'codiumai/pr-agent:latest',
            '--pr_url', mr_url,
            'review'
        ])
        
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
        
        review_status[mr_id]['end_time'] = get_china_time().isoformat()
        
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
            'timestamp': get_china_time().isoformat()
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

@app.route('/api/user/projects', methods=['GET'])
def get_user_projects():
    """获取用户的活跃项目列表"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        # 获取用户的项目，按最近活跃排序
        api_url = f"{gitlab_url}/api/v4/projects"
        params = {
            'membership': 'true',  # 只获取用户是成员的项目
            'order_by': 'last_activity_at',  # 按最后活跃时间排序
            'sort': 'desc',  # 降序
            'per_page': 50,  # 获取前50个
            'archived': 'false'  # 排除已归档的项目
        }
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        projects = response.json()
        
        # 简化项目信息
        simplified_projects = []
        for project in projects:
            simplified_projects.append({
                'id': project['id'],
                'name': project['name'],
                'path_with_namespace': project['path_with_namespace'],
                'web_url': project['web_url'],
                'last_activity_at': project.get('last_activity_at', ''),
                'description': project.get('description', '')[:100] if project.get('description') else '',
                'namespace': project.get('namespace'),  # 添加 namespace 信息
                'star_count': project.get('star_count', 0),
                'forks_count': project.get('forks_count', 0)
            })
        
        return jsonify({'projects': simplified_projects})
    except Exception as e:
        print(f"获取用户项目失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/starred-projects', methods=['GET'])
def get_starred_projects():
    """获取用户在 GitLab 上 Star 过的项目"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        # 获取用户 Star 过的项目
        api_url = f"{gitlab_url}/api/v4/projects"
        params = {
            'starred': 'true',  # 只获取 Star 过的项目
            'order_by': 'last_activity_at',
            'sort': 'desc',
            'per_page': 100
        }
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        projects = response.json()
        
        # 简化项目信息
        simplified_projects = []
        for project in projects:
            simplified_projects.append({
                'id': project['id'],
                'name': project['name'],
                'path_with_namespace': project['path_with_namespace'],
                'web_url': project['web_url'],
                'last_activity_at': project.get('last_activity_at', ''),
                'description': project.get('description', '')[:100] if project.get('description') else '',
                'namespace': project.get('namespace'),
                'star_count': project.get('star_count', 0),
                'forks_count': project.get('forks_count', 0)
            })
        
        return jsonify({'projects': simplified_projects})
    except Exception as e:
        print(f"获取 Star 项目失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/groups', methods=['GET'])
def get_user_groups():
    """获取用户的 GitLab 组列表"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        # 获取用户的组
        api_url = f"{gitlab_url}/api/v4/groups"
        params = {
            'per_page': 100,  # 每页100个
            'order_by': 'name',  # 按名称排序
            'sort': 'asc'  # 升序
        }
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        groups = response.json()
        
        # 简化组信息
        simplified_groups = []
        for group in groups:
            simplified_groups.append({
                'id': group['id'],
                'name': group['name'],
                'full_path': group['full_path'],
                'description': group.get('description', '')[:100] if group.get('description') else '',
                'web_url': group.get('web_url', '')
            })
        
        return jsonify({'groups': simplified_groups})
    except Exception as e:
        print(f"获取用户组失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/group/<int:group_id>/projects', methods=['GET'])
def get_group_projects(group_id):
    """获取指定组下的项目列表"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        # 获取组下的项目
        api_url = f"{gitlab_url}/api/v4/groups/{group_id}/projects"
        params = {
            'per_page': 100,  # 每页100个
            'order_by': 'name',  # 按名称排序
            'sort': 'asc',  # 升序
            'archived': 'false'  # 排除已归档的项目
        }
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        projects = response.json()
        
        # 简化项目信息
        simplified_projects = []
        for project in projects:
            simplified_projects.append({
                'id': project['id'],
                'name': project['name'],
                'path_with_namespace': project['path_with_namespace'],
                'web_url': project['web_url'],
                'description': project.get('description', '')[:100] if project.get('description') else ''
            })
        
        return jsonify({'projects': simplified_projects})
    except Exception as e:
        print(f"获取组项目失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/branches', methods=['POST'])
def get_branches():
    """获取项目的分支列表"""
    data = request.json
    project_url = data.get('project_url', '')
    
    if not project_url:
        return jsonify({'error': '请输入项目 URL'}), 400
    
    try:
        # 从 URL 提取项目路径
        gitlab_url = get_gitlab_url()
        project_path = project_url.replace(gitlab_url + '/', '').strip('/')
        
        # 调用 GitLab API 获取分支
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/branches"
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        params = {'per_page': 100}  # 获取最多100个分支
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        branches_data = response.json()
        
        # 返回详细的分支信息
        branches = []
        for branch in branches_data:
            branches.append({
                'name': branch['name'],
                'default': branch.get('default', False),
                'protected': branch.get('protected', False),
                'merged': branch.get('merged', False)
            })
        
        # 按默认分支优先，然后按名称排序
        branches.sort(key=lambda x: (not x['default'], x['name']))
        
        return jsonify({
            'branches': branches,
            'total': len(branches)
        })
    except Exception as e:
        print(f"获取分支列表失败: {e}")
        return jsonify({'error': str(e)}), 500

def get_branch_commits_without_mr(project_url, branch_name, limit=20):
    """获取分支上没有 MR 的 commits"""
    try:
        gitlab_url = get_gitlab_url()
        project_path = project_url.replace(gitlab_url + '/', '').strip('/')
        
        # 获取分支的 commits
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits"
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        params = {'ref_name': branch_name, 'per_page': limit}
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        commits = response.json()
        
        # 获取该分支的所有 MR
        mr_api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests"
        mr_params = {'source_branch': branch_name, 'per_page': 100}
        mr_response = requests.get(mr_api_url, headers=headers, params=mr_params)
        mr_response.raise_for_status()
        mrs = mr_response.json()
        
        # 获取所有 MR 中包含的 commit SHA
        mr_commit_shas = set()
        for mr in mrs:
            # 获取 MR 的 commits
            mr_commits_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests/{mr['iid']}/commits"
            mr_commits_response = requests.get(mr_commits_url, headers=headers)
            if mr_commits_response.status_code == 200:
                mr_commits = mr_commits_response.json()
                for commit in mr_commits:
                    mr_commit_shas.add(commit['id'])
        
        # 过滤出没有 MR 的 commits
        commits_without_mr = []
        for commit in commits:
            if commit['id'] not in mr_commit_shas:
                commits_without_mr.append({
                    'id': commit['id'],
                    'short_id': commit['short_id'],
                    'title': commit['title'],
                    'message': commit['message'],
                    'author_name': commit['author_name'],
                    'created_at': commit['created_at'],
                    'web_url': commit['web_url'],
                    'branch': branch_name,
                    'is_commit': True  # 标记这是 commit 而不是 MR
                })
        
        return commits_without_mr
    except Exception as e:
        print(f"获取分支 commits 失败: {e}")
        return []

@app.route('/api/projects/mrs', methods=['POST'])
def get_mrs():
    """获取项目的 MR 列表（可选包含没有 MR 的 commits）"""
    data = request.json
    project_url = data.get('project_url', '')
    state = data.get('state', 'opened')  # opened, merged, closed, all
    target_branch = data.get('target_branch', '')  # 目标分支过滤
    include_commits = data.get('include_commits', False)  # 是否包含没有 MR 的 commits
    
    if not project_url:
        return jsonify({'error': '请输入项目 URL'}), 400
    
    mrs = get_project_mrs(project_url, state, target_branch)
    
    # 如果选择了包含 commits，且选择了特定分支，且状态为 all
    # 则也包含该分支上没有 MR 的 commits
    if include_commits and target_branch and state == 'all':
        commits_without_mr = get_branch_commits_without_mr(project_url, target_branch, limit=20)
        # 合并 MR 和 commits
        all_items = mrs + commits_without_mr
        # 按时间排序
        all_items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'mrs': all_items, 'has_commits': len(commits_without_mr) > 0})
    
    return jsonify({'mrs': mrs, 'has_commits': False})

@app.route('/api/review', methods=['POST'])
def start_review():
    """开始审查 MR"""
    data = request.json
    mr_url = data.get('mr_url', '')
    mr_id = data.get('mr_id', '')
    file_level_review = data.get('file_level_review', False)  # 获取文件级审核参数
    
    if not mr_url or not mr_id:
        return jsonify({'error': '缺少参数'}), 400
    
    # 获取用户的 GitLab Token
    gitlab_token = request.headers.get('X-GitLab-Token')
    
    # 记录审查模式
    review_mode = '文件级审核' if file_level_review else '总体审核'
    print(f"📂 MR 审查模式: {review_mode}")
    
    # 在后台线程中执行审查
    thread = threading.Thread(target=review_mr, args=(mr_url, mr_id, gitlab_token, file_level_review))
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

@app.route('/api/user/info', methods=['GET'])
def get_user_info():
    """获取 GitLab 用户信息"""
    try:
        # 从请求头获取 Token
        gitlab_token = request.headers.get('X-GitLab-Token')
        if not gitlab_token:
            return jsonify({
                'success': False,
                'message': '未提供 GitLab Token'
            }), 401
        
        # 获取 GitLab URL
        config = load_env_config()
        gitlab_url = config.get('GITLAB__URL', 'https://gitlab.com')
        
        # 调用 GitLab API 获取用户信息
        headers = {'PRIVATE-TOKEN': gitlab_token}
        response = requests.get(f"{gitlab_url}/api/v4/user", headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                'success': True,
                'user': {
                    'id': user_data.get('id'),
                    'username': user_data.get('username'),
                    'name': user_data.get('name'),
                    'email': user_data.get('email'),
                    'avatar_url': user_data.get('avatar_url')
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Token 无效或已过期'
            }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取用户信息失败: {str(e)}'
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
                'android': {
                    'name': 'Android 项目',
                    'description': '专注于 Android/Kotlin/Java 开发的审查',
                    'prompt': '请对这个 Android Merge Request 进行审查，重点关注：\n1. Kotlin/Java 代码规范和最佳实践\n2. 内存泄漏和生命周期管理（Activity、Fragment、ViewModel）\n3. UI 性能和布局优化（避免过度绘制、使用 ConstraintLayout）\n4. Android API 使用是否正确（版本兼容性）\n5. 线程安全和异步处理（协程、RxJava、Handler）\n6. 资源管理（Bitmap、Cursor、文件流是否正确关闭）\n7. 是否遵循 Material Design 设计规范\n8. 权限申请和安全性问题\n9. 数据持久化方案（SharedPreferences、Room、SQLite）\n10. 网络请求和错误处理'
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
        file_level_review = data.get('file_level_review', False)  # 获取文件级审核参数
        
        if not commit_url or not commit_id:
            return jsonify({'error': '请提供 Commit URL 和 ID'}), 400
        
        # 获取用户的 GitLab Token
        user_gitlab_token = request.headers.get('X-GitLab-Token')
        
        # 记录审查模式
        review_mode = '文件级审核' if file_level_review else '总体审核'
        print(f"📂 Commit 审查模式: {review_mode}")
        
        # 生成唯一的审查 ID
        review_id = f"commit-{commit_id[:8]}-{int(get_china_time().timestamp())}"
        
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
                # 优先使用用户提供的 Token
                token = user_gitlab_token if user_gitlab_token else get_gitlab_token()
                headers = {'PRIVATE-TOKEN': token}
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
                
                # 根据审查模式选择不同的审查方式
                if file_level_review:
                    # 两阶段审查策略：先总体扫描，再针对性行内审查
                    review_status[review_id]['message'] = '阶段 1/2: 总体扫描，识别问题...'
                    review_status[review_id]['progress'] = 40
                    
                    # 阶段 1: 总体审查，让 AI 识别有问题的代码块
                    diff_text = ""
                    for diff in diffs[:10]:
                        diff_text += f"\n\n文件: {diff['new_path']}\n"
                        diff_text += f"变更: +{diff.get('added_lines', 0)} -{diff.get('removed_lines', 0)}\n"
                        diff_text += diff.get('diff', '')[:2000]
                    
                    # 让 AI 识别问题
                    scan_prompt = f"""请快速扫描以下代码变更，识别需要详细审查的代码块。

代码变更：
{diff_text}

请以 JSON 格式返回需要详细审查的代码块列表，格式如下：
```json
{{
  "issues": [
    {{
      "file": "文件路径",
      "line": 行号,
      "severity": "high/medium/low",
      "reason": "简短原因（不超过20字）"
    }}
  ]
}}
```

**筛选标准：**
- high: 安全漏洞、空指针、内存泄漏、逻辑错误
- medium: 性能问题、代码规范、潜在bug
- low: 代码风格、命名建议

**只返回 high 和 medium 级别的问题，忽略 low 级别。**
如果代码没有问题，返回空数组。"""

                    try:
                        scan_response = requests.post(
                            'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                            headers={
                                'Authorization': f'Bearer {ai_api_key}',
                                'Content-Type': 'application/json'
                            },
                            json={
                                'model': ai_model,
                                'input': {'messages': [{'role': 'user', 'content': scan_prompt}]},
                                'parameters': {'result_format': 'message'}
                            },
                            proxies={'http': None, 'https': None},
                            timeout=60
                        )
                        
                        if scan_response.status_code != 200:
                            raise Exception(f'总体扫描失败: {scan_response.text}')
                        
                        scan_result = scan_response.json()
                        scan_content = scan_result['output']['choices'][0]['message']['content']
                        
                        print(f"📄 AI 扫描结果:\n{scan_content[:500]}...")
                        
                        # 解析 JSON 结果
                        import json
                        import re
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', scan_content, re.DOTALL)
                        if json_match:
                            issues_data = json.loads(json_match.group(1))
                            issues = issues_data.get('issues', [])
                        else:
                            # 尝试直接解析
                            issues = json.loads(scan_content).get('issues', [])
                        
                        print(f"📊 总体扫描完成，发现 {len(issues)} 个需要详细审查的问题")
                        if issues:
                            print(f"   问题列表: {json.dumps(issues, ensure_ascii=False, indent=2)}")
                        
                        if len(issues) == 0:
                            review_status[review_id]['progress'] = 100
                            review_status[review_id]['status'] = 'success'
                            review_status[review_id]['message'] = '✅ 代码质量良好，未发现需要详细审查的问题'
                            review_status[review_id]['output'] = '✅ 总体扫描完成\n\n代码质量良好，未发现严重问题。'
                            save_history(commit_url, 'commit', 'success')
                            return
                        
                    except Exception as e:
                        print(f"⚠️ 总体扫描失败，回退到全量审查: {e}")
                        issues = []  # 如果扫描失败，回退到全量审查
                    
                    # 阶段 2: 针对性行内审查
                    review_status[review_id]['message'] = f'阶段 2/2: 详细审查 {len(issues) if issues else "所有"} 个代码块...'
                    review_status[review_id]['progress'] = 50
                    
                    comments_created = 0
                    total_files = min(len(diffs), 10)
                    
                    # 如果有 AI 识别的问题列表，只审查这些代码块
                    if issues:
                        # 针对性审查：只审查 AI 识别出的问题代码块
                        for idx, issue in enumerate(issues):
                            file_path = issue.get('file', '')
                            target_line = issue.get('line', 0)
                            severity = issue.get('severity', 'medium')
                            reason = issue.get('reason', '')
                            
                            print(f"🔍 处理问题 {idx+1}/{len(issues)}: {file_path}:{target_line} [{severity}] - {reason}")
                            
                            review_status[review_id]['progress'] = 50 + int((idx / len(issues)) * 40)
                            review_status[review_id]['message'] = f'详细审查 {idx+1}/{len(issues)}: {file_path}:{target_line}'
                            
                            # 找到对应的 diff
                            target_diff = None
                            for diff in diffs:
                                if diff['new_path'] == file_path:
                                    target_diff = diff
                                    break
                            
                            if not target_diff:
                                print(f"⚠️ 未找到文件的 diff: {file_path}")
                                print(f"   可用的文件: {[d['new_path'] for d in diffs]}")
                                continue
                            
                            diff_content = target_diff.get('diff', '')
                            if not diff_content:
                                continue
                            
                            # 解析 diff，找到目标行附近的代码块
                            import re
                            hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@([^@]*)', diff_content)
                            
                            print(f"   找到 {len(hunks)} 个代码块")
                            
                            found_target = False
                            for hunk in hunks:
                                old_start, new_start, hunk_content = hunk
                                new_line = int(new_start)
                                
                                # 提取新增的行
                                added_lines = []
                                current_line = new_line
                                for line in hunk_content.split('\n'):
                                    if line.startswith('+') and not line.startswith('+++'):
                                        added_lines.append((current_line, line[1:]))
                                        current_line += 1
                                    elif not line.startswith('-'):
                                        current_line += 1
                                
                                if not added_lines:
                                    continue
                                
                                start_line = added_lines[0][0]
                                end_line = added_lines[-1][0]
                                
                                print(f"   代码块范围: {start_line}-{end_line}, 目标行: {target_line}")
                                
                                # 检查目标行是否在这个代码块范围内（允许 ±5 行的偏差）
                                if (start_line - 5) <= target_line <= (end_line + 5):
                                    found_target = True
                                    print(f"   ✅ 找到匹配的代码块（允许偏差）")
                                    # 使用实际的代码块起始行
                                    target_line = start_line
                                    code_block = '\n'.join([line[1] for line in added_lines])
                                    
                                    # 构建详细审查 prompt
                                    block_prompt = f"""请详细审查以下代码片段（文件: {file_path}, 行 {start_line}-{end_line}）：

```
{code_block}
```

**初步扫描发现的问题：**
- 严重程度: {severity}
- 问题描述: {reason}

请提供详细的审查意见：
1. ❌ 确认问题并详细说明
2. 💡 提供具体的修复建议（包含代码示例）
3. ⚠️ 其他需要注意的地方

请使用中文，提供可执行的修复代码。"""
                                    
                                    # 调用 AI 进行详细审查
                                    try:
                                        ai_response = requests.post(
                                            'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                                            headers={
                                                'Authorization': f'Bearer {ai_api_key}',
                                                'Content-Type': 'application/json'
                                            },
                                            json={
                                                'model': ai_model,
                                                'input': {'messages': [{'role': 'user', 'content': block_prompt}]},
                                                'parameters': {'result_format': 'message'}
                                            },
                                            proxies={'http': None, 'https': None},
                                            timeout=60
                                        )
                                        
                                        if ai_response.status_code == 200:
                                            ai_result = ai_response.json()
                                            review_comment = ai_result['output']['choices'][0]['message']['content']
                                            
                                            # 创建行内评论（使用 Comments API）
                                            comment_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/comments"
                                            comment_data = {
                                                'note': f"🤖 **AI 代码审查** [{severity.upper()}]\n\n**文件:** {file_path}:{target_line}\n\n{review_comment}",
                                                'path': file_path,
                                                'line': target_line,
                                                'line_type': 'new'
                                            }
                                            
                                            comment_response = requests.post(
                                                comment_url,
                                                headers=headers,
                                                json=comment_data,
                                                timeout=30
                                            )
                                            
                                            if comment_response.status_code in [200, 201]:
                                                comments_created += 1
                                                print(f"✅ 创建行内评论: {file_path}:{target_line} [{severity}]")
                                            else:
                                                print(f"⚠️ 创建评论失败: {comment_response.status_code}")
                                                print(f"   错误详情: {comment_response.text}")
                                                print(f"   请求数据: {comment_data}")
                                    
                                    except Exception as e:
                                        print(f"⚠️ 详细审查失败: {e}")
                                        import traceback
                                        traceback.print_exc()
                                    
                                    break  # 找到目标行后跳出
                            
                            if not found_target:
                                print(f"⚠️ 未找到目标行 {target_line} 对应的代码块")
                    
                    else:
                        # 回退到全量审查：审查所有代码块
                        for idx, diff in enumerate(diffs[:10]):
                            file_path = diff['new_path']
                            diff_content = diff.get('diff', '')
                            
                            if not diff_content:
                                continue
                            
                            review_status[review_id]['progress'] = 50 + int((idx / total_files) * 30)
                            review_status[review_id]['message'] = f'审查文件 {idx+1}/{total_files}: {file_path}'
                            
                            # 解析 diff 获取变更的行号
                            import re
                            hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@([^@]*)', diff_content)
                            
                            for hunk in hunks:
                                old_start, new_start, hunk_content = hunk
                                new_line = int(new_start)
                                
                                # 只分析新增或修改的行
                                added_lines = []
                                current_line = new_line
                                for line in hunk_content.split('\n'):
                                    if line.startswith('+') and not line.startswith('+++'):
                                        added_lines.append((current_line, line[1:]))
                                        current_line += 1
                                    elif not line.startswith('-'):
                                        current_line += 1
                                
                                # 如果有新增的行，对这个代码块进行审查
                                if added_lines and len(added_lines) <= 20:
                                    code_block = '\n'.join([line[1] for line in added_lines])
                                    start_line = added_lines[0][0]
                                    end_line = added_lines[-1][0]
                                    
                                    # 构建针对这个代码块的审查 prompt
                                    block_prompt = f"""请审查以下代码片段（文件: {file_path}, 行 {start_line}-{end_line}）：

```
{code_block}
```

请简洁地指出：
1. ❌ 严重问题（如果有）
2. ⚠️ 潜在问题或改进建议（如果有）
3. ✅ 好的做法（如果有）

如果代码没有问题，请回复"✅ 代码正常"。
请使用中文，简洁明了，不超过200字。"""
                                    
                                    # 调用 AI 审查这个代码块
                                    try:
                                        ai_response = requests.post(
                                            'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                                            headers={
                                                'Authorization': f'Bearer {ai_api_key}',
                                                'Content-Type': 'application/json'
                                            },
                                            json={
                                                'model': ai_model,
                                                'input': {'messages': [{'role': 'user', 'content': block_prompt}]},
                                                'parameters': {'result_format': 'message'}
                                            },
                                            proxies={'http': None, 'https': None},
                                            timeout=60
                                        )
                                        
                                        if ai_response.status_code == 200:
                                            ai_result = ai_response.json()
                                            review_comment = ai_result['output']['choices'][0]['message']['content']
                                            
                                            # 只有在发现问题或有建议时才创建评论
                                            if '✅ 代码正常' not in review_comment and review_comment.strip():
                                                # 在 GitLab 上创建行内评论（使用 Comments API）
                                                comment_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/comments"
                                                comment_data = {
                                                    'note': f"🤖 **AI 代码审查**\n\n**文件:** {file_path}:{start_line}\n\n{review_comment}",
                                                    'path': file_path,
                                                    'line': start_line,
                                                    'line_type': 'new'
                                                }
                                                
                                                comment_response = requests.post(
                                                    comment_url,
                                                    headers=headers,
                                                    json=comment_data,
                                                    timeout=30
                                                )
                                                
                                                if comment_response.status_code in [200, 201]:
                                                    comments_created += 1
                                                    print(f"✅ 创建行内评论: {file_path}:{start_line}")
                                                else:
                                                    print(f"⚠️ 创建评论失败: {comment_response.status_code}")
                                                    print(f"   错误详情: {comment_response.text}")
                                                    print(f"   请求数据: {comment_data}")
                                        
                                    except Exception as e:
                                        print(f"⚠️ 审查代码块失败: {e}")
                                        continue
                    
                    # 构建详细的问题列表展示
                    issues_summary = "## 📊 AI 代码审查结果\n\n"
                    
                    if issues:
                        issues_summary += f"**发现 {len(issues)} 个需要关注的问题，已创建 {comments_created} 条行内评论**\n\n"
                        
                        # 按严重程度分组
                        high_issues = [i for i in issues if i.get('severity') == 'high']
                        medium_issues = [i for i in issues if i.get('severity') == 'medium']
                        low_issues = [i for i in issues if i.get('severity') == 'low']
                        
                        if high_issues:
                            issues_summary += "### 🔴 高危问题\n\n"
                            for issue in high_issues:
                                file_name = issue.get('file', '').split('/')[-1]
                                issues_summary += f"- **{file_name}:{issue.get('line')}**\n"
                                issues_summary += f"  - {issue.get('reason', '无描述')}\n\n"
                        
                        if medium_issues:
                            issues_summary += "### 🟡 中等问题\n\n"
                            for issue in medium_issues:
                                file_name = issue.get('file', '').split('/')[-1]
                                issues_summary += f"- **{file_name}:{issue.get('line')}**\n"
                                issues_summary += f"  - {issue.get('reason', '无描述')}\n\n"
                        
                        if low_issues:
                            issues_summary += "### 🟢 低危问题\n\n"
                            for issue in low_issues:
                                file_name = issue.get('file', '').split('/')[-1]
                                issues_summary += f"- **{file_name}:{issue.get('line')}**\n"
                                issues_summary += f"  - {issue.get('reason', '无描述')}\n\n"
                        
                        issues_summary += "\n💬 **详细的审查意见已添加到代码旁边，请在 GitLab Commit 页面查看行内评论。**"
                    else:
                        issues_summary += "✅ 代码质量良好，未发现需要关注的问题。"
                    
                    review_status[review_id]['progress'] = 100
                    review_status[review_id]['status'] = 'success'
                    review_status[review_id]['message'] = f'文件级审核完成！创建了 {comments_created} 条行内评论'
                    review_status[review_id]['output'] = issues_summary
                    
                    # 保存历史记录
                    save_history(commit_url, 'commit', 'success')
                    return  # 文件级审核完成，直接返回
                
                else:
                    # 总体审核 - 简洁模式
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

@app.route('/api/webhook/groups', methods=['GET'])
def get_gitlab_groups():
    """获取用户可访问的 GitLab 组"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        api_url = f"{gitlab_url}/api/v4/groups"
        params = {
            'per_page': 100,
            'order_by': 'name',
            'sort': 'asc'
        }
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        groups = response.json()
        
        # 简化组信息，并获取准确的项目数量
        simplified_groups = []
        for group in groups:
            # 获取组的准确项目数量
            group_id = group['id']
            projects_url = f"{gitlab_url}/api/v4/groups/{group_id}/projects"
            projects_params = {'per_page': 1, 'archived': False}
            
            try:
                projects_response = requests.get(projects_url, headers=headers, params=projects_params)
                # 从响应头获取总数
                total_count = int(projects_response.headers.get('X-Total', 0))
            except:
                total_count = 0
            
            simplified_groups.append({
                'id': group['id'],
                'name': group['name'],
                'full_path': group['full_path'],
                'description': group.get('description', ''),
                'project_count': total_count
            })
        
        return jsonify({'groups': simplified_groups})
    except Exception as e:
        print(f"获取组列表失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/group-projects/<group_id>', methods=['GET'])
def get_webhook_group_projects(group_id):
    """获取组内的所有项目，并检查 Webhook 配置状态"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        webhook_url = request.args.get('webhook_url', '')
        
        api_url = f"{gitlab_url}/api/v4/groups/{group_id}/projects"
        params = {
            'per_page': 100,
            'include_subgroups': True,
            'archived': False
        }
        
        all_projects = []
        page = 1
        
        while True:
            params['page'] = page
            response = requests.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            
            projects = response.json()
            if not projects:
                break
            
            for project in projects:
                project_id = project['id']
                
                # 检查该项目是否已配置 Webhook
                has_webhook = False
                actual_webhook_url = None
                if webhook_url:
                    try:
                        hooks_url = f"{gitlab_url}/api/v4/projects/{project_id}/hooks"
                        hooks_response = requests.get(hooks_url, headers=headers, timeout=2)
                        if hooks_response.status_code == 200:
                            existing_hooks = hooks_response.json()
                            for hook in existing_hooks:
                                if hook['url'] == webhook_url:
                                    has_webhook = True
                                    actual_webhook_url = hook['url']
                                    break
                            # 如果没有找到匹配的，但有其他 webhook，记录第一个
                            if not has_webhook and existing_hooks:
                                # 检查是否有包含 /webhook/gitlab 的 hook
                                for hook in existing_hooks:
                                    if '/webhook/gitlab' in hook['url']:
                                        has_webhook = True
                                        actual_webhook_url = hook['url']
                                        break
                    except:
                        pass
                
                all_projects.append({
                    'id': project['id'],
                    'name': project['name'],
                    'path_with_namespace': project['path_with_namespace'],
                    'web_url': project['web_url'],
                    'has_webhook': has_webhook,
                    'webhook_url': actual_webhook_url
                })
            
            page += 1
            if page > 10:  # 最多获取 10 页，避免超时
                break
        
        return jsonify({'projects': all_projects})
    except Exception as e:
        print(f"获取组项目失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/batch-setup', methods=['POST'])
def batch_setup_webhooks():
    """批量为项目配置 Webhook"""
    try:
        data = request.json
        project_ids = data.get('project_ids', [])
        webhook_url = data.get('webhook_url', '')
        webhook_secret = data.get('webhook_secret', '')
        
        if not project_ids or not webhook_url:
            return jsonify({'error': '缺少必要参数'}), 400
        
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        results = []
        
        for project_id in project_ids:
            try:
                # 获取项目信息
                project_url = f"{gitlab_url}/api/v4/projects/{project_id}"
                project_response = requests.get(project_url, headers=headers)
                project_info = project_response.json()
                project_name = project_info.get('path_with_namespace', str(project_id))
                
                # 检查是否已存在相同的 Webhook
                hooks_url = f"{gitlab_url}/api/v4/projects/{project_id}/hooks"
                hooks_response = requests.get(hooks_url, headers=headers)
                
                if hooks_response.status_code != 200:
                    results.append({
                        'project_id': project_id,
                        'project_name': project_name,
                        'status': 'error',
                        'message': '无权限访问项目'
                    })
                    continue
                
                existing_hooks = hooks_response.json()
                
                # 检查是否已存在
                existing_hook_id = None
                for hook in existing_hooks:
                    if hook['url'] == webhook_url:
                        existing_hook_id = hook['id']
                        break
                
                # Webhook 配置数据
                # 使用 Wildcard pattern: * 匹配所有分支
                # 注意：不同 GitLab 版本行为可能不同
                # - 不设置参数：某些版本显示 All branches，某些版本显示 Wildcard pattern
                # - 设置为 '*'：明确使用通配符匹配所有分支
                webhook_data = {
                    'url': webhook_url,
                    'token': webhook_secret,
                    'merge_requests_events': True,
                    'push_events': True,  # 启用 Push events 以触发 Commit 审查
                    'push_events_branch_filter': '*',  # 使用 * 通配符匹配所有分支
                    'issues_events': False,
                    'note_events': False,
                    'enable_ssl_verification': False
                }
                
                print(f"[DEBUG] 配置 Webhook 数据: {webhook_data}")
                
                if existing_hook_id:
                    # 更新现有 Webhook
                    update_url = f"{hooks_url}/{existing_hook_id}"
                    print(f"[DEBUG] 更新 Webhook: {update_url}")
                    update_response = requests.put(update_url, headers=headers, json=webhook_data)
                    print(f"[DEBUG] 更新响应状态: {update_response.status_code}")
                    if update_response.status_code == 200:
                        response_json = update_response.json()
                        print(f"[DEBUG] 更新响应完整内容: {response_json}")
                        print(f"[DEBUG] push_events_branch_filter 值: {response_json.get('push_events_branch_filter', 'NOT_FOUND')}")
                    else:
                        print(f"[DEBUG] 更新失败: {update_response.text}")
                    
                    if update_response.status_code == 200:
                        results.append({
                            'project_id': project_id,
                            'project_name': project_name,
                            'status': 'updated',
                            'message': 'Webhook 更新成功'
                        })
                    else:
                        results.append({
                            'project_id': project_id,
                            'project_name': project_name,
                            'status': 'error',
                            'message': f'更新失败: {update_response.text}'
                        })
                else:
                    # 添加新 Webhook
                    print(f"[DEBUG] 添加新 Webhook: {hooks_url}")
                    add_response = requests.post(hooks_url, headers=headers, json=webhook_data)
                    print(f"[DEBUG] 添加响应状态: {add_response.status_code}")
                    if add_response.status_code == 201:
                        response_json = add_response.json()
                        print(f"[DEBUG] 添加响应完整内容: {response_json}")
                        print(f"[DEBUG] push_events_branch_filter 值: {response_json.get('push_events_branch_filter', 'NOT_FOUND')}")
                    else:
                        print(f"[DEBUG] 添加失败: {add_response.text}")
                    
                    if add_response.status_code == 201:
                        results.append({
                            'project_id': project_id,
                            'project_name': project_name,
                            'status': 'success',
                            'message': 'Webhook 添加成功'
                        })
                    else:
                        results.append({
                            'project_id': project_id,
                            'project_name': project_name,
                            'status': 'error',
                            'message': f'添加失败: {add_response.text}'
                        })
                
            except Exception as e:
                results.append({
                    'project_id': project_id,
                    'project_name': project_name if 'project_name' in locals() else str(project_id),
                    'status': 'error',
                    'message': str(e)
                })
        
        # 统计结果
        success_count = sum(1 for r in results if r['status'] == 'success')
        updated_count = sum(1 for r in results if r['status'] == 'updated')
        skipped_count = sum(1 for r in results if r['status'] == 'skipped')
        error_count = sum(1 for r in results if r['status'] == 'error')
        
        return jsonify({
            'results': results,
            'summary': {
                'total': len(results),
                'success': success_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'error': error_count
            }
        })
        
    except Exception as e:
        print(f"批量配置 Webhook 失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/batch-delete', methods=['POST'])
def batch_delete_webhooks():
    """批量删除项目的 Webhook"""
    try:
        data = request.json
        project_ids = data.get('project_ids', [])
        webhook_url = data.get('webhook_url')
        
        if not project_ids or not webhook_url:
            return jsonify({'error': '缺少必要参数'}), 400
        
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        results = []
        
        for project_id in project_ids:
            try:
                # 获取项目的 Webhooks
                hooks_url = f"{gitlab_url}/api/v4/projects/{project_id}/hooks"
                hooks_response = requests.get(hooks_url, headers=headers)
                
                if hooks_response.status_code != 200:
                    results.append({
                        'project_id': project_id,
                        'status': 'error',
                        'message': '无权限访问项目'
                    })
                    continue
                
                existing_hooks = hooks_response.json()
                
                # 查找匹配的 Webhook
                hook_to_delete = None
                for hook in existing_hooks:
                    if hook['url'] == webhook_url:
                        hook_to_delete = hook
                        break
                
                if not hook_to_delete:
                    results.append({
                        'project_id': project_id,
                        'status': 'skipped',
                        'message': 'Webhook 不存在'
                    })
                    continue
                
                # 删除 Webhook
                delete_url = f"{hooks_url}/{hook_to_delete['id']}"
                delete_response = requests.delete(delete_url, headers=headers)
                
                if delete_response.status_code == 204:
                    print(f"✅ 删除 Webhook 成功: 项目 {project_id}")
                    results.append({
                        'project_id': project_id,
                        'status': 'success',
                        'message': 'Webhook 已删除'
                    })
                else:
                    results.append({
                        'project_id': project_id,
                        'status': 'error',
                        'message': f'删除失败: {delete_response.status_code}'
                    })
                    
            except Exception as e:
                print(f"删除项目 {project_id} 的 Webhook 失败: {e}")
                results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'message': str(e)
                })
        
        # 统计结果
        success_count = sum(1 for r in results if r['status'] == 'success')
        skipped_count = sum(1 for r in results if r['status'] == 'skipped')
        error_count = sum(1 for r in results if r['status'] == 'error')
        
        return jsonify({
            'results': results,
            'summary': {
                'total': len(results),
                'success': success_count,
                'skipped': skipped_count,
                'error': error_count
            }
        })
        
    except Exception as e:
        print(f"批量删除 Webhook 失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/check-config', methods=['POST'])
def check_webhook_config():
    """检查 Webhook 配置状态"""
    try:
        data = request.json
        project_id = data.get('project_id')
        webhook_url = data.get('webhook_url')
        
        if not project_id or not webhook_url:
            return jsonify({'error': '缺少必要参数'}), 400
        
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        
        # 获取项目的 Webhooks
        hooks_url = f"{gitlab_url}/api/v4/projects/{project_id}/hooks"
        hooks_response = requests.get(hooks_url, headers=headers)
        
        if hooks_response.status_code != 200:
            return jsonify({'error': '无权限访问项目'}), 403
        
        existing_hooks = hooks_response.json()
        
        # 查找匹配的 Webhook
        target_hook = None
        for hook in existing_hooks:
            if hook['url'] == webhook_url:
                target_hook = hook
                break
        
        if not target_hook:
            return jsonify({
                'configured': False,
                'message': 'Webhook 未配置'
            })
        
        # 检查配置是否正确
        issues = []
        
        # 检查 Push events
        if not target_hook.get('push_events'):
            issues.append('Push events 未启用')
        
        # 检查 branch_filter_strategy
        branch_filter = target_hook.get('branch_filter_strategy', 'wildcard')
        if branch_filter != 'all_branches':
            issues.append(f'分支过滤策略不是 All branches（当前: {branch_filter}）')
        
        # 检查 Merge Request events
        if not target_hook.get('merge_requests_events'):
            issues.append('Merge Request events 未启用')
        
        # 检查 SSL verification
        if target_hook.get('enable_ssl_verification'):
            issues.append('SSL verification 已启用（内网应禁用）')
        
        return jsonify({
            'configured': True,
            'webhook_id': target_hook['id'],
            'push_events': target_hook.get('push_events', False),
            'merge_requests_events': target_hook.get('merge_requests_events', False),
            'branch_filter_strategy': branch_filter,
            'enable_ssl_verification': target_hook.get('enable_ssl_verification', False),
            'issues': issues,
            'is_correct': len(issues) == 0
        })
        
    except Exception as e:
        print(f"检查 Webhook 配置失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auto-review/config', methods=['GET'])
def get_auto_review_config():
    """获取自动审查配置"""
    try:
        config = load_env_config()
        return jsonify({
            'auto_review_enabled': config.get('AUTO_REVIEW_ENABLED', 'false'),
            'auto_review_target_branches': config.get('AUTO_REVIEW_TARGET_BRANCHES', 'master,main,develop'),
            'auto_review_skip_draft': config.get('AUTO_REVIEW_SKIP_DRAFT', 'true'),
            'auto_review_min_changes': config.get('AUTO_REVIEW_MIN_CHANGES', '0'),
            'auto_review_push_enabled': config.get('AUTO_REVIEW_PUSH_ENABLED', 'false'),
            'auto_review_push_branches': config.get('AUTO_REVIEW_PUSH_BRANCHES', 'master,main'),
            'auto_review_push_new_branch_all_commits': config.get('AUTO_REVIEW_PUSH_NEW_BRANCH_ALL_COMMITS', 'false'),
            'auto_review_file_level_enabled': config.get('AUTO_REVIEW_FILE_LEVEL_ENABLED', 'false')  # 文件级审核，默认关闭
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/configured-projects', methods=['GET'])
def get_configured_projects():
    """获取所有已配置 Webhook 的项目"""
    try:
        gitlab_url = get_gitlab_url()
        headers = {'PRIVATE-TOKEN': get_gitlab_token()}
        webhook_url = request.args.get('webhook_url', '')
        match_mode = request.args.get('match_mode', 'exact')  # exact: 精确匹配, contains: 包含匹配, all: 所有webhook
        
        # 获取用户所有可访问的项目
        projects_url = f"{gitlab_url}/api/v4/projects"
        params = {
            'membership': 'true',
            'per_page': 100,
            'simple': 'true',
            'order_by': 'last_activity_at'
        }
        
        all_projects = []
        page = 1
        while True:
            params['page'] = page
            response = requests.get(projects_url, headers=headers, params=params)
            response.raise_for_status()
            projects = response.json()
            
            if not projects:
                break
            
            all_projects.extend(projects)
            page += 1
            
            # 限制最多获取 500 个项目
            if len(all_projects) >= 500:
                break
        
        # 检查每个项目的 Webhook 配置
        configured_projects = []
        for project in all_projects:
            project_id = project['id']
            
            # 获取项目的 Webhooks
            hooks_url = f"{gitlab_url}/api/v4/projects/{project_id}/hooks"
            try:
                hooks_response = requests.get(hooks_url, headers=headers, timeout=5)
                if hooks_response.status_code == 200:
                    hooks = hooks_response.json()
                    
                    # 查找匹配的 Webhook
                    for hook in hooks:
                        should_add = False
                        hook_url = hook.get('url', '')
                        
                        if match_mode == 'all':
                            # 显示所有配置了 webhook 的项目
                            should_add = True
                        elif match_mode == 'contains' and webhook_url:
                            # 包含匹配：只要路径部分匹配即可（忽略主机名和端口）
                            # 提取路径部分，例如从 http://localhost:8080/webhook/gitlab 提取 /webhook/gitlab
                            try:
                                # 分割 URL，获取路径部分
                                if '://' in webhook_url:
                                    webhook_path = '/' + webhook_url.split('://')[-1].split('/', 1)[1]
                                else:
                                    webhook_path = webhook_url
                                
                                if '://' in hook_url:
                                    hook_path = '/' + hook_url.split('://')[-1].split('/', 1)[1]
                                else:
                                    hook_path = hook_url
                                
                                # 检查路径是否匹配
                                should_add = webhook_path == hook_path
                            except:
                                # 如果解析失败，使用简单的包含匹配
                                should_add = '/webhook/gitlab' in hook_url
                        elif match_mode == 'exact' and webhook_url:
                            # 精确匹配
                            should_add = hook_url == webhook_url
                        elif not webhook_url:
                            # 如果没有指定 webhook_url，返回所有配置了 webhook 的项目
                            should_add = True
                        
                        if should_add:
                            configured_projects.append({
                                'id': project['id'],
                                'name': project['name'],
                                'path_with_namespace': project['path_with_namespace'],
                                'web_url': project['web_url'],
                                'namespace': project.get('namespace', {}).get('full_path', ''),
                                'hook_id': hook['id'],
                                'hook_url': hook['url'],
                                'push_events': hook.get('push_events', False),
                                'merge_requests_events': hook.get('merge_requests_events', False)
                            })
                            break  # 每个项目只添加一次
            except Exception as e:
                print(f"检查项目 {project_id} 的 Webhook 失败: {e}")
                continue
        
        return jsonify({
            'projects': configured_projects,
            'total': len(configured_projects)
        })
        
    except Exception as e:
        print(f"获取已配置项目失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auto-review/config', methods=['POST'])
def update_auto_review_config():
    """更新自动审查配置"""
    try:
        data = request.json
        
        # 读取现有配置
        config_lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'r') as f:
                config_lines = f.readlines()
        
        # 要更新的配置项
        updates = {
            'AUTO_REVIEW_ENABLED': data.get('auto_review_enabled', 'false'),
            'AUTO_REVIEW_TARGET_BRANCHES': data.get('auto_review_target_branches', 'master,main,develop'),
            'AUTO_REVIEW_SKIP_DRAFT': data.get('auto_review_skip_draft', 'true'),
            'AUTO_REVIEW_MIN_CHANGES': data.get('auto_review_min_changes', '0'),
            'AUTO_REVIEW_PUSH_ENABLED': data.get('auto_review_push_enabled', 'false'),
            'AUTO_REVIEW_PUSH_BRANCHES': data.get('auto_review_push_branches', 'master,main'),
            'AUTO_REVIEW_PUSH_NEW_BRANCH_ALL_COMMITS': data.get('auto_review_push_new_branch_all_commits', 'false'),
            'AUTO_REVIEW_FILE_LEVEL_ENABLED': data.get('auto_review_file_level_enabled', 'false')  # 文件级审核
        }
        
        # 更新配置
        new_lines = []
        updated_keys = set()
        
        for line in config_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0]
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # 添加新的配置项
        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")
        
        # 写入文件
        os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
        with open(ENV_FILE, 'w') as f:
            f.writelines(new_lines)
        
        return jsonify({
            'success': True,
            'message': '自动审查配置已保存'
        })
        
    except Exception as e:
        print(f"保存自动审查配置失败: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/review/report', methods=['GET'])
def get_review_report():
    """获取审查报表"""
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        review_type = request.args.get('type', 'all')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM review_records WHERE 1=1'
        params = []
        
        if date_from:
            query += ' AND timestamp >= ?'
            params.append(date_from)
        
        if date_to:
            # 包含当天的所有记录
            query += ' AND timestamp <= datetime(?, "+1 day")'
            params.append(date_to)
        
        if review_type != 'all':
            query += ' AND type = ?'
            params.append(review_type)
        
        query += ' ORDER BY timestamp DESC LIMIT 1000'
        
        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'records': [
                {
                    'id': r[0],
                    'type': r[1],
                    'project_id': r[2],
                    'project': r[3],
                    'title': r[4],
                    'url': r[5],
                    'author': r[6],
                    'branch': r[7],
                    'timestamp': r[8]
                }
                for r in records
            ]
        })
        
    except Exception as e:
        print(f"获取审查报表失败: {e}")
        return jsonify({'error': str(e), 'records': []}), 500

@app.route('/webhook/gitlab', methods=['POST'])
def gitlab_webhook():
    """接收 GitLab Webhook 事件"""
    try:
        # 验证 Secret Token（如果配置了）
        config = load_env_config()
        expected_token = config.get('GITLAB_WEBHOOK_SECRET', '')
        
        if expected_token:
            received_token = request.headers.get('X-Gitlab-Token', '')
            if received_token != expected_token:
                print(f"Webhook 验证失败: Token 不匹配")
                return jsonify({'error': 'Unauthorized'}), 403
        
        # 获取事件类型和数据
        event_type = request.headers.get('X-Gitlab-Event')
        data = request.json
        
        print(f"收到 Webhook: {event_type}")
        
        # 处理 Merge Request 事件
        if event_type == 'Merge Request Hook':
            threading.Thread(target=handle_mr_webhook, args=(data,)).start()
        
        # 处理 Push 事件
        elif event_type == 'Push Hook':
            threading.Thread(target=handle_push_webhook, args=(data,)).start()
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        print(f"处理 Webhook 失败: {e}")
        return jsonify({'error': str(e)}), 500

def handle_mr_webhook(data):
    """处理 MR Webhook 事件"""
    try:
        mr = data['object_attributes']
        action = mr['action']
        
        print(f"MR 事件: {action}, MR !{mr['iid']}")
        
        # 只在创建和更新时触发
        if action not in ['open', 'update', 'reopen']:
            print(f"跳过 MR !{mr['iid']}: 动作 '{action}' 不需要审查")
            return
        
        # 判断是否需要自动审查
        if not should_auto_review_mr(data):
            return
        
        # 获取 MR 信息
        project = data['project']
        project_url = project['web_url']
        mr_iid = mr['iid']
        
        # 检查是否已经审查过
        already_reviewed = has_mr_been_reviewed(project, mr_iid)
        
        # 对于 'open' 和 'reopen'，如果已审查过则跳过
        if action in ['open', 'reopen'] and already_reviewed:
            print(f"⏭️  跳过已审查的 MR !{mr_iid}")
            return
        
        # 对于 'update'，检查是否有新的 commit
        should_record = True
        if action == 'update':
            # 检查 oldrev，如果存在说明有新 commit
            oldrev = mr.get('oldrev')
            if oldrev and oldrev != '0000000000000000000000000000000000000000':
                print(f"[Webhook] MR !{mr_iid} 有新 commit，触发审查")
                should_record = True
            else:
                print(f"⏭️  MR !{mr_iid} 更新但无新 commit，仅审查不记录")
                should_record = False
        
        print(f"[Webhook] 自动审查 MR !{mr_iid} - {project['path_with_namespace']}")
        
        # 只在有意义的情况下记录（创建、重新打开、或有新 commit 的更新）
        if should_record:
            record_review(
                review_type='mr',
                project_id=project['id'],
                project_name=project['path_with_namespace'],
                title=mr['title'],
                url=mr['url'],
                author=mr['author']['name'] if 'author' in mr and mr['author'] else 'Unknown',
                branch=mr.get('target_branch', ''),
                details=json.dumps({'action': action, 'iid': mr_iid, 'has_new_commits': action != 'update' or oldrev is not None})
            )
        
        # 调用审查函数
        review_mr_from_webhook(project_url, mr_iid)
        
    except Exception as e:
        print(f"处理 MR Webhook 失败: {e}")
        import traceback
        traceback.print_exc()

def handle_push_webhook(data):
    """处理 Push Webhook 事件"""
    try:
        # 获取 push 信息
        ref = data.get('ref', '')  # refs/heads/master
        branch = ref.replace('refs/heads/', '')
        commits = data.get('commits', [])
        project = data['project']
        before_sha = data.get('before', '0000000000000000000000000000000000000000')
        
        print(f"Push 事件: {project['path_with_namespace']} - {branch} ({len(commits)} commits)")
        
        # 判断是否需要审查
        if not should_auto_review_push(data, branch):
            return
        
        # 检查是否是新分支（before 为全 0 表示新分支）
        is_new_branch = before_sha == '0000000000000000000000000000000000000000'
        config = load_env_config()
        review_all_commits = config.get('AUTO_REVIEW_PUSH_NEW_BRANCH_ALL_COMMITS', 'false').lower() == 'true'
        
        if is_new_branch and not review_all_commits:
            print(f"🆕 检测到新分支 '{branch}'，配置为不审查历史 commits，跳过所有 commits")
            return
        
        if is_new_branch and review_all_commits:
            print(f"🆕 检测到新分支 '{branch}'，配置为审查所有历史 commits")
        
        # 审查每个 commit
        for commit in commits:
            commit_sha = commit['id']
            commit_message = commit['message']
            commit_url = commit.get('url', f"{project['web_url']}/commit/{commit_sha}")
            author_name = commit.get('author', {}).get('name', 'Unknown')
            
            # 跳过 Merge commit
            if commit_message.startswith('Merge branch') or commit_message.startswith('Merge pull request'):
                print(f"⏭️  跳过 Merge commit: {commit_sha[:8]} - {commit_message[:50]}")
                continue
            
            # 检查是否已经审查过
            if has_been_reviewed(project, commit_sha):
                print(f"⏭️  跳过已审查的 Commit: {commit_sha[:8]} - {commit_message[:50]}")
                continue
            
            print(f"[Webhook] 自动审查 Commit {commit_sha[:8]} - {commit_message[:50]}")
            
            # 记录审查
            record_review(
                review_type='commit',
                project_id=project['id'],
                project_name=project['path_with_namespace'],
                title=commit_message.split('\n')[0][:100],  # 第一行作为标题
                url=commit_url,
                author=author_name,
                branch=branch,
                details=json.dumps({'sha': commit_sha, 'full_message': commit_message})
            )
            
            # 调用 commit 审查函数
            review_commit_from_webhook(project, commit_sha)
        
    except Exception as e:
        print(f"处理 Push Webhook 失败: {e}")

def has_been_reviewed(project, commit_sha):
    """检查 commit 是否已经被审查过"""
    try:
        # 方法 1: 检查数据库中是否有记录
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM review_records WHERE project_id = ? AND details LIKE ?',
            (project['id'], f'%{commit_sha}%')
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            return True
        
        # 方法 2: 检查 GitLab 上是否已有 AI 评论
        config = load_env_config()
        gitlab_url = config.get('GITLAB__URL', 'https://gitlab.com')
        gitlab_token = config.get('GITLAB__PERSONAL_ACCESS_TOKEN', '')
        
        if not gitlab_token:
            return False
        
        project_path = project['path_with_namespace']
        headers = {'PRIVATE-TOKEN': gitlab_token}
        
        # 获取 commit 的评论
        comments_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/comments"
        response = requests.get(comments_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            comments = response.json()
            # 检查是否有 AI 评论
            for comment in comments:
                if '🤖 AI 代码审查' in comment.get('note', ''):
                    return True
        
        return False
        
    except Exception as e:
        print(f"检查 Commit 审查状态失败: {e}")
        return False

def has_mr_been_reviewed(project, mr_iid):
    """检查 MR 是否已经被审查过"""
    try:
        # 方法 1: 检查数据库中是否有记录
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM review_records WHERE project_id = ? AND type = ? AND details LIKE ?',
            (project['id'], 'mr', f'%"iid": {mr_iid}%')
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            return True
        
        # 方法 2: 检查 GitLab MR 上是否已有 AI 评论
        config = load_env_config()
        gitlab_url = config.get('GITLAB__URL', 'https://gitlab.com')
        gitlab_token = config.get('GITLAB__PERSONAL_ACCESS_TOKEN', '')
        
        if not gitlab_token:
            return False
        
        project_path = project['path_with_namespace']
        headers = {'PRIVATE-TOKEN': gitlab_token}
        
        # 获取 MR 的评论
        notes_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/merge_requests/{mr_iid}/notes"
        response = requests.get(notes_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            notes = response.json()
            # 检查是否有 AI 评论
            for note in notes:
                if '🤖 AI 代码审查' in note.get('body', '') or 'PR Reviewer Guide' in note.get('body', ''):
                    return True
        
        return False
        
    except Exception as e:
        print(f"检查 MR 审查状态失败: {e}")
        return False

def should_auto_review_mr(data):
    """判断 MR 是否需要自动审查"""
    config = load_env_config()
    
    # 检查是否启用自动审查
    if config.get('AUTO_REVIEW_ENABLED', 'false').lower() != 'true':
        print("自动审查未启用")
        return False
    
    mr = data['object_attributes']
    
    # 跳过 Draft MR
    if config.get('AUTO_REVIEW_SKIP_DRAFT', 'true').lower() == 'true':
        if mr.get('work_in_progress', False) or mr.get('draft', False):
            print(f"跳过 MR !{mr['iid']}: Draft MR")
            return False
    
    # 检查目标分支
    target_branches_config = config.get('AUTO_REVIEW_TARGET_BRANCHES', '*')
    
    # 如果配置为 * 则审查所有分支
    if target_branches_config.strip() != '*':
        target_branches = target_branches_config.split(',')
        target_branches = [b.strip() for b in target_branches if b.strip()]
        
        if target_branches and mr['target_branch'] not in target_branches:
            print(f"跳过 MR !{mr['iid']}: 目标分支 '{mr['target_branch']}' 不在配置中")
            return False
    
    # 检查代码变更量
    min_changes = int(config.get('AUTO_REVIEW_MIN_CHANGES', '0'))
    if min_changes > 0:
        changes = mr.get('changes_count', 0)
        if changes and changes < min_changes:
            print(f"跳过 MR !{mr['iid']}: 代码变更太少 ({changes} < {min_changes})")
            return False
    
    return True

def should_auto_review_push(data, branch):
    """判断 Push 是否需要自动审查"""
    config = load_env_config()
    
    # 检查是否启用 Push 自动审查
    if config.get('AUTO_REVIEW_PUSH_ENABLED', 'false').lower() != 'true':
        print("Push 自动审查未启用")
        return False
    
    # 检查分支
    push_branches_config = config.get('AUTO_REVIEW_PUSH_BRANCHES', '*')
    
    # 如果配置为 * 则审查所有分支
    if push_branches_config.strip() != '*':
        push_branches = push_branches_config.split(',')
        push_branches = [b.strip() for b in push_branches if b.strip()]
        
        if push_branches and branch not in push_branches:
            print(f"跳过 Push: 分支 '{branch}' 不在配置中")
            return False
    
    # 检查是否有 commits
    commits = data.get('commits', [])
    if not commits:
        print("跳过 Push: 没有 commits")
        return False
    
    return True

def review_mr_from_webhook(project_url, mr_iid):
    """从 Webhook 触发 MR 审查"""
    try:
        mr_url = f"{project_url}/merge_requests/{mr_iid}"
        print(f"🚀 开始审查 MR: {mr_url}")
        
        # 运行 Docker 命令调用 PR-Agent
        cmd = [
            'docker', 'run', '--rm',
            '--env-file', ENV_FILE,
            'codiumai/pr-agent:latest',
            '--pr_url', mr_url,
            'review'
        ]
        
        print(f"📝 执行命令: {' '.join(cmd)}")
        
        # 执行审查（设置超时10分钟）
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print(f"✅ MR 审查完成！")
            print(f"输出: {result.stdout[:500]}")  # 打印前500字符
        else:
            print(f"❌ MR 审查失败！")
            print(f"错误: {result.stderr[:500]}")
        
    except subprocess.TimeoutExpired:
        print(f"⏱️ MR 审查超时（10分钟）")
    except Exception as e:
        print(f"❌ 审查 MR 失败: {e}")
        import traceback
        traceback.print_exc()

def review_commit_from_webhook(project, commit_sha):
    """从 Webhook 触发 Commit 审查"""
    try:
        project_url = project['web_url']
        project_path = project['path_with_namespace']
        
        print(f"=" * 80)
        print(f"开始审查 Commit: {project_url}/-/commit/{commit_sha}")
        print(f"项目: {project_path}")
        print(f"=" * 80)
        
        # 获取配置
        config = load_env_config()
        gitlab_url = config.get('GITLAB__URL', 'https://gitlab.com')
        gitlab_token = config.get('GITLAB__PERSONAL_ACCESS_TOKEN', '')
        ai_api_key = config.get('OPENAI__KEY', '')
        ai_model = config.get('CONFIG__MODEL', 'qwen-plus')
        
        if not gitlab_token:
            print("❌ 错误: 未配置 GitLab Token")
            return
        
        if not ai_api_key:
            print("❌ 错误: 未配置 AI API Key")
            return
        
        # 去掉 model 的 openai/ 前缀
        if ai_model.startswith('openai/'):
            ai_model = ai_model.replace('openai/', '')
        
        print(f"📡 获取 Commit 变更...")
        
        # 获取 Commit 的 diff
        headers = {'PRIVATE-TOKEN': gitlab_token}
        api_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/diff"
        
        diff_response = requests.get(api_url, headers=headers, timeout=30)
        
        if diff_response.status_code != 200:
            print(f"❌ 获取 Commit diff 失败: {diff_response.status_code} - {diff_response.text}")
            return
        
        diffs = diff_response.json()
        print(f"✅ 获取到 {len(diffs)} 个文件的变更")
        
        # 检查是否启用文件级审核
        file_level_enabled = config.get('AUTO_REVIEW_FILE_LEVEL_ENABLED', 'false') == 'true'
        review_mode = '文件级审核（行内评论）' if file_level_enabled else '总体审核'
        print(f"📂 审查模式: {review_mode}")
        
        if file_level_enabled:
            # 文件级审核 - 创建行内评论
            print(f"🔍 开始文件级审核...")
            comments_created = 0
            total_files = min(len(diffs), 10)
            
            for idx, diff in enumerate(diffs[:10]):
                file_path = diff['new_path']
                diff_content = diff.get('diff', '')
                
                if not diff_content:
                    continue
                
                print(f"📄 审查文件 {idx+1}/{total_files}: {file_path}")
                
                # 解析 diff 获取变更的行号
                import re
                hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@([^@]*)', diff_content)
                
                for hunk in hunks:
                    old_start, new_start, hunk_content = hunk
                    new_line = int(new_start)
                    
                    # 只分析新增或修改的行
                    added_lines = []
                    current_line = new_line
                    for line in hunk_content.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            added_lines.append((current_line, line[1:]))
                            current_line += 1
                        elif not line.startswith('-'):
                            current_line += 1
                    
                    # 如果有新增的行，对这个代码块进行审查
                    if added_lines and len(added_lines) <= 20:
                        code_block = '\n'.join([line[1] for line in added_lines])
                        start_line = added_lines[0][0]
                        
                        # 构建针对这个代码块的审查 prompt
                        block_prompt = f"""请审查以下代码片段（文件: {file_path}, 行 {start_line}）：

```
{code_block}
```

请简洁地指出：
1. ❌ 严重问题（如果有）
2. ⚠️ 潜在问题或改进建议（如果有）
3. ✅ 好的做法（如果有）

如果代码没有问题，请回复"✅ 代码正常"。
请使用中文，简洁明了，不超过200字。"""
                        
                        # 调用 AI 审查这个代码块
                        try:
                            ai_response = requests.post(
                                'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                                headers={
                                    'Authorization': f'Bearer {ai_api_key}',
                                    'Content-Type': 'application/json'
                                },
                                json={
                                    'model': ai_model,
                                    'input': {'messages': [{'role': 'user', 'content': block_prompt}]},
                                    'parameters': {'result_format': 'message'}
                                },
                                proxies={'http': None, 'https': None},
                                timeout=60
                            )
                            
                            if ai_response.status_code == 200:
                                ai_result = ai_response.json()
                                review_comment = ai_result['output']['choices'][0]['message']['content']
                                
                                # 只有在发现问题或有建议时才创建评论
                                if '✅ 代码正常' not in review_comment and review_comment.strip():
                                    # 在 GitLab 上创建行内评论
                                    discussion_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/discussions"
                                    discussion_data = {
                                        'body': f"🤖 **AI 代码审查（自动触发）**\n\n{review_comment}",
                                        'position': {
                                            'base_sha': commit_sha,
                                            'start_sha': commit_sha,
                                            'head_sha': commit_sha,
                                            'position_type': 'text',
                                            'new_path': file_path,
                                            'new_line': start_line,
                                            'old_path': diff.get('old_path', file_path),
                                        }
                                    }
                                    
                                    discussion_response = requests.post(
                                        discussion_url,
                                        headers=headers,
                                        json=discussion_data,
                                        timeout=30
                                    )
                                    
                                    if discussion_response.status_code in [200, 201]:
                                        comments_created += 1
                                        print(f"  ✅ 创建行内评论: {file_path}:{start_line}")
                                    else:
                                        print(f"  ⚠️ 创建评论失败: {discussion_response.status_code}")
                        
                        except Exception as e:
                            print(f"  ⚠️ 审查代码块失败: {e}")
                            continue
            
            print(f"✅ 文件级审核完成！创建了 {comments_created} 条行内评论")
            return
        
        # 总体审核 - 创建总评论
        # 构建 diff 文本
        diff_text = ""
        for diff in diffs[:10]:  # 限制最多10个文件
            diff_text += f"\n\n文件: {diff['new_path']}\n"
            diff_text += f"变更: +{diff.get('added_lines', 0)} -{diff.get('removed_lines', 0)}\n"
            diff_text += diff.get('diff', '')[:2000]  # 每个文件最多2000字符
        
        print(f"🤖 调用 AI 进行代码审查...")
        
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

        # 禁用代理
        proxies = {'http': None, 'https': None}
        
        # 调用 AI API
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
        
        if ai_response.status_code != 200:
            print(f"❌ AI 审查失败: {ai_response.status_code} - {ai_response.text}")
            return
        
        ai_result = ai_response.json()
        review_content = ai_result['output']['choices'][0]['message']['content']
        
        print(f"✅ AI 审查完成")
        print(f"📝 发布评论到 GitLab...")
        
        # 发布评论到 GitLab Commit
        comment_url = f"{gitlab_url}/api/v4/projects/{project_path.replace('/', '%2F')}/repository/commits/{commit_sha}/comments"
        comment_data = {'note': f"🤖 AI 代码审查\n\n{review_content}"}
        
        comment_response = requests.post(
            comment_url,
            headers=headers,
            json=comment_data,
            timeout=30
        )
        
        if comment_response.status_code in [200, 201]:
            print(f"✅ 评论发布成功！")
            print(f"🔗 查看: {project_url}/-/commit/{commit_sha}")
        else:
            print(f"❌ 发布评论失败: {comment_response.status_code} - {comment_response.text}")
        
        print(f"=" * 80)
        
    except Exception as e:
        print(f"❌ 审查 Commit 失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 PR-Agent 可视化管理平台")
    print("=" * 60)
    print(f"📂 配置文件: {ENV_FILE}")
    print(f"📊 历史记录: {HISTORY_FILE}")
    print(f"💾 审查数据库: {DB_FILE}")
    print(f"🌐 访问地址: http://localhost:8080")
    print("=" * 60)
    
    # 初始化数据库
    init_database()
    
    print("按 Ctrl+C 停止服务")
    print()
    
    app.run(debug=True, host='0.0.0.0', port=8080)
