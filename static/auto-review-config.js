/**
 * 自动审查配置功能
 * 用于配置 MR 和 Push 事件的自动审查规则
 */

// 重置自动审查配置为默认值
window.resetAutoReviewConfig = function() {
    // MR 配置 - 默认关闭
    document.getElementById('autoReviewMrEnabled').checked = false;
    document.getElementById('autoReviewSkipDraft').checked = true;
    document.getElementById('autoReviewMinChanges').value = '0';
    
    // Push 配置 - 默认关闭
    document.getElementById('autoReviewPushEnabled').checked = false;
    
    // 隐藏选项
    document.getElementById('mrReviewOptions').classList.add('hidden');
    document.getElementById('pushReviewOptions').classList.add('hidden');
    
    console.log('自动审查配置已重置为默认值');
}

// 加载自动审查配置（从服务器）
window.loadAutoReviewConfig = async function() {
    try {
        const response = await fetch('/api/auto-review/config');
        const data = await response.json();
        
        if (data.error) {
            console.error('加载配置失败:', data.error);
            return;
        }
        
        // MR 配置
        const mrEnabled = data.auto_review_enabled === 'true';
        document.getElementById('autoReviewMrEnabled').checked = mrEnabled;
        document.getElementById('autoReviewSkipDraft').checked = data.auto_review_skip_draft !== 'false';
        document.getElementById('autoReviewMinChanges').value = data.auto_review_min_changes || '0';
        
        // Push 配置
        const pushEnabled = data.auto_review_push_enabled === 'true';
        document.getElementById('autoReviewPushEnabled').checked = pushEnabled;
        document.getElementById('autoReviewPushNewBranchAllCommits').checked = data.auto_review_push_new_branch_all_commits === 'true';
        
        // 显示/隐藏选项
        document.getElementById('mrReviewOptions').classList.toggle('hidden', !mrEnabled);
        document.getElementById('pushReviewOptions').classList.toggle('hidden', !pushEnabled);
        
        console.log('自动审查配置已加载', { mrEnabled, pushEnabled });
        
        // 显示加载成功提示
        const messageDiv = document.getElementById('autoReviewConfigMessage');
        if (messageDiv) {
            messageDiv.classList.remove('hidden', 'bg-red-100', 'text-red-700');
            messageDiv.classList.add('bg-green-100', 'text-green-700');
            messageDiv.textContent = '✅ 已加载上次保存的配置';
            setTimeout(() => {
                messageDiv.classList.add('hidden');
            }, 2000);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 更新配置（切换开关时）
window.updateAutoReviewConfig = function() {
    const mrEnabled = document.getElementById('autoReviewMrEnabled').checked;
    const pushEnabled = document.getElementById('autoReviewPushEnabled').checked;
    
    // 显示/隐藏选项
    document.getElementById('mrReviewOptions').classList.toggle('hidden', !mrEnabled);
    document.getElementById('pushReviewOptions').classList.toggle('hidden', !pushEnabled);
}

// 保存自动审查配置
window.saveAutoReviewConfig = async function() {
    const config = {
        auto_review_enabled: document.getElementById('autoReviewMrEnabled').checked ? 'true' : 'false',
        auto_review_target_branches: '*',  // 所有分支
        auto_review_skip_draft: document.getElementById('autoReviewSkipDraft').checked ? 'true' : 'false',
        auto_review_min_changes: document.getElementById('autoReviewMinChanges').value.trim() || '0',
        auto_review_push_enabled: document.getElementById('autoReviewPushEnabled').checked ? 'true' : 'false',
        auto_review_push_branches: '*',  // 所有分支
        auto_review_push_new_branch_all_commits: document.getElementById('autoReviewPushNewBranchAllCommits').checked ? 'true' : 'false'
    };
    
    const messageDiv = document.getElementById('autoReviewConfigMessage');
    messageDiv.classList.remove('hidden', 'bg-green-100', 'bg-red-100', 'text-green-700', 'text-red-700');
    messageDiv.textContent = '保存中...';
    messageDiv.classList.add('bg-blue-100', 'text-blue-700');
    
    try {
        const response = await fetch('/api/auto-review/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        if (data.success) {
            messageDiv.classList.add('bg-green-100', 'text-green-700');
            messageDiv.textContent = '✅ ' + data.message;
            
            // 3秒后隐藏消息
            setTimeout(() => {
                messageDiv.classList.add('hidden');
            }, 3000);
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

// 显示自动审查配置对话框（打开 Webhook 对话框并跳到步骤 4）
window.showAutoReviewConfigDialog = function() {
    // 打开 Webhook 对话框
    document.getElementById('webhookDialog').classList.remove('hidden');
    
    // 隐藏步骤 1-3
    document.getElementById('step1')?.classList.add('hidden');
    document.getElementById('step2')?.classList.add('hidden');
    document.getElementById('step3')?.classList.add('hidden');
    
    // 显示步骤 4（自动审查配置）
    const step4 = document.getElementById('step4');
    if (step4) {
        step4.classList.remove('hidden');
        // 加载配置
        window.loadAutoReviewConfig();
    }
}

// 关闭自动审查配置对话框
window.closeAutoReviewConfigDialog = function() {
    document.getElementById('webhookDialog').classList.add('hidden');
    // 重置步骤显示
    document.getElementById('step1')?.classList.remove('hidden');
    document.getElementById('step4')?.classList.add('hidden');
}

console.log('✅ auto-review-config.js 已加载');
