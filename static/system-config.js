/**
 * 系统配置功能
 * 用于管理 GitLab 和 AI 配置
 */

// 全局变量
window.currentConfig = window.currentConfig || {};
window.currentPrompts = window.currentPrompts || {};

// 加载配置信息
window.loadConfig = async function() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        window.currentConfig = data.full;
        
        document.getElementById('configDisplay').innerHTML = `
            <p><strong>GitLab URL:</strong> ${data.safe.gitlab_url}</p>
            <p><strong>GitLab Token:</strong> ${data.safe.gitlab_token_masked}</p>
            <p><strong>AI API Key:</strong> ${data.safe.openai_key_masked}</p>
            <p><strong>AI API Base:</strong> ${data.safe.openai_api_base}</p>
            <p><strong>AI Model:</strong> ${data.safe.model}</p>
            <p><strong>响应语言:</strong> ${data.safe.language}</p>
        `;
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 切换配置编辑模式
window.toggleConfigEdit = function() {
    const display = document.getElementById('configDisplay');
    const edit = document.getElementById('configEdit');
    const btn = document.getElementById('editConfigBtn');
    
    if (edit.classList.contains('hidden')) {
        // 进入编辑模式
        display.classList.add('hidden');
        edit.classList.remove('hidden');
        btn.textContent = '取消编辑';
        
        // 填充当前配置
        document.getElementById('editGitlabUrl').value = window.currentConfig.gitlab_url || '';
        document.getElementById('editOpenaiKey').value = window.currentConfig.openai_key || '';
        document.getElementById('editOpenaiApiBase').value = window.currentConfig.openai_api_base || '';
        document.getElementById('editModel').value = window.currentConfig.model || '';
        document.getElementById('editLanguage').value = window.currentConfig.language || '';
    } else {
        // 退出编辑模式
        display.classList.remove('hidden');
        edit.classList.add('hidden');
        btn.textContent = '编辑配置';
        document.getElementById('configMessage').classList.add('hidden');
    }
}

// 测试连接
window.testConnection = async function() {
    const gitlab_url = document.getElementById('editGitlabUrl').value;
    const gitlab_token = getStoredToken(); // 使用个人 Token
    const messageDiv = document.getElementById('configMessage');
    
    messageDiv.classList.remove('hidden', 'bg-green-100', 'bg-red-100', 'text-green-700', 'text-red-700');
    messageDiv.textContent = '测试中...';
    messageDiv.classList.add('bg-blue-100', 'text-blue-700');
    
    try {
        const response = await fetch('/api/config/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({gitlab_url, gitlab_token})
        });
        
        const data = await response.json();
        
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        if (data.success) {
            messageDiv.classList.add('bg-green-100', 'text-green-700');
            messageDiv.textContent = '✅ ' + data.message;
        } else {
            messageDiv.classList.add('bg-red-100', 'text-red-700');
            messageDiv.textContent = '❌ ' + data.message;
        }
    } catch (error) {
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        messageDiv.classList.add('bg-red-100', 'text-red-700');
        messageDiv.textContent = '❌ 测试失败: ' + error.message;
    }
}

// 保存配置
window.saveConfig = async function() {
    const config = {
        gitlab_url: document.getElementById('editGitlabUrl').value,
        openai_key: document.getElementById('editOpenaiKey').value,
        openai_api_base: document.getElementById('editOpenaiApiBase').value,
        model: document.getElementById('editModel').value,
        language: document.getElementById('editLanguage').value
    };
    
    const messageDiv = document.getElementById('configMessage');
    messageDiv.classList.remove('hidden', 'bg-green-100', 'bg-red-100', 'text-green-700', 'text-red-700');
    messageDiv.textContent = '保存中...';
    messageDiv.classList.add('bg-blue-100', 'text-blue-700');
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        if (data.success) {
            messageDiv.classList.add('bg-green-100', 'text-green-700');
            messageDiv.textContent = '✅ ' + data.message;
            
            // 重新加载配置
            setTimeout(() => {
                loadConfig();
                toggleConfigEdit();
            }, 1500);
        } else {
            messageDiv.classList.add('bg-red-100', 'text-red-700');
            messageDiv.textContent = '❌ ' + (data.error || '保存失败');
        }
    } catch (error) {
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        messageDiv.classList.add('bg-red-100', 'text-red-700');
        messageDiv.textContent = '❌ 保存失败: ' + error.message;
    }
}

console.log('✅ system-config.js 已加载');
