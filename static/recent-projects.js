// 最近活跃项目管理
let recentProjects = [];
let allRecentProjects = [];
let currentProjectInputMode = 'recent';

// 切换项目输入模式
function switchProjectInputMode(mode) {
    currentProjectInputMode = mode;
    
    // 更新选项卡样式
    const tabs = {
        'recent': document.getElementById('recentProjectsTab'),
        'group': document.getElementById('groupSelectTab'),
        'manual': document.getElementById('manualInputTab')
    };
    
    const modes = {
        'recent': document.getElementById('recentProjectsMode'),
        'group': document.getElementById('groupSelectMode'),
        'manual': document.getElementById('manualInputMode')
    };
    
    // 重置所有选项卡样式
    Object.values(tabs).forEach(tab => {
        tab.className = 'flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors text-gray-600 hover:text-gray-900';
    });
    
    // 隐藏所有模式
    Object.values(modes).forEach(modeDiv => {
        modeDiv.classList.add('hidden');
    });
    
    // 激活当前选项卡
    tabs[mode].className = 'flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors bg-white text-indigo-600 shadow-sm';
    
    // 显示当前模式
    modes[mode].classList.remove('hidden');
    
    // 如果切换到最近项目模式，加载数据
    if (mode === 'recent' && recentProjects.length === 0) {
        loadRecentProjects();
    }
}

// 加载最近活跃项目
async function loadRecentProjects() {
    const listContainer = document.getElementById('recentProjectsList');
    
    try {
        listContainer.innerHTML = `
            <div class="p-8 text-center text-gray-500">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
                <p class="text-sm">正在加载最近活跃项目...</p>
            </div>
        `;
        
        const gitlabToken = localStorage.getItem('gitlab_token');
        if (!gitlabToken) {
            throw new Error('请先配置 GitLab Token');
        }
        
        const response = await fetch('/api/recent-projects', {
            headers: {
                'X-GitLab-Token': gitlabToken
            }
        });
        
        if (!response.ok) {
            throw new Error('加载失败');
        }
        
        const data = await response.json();
        allRecentProjects = data.projects || [];
        recentProjects = [...allRecentProjects];
        
        renderRecentProjects();
        
    } catch (error) {
        console.error('加载最近活跃项目失败:', error);
        listContainer.innerHTML = `
            <div class="p-8 text-center text-gray-500">
                <svg class="w-12 h-12 mx-auto mb-3 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="text-sm text-red-600">${error.message}</p>
                <button onclick="loadRecentProjects()" class="mt-3 text-indigo-600 hover:text-indigo-700 text-sm font-medium">
                    重试
                </button>
            </div>
        `;
    }
}

// 渲染最近活跃项目列表
function renderRecentProjects() {
    const listContainer = document.getElementById('recentProjectsList');
    
    if (recentProjects.length === 0) {
        listContainer.innerHTML = `
            <div class="p-8 text-center text-gray-500">
                <svg class="w-12 h-12 mx-auto mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                </svg>
                <p class="text-sm">没有找到匹配的项目</p>
            </div>
        `;
        return;
    }
    
    listContainer.innerHTML = recentProjects.map(project => `
        <div class="p-4 hover:bg-gray-50 cursor-pointer transition-colors" onclick="selectRecentProject('${project.id}', '${escapeHtml(project.name)}', '${escapeHtml(project.web_url)}')">
            <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center space-x-2">
                        <h3 class="text-sm font-medium text-gray-900 truncate">${escapeHtml(project.name)}</h3>
                        ${project.star_count > 0 ? `<span class="text-xs text-yellow-600">⭐ ${project.star_count}</span>` : ''}
                    </div>
                    <p class="text-xs text-gray-500 truncate mt-1">${escapeHtml(project.path_with_namespace)}</p>
                    <div class="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                        ${project.last_activity_at ? `
                            <span class="flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                                ${formatRelativeTime(project.last_activity_at)}
                            </span>
                        ` : ''}
                        ${project.open_issues_count !== undefined ? `
                            <span class="flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                                </svg>
                                ${project.open_issues_count} issues
                            </span>
                        ` : ''}
                    </div>
                </div>
                <div class="ml-4">
                    <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                </div>
            </div>
        </div>
    `).join('');
}

// 过滤最近项目
function filterRecentProjects() {
    const searchInput = document.getElementById('recentProjectSearch');
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    if (!searchTerm) {
        recentProjects = [...allRecentProjects];
    } else {
        recentProjects = allRecentProjects.filter(project => {
            return project.name.toLowerCase().includes(searchTerm) ||
                   project.path_with_namespace.toLowerCase().includes(searchTerm) ||
                   (project.description && project.description.toLowerCase().includes(searchTerm));
        });
    }
    
    renderRecentProjects();
}

// 选择最近项目
function selectRecentProject(projectId, projectName, projectUrl) {
    // 显示选中的项目信息
    const infoDiv = document.getElementById('selectedProjectInfo');
    const nameSpan = document.getElementById('selectedProjectName');
    const urlSpan = document.getElementById('selectedProjectUrl');
    
    nameSpan.textContent = projectName;
    urlSpan.textContent = projectUrl;
    infoDiv.classList.remove('hidden');
    
    // 保存到全局变量
    window.selectedProject = {
        id: projectId,
        name: projectName,
        url: projectUrl
    };
    
    // 同时更新手动输入框（以便兼容现有逻辑）
    document.getElementById('projectUrl').value = projectUrl;
}

// 从选中的项目加载 MR
function loadMRsFromSelected() {
    if (window.selectedProject) {
        document.getElementById('projectUrl').value = window.selectedProject.url;
        loadMRs();
    }
}

// 格式化相对时间
function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} 周前`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} 个月前`;
    return `${Math.floor(diffDays / 365)} 年前`;
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    // 默认显示最近活跃项目模式
    if (document.getElementById('manual-review')) {
        switchProjectInputMode('recent');
    }
});
