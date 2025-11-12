/**
 * Token 管理模块
 * 负责 Token 的存储、验证和用户信息显示
 */

// ========== Token 存储 ==========
function getStoredToken() {
    return localStorage.getItem('gitlab_token') || '';
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
    alert('Token 已保存');
}

// ========== 对话框管理 ==========
function showTokenDialog() {
    document.getElementById('tokenDialog').classList.remove('hidden');
    document.getElementById('gitlabToken').value = getStoredToken();
}

function closeTokenDialog() {
    document.getElementById('tokenDialog').classList.add('hidden');
}

// ========== Token 状态更新 ==========
async function updateTokenStatus() {
    const token = getStoredToken();
    const userInfoEl = document.getElementById('userInfo');
    
    if (!token) {
        userInfoEl.innerHTML = '<p class="text-sm text-gray-500">未设置 Token</p>';
        // 自动弹出设置对话框
        setTimeout(() => showTokenDialog(), 500);
        return;
    }
    
    // 显示加载状态
    userInfoEl.innerHTML = '<p class="text-sm text-gray-400">加载中...</p>';
    
    try {
        const response = await fetch('/api/user/info');
        const data = await response.json();
        
        console.log('用户信息响应:', data); // 调试日志
        
        // 修复：正确访问 data.user.username
        if (data.success && data.user && data.user.username) {
            userInfoEl.innerHTML = `
                <div class="text-sm">
                    <p class="text-gray-600">当前用户</p>
                    <p class="font-medium text-gray-900">${data.user.name || data.user.username}</p>
                    ${data.user.email ? `<p class="text-xs text-gray-500">${data.user.email}</p>` : ''}
                </div>
            `;
        } else {
            // Token 无效或返回数据不正确
            userInfoEl.innerHTML = '<p class="text-sm text-red-500">Token 无效</p>';
            console.error('用户信息格式错误:', data);
        }
    } catch (error) {
        console.error('获取用户信息失败:', error);
        userInfoEl.innerHTML = '<p class="text-sm text-red-500">获取失败</p>';
    }
}

// ========== fetch 拦截器 ==========
function setupFetchInterceptor() {
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
}

// ========== 初始化 ==========
function initTokenManager() {
    // 设置 fetch 拦截器
    setupFetchInterceptor();
    
    // 更新 Token 状态
    updateTokenStatus();
}

// 页面加载时初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTokenManager);
} else {
    initTokenManager();
}

console.log('✅ token-manager.js 已加载');
