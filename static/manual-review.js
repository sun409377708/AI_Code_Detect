/**
 * 手动审查功能
 * 用于加载项目、MR列表和执行审查
 */

// 全局变量
window.currentMRs = window.currentMRs || [];
window.currentGroups = window.currentGroups || [];

// 加载 GitLab 组列表
window.loadGroups = async function() {
    console.log('🔄 开始加载 GitLab 组...');
    try {
        const response = await fetch('/api/user/groups');
        console.log('📡 API 响应状态:', response.status);
        
        const data = await response.json();
        console.log('📦 API 返回数据:', data);
        
        if (data.error) {
            console.error('❌ 加载组失败:', data.error);
            alert('加载组失败: ' + data.error);
            return;
        }
        
        const groups = data.groups || [];
        window.currentGroups = groups;
        const groupSelect = document.getElementById('groupSelect');
        
        if (!groupSelect) {
            console.error('❌ 找不到 groupSelect 元素');
            return;
        }
        
        // 清空并重新填充
        groupSelect.innerHTML = '<option value="">1️⃣ 选择 GitLab 组...</option>';
        
        groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = `${group.full_path} (${group.name})`;
            if (group.description) {
                option.title = group.description;
            }
            groupSelect.appendChild(option);
        });
        
        console.log(`✅ 已加载 ${groups.length} 个组`);
    } catch (error) {
        console.error('❌ 加载组失败:', error);
        alert('加载组失败: ' + error.message);
    }
};

// 选择组后加载该组下的项目
window.selectGroup = async function() {
    const groupSelect = document.getElementById('groupSelect');
    const projectSelect = document.getElementById('projectSelect');
    const groupId = groupSelect.value;
    
    if (!groupId) {
        // 清空项目列表
        projectSelect.innerHTML = '<option value="">2️⃣ 先选择组，再选择项目...</option>';
        projectSelect.disabled = true;
        return;
    }
    
    console.log('🔄 加载组下的项目，组 ID:', groupId);
    
    try {
        const response = await fetch(`/api/group/${groupId}/projects`);
        const data = await response.json();
        
        if (data.error) {
            console.error('❌ 加载项目失败:', data.error);
            alert('加载项目失败: ' + data.error);
            return;
        }
        
        const projects = data.projects || [];
        
        // 清空并重新填充
        projectSelect.innerHTML = '<option value="">2️⃣ 选择项目...</option>';
        projectSelect.disabled = false;
        
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.web_url;
            option.textContent = `${project.name}`;
            if (project.description) {
                option.title = project.description;
            }
            projectSelect.appendChild(option);
        });
        
        console.log(`✅ 已加载 ${projects.length} 个项目`);
    } catch (error) {
        console.error('❌ 加载项目失败:', error);
        alert('加载项目失败: ' + error.message);
    }
};

// 加载用户的活跃项目（保留原有功能）
window.loadUserProjects = async function() {
    console.log('🔄 开始加载用户项目...');
    try {
        const response = await fetch('/api/user/projects');
        console.log('📡 API 响应状态:', response.status);
        
        const data = await response.json();
        console.log('📦 API 返回数据:', data);
        
        if (data.error) {
            console.error('❌ 加载项目失败:', data.error);
            alert('加载项目失败: ' + data.error);
            return;
        }
        
        const projects = data.projects || [];
        const projectSelect = document.getElementById('projectSelect');
        
        if (!projectSelect) {
            console.error('❌ 找不到 projectSelect 元素');
            return;
        }
        
        // 清空并重新填充
        projectSelect.innerHTML = '<option value="">选择最近活跃的项目...</option>';
        
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.web_url;
            option.textContent = `${project.path_with_namespace}`;
            if (project.description) {
                option.title = project.description;
            }
            projectSelect.appendChild(option);
        });
        
        console.log(`✅ 已加载 ${projects.length} 个项目`);
    } catch (error) {
        console.error('❌ 加载项目失败:', error);
        alert('加载项目失败: ' + error.message);
    }
}

// 选择项目
window.selectProject = async function() {
    const projectSelect = document.getElementById('projectSelect');
    const projectUrl = projectSelect.value;
    
    if (projectUrl) {
        document.getElementById('projectUrl').value = projectUrl;
        // 先加载分支列表，再加载 MR
        await window.loadBranches();
        window.loadMRs();
    }
}

