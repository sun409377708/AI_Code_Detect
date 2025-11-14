// 项目列表管理功能

// 全局变量
let allProjects = [];
let allGroups = [];
let currentView = 'all'; // all, group, favorite
let favoriteProjects = [];

// 从 localStorage 获取收藏的项目
function loadFavoriteProjects() {
    const stored = localStorage.getItem('favorite_projects');
    if (stored) {
        try {
            favoriteProjects = JSON.parse(stored);
        } catch (e) {
            console.error('解析收藏项目失败:', e);
            favoriteProjects = [];
        }
    }
    return favoriteProjects;
}

// 保存收藏的项目到 localStorage
function saveFavoriteProjects() {
    localStorage.setItem('favorite_projects', JSON.stringify(favoriteProjects));
}

// 切换收藏状态
function toggleFavorite(projectId) {
    const index = favoriteProjects.indexOf(projectId);
    if (index > -1) {
        favoriteProjects.splice(index, 1);
    } else {
        favoriteProjects.push(projectId);
    }
    saveFavoriteProjects();
    
    // 刷新当前视图
    if (currentView === 'favorite') {
        renderFavoriteView();
    } else {
        // 更新收藏图标
        const btn = document.querySelector(`[data-project-id="${projectId}"] .favorite-btn`);
        if (btn) {
            btn.textContent = favoriteProjects.includes(projectId) ? '⭐' : '☆';
        }
    }
}

// 加载项目列表页面
async function loadProjectListPage() {
    const tokenWarning = document.getElementById('projectListTokenWarning');
    const projectListContent = document.getElementById('projectListContent');
    
    // 检查是否配置了 Token
    const token = localStorage.getItem('gitlab_token');
    if (!token) {
        tokenWarning.classList.remove('hidden');
        projectListContent.classList.add('hidden');
        return;
    }
    
    // 隐藏警告，显示内容
    tokenWarning.classList.add('hidden');
    projectListContent.classList.remove('hidden');
    
    // 加载收藏列表
    loadFavoriteProjects();
    
    // 加载项目数据
    await loadProjectList();
}

// 加载项目列表
async function loadProjectList() {
    const loading = document.getElementById('projectListLoading');
    const container = document.getElementById('projectListContainer');
    
    loading.classList.remove('hidden');
    container.classList.add('hidden');
    
    try {
        // 并行加载项目和组
        const [projectsResponse, groupsResponse] = await Promise.all([
            fetch('/api/user/projects'),
            fetch('/api/user/groups')
        ]);
        
        const projectsData = await projectsResponse.json();
        const groupsData = await groupsResponse.json();
        
        allProjects = projectsData.projects || [];
        allGroups = groupsData.groups || [];
        
        // 更新统计信息
        document.getElementById('totalProjectCount').textContent = allProjects.length;
        document.getElementById('totalGroupCount').textContent = allGroups.length;
        
        // 渲染当前视图
        renderCurrentView();
        
        loading.classList.add('hidden');
        container.classList.remove('hidden');
    } catch (error) {
        console.error('加载项目列表失败:', error);
        loading.innerHTML = `
            <div class="text-red-600">
                <p class="font-medium">加载失败</p>
                <p class="text-sm mt-2">${error.message}</p>
                <button onclick="loadProjectList()" class="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                    重试
                </button>
            </div>
        `;
    }
}

// 切换视图
function switchProjectView(view) {
    currentView = view;
    
    // 更新按钮状态
    const buttons = {
        'all': document.getElementById('viewAllBtn'),
        'group': document.getElementById('viewGroupBtn'),
        'favorite': document.getElementById('viewFavoriteBtn')
    };
    
    Object.keys(buttons).forEach(key => {
        const btn = buttons[key];
        if (key === view) {
            btn.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
            btn.classList.add('bg-indigo-600', 'text-white');
        } else {
            btn.classList.remove('bg-indigo-600', 'text-white');
            btn.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
        }
    });
    
    // 渲染视图
    renderCurrentView();
}

// 渲染当前视图
function renderCurrentView() {
    const allView = document.getElementById('allProjectsView');
    const groupView = document.getElementById('groupProjectsView');
    const favoriteView = document.getElementById('favoriteProjectsView');
    
    // 隐藏所有视图
    allView.classList.add('hidden');
    groupView.classList.add('hidden');
    favoriteView.classList.add('hidden');
    
    // 显示对应视图
    if (currentView === 'all') {
        allView.classList.remove('hidden');
        renderAllProjectsView();
    } else if (currentView === 'group') {
        groupView.classList.remove('hidden');
        renderGroupView();
    } else if (currentView === 'favorite') {
        favoriteView.classList.remove('hidden');
        renderFavoriteView();
    }
}

