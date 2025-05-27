/**
 * 美妆销售数据分析助手前端脚本
 */

// 获取DOM元素
const uploadForm = document.getElementById('upload-form');
const dataSourceList = document.getElementById('data-source-list');
const currentSourceName = document.getElementById('current-source-name');
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const newSessionButton = document.getElementById('new-session-button');
const suggestionPills = document.querySelectorAll('.suggestion-pill');

// 状态变量
let currentSession = null;
let currentDataSource = null;

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    // 加载数据源列表
    loadDataSources();
    
    // 设置事件监听器
    setupEventListeners();
});

/**
 * 设置事件监听器
 */
function setupEventListeners() {
    // 文件上传表单提交
    uploadForm.addEventListener('submit', handleFormSubmit);
    
    // 发送消息按钮
    sendButton.addEventListener('click', sendMessage);
    
    // 新建会话按钮
    newSessionButton.addEventListener('click', startNewSession);
    
    // 消息输入框回车键
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 问题建议点击
    suggestionPills.forEach(pill => {
        pill.addEventListener('click', () => {
            messageInput.value = pill.textContent;
            // 只有在选择了数据源的情况下才发送
            if (currentDataSource) {
                sendMessage();
            }
        });
    });
}

/**
 * 加载数据源列表
 */
async function loadDataSources() {
    try {
        const response = await fetch('/api/data/sources');
        const dataSources = await response.json();
        
        // 清空当前列表
        dataSourceList.innerHTML = '';
        
        if (dataSources.length === 0) {
            // 没有数据源
            dataSourceList.innerHTML = '<div class="empty-state">没有可用的数据源</div>';
            return;
        }
        
        // 添加数据源到列表
        dataSources.forEach(source => {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'source-item';
            sourceItem.dataset.id = source.id;
            sourceItem.textContent = source.name;
            
            // 点击选中数据源
            sourceItem.addEventListener('click', () => selectDataSource(source));
            
            dataSourceList.appendChild(sourceItem);
        });
    } catch (error) {
        console.error('加载数据源失败:', error);
        showError('加载数据源列表失败，请检查网络连接。');
    }
}

/**
 * 处理文件上传表单提交
 * @param {Event} e - 表单提交事件
 */
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(uploadForm);
    
    try {
        const response = await fetch('/api/data/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '上传失败');
        }
        
        const data = await response.json();
        
        // 显示成功消息
        showSuccess('数据上传成功!');
        
        // 重置表单
        uploadForm.reset();
        
        // 重新加载数据源列表
        loadDataSources();
        
        // 自动选择新上传的数据源
        selectDataSource(data);
    } catch (error) {
        console.error('上传文件失败:', error);
        showError(`上传失败: ${error.message}`);
    }
}

/**
 * 选择数据源
 * @param {Object} source - 数据源对象
 */
function selectDataSource(source) {
    // 设置当前数据源
    currentDataSource = source;
    
    // 更新UI显示
    currentSourceName.textContent = source.name;
    
    // 移除所有源的active类
    const sourceItems = document.querySelectorAll('.source-item');
    sourceItems.forEach(item => item.classList.remove('active'));
    
    // 为当前选中的源添加active类
    const selectedItem = document.querySelector(`.source-item[data-id="${source.id}"]`);
    if (selectedItem) {
        selectedItem.classList.add('active');
    }
    
    // 启用消息输入和新建会话按钮
    messageInput.disabled = false;
    sendButton.disabled = false;
    newSessionButton.disabled = false;
    
    // 创建新的聊天会话
    createNewChatSession();
}

/**
 * 创建新的聊天会话
 */
async function createNewChatSession() {
    // 清空聊天消息
    chatMessages.innerHTML = '';
    
    // 添加系统欢迎消息
    addMessage('system', `您好，我是您的美妆销售数据分析助手。我已加载"${currentDataSource.name}"数据集，请问有什么我可以帮您分析的吗？`);
    
    // 重置当前会话ID
    currentSession = null;
}

/**
 * 发送消息
 */