// 加载分支列表
window.loadBranches = async function() {
    const projectUrl = document.getElementById('projectUrl').value.trim();
    
    if (!projectUrl) {
        alert('请先输入项目 URL');
        return;
    }
    
    try {
        const response = await fetch('/api/projects/branches', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({project_url: projectUrl})
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('加载分支失败: ' + data.error);
            return;
        }
        
        const branchSelect = document.getElementById('targetBranch');
        branchSelect.innerHTML = '<option value="">全部分支</option>';
        
        data.branches.forEach(branch => {
            const option = document.createElement('option');
            option.value = branch.name;
            option.textContent = branch.name;
            branchSelect.appendChild(option);
        });
        
        console.log(`已加载 ${data.branches.length} 个分支`);
    } catch (error) {
        console.error('加载分支失败:', error);
        alert('加载分支失败: ' + error.message);
    }
}

// 加载 MR 列表
window.loadMRs = async function() {
    console.log('🔄 开始加载 MR 列表...');
    const projectUrl = document.getElementById('projectUrl').value.trim();
    const state = document.getElementById('mrState').value;
    const targetBranch = document.getElementById('targetBranch').value;
    const includeCommits = document.getElementById('includeCommits').checked;
    
    console.log('📋 参数:', { projectUrl, state, targetBranch, includeCommits });
    
    if (!projectUrl) {
        alert('请输入项目 URL');
        return;
    }

    // 如果分支列表为空，先加载分支
    const branchSelect = document.getElementById('targetBranch');
    if (branchSelect.options.length === 1) {
        console.log('🌿 分支列表为空，先加载分支...');
        await window.loadBranches();
    }

    const mrList = document.getElementById('mrList');
    mrList.innerHTML = '<p class="text-gray-500 text-center py-8">加载中...</p>';

    try {
        const response = await fetch('/api/projects/mrs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                project_url: projectUrl, 
                state: state,
                target_branch: targetBranch,
                include_commits: includeCommits
            })
        });

        console.log('📡 MR API 响应状态:', response.status);
        const data = await response.json();
        console.log('📦 MR API 返回数据:', data);
        window.currentMRs = data.mrs || [];

        // 更新标题
        const stateNames = {
            'opened': 'Open',
            'merged': 'Merged',
            'closed': 'Closed',
            'all': 'All'
        };
        document.getElementById('mrTitle').textContent = `${stateNames[state]} Merge Requests`;

        if (window.currentMRs.length === 0) {
            mrList.innerHTML = `<p class="text-gray-500 text-center py-8">没有找到 ${stateNames[state]} 状态的 MR</p>`;
            return;
        }

        document.getElementById('mrCount').textContent = `(${window.currentMRs.length})`;
        
        // 只在 Open 状态下显示批量审查按钮
        const batchBtn = document.getElementById('batchReviewBtn');
        if (state === 'opened') {
            const unreviewed = window.currentMRs.filter(mr => !mr.reviewed);
            if (unreviewed.length > 0) {
                batchBtn.classList.remove('hidden');
            } else {
                batchBtn.classList.add('hidden');
            }
        } else {
            batchBtn.classList.add('hidden');
        }

        renderMRList();
    } catch (error) {
        console.error('加载 MR 失败:', error);
        mrList.innerHTML = '<p class="text-red-500 text-center py-8">加载失败，请检查项目 URL 和网络连接</p>';
    }
}

