// ============================================================
// PR-Agent Dashboard - 主应用 JS
// ============================================================

// ============================================================
// 全局变量
// ============================================================
let currentPage = 'dashboard';
let reviewStatus = {};

// ============================================================
// Token 管理
// ============================================================

function getStoredToken() {
    return localStorage.getItem('gitlab_token');
}

function saveToken() {
    const token = document.getElementById('gitlabToken').value.trim();
    if (!token) {
        alert('请输入 Token');
        return;
    }
    localStorage.setItem('gitlab_token', token);
    closeTokenDialog();
    updateTokenStatus();
    alert('Token 已保存！');
}

function showTokenDialog() {
    document.getElementById('tokenDialog').classList.remove('hidden');
}

function closeTokenDialog() {
    document.getElementById('tokenDialog').classList.add('hidden');
}

// 更新 Token 状态显示
async function updateTokenStatus() {
    const token = getStoredToken();
    const statusEl = document.getElementById('userInfo');
    
    if (token) {
        try {
            const response = await fetch('/api/user/info', {
                headers: { 'X-GitLab-Token': token }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.user) {
                    statusEl.innerHTML = `
                        <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                            ${data.user.avatar_url ? 
                                `<img src="${data.user.avatar_url}" class="w-10 h-10 rounded-full" alt="avatar">` : 
                                '<div class="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-semibold">👤</div>'
                            }
                            <div class="flex-1 min-w-0">
                                <p class="text-sm font-medium text-gray-900 truncate">${data.user.name || data.user.username}</p>
                                <p class="text-xs text-gray-500 truncate">${data.user.email || ''}</p>
                            </div>
                        </div>
                    `;
                    return;
                }
            }
            
            statusEl.innerHTML = `
                <div class="p-3 bg-yellow-50 rounded-lg">
                    <p class="text-sm text-yellow-800">⚠️ Token 可能无效</p>
                    <button onclick="showTokenDialog()" class="text-xs text-yellow-600 hover:text-yellow-800 mt-1">重新设置</button>
                </div>
            `;
        } catch (error) {
            console.error('获取用户信息失败:', error);
            statusEl.innerHTML = `
                <div class="p-3 bg-green-50 rounded-lg">
                    <p class="text-sm text-green-800">🔑 Token 已设置</p>
                </div>
            `;
        }
    } else {
        statusEl.innerHTML = `
            <div class="p-3 bg-red-50 rounded-lg">
                <p class="text-sm text-red-800">未设置 Token</p>
                <button onclick="showTokenDialog()" class="text-xs text-red-600 hover:text-red-800 mt-1">立即设置</button>
            </div>
        `;
    }
}

// ============================================================
// 页面导航
// ============================================================

function showPage(pageId) {
    currentPage = pageId;
    
    // 隐藏所有页面
    document.querySelectorAll('.page-content').forEach(page => {
        page.classList.add('hidden');
    });
    
    // 显示目标页面
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.classList.remove('hidden');
    }
    
    // 更新菜单高亮
    document.querySelectorAll('.menu-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeMenuItem = document.querySelector(`[href="#${pageId}"]`);
    if (activeMenuItem) {
        activeMenuItem.classList.add('active');
    }
    
    // 更新 URL
    window.location.hash = pageId;
    
    // 页面切换后的回调
    onPageChanged(pageId);
}

function onPageChanged(pageId) {
    // 根据不同页面执行不同的初始化
    switch(pageId) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'review-report':
            // 审查报表页面已经有自己的初始化逻辑
            break;
        case 'configured-projects':
            // 已配置项目页面已经有自己的初始化逻辑
            break;
    }
}

// ============================================================
// 数据概览（Dashboard）
// ============================================================

async function loadDashboardData() {
    try {
        // 加载统计数据
        await loadDashboardStats();
        // 加载最近审查
        await loadRecentReviews();
        // 加载项目排行
        await loadProjectRanking();
    } catch (error) {
        console.error('加载数据概览失败:', error);
    }
}

