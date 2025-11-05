// Commit 审查功能

// 切换 Commits 列表显示
async function toggleCommits(mrId, mrUrl) {
    const commitsDiv = document.getElementById('commits-' + mrId);
    const commitsContent = document.getElementById('commitsContent-' + mrId);
    
    if (commitsDiv.classList.contains('hidden')) {
        // 显示并加载 Commits
        commitsDiv.classList.remove('hidden');
        commitsContent.innerHTML = '<p class="text-gray-600 text-sm">加载中...</p>';
        
        try {
            const response = await fetch('/api/mr/commits', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mr_url: mrUrl})
            });
            
            const data = await response.json();
            
            if (data.commits && data.commits.length > 0) {
                renderCommits(mrId, data.commits);
            } else {
                commitsContent.innerHTML = '<p class="text-gray-500 text-sm">没有找到 Commits</p>';
            }
        } catch (error) {
            console.error('加载 Commits 失败:', error);
            commitsContent.innerHTML = '<p class="text-red-500 text-sm">加载失败: ' + error.message + '</p>';
        }
    } else {
        // 隐藏
        commitsDiv.classList.add('hidden');
    }
}

// 渲染 Commits 列表
function renderCommits(mrId, commits) {
    const commitsContent = document.getElementById('commitsContent-' + mrId);
    
    const html = commits.map(commit => `
        <div class="border border-gray-200 rounded p-3 bg-white hover:shadow-sm transition">
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <div class="flex items-center gap-2">
                        <span class="font-mono text-xs bg-gray-100 px-2 py-1 rounded">${commit.short_id}</span>
                        <span class="text-sm font-medium text-gray-900">${escapeHtml(commit.title)}</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">
                        ${commit.author_name} • ${new Date(commit.created_at).toLocaleString('zh-CN')}
                    </p>
                </div>
                <div class="flex gap-2 ml-4">
                    <button 
                        onclick="reviewCommit('${commit.web_url}', '${commit.id}', '${commit.short_id}')"
                        class="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-xs font-medium"
                        id="commitReviewBtn-${commit.short_id}"
                    >
                        AI 审查
                    </button>
                    <a 
                        href="${commit.web_url}" 
                        target="_blank"
                        class="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-1 rounded text-xs font-medium"
                    >
                        查看
                    </a>
                </div>
            </div>
            
            <!-- Commit 审查进度 -->
            <div id="commitProgress-${commit.short_id}" class="mt-3 hidden">
                <div class="w-full bg-gray-200 rounded-full h-1.5">
                    <div class="bg-green-600 h-1.5 rounded-full" style="width: 0%" id="commitProgressBar-${commit.short_id}"></div>
                </div>
                <p class="mt-1 text-xs text-gray-600" id="commitProgressText-${commit.short_id}">准备中...</p>
            </div>
            
            <!-- Commit 审查结果 -->
            <div id="commitResult-${commit.short_id}" class="mt-3 hidden">
                <div class="border-t pt-2">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-xs font-medium text-gray-700">AI 审查结果</span>
                        <button 
                            onclick="toggleCommitResult('${commit.short_id}')"
                            class="text-xs text-indigo-600 hover:text-indigo-800"
                            id="toggleCommitResultBtn-${commit.short_id}"
                        >
                            收起
                        </button>
                    </div>
                    <div id="commitResultContent-${commit.short_id}" class="bg-gray-50 rounded p-2 text-xs overflow-auto max-h-64">
                        <p class="text-gray-600">加载中...</p>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
    
    commitsContent.innerHTML = html;
}

// 审查单个 Commit
async function reviewCommit(commitUrl, commitId, shortId) {
    const btn = document.getElementById('commitReviewBtn-' + shortId);
    const progress = document.getElementById('commitProgress-' + shortId);
    const progressBar = document.getElementById('commitProgressBar-' + shortId);
    const progressText = document.getElementById('commitProgressText-' + shortId);
    
    btn.disabled = true;
    btn.textContent = '审查中...';
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    progress.classList.remove('hidden');
    
    try {
        // 启动审查
        const response = await fetch('/api/commit/review', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({commit_url: commitUrl, commit_id: commitId})
        });
        
        const data = await response.json();
        const reviewId = data.review_id;
        
        // 轮询状态
        const checkStatus = setInterval(async () => {
            const statusResponse = await fetch('/api/commit/review/status/' + reviewId);
            const status = await statusResponse.json();
            
            progressBar.style.width = (status.progress || 0) + '%';
            progressText.textContent = status.message || '处理中...';
            
            if (status.status === 'success') {
                clearInterval(checkStatus);
                btn.textContent = '审查完成 ✓';
                btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                btn.classList.add('bg-green-500');
                progressText.textContent = '✅ 审查完成！结果已显示在下方';
                progressText.classList.add('text-green-600', 'font-medium');
                
                // 显示结果（使用格式化）
                if (status.output) {
                    const resultDiv = document.getElementById('commitResult-' + shortId);
                    const resultContent = document.getElementById('commitResultContent-' + shortId);
                    resultDiv.classList.remove('hidden');
                    resultContent.innerHTML = formatReviewResult(status.output);
                }
            } else if (status.status === 'failed') {
                clearInterval(checkStatus);
                btn.textContent = '审查失败';
                btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                btn.classList.add('bg-red-600');
                progressText.textContent = '❌ ' + (status.message || '审查失败');
                progressText.classList.add('text-red-600');
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }, 2000);
        
    } catch (error) {
        console.error('审查 Commit 失败:', error);
        btn.textContent = '审查失败';
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        progressText.textContent = '❌ 审查失败: ' + error.message;
        progressText.classList.add('text-red-600');
    }
}

// 切换 Commit 结果显示
function toggleCommitResult(shortId) {
    const content = document.getElementById('commitResultContent-' + shortId);
    const btn = document.getElementById('toggleCommitResultBtn-' + shortId);
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        btn.textContent = '收起';
    } else {
        content.classList.add('hidden');
        btn.textContent = '展开';
    }
}