// 渲染所有项目视图
function renderAllProjectsView() {
    const container = document.getElementById('allProjectsView');
    const searchTerm = document.getElementById('projectSearchInput').value.toLowerCase();
    
    // 筛选项目
    const filteredProjects = allProjects.filter(project => {
        return project.name.toLowerCase().includes(searchTerm) || 
               project.path_with_namespace.toLowerCase().includes(searchTerm);
    });
    
    // 更新显示数量
    document.getElementById('visibleProjectCount').textContent = filteredProjects.length;
    
    if (filteredProjects.length === 0) {
        document.getElementById('emptyProjectsState').classList.remove('hidden');
        container.innerHTML = '';
        return;
    }
    
    document.getElementById('emptyProjectsState').classList.add('hidden');
    
    // 渲染项目卡片
    container.innerHTML = filteredProjects.map(project => createProjectCard(project)).join('');
}

// 渲染按组分类视图
function renderGroupView() {
    const container = document.getElementById('groupProjectsView');
    const searchTerm = document.getElementById('projectSearchInput').value.toLowerCase();
    
    console.log('=== 按组分类视图 ===');
    console.log('所有组数量:', allGroups.length);
    console.log('所有项目数量:', allProjects.length);
    
    // 使用 GitLab 的所有组来分类
    const projectsByGroup = {};
    
    // 初始化所有组
    allGroups.forEach(group => {
        projectsByGroup[group.id] = {
            group: group,
            projects: []
        };
    });
    
    // 添加个人项目组
    projectsByGroup['personal'] = {
        group: {name: '个人项目', id: 'personal'},
        projects: []
    };
    
    // 将项目分配到对应的组
    allProjects.forEach(project => {
        // 筛选
        if (searchTerm && !project.name.toLowerCase().includes(searchTerm) && 
            !project.path_with_namespace.toLowerCase().includes(searchTerm)) {
            return;
        }
        
        if (project.namespace && project.namespace.kind === 'group') {
            const groupId = project.namespace.id;
            console.log(`项目 ${project.name} 属于组 ${project.namespace.name} (ID: ${groupId})`);
            if (projectsByGroup[groupId]) {
                projectsByGroup[groupId].projects.push(project);
            } else {
                console.warn(`组 ${groupId} 不在 allGroups 中，项目: ${project.name}`);
            }
        } else {
            projectsByGroup['personal'].projects.push(project);
        }
    });
    
    // 计算显示的项目数量
    let visibleCount = 0;
    Object.values(projectsByGroup).forEach(group => {
        visibleCount += group.projects.length;
    });
    document.getElementById('visibleProjectCount').textContent = visibleCount;
    
    if (visibleCount === 0) {
        document.getElementById('emptyProjectsState').classList.remove('hidden');
        container.innerHTML = '';
        return;
    }
    
    document.getElementById('emptyProjectsState').classList.add('hidden');
    
    // 渲染组和项目（只渲染有项目的组）
    let html = '';
    let renderedGroupCount = 0;
    
    // 先渲染有项目的 GitLab 组
    allGroups.forEach(group => {
        const groupData = projectsByGroup[group.id];
        if (groupData && groupData.projects.length > 0) {
            console.log(`渲染组: ${group.name}, 项目数: ${groupData.projects.length}`);
            html += createGroupCard(groupData.group, groupData.projects);
            renderedGroupCount++;
        }
    });
    
    // 最后渲染个人项目
    if (projectsByGroup['personal'].projects.length > 0) {
        console.log(`渲染个人项目组, 项目数: ${projectsByGroup['personal'].projects.length}`);
        html += createGroupCard(projectsByGroup['personal'].group, projectsByGroup['personal'].projects);
        renderedGroupCount++;
    }
    
    console.log(`总共渲染了 ${renderedGroupCount} 个组`);
    container.innerHTML = html;
}