async function loadDashboardStats() {
    try {
        const response = await fetch('/api/review/report?type=all');
        const data = await response.json();
        
        if (data.records) {
            const records = data.records;
            const today = new Date().toISOString().split('T')[0];
            const thisWeek = getThisWeekStart();
            
            // 今日审查
            const todayCount = records.filter(r => r.timestamp.startsWith(today)).length;
            document.getElementById('todayCount').textContent = todayCount;
            
            // 本周审查
            const weekCount = records.filter(r => r.timestamp >= thisWeek).length;
            document.getElementById('weekCount').textContent = weekCount;
            
            // 成功率（假设所有记录都是成功的，实际应该根据状态判断）
            const successRate = records.length > 0 ? 100 : 0;
            document.getElementById('successRate').textContent = successRate.toFixed(1) + '%';
            
            // 失败数（这里暂时显示 0，需要后端支持状态字段）
            document.getElementById('failedCount').textContent = '0';
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
    }
}

async function loadRecentReviews() {
    try {
        const response = await fetch('/api/review/report?type=all');
        const data = await response.json();
        
        if (data.records) {
            const recentReviews = data.records.slice(0, 10);
            const container = document.getElementById('recentReviews');
            
            if (recentReviews.length === 0) {
                container.innerHTML = '<p class="text-gray-500 text-sm">暂无审查记录</p>';
                return;
            }
            
            container.innerHTML = recentReviews.map(record => `
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-gray-900 truncate">${record.title}</p>
                        <p class="text-xs text-gray-500">${record.project} • ${record.timestamp}</p>
                    </div>
                    <span class="ml-2 px-2 py-1 text-xs rounded ${record.type === 'mr' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}">
                        ${record.type === 'mr' ? 'MR' : 'Commit'}
                    </span>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('加载最近审查失败:', error);
    }
}

async function loadProjectRanking() {
    try {
        const response = await fetch('/api/review/report?type=all');
        const data = await response.json();
        
        if (data.records) {
            // 统计每个项目的审查次数
            const projectStats = {};
            data.records.forEach(record => {
                projectStats[record.project] = (projectStats[record.project] || 0) + 1;
            });
            
            // 排序并取前 10
            const ranking = Object.entries(projectStats)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);
            
            const tbody = document.getElementById('projectRanking');
            
            if (ranking.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-gray-500 py-4">暂无数据</td></tr>';
                return;
            }
            
            tbody.innerHTML = ranking.map((item, index) => `
                <tr class="border-t border-gray-100">
                    <td class="py-3">
                        <span class="inline-flex items-center justify-center w-6 h-6 rounded-full ${
                            index === 0 ? 'bg-yellow-100 text-yellow-800' :
                            index === 1 ? 'bg-gray-100 text-gray-800' :
                            index === 2 ? 'bg-orange-100 text-orange-800' :
                            'bg-gray-50 text-gray-600'
                        } text-xs font-semibold">
                            ${index + 1}
                        </span>
                    </td>
                    <td class="py-3 text-sm text-gray-900">${item[0]}</td>
                    <td class="py-3 text-sm font-semibold text-gray-900">${item[1]}</td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('加载项目排行失败:', error);
    }
}

function getThisWeekStart() {
    const now = new Date();
    const dayOfWeek = now.getDay();
    const diff = now.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    return monday.toISOString().split('T')[0];
}

// ============================================================
// 页面初始化
// ============================================================

window.addEventListener('DOMContentLoaded', () => {
    // 更新用户信息
    updateTokenStatus();
    
    // 检查 Token
    const token = getStoredToken();
    if (!token) {
        setTimeout(() => showTokenDialog(), 500);
    }
    
    // 根据 URL hash 显示对应页面
    const hash = window.location.hash.slice(1) || 'dashboard';
    showPage(hash);
});

// 监听 hash 变化
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.slice(1);
    if (hash) {
        showPage(hash);
    }
});

// 修改所有 API 请求，添加 Token 到请求头
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const token = getStoredToken();
    if (token) {
        if (!args[1]) {
            args[1] = {};
        }
        args[1].headers = args[1].headers || {};
        args[1].headers['X-GitLab-Token'] = token;
    }
    return originalFetch.apply(this, args);
};