// 渲染 MR 列表
function renderMRList() {
    const mrList = document.getElementById('mrList');
    mrList.innerHTML = window.currentMRs.map(item => {
        // 判断是 MR 还是 Commit
        if (item.is_commit) {
            // 渲染 Commit
            return `
            <div class="border border-orange-200 rounded-lg p-4 hover:shadow-md transition bg-orange-50">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="px-2 py-1 text-xs font-medium text-orange-700 bg-orange-200 rounded">📝 Commit (未创建 MR)</span>
                            <span class="text-sm font-medium text-gray-500">${item.short_id}</span>
                            <h3 class="text-base font-medium text-gray-900">${item.title}</h3>
                        </div>
                        <p class="mt-1 text-sm text-gray-500">
                            作者: ${item.author_name} | 
                            提交时间: ${new Date(item.created_at).toLocaleString('zh-CN')}
                        </p>
                        <p class="mt-1 text-sm text-gray-600">
                            分支: ${item.branch}
                        </p>
                    </div>
                    <div class="flex gap-2 ml-4">
                        <button 
                            onclick="window.reviewCommit('${item.web_url}', '${item.id}', '${item.short_id}')"
                            class="bg-orange-600 hover:bg-orange-700 text-white px-4 py-2 rounded text-sm font-medium"
                            id="commitReviewBtn-${item.short_id}"
                        >
                            审查 Commit
                        </button>
                        <a 
                            href="${item.web_url}" 
                            target="_blank"
                            class="bg-gray-200 hover:bg-gray-300 text-gray-700 px-4 py-2 rounded text-sm font-medium"
                        >
                            查看 Commit
                        </a>
                    </div>
                </div>
                
                <!-- Commit 审查进度 -->
                <div id="commitProgress-${item.short_id}" class="mt-3 hidden">
                    <div class="w-full bg-gray-200 rounded-full h-1.5">
                        <div class="bg-orange-600 h-1.5 rounded-full" style="width: 0%" id="commitProgressBar-${item.short_id}"></div>
                    </div>
                    <p class="mt-1 text-xs text-gray-600" id="commitProgressText-${item.short_id}">准备中...</p>
                </div>
                
                <!-- Commit 审查结果 -->
                <div id="commitResult-${item.short_id}" class="mt-3 hidden">
                    <div class="border-t pt-2">
                        <div class="flex justify-between items-center mb-1">
                            <span class="text-xs font-medium text-gray-700">AI 审查结果</span>
                            <button 
                                onclick="window.toggleCommitResult('${item.short_id}')"
                                class="text-xs text-indigo-600 hover:text-indigo-800"
                                id="toggleCommitResultBtn-${item.short_id}"
                            >
                                收起
                            </button>
                        </div>
                        <div id="commitResultContent-${item.short_id}" class="bg-gray-50 rounded p-2 text-xs overflow-auto max-h-64">
                            <p class="text-gray-600">加载中...</p>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }
        
        // 渲染 MR
        const mr = item;
        let statusBadge = '';
        if (mr.state === 'merged') {
            statusBadge = '<span class="px-2 py-1 text-xs font-medium text-purple-700 bg-purple-100 rounded">已合并</span>';
        } else if (mr.state === 'closed') {
            statusBadge = '<span class="px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded">已关闭</span>';
        } else if (mr.state === 'opened') {
            statusBadge = '<span class="px-2 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded">Open</span>';
        }
        
        let reviewBadge = '';
        if (mr.state === 'opened') {
            reviewBadge = mr.reviewed ? 
                '<span class="px-2 py-1 text-xs font-medium text-green-700 bg-green-100 rounded">已审查</span>' :
                '<span class="px-2 py-1 text-xs font-medium text-yellow-700 bg-yellow-100 rounded">未审查</span>';
        }
        
        return `
        <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition">
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-sm font-medium text-gray-500">!${mr.iid}</span>
                        <h3 class="text-base font-medium text-gray-900">${mr.title}</h3>
                        ${statusBadge}
                        ${reviewBadge}
                    </div>
                    <p class="mt-1 text-sm text-gray-500">
                        作者: ${mr.author.name} | 
                        创建时间: ${new Date(mr.created_at).toLocaleString('zh-CN')}
                    </p>
                    <p class="mt-1 text-sm text-gray-600">
                        ${mr.source_branch} → ${mr.target_branch}
                    </p>
                </div>
                <div class="flex gap-2 ml-4">
                    ${mr.state === 'opened' ? `
                        <button 
                            onclick="reviewMR('${mr.web_url}', ${mr.iid})"
                            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium"
                            id="reviewBtn-${mr.iid}"
                        >
                            ${mr.reviewed ? '重新审查' : '立即审查'}
                        </button>
                    ` : ''}
                    ${mr.state === 'merged' || mr.state === 'closed' ? `
                        <button 
                            onclick="reviewMR('${mr.web_url}', ${mr.iid})"
                            class="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded text-sm font-medium"
                            id="reviewBtn-${mr.iid}"
                            title="对已${mr.state === 'merged' ? '合并' : '关闭'}的 MR 进行 AI 分析"
                        >
                            AI 分析
                        </button>
                    ` : ''}
                    <button 
                        onclick="toggleCommits(${mr.iid}, '${mr.web_url}')"
                        class="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded text-sm font-medium"
                        id="commitsBtn-${mr.iid}"
                    >
                        查看 Commits
                    </button>
                    <a 
                        href="${mr.web_url}" 
                        target="_blank"
                        class="bg-gray-200 hover:bg-gray-300 text-gray-700 px-4 py-2 rounded text-sm font-medium"
                    >
                        查看 MR
                    </a>
                </div>
            </div>
            <div id="progress-${mr.iid}" class="mt-4 hidden">
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="bg-blue-600 h-2 rounded-full progress-bar" style="width: 0%" id="progressBar-${mr.iid}"></div>
                </div>
                <p class="mt-2 text-sm text-gray-600" id="progressText-${mr.iid}">准备中...</p>
            </div>
            
            <!-- Commits 列表显示区域 -->
            <div id="commits-${mr.iid}" class="mt-4 hidden">
                <div class="border-t pt-4">
                    <div class="flex justify-between items-center mb-3">
                        <h4 class="font-medium text-gray-900">Commits 列表</h4>
                        <button 
                            onclick="toggleCommits(${mr.iid}, '${mr.web_url}')"
                            class="text-sm text-indigo-600 hover:text-indigo-800"
                        >
                            收起
                        </button>
                    </div>
                    <div id="commitsContent-${mr.iid}" class="space-y-2">
                        <p class="text-gray-600 text-sm">加载中...</p>
                    </div>
                </div>
            </div>
            
            <!-- 审查结果显示区域 -->
            <div id="result-${mr.iid}" class="mt-4 hidden">
                <div class="border-t pt-4">
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="font-medium text-gray-900">AI 审查结果</h4>
                        <button 
                            onclick="toggleResult(${mr.iid})"
                            class="text-sm text-indigo-600 hover:text-indigo-800"
                            id="toggleResultBtn-${mr.iid}"
                        >
                            收起
                        </button>
                    </div>
                    <div id="resultContent-${mr.iid}" class="bg-gray-50 rounded p-4 text-sm overflow-auto max-h-96">
                        <p class="text-gray-600">加载中...</p>
                    </div>
                </div>
            </div>
        </div>
        `;
    }).join('');
}

// 切换结果显示
window.toggleResult = function(mrId) {
    const content = document.getElementById('resultContent-' + mrId);
    const btn = document.getElementById('toggleResultBtn-' + mrId);
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        btn.textContent = '收起';
    } else {
        content.classList.add('hidden');
        btn.textContent = '展开';
    }
}

// 审查单个 MR 或 Commit
window.reviewItem = async function(mrUrl, mrId) {
    const btn = document.getElementById(`reviewBtn-${mrId}`);
    const progress = document.getElementById(`progress-${mrId}`);
    const progressBar = document.getElementById(`progressBar-${mrId}`);
    const progressText = document.getElementById(`progressText-${mrId}`);

    // 判断是审查还是分析
    const isAnalysis = btn.textContent.includes('AI 分析');
    const actionText = isAnalysis ? '分析' : '审查';

    btn.disabled = true;
    btn.textContent = `${actionText}中...`;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    progress.classList.remove('hidden');

    try {
        // 获取文件级审核选项
        const fileLevelEnabled = document.getElementById('manualReviewFileLevelEnabled')?.checked || false;
        
        // 启动审查
        const response = await fetch('/api/review', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                mr_url: mrUrl, 
                mr_id: mrId.toString(),
                file_level_review: fileLevelEnabled  // 添加文件级审核参数
            })
        });

        const data = await response.json();

        // 轮询状态
        const checkStatus = setInterval(async () => {
            const statusResponse = await fetch(`/api/review/status/${mrId}`);
            const status = await statusResponse.json();

            progressBar.style.width = `${status.progress || 0}%`;
            progressText.textContent = status.message || '处理中...';

            if (status.status === 'success') {
                clearInterval(checkStatus);
                btn.textContent = `${actionText}完成 ✓`;
                btn.classList.remove('bg-blue-600', 'hover:bg-blue-700', 'bg-purple-600', 'hover:bg-purple-700');
                btn.classList.add('bg-green-600');
                progressText.textContent = `✅ ${actionText}完成！结果已显示在下方`;
                progressText.classList.add('text-green-600', 'font-medium');
                
                // 显示结果（使用格式化）
                if (status.output) {
                    const resultDiv = document.getElementById('result-' + mrId);
                    const resultContent = document.getElementById('resultContent-' + mrId);
                    resultDiv.classList.remove('hidden');
                    resultContent.innerHTML = formatReviewResult(status.output);
                }
                
                // 3秒后刷新列表
                setTimeout(() => loadMRs(), 3000);
            } else if (status.status === 'failed') {
                clearInterval(checkStatus);
                btn.textContent = `${actionText}失败`;
                btn.classList.remove('bg-blue-600', 'hover:bg-blue-700', 'bg-purple-600', 'hover:bg-purple-700');
                btn.classList.add('bg-red-600');
                progressText.textContent = '❌ ' + (status.message || `${actionText}失败`);
                progressText.classList.add('text-red-600');
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }, 2000);

    } catch (error) {
        console.error(`${actionText}失败:`, error);
        btn.textContent = `${actionText}失败`;
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        progressText.textContent = `❌ ${actionText}失败: ` + error.message;
        progressText.classList.add('text-red-600');
    }
}

// 批量审查
window.batchReview = async function() {
    const unreviewed = window.currentMRs.filter(mr => !mr.reviewed);
    if (unreviewed.length === 0) {
        alert('没有未审查的 MR');
        return;
    }

    if (!confirm(`确定要审查 ${unreviewed.length} 个 MR 吗？这可能需要一些时间。`)) {
        return;
    }

    // 依次审查每个 MR
    for (const mr of unreviewed) {
        await reviewMR(mr.web_url, mr.iid);
        // 等待5秒再审查下一个，避免API限流
        await new Promise(resolve => setTimeout(resolve, 5000));
    }
}

console.log('✅ manual-review.js 已加载');
