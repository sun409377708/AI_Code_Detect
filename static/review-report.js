// 审查报表功能
let allReviews = [];
let filteredReviews = [];

// 加载审查报表页面
async function loadReviewReportPage() {
    const tokenWarning = document.getElementById('reportTokenWarning');
    const reportContent = document.getElementById('reportContent');
    
    const gitlabToken = localStorage.getItem('gitlab_token');
    
    if (!gitlabToken) {
        tokenWarning.classList.remove('hidden');
        reportContent.classList.add('hidden');
        return;
    }
    
    tokenWarning.classList.add('hidden');
    reportContent.classList.remove('hidden');
    
    // 设置默认时间范围（最近30天）
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    document.getElementById('reportDateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('reportDateTo').value = today.toISOString().split('T')[0];
    
    // 加载数据
    await loadReviewReport();
}

// 加载审查报表
async function loadReviewReport() {
    const loading = document.getElementById('reviewReportLoading');
    const list = document.getElementById('reviewReportList');
    
    loading.classList.remove('hidden');
    list.classList.add('hidden');
    
    try {
        const gitlabToken = localStorage.getItem('gitlab_token');
        
        const response = await fetch('/api/history', {
            headers: {
                'X-GitLab-Token': gitlabToken
            }
        });
        
        const data = await response.json();
        
        if (data.source === 'new' && data.history) {
            allReviews = data.history;
            
            // 更新统计卡片
            if (data.stats) {
                document.getElementById('totalReviews').textContent = data.stats.total || 0;
                document.getElementById('avgScore').textContent = data.stats.avg_score || '-';
                document.getElementById('highIssues').textContent = data.stats.severity.high || 0;
                document.getElementById('mediumIssues').textContent = data.stats.severity.medium || 0;
                document.getElementById('lowIssues').textContent = data.stats.severity.low || 0;
            }
        } else {
            // 旧数据格式
            allReviews = data.history || [];
        }
        
        // 应用筛选
        applyFilters();
        
        loading.classList.add('hidden');
        list.classList.remove('hidden');
        
    } catch (error) {
        console.error('加载审查报表失败:', error);
        loading.innerHTML = '<p class="text-red-500 text-center py-8">加载失败: ' + error.message + '</p>';
    }
}

// 应用筛选
function applyFilters() {
    const typeFilter = document.getElementById('reportTypeFilter').value;
    const modeFilter = document.getElementById('reportModeFilter').value;
    const severityFilter = document.getElementById('reportSeverityFilter').value;
    const scoreFilter = document.getElementById('reportScoreFilter').value;
    const projectFilter = document.getElementById('reportProjectFilter').value.toLowerCase();
    const dateFrom = document.getElementById('reportDateFrom').value;
    const dateTo = document.getElementById('reportDateTo').value;
    
    filteredReviews = allReviews.filter(review => {
        // 类型筛选
        if (typeFilter !== 'all' && review.type !== typeFilter) return false;
        
        // 模式筛选
        if (modeFilter !== 'all' && review.mode !== modeFilter) return false;
        
        // 严重程度筛选
        if (severityFilter !== 'all') {
            if (severityFilter === 'high' && (!review.severity || review.severity.high === 0)) return false;
            if (severityFilter === 'medium' && (!review.severity || (review.severity.medium === 0 && review.severity.high === 0))) return false;
            if (severityFilter === 'low' && (!review.severity || (review.severity.low === 0 && review.severity.medium === 0 && review.severity.high === 0))) return false;
            if (severityFilter === 'none' && review.issues_found > 0) return false;
        }
        
        // 评分筛选
        if (scoreFilter !== 'all') {
            const [min, max] = scoreFilter.split('-').map(Number);
            if (review.quality_score < min || review.quality_score > max) return false;
        }
        
        // 项目筛选
        if (projectFilter && !review.project_name.toLowerCase().includes(projectFilter)) return false;
        
        // 时间筛选
        if (dateFrom || dateTo) {
            const reviewDate = new Date(review.timestamp).toISOString().split('T')[0];
            if (dateFrom && reviewDate < dateFrom) return false;
            if (dateTo && reviewDate > dateTo) return false;
        }
        
        return true;
    });
    
    renderReviewTable();
}

// 渲染审查表格
function renderReviewTable() {
    const tbody = document.getElementById('reviewReportTableBody');
    const recordCount = document.getElementById('reviewRecordCount');
    
    recordCount.textContent = filteredReviews.length;
    
    if (filteredReviews.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-6 py-8 text-center text-gray-500">
                    <svg class="w-12 h-12 mx-auto mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                    </svg>
                    <p class="text-sm">没有找到匹配的审查记录</p>
                    <p class="text-xs text-gray-400 mt-1">尝试调整筛选条件</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filteredReviews.map(review => {
        // 格式化时间
        const date = new Date(review.timestamp);
        const dateStr = date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
        
        // 类型和模式标签
        const typeLabel = review.type === 'mr' ? 'MR' : 'Commit';
        const typeColor = review.type === 'mr' ? 'bg-green-100 text-green-800' : 'bg-purple-100 text-purple-800';
        const modeLabel = review.mode === 'inline' ? '行内' : '总体';
        const modeColor = review.mode === 'inline' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800';
        
        // 评分显示
        const score = review.quality_score || 0;
        let scoreColor = 'text-gray-600';
        let scoreEmoji = '';
        if (score >= 90) {
            scoreColor = 'text-green-600';
            scoreEmoji = '🌟';
        } else if (score >= 80) {
            scoreColor = 'text-blue-600';
            scoreEmoji = '👍';
        } else if (score >= 70) {
            scoreColor = 'text-yellow-600';
            scoreEmoji = '⚠️';
        } else if (score > 0) {
            scoreColor = 'text-red-600';
            scoreEmoji = '❗';
        }
        
        // 问题统计
        const severity = review.severity || { high: 0, medium: 0, low: 0 };
        const issuesHtml = [];
        if (severity.high > 0) issuesHtml.push(`<span class="text-red-600">🔴 ${severity.high}</span>`);
        if (severity.medium > 0) issuesHtml.push(`<span class="text-yellow-600">🟡 ${severity.medium}</span>`);
        if (severity.low > 0) issuesHtml.push(`<span class="text-green-600">🟢 ${severity.low}</span>`);
        const issuesDisplay = issuesHtml.length > 0 ? issuesHtml.join(' ') : '<span class="text-gray-400">无问题</span>';
        
        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 text-sm text-gray-900 whitespace-nowrap">${dateStr}</td>
                <td class="px-6 py-4 text-sm">
                    <div class="flex gap-1">
                        <span class="px-2 py-1 text-xs font-medium rounded ${typeColor}">${typeLabel}</span>
                        <span class="px-2 py-1 text-xs font-medium rounded ${modeColor}">${modeLabel}</span>
                    </div>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">${review.project_name || '-'}</td>
                <td class="px-6 py-4 text-sm">
                    <div class="flex items-center gap-2">
                        <span class="text-2xl font-bold ${scoreColor}">${score > 0 ? score : '-'}</span>
                        ${score > 0 ? `<span class="text-lg">${scoreEmoji}</span>` : ''}
                    </div>
                </td>
                <td class="px-6 py-4 text-sm">
                    <div class="flex gap-2">
                        ${issuesDisplay}
                    </div>
                </td>
                <td class="px-6 py-4 text-sm">
                    <a href="${review.url}" target="_blank" class="text-indigo-600 hover:text-indigo-800 font-medium">
                        查看详情 →
                    </a>
                </td>
            </tr>
        `;
    }).join('');
}

// 筛选审查报表
function filterReviewReport() {
    applyFilters();
}

// 重置筛选
function resetReportFilters() {
    document.getElementById('reportTypeFilter').value = 'all';
    document.getElementById('reportModeFilter').value = 'all';
    document.getElementById('reportSeverityFilter').value = 'all';
    document.getElementById('reportScoreFilter').value = 'all';
    document.getElementById('reportProjectFilter').value = '';
    
    // 重置时间为最近30天
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    document.getElementById('reportDateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('reportDateTo').value = today.toISOString().split('T')[0];
    
    applyFilters();
}