// 渲染收藏视图（从 GitLab 获取 Star 项目）
async function renderFavoriteView() {
    const container = document.getElementById('favoriteProjectsView');
    
    // 显示加载状态
    container.innerHTML = `
        <div class="bg-white shadow rounded-lg p-8 text-center">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            <p class="mt-2 text-gray-600">加载 GitLab Star 项目中...</p>
        </div>
    `;
    
    try {
        // 从 GitLab 获取 Star 过的项目
        const response = await fetch('/api/user/starred-projects');
        const data = await response.json();
        
        const starredProjects = data.projects || [];
        
        // 更新显示数量
        document.getElementById('visibleProjectCount').textContent = starredProjects.length;
        
        if (starredProjects.length === 0) {
            container.innerHTML = `
                <div class="bg-white shadow rounded-lg p-8 text-center text-gray-500">
                    <svg class="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                    </svg>
                    <p class="text-lg font-medium">还没有 Star 过的项目</p>
                    <p class="text-sm mt-2">在 GitLab 项目页面点击 ⭐ Star 按钮收藏项目</p>
                    <a href="http://gitlab.it.ikang.com" target="_blank" class="mt-4 inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                        前往 GitLab
                    </a>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `<div class="space-y-2">${starredProjects.map(project => createProjectCard(project)).join('')}</div>`;
    } catch (error) {
        console.error('加载 Star 项目失败:', error);
        container.innerHTML = `
            <div class="bg-white shadow rounded-lg p-8 text-center text-red-600">
                <p class="font-medium">加载失败</p>
                <p class="text-sm mt-2">${error.message}</p>
                <button onclick="renderFavoriteView()" class="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                    重试
                </button>
            </div>
        `;
    }
}

// 创建项目卡片（紧凑版）
function createProjectCard(project) {
    const isFavorite = favoriteProjects.includes(project.id);
    const lastActivity = project.last_activity_at ? new Date(project.last_activity_at).toLocaleDateString('zh-CN') : '未知';
    
    return `
        <div class="bg-white shadow rounded-lg p-3 hover:shadow-md transition-shadow" data-project-id="${project.id}">
            <div class="flex items-center justify-between gap-3">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <button onclick="toggleFavorite(${project.id})" class="favorite-btn text-lg hover:scale-110 transition-transform flex-shrink-0" title="${isFavorite ? '取消收藏' : '收藏项目'}">
                            ${isFavorite ? '⭐' : '☆'}
                        </button>
                        <h3 class="text-sm font-semibold text-gray-900 truncate">${project.name}</h3>
                    </div>
                    <p class="text-xs text-gray-500 truncate mt-0.5">${project.path_with_namespace}</p>
                    <div class="flex items-center gap-3 text-xs text-gray-400 mt-1">
                        <span>📅 ${lastActivity}</span>
                        ${project.star_count ? `<span>⭐ ${project.star_count}</span>` : ''}
                    </div>
                </div>
                <div class="flex gap-2 flex-shrink-0">
                    <a href="${project.web_url}" target="_blank" class="px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-xs rounded text-center whitespace-nowrap">
                        🔗 打开项目
                    </a>
                    <button onclick="goToManualReview('${project.path_with_namespace}')" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded whitespace-nowrap">
                        ✋ 手动审查
                    </button>
                    <button onclick="goToAutoReview(${project.id})" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs rounded whitespace-nowrap">
                        🤖 配置审查
                    </button>
                </div>
            </div>
        </div>
    `;
}

// 创建组卡片（默认折叠）
function createGroupCard(group, projects) {
    const groupId = `group-${group.id}`;
    // 默认折叠，除非用户手动展开过
    const isExpanded = localStorage.getItem(groupId) === 'expanded';
    
    return `
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="bg-gray-50 px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-100" onclick="toggleGroup('${groupId}')">
                <div class="flex items-center gap-3">
                    <span class="text-xl">📁</span>
                    <div>
                        <h3 class="text-base font-semibold text-gray-900">${group.name}</h3>
                        <p class="text-xs text-gray-500">${projects.length} 个项目</p>
                    </div>
                </div>
                <svg id="${groupId}-icon" class="w-5 h-5 text-gray-600 transition-transform ${isExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                </svg>
            </div>
            <div id="${groupId}-content" class="p-3 space-y-2 ${isExpanded ? '' : 'hidden'}">
                ${projects.map(project => createProjectCard(project)).join('')}
            </div>
        </div>
    `;
}

// 切换组展开/折叠
function toggleGroup(groupId) {
    const content = document.getElementById(`${groupId}-content`);
    const icon = document.getElementById(`${groupId}-icon`);
    
    if (content.classList.contains('hidden')) {
        // 展开
        content.classList.remove('hidden');
        icon.classList.add('rotate-180');
        localStorage.setItem(groupId, 'expanded');
    } else {
        // 折叠
        content.classList.add('hidden');
        icon.classList.remove('rotate-180');
        localStorage.removeItem(groupId);
    }
}

// 筛选项目
function filterProjects() {
    renderCurrentView();
}

// 跳转到手动审查页面
function goToManualReview(projectPath) {
    // 切换到手动审查页面
    switchPage('manual-review');
    
    // TODO: 自动填充项目路径
    // 需要在 manual-review.js 中添加相应函数
}

// 跳转到自动审查配置页面
function goToAutoReview(projectId) {
    // 切换到自动审查页面
    switchPage('auto-review');
    
    // TODO: 自动定位到该项目
}

console.log('✅ project-list.js 已加载');
