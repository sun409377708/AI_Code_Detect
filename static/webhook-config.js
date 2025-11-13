/**
 * Webhook 批量配置功能
 * 用于批量为 GitLab 项目配置 Webhook
 */

window.currentGroupProjects = [];

// 显示 Webhook 配置对话框
window.showWebhookDialog = function() {
    // 先重置对话框状态
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step4').classList.add('hidden');
    document.getElementById('setupProgress').classList.add('hidden');
    document.getElementById('setupResults').classList.add('hidden');
    window.currentGroupProjects = [];
    
    // 重置选择框
    const groupSelect = document.getElementById('webhookGroupSelect');
    if (groupSelect) {
        groupSelect.selectedIndex = 0;
    }
    
    // 清空项目列表
    const projectList = document.getElementById('projectList');
    if (projectList) {
        projectList.innerHTML = '';
    }
    
    // 显示对话框
    document.getElementById('webhookDialog').classList.remove('hidden');
    
    // 加载组列表和自动填充 URL
    window.loadWebhookGroups();
    window.autoFillWebhookUrl();
}

// 关闭 Webhook 配置对话框
window.closeWebhookDialog = function() {
    document.getElementById('webhookDialog').classList.add('hidden');
    // 重置状态
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step4').classList.add('hidden');
    document.getElementById('setupProgress').classList.add('hidden');
    document.getElementById('setupResults').classList.add('hidden');
    window.currentGroupProjects = [];
}

// 加载 GitLab 组列表（用于 Webhook 配置）
window.loadWebhookGroups = async function() {
    console.log('🔄 开始加载 Webhook 组列表...');
    try {
        const response = await fetch('/api/webhook/groups');
        const data = await response.json();
        
        if (data.error) {
            console.error('❌ 加载组列表失败:', data.error);
            alert('加载组列表失败: ' + data.error);
            return;
        }
        
        const groupSelect = document.getElementById('webhookGroupSelect');
        if (!groupSelect) {
            console.error('❌ 找不到 webhookGroupSelect 元素');
            return;
        }
        
        groupSelect.innerHTML = '<option value="">选择一个组...</option>';
        
        data.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = `${group.full_path} (${group.project_count || '?'} 个项目)`;
            option.dataset.fullPath = group.full_path;
            groupSelect.appendChild(option);
        });
        
        console.log(`✅ 已加载 ${data.groups.length} 个 Webhook 组`);
    } catch (error) {
        console.error('❌ 加载组列表失败:', error);
        alert('加载组列表失败: ' + error.message);
    }
}