async function sendMessage() {
    // 获取消息内容
    const message = messageInput.value.trim();
    
    // 空消息不处理
    if (!message) return;
    
    // 添加用户消息到聊天框
    const userMessageId = addMessage('user', message);
    
    // 清空输入框
    messageInput.value = '';
    
    try {
        // 准备请求数据
        const requestData = {
            message: message
        };
        
        // 如果有会话ID，添加到请求中
        if (currentSession) {
            requestData.session_id = currentSession;
        } else {
            // 首次聊天，需要指定数据源
            requestData.data_source_id = currentDataSource.id;
        }
        
        // 创建分析过程容器，直接添加到用户消息之后
        const analysisProcessId = `analysis-process-${Date.now()}`;
        const userMessageElement = document.getElementById(userMessageId);
        
        // 创建并添加分析过程容器
        const processContainer = document.createElement('div');
        processContainer.className = 'analysis-process-container';
        processContainer.id = analysisProcessId;
        processContainer.setAttribute('data-expanded', 'true');
        processContainer.setAttribute('data-final-response', '');
        
        // 添加初始思考指示器
        const thinkingIndicator = document.createElement('div');
        thinkingIndicator.className = 'thinking-indicator';
        thinkingIndicator.innerHTML = `<span class="thinking-dots">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>`;
        processContainer.appendChild(thinkingIndicator);
        
        // 将分析过程容器插入到用户消息之后
        if (userMessageElement.nextSibling) {
            chatMessages.insertBefore(processContainer, userMessageElement.nextSibling);
        } else {
            chatMessages.appendChild(processContainer);
        }
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // 创建请求
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP错误 ${response.status}`);
        }
        
        // 读取流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResponse = '';
        let visualizationId = null;
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            // 解码响应数据
            buffer += decoder.decode(value, { stream: true });
            
            // 处理可能同时到达的多个JSON数据包
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // 保留最后一个（可能不完整的）行
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const data = JSON.parse(line);
                    
                    // 处理流式消息
                    processStreamingMessage(data, analysisProcessId);
                    
                    // 保存会话ID
                    if (data.type === 'start' && data.content.session_id) {
                        currentSession = data.content.session_id;
                    }
                    
                    // 记录最终回复和可视化ID
                    if (data.type === 'final') {
                        finalResponse = data.content.response;
                        
                        // 移除思考指示器
                        const thinkingIndicator = processContainer.querySelector('.thinking-indicator');
                        if (thinkingIndicator) {
                            thinkingIndicator.remove();
                        }
                        
                        // 创建折叠/展开按钮
                        if (!processContainer.querySelector('.toggle-process-btn')) {
                            const buttonContainer = document.createElement('div');
                            buttonContainer.className = 'process-button-container';
                            
                            const toggleButton = document.createElement('button');
                            toggleButton.className = 'toggle-process-btn';
                            toggleButton.innerHTML = '收起思考过程';
                            toggleButton.onclick = function() {
                                const isExpanded = processContainer.getAttribute('data-expanded') !== 'false';
                                
                                // 获取所有思考步骤元素
                                const thinkingElements = processContainer.querySelectorAll('.plan-step, .experts-step, .expert-start');
                                
                                // 获取最终结果元素
                                const finalResult = processContainer.querySelector('.final-result');
                                
                                if (isExpanded) {
                                    // 收起思考过程
                                    thinkingElements.forEach(el => {
                                        el.style.display = 'none';
                                    });
                                    toggleButton.innerHTML = '展开思考过程';
                                    processContainer.setAttribute('data-expanded', 'false');
                                } else {
                                    // 展开思考过程
                                    thinkingElements.forEach(el => {
                                        el.style.display = '';
                                    });
                                    toggleButton.innerHTML = '收起思考过程';
                                    processContainer.setAttribute('data-expanded', 'true');
                                }
                            };
                            
                            buttonContainer.appendChild(toggleButton);
                            processContainer.insertBefore(buttonContainer, processContainer.firstChild);
                        }
                        
                        // 更新分析过程容器的data-final-response属性
                        processContainer.setAttribute('data-final-response', finalResponse);
                        
                        if (data.content.visualization_id) {
                            visualizationId = data.content.visualization_id;
                        }
                        
                        // 添加助手的最终回复消息（在分析过程容器之后）
                        const assistantMessageId = addMessage('assistant', finalResponse);
                        
                        // 将分析过程容器移动到新的助手消息之前
                        const assistantMessageElement = document.getElementById(assistantMessageId);
                        if (assistantMessageElement) {
                            chatMessages.insertBefore(processContainer, assistantMessageElement);
                        }
                    }
                } catch (e) {
                    console.error('解析流式响应失败:', e, line);
                }
            }
        }
        
    } catch (error) {
        console.error('发送消息失败:', error);
        // 在用户消息后添加错误消息
        addMessage('system', `抱歉，我遇到了一些问题: ${error.message}`);
    }
}

/**
 * 处理流式消息
 * @param {Object} data - 消息数据
 * @param {string} analysisProcessId - 分析过程容器ID
 */
function processStreamingMessage(data, analysisProcessId) {
    const processContainer = document.getElementById(analysisProcessId);
    if (!processContainer) return;
    
    // 思考过程显示在上方，最终结果显示在下方
    switch (data.type) {
        case 'thinking':
            // 思考过程已经通过思考指示器表示，不需要额外处理
            break;
            
        case 'plan':
            // 查找容器中是否已有计划步骤
            let planStepDiv = processContainer.querySelector('.plan-step');
            
            if (planStepDiv) {
                // 已存在，更新内容
                const planContentDiv = planStepDiv.querySelector('.plan-content-wrapper');
                if (planContentDiv) {
                    // 确保使用格式化的内容更新
                    planContentDiv.innerHTML = formatPlanContent(data.content, true);
                }
            } else {
                // 不存在，创建新元素
                planStepDiv = document.createElement('div');
                planStepDiv.className = 'plan-step';
                planStepDiv.innerHTML = `
                    <span class="step-icon">📋</span>
                    <strong>分析计划</strong>
                    <div class="plan-content-wrapper">
                        ${formatPlanContent(data.content, true)}
                    </div>
                `;
                processContainer.appendChild(planStepDiv);
            }
            break;
            
        case 'experts':
            // 查找容器中是否已有专家团队步骤
            let expertsStepDiv = processContainer.querySelector('.experts-step');
            const expertsHTML = `<span class="step-icon">👩‍💼</span> <strong>专家团队</strong><div class="experts-list">${data.content.map(expert => `<span class="expert-badge">${expert}</span>`).join(' ')}</div>`;
            
            if (expertsStepDiv) {
                // 已存在，更新内容
                expertsStepDiv.innerHTML = expertsHTML;
            } else {
                // 不存在，创建新元素
                expertsStepDiv = document.createElement('div');
                expertsStepDiv.className = 'experts-step';
                expertsStepDiv.innerHTML = expertsHTML;
                processContainer.appendChild(expertsStepDiv);
            }
            break;
            
        case 'expert_start':
            const { expert_name, step, total_steps } = data.content;
            // 检查是否已存在该专家步骤
            let expertDiv = processContainer.querySelector(`#expert-${step}`);
            
            if (!expertDiv) {
                expertDiv = document.createElement('div');
                expertDiv.className = 'expert-start';
                expertDiv.id = `expert-${step}`;
                
                // 检查expert_name是否已经包含"专家"字样，避免重复
                const displayName = expert_name.endsWith('专家') ? expert_name : `${expert_name}专家`;
                
                expertDiv.innerHTML = `
                    <span class="step-icon">⚙️</span> 
                    <strong>步骤 ${step}/${total_steps}: ${displayName}</strong>
                    <div class="expert-progress">
                        <div class="progress-bar in-progress"></div>
                        <span class="status-text">处理中...</span>
                    </div>
                `;
                processContainer.appendChild(expertDiv);
            }
            break;
            
        case 'intermediate':
            const expertStepDiv = processContainer.querySelector(`#expert-${data.content.step}`);
            if (expertStepDiv) {
                // 更新专家进度状态为已完成
                const progressBar = expertStepDiv.querySelector('.progress-bar');
                const statusText = expertStepDiv.querySelector('.status-text');
                if (progressBar) progressBar.className = 'progress-bar completed';
                if (statusText) statusText.textContent = '已完成';
                
                // 添加专家结果预览（如果有且不存在）
                if (data.content.result && data.content.result.response && !expertStepDiv.querySelector('.result-preview')) {
                    const resultPreview = document.createElement('div');
                    resultPreview.className = 'result-preview';
                    resultPreview.textContent = truncateText(data.content.result.response, 150);
                    expertStepDiv.appendChild(resultPreview);
                }
                
                // 添加可视化预览（如果有且不存在）
                if (data.content.visualization && !expertStepDiv.querySelector('.visualization-preview')) {
                    // 创建可视化预览容器
                    const visualizationPreview = document.createElement('div');
                    visualizationPreview.className = 'visualization-preview';
                    
                    // 创建图像元素
                    const imgElement = document.createElement('img');
                    imgElement.className = 'visualization-image';
                    
                    // 确保base64字符串格式正确
                    const imageData = data.content.visualization;
                    if (!imageData.startsWith('data:image')) {
                        imgElement.src = `data:image/png;base64,${imageData}`;
                    } else {
                        imgElement.src = imageData;
                    }
                    
                    visualizationPreview.appendChild(imgElement);
                    expertStepDiv.appendChild(visualizationPreview);
                }
            }
            
            // *** 新增功能：在聊天框中显示专家结果 ***
            if (data.content.result) {
                addExpertResultMessage(data.content);
            }
            break;
            
        case 'final':
            // 当接收到最终回答时，在分析过程下方添加一个最终结果区域
            if (!processContainer.querySelector('.final-result')) {
                const finalResult = document.createElement('div');
                finalResult.className = 'final-result';
                finalResult.innerHTML = `
                    <div class="result-divider"></div>
                    <div class="result-header">
                        <span class="result-icon">✅</span>
                        <strong>分析结果</strong>
                    </div>
                    <div class="result-content">${data.content.response}</div>
                `;
                processContainer.appendChild(finalResult);
            }
            break;
    }
}

