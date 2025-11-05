// 审查结果格式化和美化

/**
 * 格式化审查结果，添加颜色和图标
 */
function formatReviewResult(text) {
    if (!text) return '<p class="text-gray-500">暂无结果</p>';
    
    // 按行分割
    const lines = text.split('\n');
    let formattedHtml = '';
    let inCodeBlock = false;
    let codeBlockContent = '';
    
    for (let line of lines) {
        // 检测代码块
        if (line.trim().startsWith('```')) {
            if (inCodeBlock) {
                // 结束代码块
                formattedHtml += `<pre class="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto my-2"><code>${escapeHtml(codeBlockContent)}</code></pre>`;
                codeBlockContent = '';
                inCodeBlock = false;
            } else {
                // 开始代码块
                inCodeBlock = true;
            }
            continue;
        }
        
        if (inCodeBlock) {
            codeBlockContent += line + '\n';
            continue;
        }
        
        // 空行
        if (line.trim() === '') {
            formattedHtml += '<div class="h-2"></div>';
            continue;
        }
        
        // 标题（以 # 开头）
        if (line.trim().startsWith('#')) {
            const level = line.match(/^#+/)[0].length;
            const text = line.replace(/^#+\s*/, '');
            const sizes = ['text-xl', 'text-lg', 'text-base', 'text-sm'];
            const size = sizes[Math.min(level - 1, 3)];
            formattedHtml += `<h${level} class="${size} font-bold text-gray-900 mt-4 mb-2">${escapeHtml(text)}</h${level}>`;
            continue;
        }
        
        // 成功/通过（绿色）
        if (line.match(/✅|✓|通过|成功|good|correct|well/i)) {
            formattedHtml += `<div class="flex items-start gap-2 my-1 p-2 bg-green-50 rounded">
                <span class="text-green-600 flex-shrink-0">✅</span>
                <span class="text-green-800 text-sm">${escapeHtml(line.replace(/✅|✓/g, '').trim())}</span>
            </div>`;
            continue;
        }
        
        // 错误/问题（红色）
        if (line.match(/❌|✗|错误|失败|error|bug|issue|problem|wrong/i)) {
            formattedHtml += `<div class="flex items-start gap-2 my-1 p-2 bg-red-50 rounded">
                <span class="text-red-600 flex-shrink-0">❌</span>
                <span class="text-red-800 text-sm font-medium">${escapeHtml(line.replace(/❌|✗/g, '').trim())}</span>
            </div>`;
            continue;
        }
        
        // 警告/建议（黄色/橙色）
        if (line.match(/⚠️|⚠|警告|建议|注意|warning|suggestion|should|recommend/i)) {
            formattedHtml += `<div class="flex items-start gap-2 my-1 p-2 bg-yellow-50 rounded">
                <span class="text-yellow-600 flex-shrink-0">⚠️</span>
                <span class="text-yellow-800 text-sm">${escapeHtml(line.replace(/⚠️|⚠/g, '').trim())}</span>
            </div>`;
            continue;
        }
        
        // 提示/优化（蓝色）
        if (line.match(/💡|ℹ️|提示|优化|技巧|info|tip|hint|optimization|consider/i)) {
            formattedHtml += `<div class="flex items-start gap-2 my-1 p-2 bg-blue-50 rounded">
                <span class="text-blue-600 flex-shrink-0">💡</span>
                <span class="text-blue-800 text-sm">${escapeHtml(line.replace(/💡|ℹ️/g, '').trim())}</span>
            </div>`;
            continue;
        }
        
        // 列表项（以 - 或 * 或数字. 开头）
        if (line.match(/^\s*[-*•]\s+/) || line.match(/^\s*\d+\.\s+/)) {
            const content = line.replace(/^\s*[-*•]\s+/, '').replace(/^\s*\d+\.\s+/, '');
            formattedHtml += `<div class="flex items-start gap-2 my-1 ml-4">
                <span class="text-gray-400 flex-shrink-0">•</span>
                <span class="text-gray-700 text-sm">${escapeHtml(content)}</span>
            </div>`;
            continue;
        }
        
        // 粗体文本（**text**）
        let processedLine = line;
        processedLine = processedLine.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        
        // 代码片段（`code`）
        processedLine = processedLine.replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono text-gray-800">$1</code>');
        
        // 普通文本
        formattedHtml += `<p class="text-gray-700 text-sm my-1">${processedLine}</p>`;
    }
    
    return formattedHtml;
}

/**
 * 简化版格式化（用于快速预览）
 */
function formatReviewResultSimple(text) {
    if (!text) return '<p class="text-gray-500">暂无结果</p>';
    
    // 提取关键信息
    const lines = text.split('\n');
    let summary = {
        success: [],
        errors: [],
        warnings: [],
        tips: []
    };
    
    for (let line of lines) {
        if (line.match(/✅|✓|通过|成功/i)) {
            summary.success.push(line.replace(/✅|✓/g, '').trim());
        } else if (line.match(/❌|✗|错误|失败/i)) {
            summary.errors.push(line.replace(/❌|✗/g, '').trim());
        } else if (line.match(/⚠️|⚠|警告|建议/i)) {
            summary.warnings.push(line.replace(/⚠️|⚠/g, '').trim());
        } else if (line.match(/💡|提示|优化/i)) {
            summary.tips.push(line.replace(/💡/g, '').trim());
        }
    }
    
    let html = '<div class="space-y-2">';
    
    if (summary.errors.length > 0) {
        html += `<div class="bg-red-50 border-l-4 border-red-500 p-2">
            <p class="text-red-800 font-medium text-sm">❌ 发现 ${summary.errors.length} 个问题</p>
        </div>`;
    }
    
    if (summary.warnings.length > 0) {
        html += `<div class="bg-yellow-50 border-l-4 border-yellow-500 p-2">
            <p class="text-yellow-800 font-medium text-sm">⚠️ ${summary.warnings.length} 条建议</p>
        </div>`;
    }
    
    if (summary.success.length > 0) {
        html += `<div class="bg-green-50 border-l-4 border-green-500 p-2">
            <p class="text-green-800 font-medium text-sm">✅ ${summary.success.length} 项通过</p>
        </div>`;
    }
    
    if (summary.tips.length > 0) {
        html += `<div class="bg-blue-50 border-l-4 border-blue-500 p-2">
            <p class="text-blue-800 font-medium text-sm">💡 ${summary.tips.length} 条优化建议</p>
        </div>`;
    }
    
    html += '</div>';
    return html;
}
