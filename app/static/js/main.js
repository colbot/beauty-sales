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
const visualizationContainer = document.getElementById('visualization-container');

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
    
    // 清空可视化区域
    visualizationContainer.innerHTML = `
        <div class="empty-state">
            <p>数据可视化将在这里显示</p>
            <p>通过聊天询问数据分析问题，助手将在需要时自动生成图表</p>
        </div>
    `;
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
    addMessage('user', message);
    
    // 清空输入框
    messageInput.value = '';
    
    // 显示思考中消息
    const thinkingId = addMessage('assistant', '思考中...');
    
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
        
        // 使用流式API发送消息
        await streamMessage(requestData, thinkingId);
    } catch (error) {
        console.error('发送消息失败:', error);
        updateMessage(thinkingId, 'assistant', `抱歉，我遇到了一些问题: ${error.message}`);
    }
}

/**
 * 使用流式API发送消息并处理响应
 * @param {Object} requestData - 请求数据
 * @param {string} messageId - 消息ID
 */
async function streamMessage(requestData, messageId) {
    try {
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
        
        // 创建用于实时显示分析过程的容器
        const analysisProcessId = `analysis-process-${Date.now()}`;
        appendAnalysisProcessContainer(messageId, analysisProcessId);
        
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
                    processStreamingMessage(data, messageId, analysisProcessId);
        
        // 保存会话ID
                    if (data.type === 'start' && data.content.session_id) {
                        currentSession = data.content.session_id;
                    }
                    
                    // 记录最终回复和可视化ID
                    if (data.type === 'final') {
                        finalResponse = data.content.response;
                        
                        if (data.content.visualization_id) {
                            visualizationId = data.content.visualization_id;
                        }
                    }
                } catch (e) {
                    console.error('解析流式响应失败:', e, line);
                }
            }
        }
        
        // 更新最终助手回复
        updateMessage(messageId, 'assistant', finalResponse);
        
        // 如果有可视化，显示图表
        if (visualizationId) {
            loadVisualization(visualizationId);
        }
    } catch (error) {
        console.error('流式处理失败:', error);
        throw error;
    }
}

/**
 * 处理流式消息
 * @param {Object} data - 消息数据
 * @param {string} messageId - 消息DOM元素ID
 * @param {string} analysisProcessId - 分析过程容器ID
 */