// 加载组内项目
window.loadGroupProjects = async function() {
    const groupSelect = document.getElementById('webhookGroupSelect');
    const groupId = groupSelect.value;
    
    if (!groupId) {
        alert('请先选择一个组');
        return;
    }
    
    const groupName = groupSelect.options[groupSelect.selectedIndex].dataset.fullPath;
    const webhookUrl = document.getElementById('webhookUrl').value.trim();
    
    try {
        const url = `/api/webhook/group-projects/${groupId}${webhookUrl ? '?webhook_url=' + encodeURIComponent(webhookUrl) : ''}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.error) {
            alert('加载项目失败: ' + data.error);
            return;
        }
        
        currentGroupProjects = data.projects;
        
        // 显示步骤 2
        document.getElementById('step2').classList.remove('hidden');
        
        // 渲染项目列表
        const projectList = document.getElementById('projectList');
        projectList.innerHTML = '';
        
        if (currentGroupProjects.length === 0) {
            projectList.innerHTML = '<p class="text-gray-500 text-center py-4">该组没有项目</p>';
            return;
        }
        
        // 统计已配置数量
        let configuredCount = 0;
        
        currentGroupProjects.forEach(project => {
            const div = document.createElement('div');
            const isConfigured = project.has_webhook;
            
            if (isConfigured) {
                configuredCount++;
                div.className = 'flex items-center gap-2 p-2 bg-green-50 rounded border border-green-200';
            } else {
                div.className = 'flex items-center gap-2 p-2 hover:bg-gray-100 rounded';
            }
            
            div.innerHTML = `
                <input type="checkbox" 
                    id="project-${project.id}" 
                    value="${project.id}"
                    class="project-checkbox rounded border-gray-300"
                    ${isConfigured ? 'disabled' : ''}
                    onchange="updateSelectedCount()">
                <label for="project-${project.id}" class="flex-1 text-sm ${isConfigured ? 'text-gray-500' : 'cursor-pointer'}">
                    ${project.path_with_namespace}
                    ${isConfigured ? '<span class="ml-2 text-xs text-green-600">✓ 已配置</span>' : ''}
                </label>
            `;
            projectList.appendChild(div);
        });
        
        window.updateSelectedCount();
        
        // 显示信息
        const unconfiguredCount = currentGroupProjects.length - configuredCount;
        document.getElementById('groupInfo').innerHTML = `
            已加载 ${groupName} 的 ${currentGroupProjects.length} 个项目
            <span class="ml-2 text-green-600">(${configuredCount} 个已配置)</span>
            <span class="ml-2 text-gray-600">(${unconfiguredCount} 个未配置)</span>
        `;
        document.getElementById('groupInfo').classList.remove('hidden');
        
        // 显示步骤 4 并加载配置
        document.getElementById('step4').classList.remove('hidden');
        if (typeof loadAutoReviewConfig === 'function') {
            loadAutoReviewConfig();
        }
        
    } catch (error) {
        console.error('加载项目失败:', error);
        alert('加载项目失败: ' + error.message);
    }
}

// 全选项目（只选择未配置的）
window.selectAllProjects = function() {
    document.querySelectorAll('.project-checkbox:not(:disabled)').forEach(cb => {
        cb.checked = true;
    });
    updateSelectedCount();
}

// 取消全选
window.deselectAllProjects = function() {
    document.querySelectorAll('.project-checkbox:not(:disabled)').forEach(cb => {
        cb.checked = false;
    });
    updateSelectedCount();
}

// 更新已选择数量
window.updateSelectedCount = function() {
    const count = document.querySelectorAll('.project-checkbox:checked').length;
    document.getElementById('selectedCount').textContent = `已选择: ${count} 个项目`;
}

// 自动填充 Webhook URL
window.autoFillWebhookUrl = function() {
    const currentHost = window.location.hostname;
    const currentPort = window.location.port || '8080';
    const webhookUrl = `http://${currentHost}:${currentPort}/webhook/gitlab`;
    document.getElementById('webhookUrl').value = webhookUrl;
}

// 开始批量配置
window.startBatchSetup = async function() {
    const selectedCheckboxes = document.querySelectorAll('.project-checkbox:checked');
    const projectIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    if (projectIds.length === 0) {
        alert('请至少选择一个项目');
        return;
    }
    
    const webhookUrl = document.getElementById('webhookUrl').value.trim();
    const webhookSecret = document.getElementById('webhookSecret').value.trim();
    
    if (!webhookUrl) {
        alert('请输入 Webhook URL');
        return;
    }
    
    if (!confirm(`确定要为 ${projectIds.length} 个项目配置 Webhook 吗？`)) {
        return;
    }
    
    // 禁用按钮
    const setupBtn = document.querySelector('button[onclick="startBatchSetup()"]');
    const originalBtnText = setupBtn.innerHTML;
    setupBtn.disabled = true;
    setupBtn.innerHTML = '<span class="inline-block animate-spin mr-2">⏳</span> 配置中...';
    setupBtn.classList.add('opacity-50', 'cursor-not-allowed');
    
    // 显示进度
    document.getElementById('setupProgress').classList.remove('hidden');
    document.getElementById('setupResults').classList.add('hidden');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').textContent = '正在配置...';
    
    try {
        const response = await fetch('/api/webhook/batch-setup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                project_ids: projectIds,
                webhook_url: webhookUrl,
                webhook_secret: webhookSecret
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('配置失败: ' + data.error);
            return;
        }
        
        // 更新进度
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('progressText').textContent = '配置完成！';
        
        // 显示结果
        window.displayWebhookResults(data);
        
    } catch (error) {
        console.error('批量配置失败:', error);
        alert('批量配置失败: ' + error.message);
        document.getElementById('progressText').textContent = '配置失败';
    } finally {
        // 恢复按钮状态
        setupBtn.disabled = false;
        setupBtn.innerHTML = originalBtnText;
        setupBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// 显示配置结果
window.displayWebhookResults = function(data) {
    const summary = data.summary;
    const results = data.results;
    
    // 显示成功提示弹窗
    const successCount = (summary.success || 0) + (summary.updated || 0);
    let alertIcon = '🎉';
    let alertTitle = '配置完成！';
    let alertMessage = '';
    let alertClass = 'bg-green-50 border-green-500 text-green-900';
    
    if (successCount === summary.total) {
        if (summary.updated > 0) {
            alertMessage = `所有 ${summary.total} 个项目配置完成！（新增 ${summary.success || 0} 个，更新 ${summary.updated} 个）`;
        } else {
            alertMessage = `所有 ${summary.total} 个项目配置成功！`;
        }
    } else if (successCount > 0) {
        alertIcon = '⚠️';
        alertTitle = '部分配置成功';
        const parts = [];
        if (summary.success > 0) parts.push(`新增 ${summary.success} 个`);
        if (summary.updated > 0) parts.push(`更新 ${summary.updated} 个`);
        if (summary.skipped > 0) parts.push(`跳过 ${summary.skipped} 个`);
        if (summary.error > 0) parts.push(`失败 ${summary.error} 个`);
        alertMessage = parts.join('，');
        alertClass = 'bg-yellow-50 border-yellow-500 text-yellow-900';
    } else {
        alertIcon = '❌';
        alertTitle = '配置失败';
        alertMessage = `所有项目配置失败，请检查权限和网络`;
        alertClass = 'bg-red-50 border-red-500 text-red-900';
    }
    
    // 显示顶部提示
    const alertDiv = document.createElement('div');
    alertDiv.className = `fixed top-20 left-1/2 transform -translate-x-1/2 z-50 ${alertClass} border-l-4 p-4 rounded-lg shadow-lg max-w-md animate-bounce`;
    alertDiv.innerHTML = `
        <div class="flex items-center">
            <span class="text-3xl mr-3">${alertIcon}</span>
            <div>
                <p class="font-bold text-lg">${alertTitle}</p>
                <p class="text-sm">${alertMessage}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-2xl hover:opacity-70">×</button>
        </div>
    `;
    document.body.appendChild(alertDiv);
    
    // 3秒后自动移除提示
    setTimeout(() => {
        alertDiv.classList.remove('animate-bounce');
    }, 1000);
    
    setTimeout(() => {
        alertDiv.style.transition = 'opacity 0.5s';
        alertDiv.style.opacity = '0';
        setTimeout(() => alertDiv.remove(), 500);
    }, 5000);
    
    // 显示结果区域
    document.getElementById('setupResults').classList.remove('hidden');
    document.getElementById('setupResults').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    // 显示摘要
    const summaryDiv = document.getElementById('resultSummary');
    summaryDiv.innerHTML = `
        <div class="grid grid-cols-5 gap-4 text-center">
            <div>
                <div class="text-2xl font-bold text-gray-700">${summary.total}</div>
                <div class="text-sm text-gray-500">总计</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-green-600">${summary.success || 0}</div>
                <div class="text-sm text-gray-500">新增</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-blue-600">${summary.updated || 0}</div>
                <div class="text-sm text-gray-500">更新</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-yellow-600">${summary.skipped || 0}</div>
                <div class="text-sm text-gray-500">跳过</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-red-600">${summary.error || 0}</div>
                <div class="text-sm text-gray-500">失败</div>
            </div>
        </div>
    `;
    
    // 显示详细结果
    const detailsDiv = document.getElementById('resultDetails');
    detailsDiv.innerHTML = '';
    
    results.forEach(result => {
        const div = document.createElement('div');
        div.className = 'p-3 rounded border';
        
        let statusIcon = '';
        let statusClass = '';
        
        if (result.status === 'success') {
            statusIcon = '✅';
            statusClass = 'bg-green-50 border-green-200';
        } else if (result.status === 'updated') {
            statusIcon = '🔄';
            statusClass = 'bg-blue-50 border-blue-200';
        } else if (result.status === 'skipped') {
            statusIcon = '⏭️';
            statusClass = 'bg-yellow-50 border-yellow-200';
        } else {
            statusIcon = '❌';
            statusClass = 'bg-red-50 border-red-200';
        }
        
        div.className += ' ' + statusClass;
        div.innerHTML = `
            <div class="flex items-start gap-2">
                <span class="text-lg">${statusIcon}</span>
                <div class="flex-1">
                    <div class="font-medium text-sm">${result.project_name}</div>
                    <div class="text-xs text-gray-600 mt-1">${result.message}</div>
                </div>
            </div>
        `;
        
        detailsDiv.appendChild(div);
    });
}

console.log('✅ webhook-config.js 已加载');