/**
 * 在聊天框中添加专家结果消息
 * @param {Object} expertData - 专家数据
 */
function addExpertResultMessage(expertData) {
    const { expert_name, result, visualization, step, total_steps, source } = expertData;
    
    // 生成专家消息ID
    const expertMessageId = `expert-msg-${step}-${Date.now()}`;
    
    // 创建专家消息元素
    const messageElement = document.createElement('div');
    messageElement.className = 'message expert';
    messageElement.id = expertMessageId;
    
    // 根据专家来源确定类型
    let expertType = 'default';
    if (source) {
        expertType = source;
    } else {
        // 从专家名称推断类型
        const name = expert_name.toLowerCase();
        if (name.includes('知识') || name.includes('行业')) {
            expertType = 'knowledge';
        } else if (name.includes('sql') || name.includes('数据库')) {
            expertType = 'sql';
        } else if (name.includes('数据分析') || name.includes('分析')) {
            expertType = 'data';
        } else if (name.includes('可视化') || name.includes('图表')) {
            expertType = 'visualization';
        }
    }
    
    // 设置专家类型数据属性
    messageElement.setAttribute('data-expert-type', expertType);
    
    // 创建消息内容
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content expert-content';
    
    // 检查expert_name是否已经包含"专家"字样，避免重复
    const displayName = expert_name.endsWith('专家') ? expert_name : `${expert_name}专家`;
    
    // 根据专家类型选择图标
    const expertIcons = {
        'knowledge': '📚',
        'sql': '🔍',
        'data': '📊',
        'visualization': '📈',
        'default': '🎯'
    };
    const expertIcon = expertIcons[expertType] || expertIcons['default'];
    
    // 构建专家结果内容
    let expertContent = `<div class="expert-header">
        <span class="expert-icon">${expertIcon}</span>
        <strong>${displayName}</strong>
        <span class="expert-step-badge">步骤 ${step}/${total_steps}</span>
    </div>`;
    
    // 添加专家的回答内容
    if (result) {
        let responseText = '';
        if (typeof result === 'string') {
            responseText = result;
        } else if (result.response) {
            responseText = result.response;
        } else if (result.description) {
            responseText = result.description;
        }
        
        if (responseText) {
            // 截断过长的文本
            const truncatedText = truncateText(responseText, 500);
            expertContent += `<div class="expert-response">${truncatedText}</div>`;
            
            // 如果文本被截断了，添加展开按钮
            if (responseText.length > 500) {
                expertContent += `<button class="expand-btn" onclick="expandExpertResponse('${expertMessageId}', '${encodeURIComponent(responseText)}')">查看完整回答</button>`;
            }
        }
    }
    
    // 添加可视化内容（如果有）
    if (visualization) {
        expertContent += `<div class="expert-visualization">
            <img src="data:image/png;base64,${visualization}" alt="可视化图表" class="expert-viz-image">
        </div>`;
    }
    
    contentElement.innerHTML = expertContent;
    messageElement.appendChild(contentElement);
    
    // 将专家消息插入到聊天框中
    chatMessages.appendChild(messageElement);
    
    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * 展开专家回答的完整内容
 * @param {string} messageId - 消息ID
 * @param {string} fullText - 完整文本（URL编码）
 */
function expandExpertResponse(messageId, fullText) {
    const messageElement = document.getElementById(messageId);
    if (!messageElement) return;
    
    const responseDiv = messageElement.querySelector('.expert-response');
    const expandBtn = messageElement.querySelector('.expand-btn');
    
    if (responseDiv && expandBtn) {
        // 解码并显示完整文本
        const decodedText = decodeURIComponent(fullText);
        responseDiv.textContent = decodedText;
        
        // 移除展开按钮
        expandBtn.remove();
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

/**
 * 格式化分析计划内容
 * @param {string} planContent - 计划内容文本
 * @param {boolean} contentOnly - 是否只返回内容部分而不包含外层HTML
 * @returns {string} 格式化后的HTML
 */
function formatPlanContent(planContent, contentOnly = false) {
    if (!planContent) return '';
    
    // 提取执行计划部分
    const planLines = planContent.split('\n').filter(line => line.trim() !== '');
    let formattedContent = '';
    
    if (planLines.length > 0) {
        // 检查是否有执行计划行
        const planLineIndex = planLines.findIndex(line => line.includes('执行计划:'));
        
        if (planLineIndex !== -1) {
            // 提取执行计划部分
            const planLine = planLines[planLineIndex];
            formattedContent += `<div class="plan-line">${planLine}</div>`;
            
            // 添加后续步骤描述
            const steps = [];
            for (let i = planLineIndex + 1; i < planLines.length; i++) {
                const line = planLines[i].trim();
                if (line.match(/^\d+\.\s/) || line.match(/^- /)) {
                    steps.push(`<div class="plan-step-item">${line}</div>`);
                }
            }
            
            if (steps.length > 0) {
                formattedContent += `<div class="plan-steps">${steps.join('')}</div>`;
            }
        } else {
            // 如果没有找到执行计划行，直接显示所有内容
            formattedContent = planLines.map(line => `<div class="plan-line">${line}</div>`).join('');
        }
    }
    
    return formattedContent;
}

/**
 * 截断文本
 * @param {string} text - 原文本
 * @param {number} maxLength - 最大长度
 * @returns {string} 截断后的文本
 */
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

/**
 * 添加消息到聊天框
 * @param {string} role - 消息角色 (user, assistant, system)
 * @param {string} content - 消息内容
 * @returns {string} 消息DOM元素ID
 */
function addMessage(role, content) {
    const messageId = `msg-${Date.now()}`;
    
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;
    messageElement.id = messageId;
    
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    
    contentElement.textContent = content;
    
    messageElement.appendChild(contentElement);
    chatMessages.appendChild(messageElement);
    
    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

/**
 * 更新消息内容
 * @param {string} messageId - 消息ID
 * @param {string} role - 消息角色
 * @param {string} content - 新消息内容
 */
function updateMessage(messageId, role, content) {
    const messageElement = document.getElementById(messageId);
    if (!messageElement) return;
    
    // 更新消息内容
    const contentElement = messageElement.querySelector('.message-content');
    contentElement.textContent = content;
    
    // 更新消息角色类
    messageElement.className = `message ${role}`;
    
    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * 显示成功消息
 * @param {string} message - 成功消息内容
 */
function showSuccess(message) {
    alert(message); // 简化版本，实际项目中可以使用toast或其他UI组件
}

/**
 * 显示错误消息
 * @param {string} message - 错误消息内容
 */
function showError(message) {
    alert(`错误: ${message}`); // 简化版本，实际项目中可以使用toast或其他UI组件
}

/**
 * 启动新的会话（清除历史对话）
 */
async function startNewSession() {
    if (!currentDataSource) {
        showError('请先选择一个数据源');
        return;
    }
    
    try {
        // 禁用按钮，防止重复点击
        newSessionButton.disabled = true;
        
        // 添加系统消息表示正在创建新会话
        const loadingId = addMessage('system', '正在创建新会话...');
        
        // 调用后端API创建新会话
        const response = await fetch('/api/chat/new', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data_source_id: currentDataSource.id
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '创建新会话失败');
        }
        
        const data = await response.json();
        
        // 更新当前会话ID
        currentSession = data.session_id;
        
        // 清空聊天消息
        chatMessages.innerHTML = '';
        
        // 添加新会话欢迎消息
        addMessage('system', `已创建新会话。您现在正在使用"${currentDataSource.name}"数据集，请问有什么我可以帮您分析的吗？`);
        
        // 重新启用按钮
        newSessionButton.disabled = false;
        
    } catch (error) {
        console.error('创建新会话失败:', error);
        showError(`创建新会话失败: ${error.message}`);
        newSessionButton.disabled = false;
    }
} 