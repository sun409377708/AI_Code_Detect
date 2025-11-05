// Prompt 管理功能

// 加载 Prompt 配置
async function loadPrompts() {
    try {
        const response = await fetch('/api/prompts');
        const data = await response.json();
        window.currentPrompts = data;
        
        // 显示当前使用的 Prompt
        const currentTemplate = data.templates[data.current];
        document.getElementById('currentPromptInfo').innerHTML = `
            <div class="space-y-2">
                <p class="font-medium text-gray-900">${currentTemplate.name}</p>
                <p class="text-sm text-gray-600">${currentTemplate.description}</p>
                <div class="mt-3 bg-white rounded border p-3">
                    <pre class="text-xs text-gray-700 whitespace-pre-wrap">${currentTemplate.prompt}</pre>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('加载 Prompt 失败:', error);
    }
}

// 切换 Prompt 编辑模式
function togglePromptEdit() {
    const display = document.getElementById('promptDisplay');
    const edit = document.getElementById('promptEdit');
    const btn = document.getElementById('editPromptBtn');
    
    if (edit.classList.contains('hidden')) {
        display.classList.add('hidden');
        edit.classList.remove('hidden');
        btn.textContent = '取消编辑';
        document.getElementById('promptTemplate').value = window.currentPrompts.current;
        loadPromptTemplate();
    } else {
        display.classList.remove('hidden');
        edit.classList.add('hidden');
        btn.textContent = '编辑 Prompt';
        document.getElementById('promptMessage').classList.add('hidden');
    }
}

// 加载选中的模板
function loadPromptTemplate() {
    const templateId = document.getElementById('promptTemplate').value;
    const template = window.currentPrompts.templates[templateId];
    
    if (template) {
        document.getElementById('promptDescription').textContent = template.description;
        document.getElementById('promptContent').value = template.prompt;
    }
}

// 保存 Prompt
async function savePrompt() {
    const templateId = document.getElementById('promptTemplate').value;
    const content = document.getElementById('promptContent').value;
    
    if (!content.trim()) {
        alert('Prompt 内容不能为空');
        return;
    }
    
    const messageDiv = document.getElementById('promptMessage');
    messageDiv.classList.remove('hidden', 'bg-green-100', 'bg-red-100', 'text-green-700', 'text-red-700');
    messageDiv.textContent = '保存中...';
    messageDiv.classList.add('bg-blue-100', 'text-blue-700');
    
    try {
        const saveData = {
            current: templateId,
        };
        
        if (templateId === 'custom') {
            saveData.custom = {
                name: '自定义',
                description: '用户自定义的审查 Prompt',
                prompt: content
            };
        }
        
        const response = await fetch('/api/prompts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(saveData)
        });
        
        const data = await response.json();
        
        messageDiv.classList.remove('bg-blue-100', 'text-blue-700');
        if (data.success) {
            messageDiv.classList.add('bg-green-100', 'text-green-700');
            messageDiv.textContent = '✅ ' + data.message;
            setTimeout(() => {
                loadPrompts();
                togglePromptEdit();
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