function processStreamingMessage(data, messageId, analysisProcessId) {
    const processContainer = document.getElementById(analysisProcessId);
    if (!processContainer) return;
    
    switch (data.type) {
        case 'thinking':
            // 思考中...消息只显示一次
            if (!processContainer.querySelector('.thinking-step')) {
                const thinkingDiv = document.createElement('div');
                thinkingDiv.className = 'thinking-step';
                thinkingDiv.innerHTML = `<span class="step-icon">🤔</span> ${data.content}`;
                processContainer.appendChild(thinkingDiv);
            }
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
            }
            break;
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
 * 加载可视化图表
 * @param {number} visualizationId - 可视化ID
 */
async function loadVisualization(visualizationId) {
    try {
        const response = await fetch(`/api/visualization/${visualizationId}`);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        
        const visualization = await response.json();
        
        // 清空可视化容器
        visualizationContainer.innerHTML = '';
        
        // 创建图表标题
        const titleElement = document.createElement('h3');
        titleElement.textContent = visualization.chart_title;
        visualizationContainer.appendChild(titleElement);
        
        // 解析图表数据
        let chartData;
        try {
            chartData = JSON.parse(visualization.chart_data);
        } catch (e) {
            console.error('解析图表数据失败:', e);
            // 如果不是有效的JSON，可能是直接的base64字符串
            chartData = visualization.chart_data;
        }
        
        console.log('图表类型:', visualization.chart_type);
        console.log('图表数据结构:', typeof chartData);
        
        // 处理不同类型的可视化
        if (visualization.chart_type === "image") {
            // 如果是base64图像，直接显示图像
            let imageData;
            
            // 检查chartData是对象还是字符串
            if (typeof chartData === 'object' && chartData.image) {
                imageData = chartData.image;
                console.log('检测到image属性的对象');
            } else if (typeof chartData === 'string') {
                imageData = chartData;
                console.log('检测到字符串形式的图像数据');
            }
            
            if (imageData) {
                const imgElement = document.createElement('img');
                // 确保base64字符串格式正确
                if (!imageData.startsWith('data:image')) {
                    imgElement.src = `data:image/png;base64,${imageData}`;
                } else {
                    imgElement.src = imageData;
                }
                
                imgElement.style.maxWidth = '100%';
                imgElement.style.height = 'auto';
                imgElement.style.display = 'block';
                imgElement.style.margin = '0 auto';
                imgElement.style.border = '1px solid #ddd';
                imgElement.style.borderRadius = '4px';
                imgElement.style.padding = '4px';
                imgElement.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                imgElement.alt = 'Data Visualization';
                
                imgElement.onload = function() {
                    console.log('图片已成功加载');
                };
                
                imgElement.onerror = function() {
                    console.error('图片加载失败');
                    // 显示错误信息
                    this.style.display = 'none';
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'error-state';
                    errorMsg.textContent = '图表加载失败';
                    visualizationContainer.appendChild(errorMsg);
                };
                
                visualizationContainer.appendChild(imgElement);
                console.log('图像元素已添加到容器中');
            } else {
                throw new Error('无效的图像数据');
            }
        } else if (chartData && (Array.isArray(chartData) || (typeof chartData === 'object' && chartData.data))) {
            // 创建图表容器
            const chartContainer = document.createElement('div');
            chartContainer.id = 'chart-' + Date.now(); // 使用唯一ID避免冲突
            chartContainer.style.width = '100%';
            chartContainer.style.height = '400px';
            visualizationContainer.appendChild(chartContainer);
            
            // 根据图表类型创建不同的图表
            switch (visualization.chart_type) {
                case 'line':
                    createLineChart(chartContainer.id, chartData);
                    break;
                case 'bar':
                    createBarChart(chartContainer.id, chartData);
                    break;
                case 'pie':
                    createPieChart(chartContainer.id, chartData);
                    break;
                case 'scatter':
                    createScatterChart(chartContainer.id, chartData);
                    break;
                default:
                    // 默认使用Plotly自动创建
                    try {
                        const plotData = Array.isArray(chartData) ? chartData : (chartData.data || []);
                        const layout = (typeof chartData === 'object' && chartData.layout) ? chartData.layout : {};
                        Plotly.newPlot(chartContainer.id, plotData, layout);
                    } catch (e) {
                        console.error('Plotly绘图失败:', e);
                        // 如果Plotly失败，尝试显示为图像
                        handleFallbackVisualization(chartData, visualizationContainer);
                    }
            }
        } else {
            // 如果没有有效的图表数据，显示错误信息
            handleFallbackVisualization(chartData, visualizationContainer);
        }
        
        // 如果有描述，添加描述
        if (visualization.chart_description) {
            const descElement = document.createElement('p');
            descElement.className = 'chart-description';
            descElement.textContent = visualization.chart_description;
            visualizationContainer.appendChild(descElement);
        }
    } catch (error) {
        console.error('加载可视化失败:', error);
        visualizationContainer.innerHTML = `
            <div class="error-state">
                <p>加载图表失败</p>
                <p>错误: ${error.message}</p>
            </div>
        `;
    }
}

/**
 * 处理可视化展示失败时的回退方案
 * @param {any} data - 可视化数据
 * @param {HTMLElement} container - 容器元素
 */
function handleFallbackVisualization(data, container) {
    // 尝试将数据显示为图像或文本
    if (typeof data === 'string' && data.length > 100) {
        // 可能是base64字符串
        try {
            const imgElement = document.createElement('img');
            imgElement.src = `data:image/png;base64,${data}`;
            imgElement.style.maxWidth = '100%';
            imgElement.style.height = 'auto';
            container.appendChild(imgElement);
            return;
        } catch (e) {
            console.warn('无法作为图像显示:', e);
        }
    }
    
    // 显示数据的原始表示
    const dataDisplay = document.createElement('pre');
    dataDisplay.className = 'data-display';
    dataDisplay.textContent = typeof data === 'object' ? JSON.stringify(data, null, 2) : String(data);
    container.appendChild(dataDisplay);
}

/**
 * 创建折线图
 * @param {string} containerId - 图表容器ID
 * @param {Object} chartData - 图表数据
 */
function createLineChart(containerId, chartData) {
    const data = chartData.data || [];
    const layout = chartData.layout || {};
    
    // 使用Plotly创建折线图
    Plotly.newPlot(containerId, data, layout);
}

/**
 * 创建柱状图
 * @param {string} containerId - 图表容器ID
 * @param {Object} chartData - 图表数据
 */
function createBarChart(containerId, chartData) {
    const data = chartData.data || [];
    const layout = chartData.layout || {};
    
    // 使用Plotly创建柱状图
    Plotly.newPlot(containerId, data, layout);
}

/**
 * 创建饼图
 * @param {string} containerId - 图表容器ID
 * @param {Object} chartData - 图表数据
 */
function createPieChart(containerId, chartData) {
    const data = chartData.data || [];
    const layout = chartData.layout || {};
    
    // 使用Plotly创建饼图
    Plotly.newPlot(containerId, data, layout);
}

/**
 * 创建散点图
 * @param {string} containerId - 图表容器ID
 * @param {Object} chartData - 图表数据
 */
function createScatterChart(containerId, chartData) {
    const data = chartData.data || [];
    const layout = chartData.layout || {};
    
    // 使用Plotly创建散点图
    Plotly.newPlot(containerId, data, layout);
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
        
        // 清空可视化区域
        visualizationContainer.innerHTML = `
            <div class="empty-state">
                <p>数据可视化将在这里显示</p>
                <p>通过聊天询问数据分析问题，助手将在需要时自动生成图表</p>
            </div>
        `;
        
        // 重新启用按钮
        newSessionButton.disabled = false;
        
    } catch (error) {
        console.error('创建新会话失败:', error);
        showError(`创建新会话失败: ${error.message}`);
        newSessionButton.disabled = false;
    }
}

/**
 * 在消息下面添加分析过程容器
 * @param {string} messageId - 消息ID
 * @param {string} processId - 分析过程容器ID
 */
function appendAnalysisProcessContainer(messageId, processId) {
    const messageElement = document.getElementById(messageId);
    if (!messageElement) return;
    
    // 创建分析过程容器
    const processContainer = document.createElement('div');
    processContainer.className = 'analysis-process-container';
    processContainer.id = processId;
    
    // 添加到消息元素后面
    messageElement.appendChild(processContainer);
} 