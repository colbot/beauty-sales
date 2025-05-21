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
        
        // 发送消息到服务器
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '发送消息失败');
        }
        
        const data = await response.json();
        
        // 保存会话ID
        currentSession = data.session_id;
        
        // 更新助手回复
        updateMessage(thinkingId, 'assistant', data.response);
        
        // 如果有可视化，显示图表
        if (data.visualization_id) {
            loadVisualization(data.visualization_id);
        }
    } catch (error) {
        console.error('发送消息失败:', error);
        updateMessage(thinkingId, 'assistant', `抱歉，我遇到了一些问题: ${error.message}`);
    }
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
        const visualization = await response.json();
        
        // 清空可视化容器
        visualizationContainer.innerHTML = '';
        
        // 创建图表标题
        const titleElement = document.createElement('h3');
        titleElement.textContent = visualization.chart_title;
        visualizationContainer.appendChild(titleElement);
        
        // 创建图表容器
        const chartContainer = document.createElement('div');
        chartContainer.id = 'chart';
        chartContainer.style.width = '100%';
        chartContainer.style.height = '400px';
        visualizationContainer.appendChild(chartContainer);
        
        // 解析图表数据
        const chartData = JSON.parse(visualization.chart_data);
        
        // 根据图表类型创建不同的图表
        switch (visualization.chart_type) {
            case 'line':
                createLineChart('chart', chartData);
                break;
            case 'bar':
                createBarChart('chart', chartData);
                break;
            case 'pie':
                createPieChart('chart', chartData);
                break;
            case 'scatter':
                createScatterChart('chart', chartData);
                break;
            default:
                // 默认使用Plotly自动创建
                Plotly.newPlot('chart', chartData.data, chartData.layout || {});
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