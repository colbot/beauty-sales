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
                        let lastThinkingIndicator = processContainer.querySelector('.thinking-indicator');
                        if (lastThinkingIndicator) {
                            lastThinkingIndicator.remove();
                        }
                        
                        // 创建折叠/展开按钮
                        if (!processContainer.querySelector('.toggle-process-btn')) {
                            const buttonContainer = document.createElement('div');
                            buttonContainer.className = 'process-button-container';
                            
                            const toggleButton = document.createElement('button');
                            toggleButton.className = 'toggle-process-btn';
                            toggleButton.textContent = '收起分析过程';
                            toggleButton.onclick = function() {
                                const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
                                const isCurrentlyVisible = toggleButton.getAttribute('data-collapsed') !== 'true';
                                
                                processSteps.forEach(step => {
                                    step.style.display = isCurrentlyVisible ? 'none' : 'block';
                                });
                                
                                if (isCurrentlyVisible) {
                                    // 当前可见，点击后隐藏
                                    toggleButton.textContent = "展开分析过程";
                                    toggleButton.setAttribute('data-collapsed', 'true');
                                } else {
                                    // 当前隐藏，点击后显示
                                    toggleButton.textContent = "收起分析过程";
                                    toggleButton.setAttribute('data-collapsed', 'false');
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
                        
                        // 改进可视化数据处理
                        let visualizationBase64 = null;
                        
                        // 多重检查可视化数据来源
                        if (data.content.visualization) {
                            visualizationBase64 = data.content.visualization;
                            console.log("Found visualization in resultContent.visualization");
                        } else if (data.content.visualization_result && data.content.visualization_result.visualization) {
                            visualizationBase64 = data.content.visualization_result.visualization;
                            console.log("Found visualization in resultContent.visualization_result.visualization");
                        } else if (data.content.visualization_result && data.content.visualization_result.image_data) {
                            // 兼容不同的字段名
                            visualizationBase64 = data.content.visualization_result.image_data;
                            console.log("Found visualization in resultContent.visualization_result.image_data");
                        } else {
                            console.log("No visualization data found");
                            // 打印可用的字段以便调试
                            console.log("Available fields:", Object.keys(data.content));
                            if (data.content.visualization_result) {
                                console.log("visualization_result fields:", Object.keys(data.content.visualization_result));
                            }
                        }
                        
                        if (visualizationBase64) {
                            const imgElement = document.createElement('img');
                            imgElement.src = `data:image/png;base64,${visualizationBase64}`;
                            imgElement.style.maxWidth = '100%';
                            imgElement.style.height = 'auto';
                            imgElement.style.border = '1px solid #ddd';
                            imgElement.style.borderRadius = '8px';
                            imgElement.style.marginTop = '15px';
                            imgElement.style.cursor = 'pointer';
                            
                            // 添加点击放大功能
                            imgElement.onclick = function() {
                                const modal = document.createElement('div');
                                modal.style.cssText = `
                                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                                    background: rgba(0,0,0,0.8); display: flex; justify-content: center;
                                    align-items: center; z-index: 1000; cursor: pointer;
                                `;
                                
                                const modalImg = document.createElement('img');
                                modalImg.src = imgElement.src;
                                modalImg.style.maxWidth = '90%';
                                modalImg.style.maxHeight = '90%';
                                modalImg.style.objectFit = 'contain';
                                
                                modal.appendChild(modalImg);
                                document.body.appendChild(modal);
                                
                                modal.onclick = function() {
                                    document.body.removeChild(modal);
                                };
                            };
                            
                            processContainer.appendChild(imgElement);
                            console.log("Visualization image added successfully");
                        } else {
                            console.log("No visualization data to display");
                        }
                        
                        // 将按钮容器和最终结果添加到分析过程容器
                        processContainer.appendChild(buttonContainer);
                        processContainer.appendChild(processContainer.lastChild);
                        
                        // 确保所有分析过程步骤都是可见的（默认展开状态）
                        const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
                        processSteps.forEach(step => {
                            step.style.display = 'block';  // 确保所有步骤都显示
                        });
                        
                        // 设置按钮初始状态为展开（false表示未收起）
                        toggleButton.setAttribute('data-collapsed', 'false');
                    }
                } catch (e) {
                    console.error('解析流式响应失败:', e, line);
                }
            }
        }
        
    } catch (error) {
        console.error('发送消息失败:', error);
        
        // 查找最新的分析过程容器，避免直接使用可能未定义的analysisProcessId
        const processContainers = document.querySelectorAll('.analysis-process-container');
        const processContainer = processContainers.length > 0 ? processContainers[processContainers.length - 1] : null;
        
        if (processContainer) {
            let lastThinkingIndicator = processContainer.querySelector('.thinking-indicator');
            if (lastThinkingIndicator) {
                lastThinkingIndicator.remove();
            }
            
            // 检查是否有专家结果，如果有则生成总结
            const expertResults = processContainer.querySelectorAll('.expert-start');
            if (expertResults.length > 0) {
                // 生成分析总结
                const summaryContent = generateAnalysisSummary(expertResults, message);
                addMessage('assistant', summaryContent);
                
                // 保留分析过程容器，让用户通过按钮控制显示/隐藏
                // processContainer.style.display = 'none';  // 注释掉这行，让分析过程保持可见
                
                // 如果还没有最终结果样式，为错误情况添加基本的结果样式
                if (!processContainer.classList.contains('has-final-result')) {
                    processContainer.classList.add('has-final-result');
                    
                    // 创建折叠/展开按钮
                    const toggleButton = document.createElement("button");
                    toggleButton.className = "toggle-process-btn";
                    toggleButton.textContent = "收起分析过程";
                    toggleButton.onclick = function() {
                        const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
                        const isCurrentlyVisible = toggleButton.getAttribute('data-collapsed') !== 'true';
                        
                        processSteps.forEach(step => {
                            step.style.display = isCurrentlyVisible ? 'none' : 'block';
                        });
                        
                        if (isCurrentlyVisible) {
                            toggleButton.textContent = "展开分析过程";
                            toggleButton.setAttribute('data-collapsed', 'true');
                        } else {
                            toggleButton.textContent = "收起分析过程";
                            toggleButton.setAttribute('data-collapsed', 'false');
                        }
                    };
                    
                    const buttonContainer = document.createElement("div");
                    buttonContainer.className = "process-button-container";
                    buttonContainer.appendChild(toggleButton);
                    processContainer.appendChild(buttonContainer);
                    
                    // 确保分析过程步骤可见
                    const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
                    processSteps.forEach(step => {
                        step.style.display = 'block';
                    });
                    
                    toggleButton.setAttribute('data-collapsed', 'false');
                }
            } else {
                // 如果没有任何分析过程，显示友好的提示
                addMessage('system', '分析过程中断，请重新尝试您的问题。您可以尝试简化问题或检查网络连接。');
            }
        } else {
            // 如果没有分析过程容器，显示友好的提示
            addMessage('system', '连接中断，请重新尝试您的问题。');
        }
    }
}

/**
 * 处理流式消息
 * @param {Object} data - 消息数据
 * @param {string} analysisProcessId - 分析过程容器ID
 */
function processStreamingMessage(data, analysisProcessId) {
    // 处理流式消息
    console.log("Received streaming message:", data);

    if (!data) return;

    // 如果是最终结果
    if (data.type === "final") {
        let resultContent = data.content;
        let processContainer = document.getElementById(analysisProcessId);
        
        if (processContainer) {
            // 添加最终结果区域，但保留分析过程
            processContainer.classList.add("has-final-result");
            
            // 创建折叠/展开按钮
            const toggleButton = document.createElement("button");
            toggleButton.className = "toggle-process-btn";
            toggleButton.textContent = "收起分析过程";  // 默认是展开状态，所以显示"收起"
            toggleButton.onclick = function() {
                const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
                const isCurrentlyVisible = toggleButton.getAttribute('data-collapsed') !== 'true';
                
                processSteps.forEach(step => {
                    step.style.display = isCurrentlyVisible ? 'none' : 'block';
                });
                
                if (isCurrentlyVisible) {
                    // 当前可见，点击后隐藏
                    toggleButton.textContent = "展开分析过程";
                    toggleButton.setAttribute('data-collapsed', 'true');
                } else {
                    // 当前隐藏，点击后显示
                    toggleButton.textContent = "收起分析过程";
                    toggleButton.setAttribute('data-collapsed', 'false');
                }
            };
            
            // 创建按钮容器
            const buttonContainer = document.createElement("div");
            buttonContainer.className = "process-button-container";
            buttonContainer.appendChild(toggleButton);
            
            // 创建最终结果区域
            const finalResultDiv = document.createElement("div");
            finalResultDiv.className = "final-result";
            
            // 创建结果标题
            const resultHeader = document.createElement("div");
            resultHeader.className = "result-header";
            resultHeader.innerHTML = '<span class="result-icon">✨</span> 分析结果';
            
            // 创建分隔线
            const resultDivider = document.createElement("div");
            resultDivider.className = "result-divider";
            
            // 创建结果内容
            const resultContentDiv = document.createElement("div");
            resultContentDiv.className = "result-content";
            
            // 使用markdown解析器渲染内容
            const markdownContent = parseMarkdown(resultContent.response || "分析完成");
            resultContentDiv.innerHTML = markdownContent;
            
            // 组合最终结果
            finalResultDiv.appendChild(resultHeader);
            finalResultDiv.appendChild(resultDivider);
            finalResultDiv.appendChild(resultContentDiv);
            
            // 改进可视化数据处理
            let visualizationBase64 = null;
            
            // 多重检查可视化数据来源
            if (resultContent.visualization) {
                visualizationBase64 = resultContent.visualization;
                console.log("Found visualization in resultContent.visualization");
            } else if (resultContent.visualization_result && resultContent.visualization_result.visualization) {
                visualizationBase64 = resultContent.visualization_result.visualization;
                console.log("Found visualization in resultContent.visualization_result.visualization");
            } else if (resultContent.visualization_result && resultContent.visualization_result.image_data) {
                // 兼容不同的字段名
                visualizationBase64 = resultContent.visualization_result.image_data;
                console.log("Found visualization in resultContent.visualization_result.image_data");
            } else {
                console.log("No visualization data found");
                // 打印可用的字段以便调试
                console.log("Available fields:", Object.keys(resultContent));
                if (resultContent.visualization_result) {
                    console.log("visualization_result fields:", Object.keys(resultContent.visualization_result));
                }
            }
            
            if (visualizationBase64) {
                const imgElement = document.createElement('img');
                imgElement.src = `data:image/png;base64,${visualizationBase64}`;
                imgElement.style.maxWidth = '100%';
                imgElement.style.height = 'auto';
                imgElement.style.border = '1px solid #ddd';
                imgElement.style.borderRadius = '8px';
                imgElement.style.marginTop = '15px';
                imgElement.style.cursor = 'pointer';
                
                // 添加点击放大功能
                imgElement.onclick = function() {
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                        background: rgba(0,0,0,0.8); display: flex; justify-content: center;
                        align-items: center; z-index: 1000; cursor: pointer;
                    `;
                    
                    const modalImg = document.createElement('img');
                    modalImg.src = imgElement.src;
                    modalImg.style.maxWidth = '90%';
                    modalImg.style.maxHeight = '90%';
                    modalImg.style.objectFit = 'contain';
                    
                    modal.appendChild(modalImg);
                    document.body.appendChild(modal);
                    
                    modal.onclick = function() {
                        document.body.removeChild(modal);
                    };
                };
                
                finalResultDiv.appendChild(imgElement);
                console.log("Visualization image added successfully");
            } else {
                console.log("No visualization data to display");
            }
            
            // 将按钮容器和最终结果添加到分析过程容器
            processContainer.appendChild(buttonContainer);
            processContainer.appendChild(finalResultDiv);

            // 确保所有分析过程步骤都是可见的（默认展开状态）
            const processSteps = processContainer.querySelectorAll('.thinking-step, .plan-step, .experts-step, .expert-start');
            processSteps.forEach(step => {
                step.style.display = 'block';  // 确保所有步骤都显示
            });
            
            // 设置按钮初始状态为展开（false表示未收起）
            toggleButton.setAttribute('data-collapsed', 'false');
        }

        // 添加完整的助手消息
        addMessage('assistant', resultContent.response);
    }
    // 如果是思考步骤
    else if (data.type === "thinking") {
        // 如果分析过程容器不存在，则创建一个
        let processContainer = document.getElementById(analysisProcessId);
        if (!processContainer) {
            processContainer = document.createElement("div");
            processContainer.className = "analysis-process-container";
            processContainer.id = analysisProcessId;
            document.getElementById("chat-messages").appendChild(processContainer);
        }
        
        // 查找或创建thinking-step元素
        let thinkingStep = processContainer.querySelector('.thinking-step');
        if (!thinkingStep) {
            thinkingStep = document.createElement("div");
            thinkingStep.className = "thinking-step";
            thinkingStep.innerHTML = '<span class="step-icon">🧠</span> <strong>思考中</strong>';
            processContainer.appendChild(thinkingStep);
        }
        
        // 创建或更新临时思考消息
        let tempThinking = processContainer.querySelector('.temporary-thinking');
        if (!tempThinking) {
            tempThinking = document.createElement("div");
            tempThinking.className = "temporary-thinking";
            thinkingStep.appendChild(tempThinking);
        }
        
        tempThinking.textContent = data.content || "正在思考...";
    }
    // 如果是计划步骤
    else if (data.type === "plan") {
        let processContainer = document.getElementById(analysisProcessId);
    if (!processContainer) return;
    
        // 移除thinking-indicator如果存在
        let lastThinkingIndicator = processContainer.querySelector('.thinking-indicator');
        if (lastThinkingIndicator) {
            lastThinkingIndicator.remove();
        }
        
        // 移除临时思考消息
        const tempThinking = processContainer.querySelector('.temporary-thinking');
        if (tempThinking) {
            tempThinking.remove();
        }
        
        // 查找或创建plan-step元素
        let planStep = processContainer.querySelector('.plan-step');
        if (!planStep) {
            planStep = document.createElement("div");
            planStep.className = "plan-step";
            planStep.innerHTML = '<span class="step-icon">📋</span> <strong>分析计划</strong>';
            processContainer.appendChild(planStep);
            
            // 创建计划内容包装器
            const planContentWrapper = document.createElement("div");
            planContentWrapper.className = "plan-content-wrapper";
            planStep.appendChild(planContentWrapper);
        }
        
        // 格式化并显示计划内容
        const planContentWrapper = planStep.querySelector('.plan-content-wrapper');
        if (planContentWrapper) {
            planContentWrapper.innerHTML = formatPlanContent(data.content);
        }
    }
    // 如果是专家步骤
    else if (data.type === "experts") {
        let processContainer = document.getElementById(analysisProcessId);
        if (!processContainer) return;
        
        // 查找或创建experts-step元素
        let expertsStep = processContainer.querySelector('.experts-step');
        if (!expertsStep) {
            expertsStep = document.createElement("div");
            expertsStep.className = "experts-step";
            expertsStep.innerHTML = '<span class="step-icon">👥</span> <strong>专家团队</strong>';
            processContainer.appendChild(expertsStep);
            
            // 创建专家列表
            const expertsList = document.createElement("div");
            expertsList.className = "experts-list";
            expertsStep.appendChild(expertsList);
        }
        
        // 显示专家列表
        const expertsList = expertsStep.querySelector('.experts-list');
        if (expertsList && Array.isArray(data.content)) {
            expertsList.innerHTML = '';  // 清空现有内容
            
            data.content.forEach(expertName => {
                const expertBadge = document.createElement("span");
                expertBadge.className = "expert-badge";
                expertBadge.textContent = expertName;
                expertsList.appendChild(expertBadge);
            });
        }
    }
    // 如果是专家开始工作
    else if (data.type === "expert_start") {
        let processContainer = document.getElementById(analysisProcessId);
        if (!processContainer) return;
        
        const expertData = data.content;
        if (!expertData) return;
        
        // 创建专家开始元素
        const expertStart = document.createElement("div");
        expertStart.className = "expert-start";
        expertStart.setAttribute("data-expert-type", expertData.expert_type);
        
        // 创建专家头部
        const expertHeader = document.createElement("div");
        expertHeader.innerHTML = `<span class="step-icon">🔍</span> <strong>${expertData.expert_name}</strong> <span class="expert-step-badge">步骤 ${expertData.step}/${expertData.total_steps}</span>`;
        
        // 创建进度条
        const expertProgress = document.createElement("div");
        expertProgress.className = "expert-progress";
        
        const progressBar = document.createElement("div");
        progressBar.className = "progress-bar in-progress";
        
        const statusText = document.createElement("span");
        statusText.className = "status-text";
        statusText.textContent = "处理中...";
        
        expertProgress.appendChild(progressBar);
        expertProgress.appendChild(statusText);
        
        // 组合专家开始元素
        expertStart.appendChild(expertHeader);
        expertStart.appendChild(expertProgress);
        
        // 添加到分析过程容器
        processContainer.appendChild(expertStart);
        
        // 滚动到最新内容
        expertStart.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    // 如果是中间结果
    else if (data.type === "intermediate") {
        const expertData = data.content;
        if (!expertData) return;
        
        let processContainer = document.getElementById(analysisProcessId);
        if (!processContainer) return;
        
        // 查找对应的专家开始元素
        const expertStarts = processContainer.querySelectorAll('.expert-start');
        let currentExpertStart = null;
        
        for (let i = expertStarts.length - 1; i >= 0; i--) {
            if (expertStarts[i].querySelector('strong').textContent === expertData.expert_name) {
                currentExpertStart = expertStarts[i];
            break;
            }
        }
        
        if (!currentExpertStart) return;
        
        // 更新进度条状态为完成
        const progressBar = currentExpertStart.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.className = "progress-bar completed";
        }
        
        // 更新状态文本
        const statusText = currentExpertStart.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = "完成";
        }
        
        // 如果有结果，添加到专家开始元素
        if (expertData.result) {
            // 先移除之前的结果预览（如果有）
            const existingPreview = currentExpertStart.querySelector('.result-preview');
            if (existingPreview) {
                existingPreview.remove();
            }
            
            // 创建结果预览
            const resultPreview = document.createElement("div");
            resultPreview.className = "result-preview";
            
            // 根据结果类型显示不同内容
            if (typeof expertData.result === 'string') {
                resultPreview.textContent = truncateText(expertData.result, 300);
            } else if (typeof expertData.result === 'object') {
                if (expertData.result.response) {
                    resultPreview.textContent = truncateText(expertData.result.response, 300);
            } else {
                    resultPreview.textContent = "处理完成";
                }
                
                // 如果有可视化，显示缩略图
                if (expertData.visualization) {
                    const visContainer = document.createElement("div");
                    visContainer.style.textAlign = "center";
                    visContainer.style.marginTop = "10px";
                    
                    const visImage = document.createElement("img");
                    visImage.src = "data:image/png;base64," + expertData.visualization;
                    visImage.style.maxWidth = "100%";
                    visImage.style.maxHeight = "150px";
                    visImage.style.borderRadius = "4px";
                    
                    visContainer.appendChild(visImage);
                    resultPreview.appendChild(visContainer);
                }
            }
            
            currentExpertStart.appendChild(resultPreview);
            
            // 如果最后一个专家完成了，添加一个思考指示器表示正在生成最终结果
            if (expertData.step === expertData.total_steps) {
                const finalProcessThinkingIndicator = document.createElement("div");
                finalProcessThinkingIndicator.className = "thinking-indicator";
                finalProcessThinkingIndicator.innerHTML = `
                    <div class="thinking-dots">
                        正在生成最终分析结果<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
                    </div>
                `;
                processContainer.appendChild(finalProcessThinkingIndicator);
                finalProcessThinkingIndicator.scrollIntoView({ behavior: "smooth", block: "end" });
            }
        }
    }
    
    // 更新滚动位置
    updateScroll();
}

/**
 * 更新滚动位置，确保聊天窗口滚动到最新消息
 */
function updateScroll() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
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
                // 创建唯一ID用于存储完整文本
                const fullTextId = `full-text-${expertMessageId}`;
                
                // 创建隐藏的div存储完整文本
                expertContent += `<div id="${fullTextId}" style="display:none;">${responseText}</div>`;
                
                // 添加展开按钮，传入消息ID和完整文本ID
                expertContent += `<button class="expand-btn" onclick="expandExpertResponse('${expertMessageId}', '${fullTextId}')">查看完整回答</button>`;
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
 * @param {string} fullTextId - 完整文本ID
 */
function expandExpertResponse(messageId, fullTextId) {
    const messageElement = document.getElementById(messageId);
    if (!messageElement) return;
    
    const responseDiv = messageElement.querySelector('.expert-response');
    const expandBtn = messageElement.querySelector('.expand-btn');
    
    if (responseDiv && expandBtn) {
        try {
            // 获取完整文本
            const fullTextElement = document.getElementById(fullTextId);
            const fullText = fullTextElement ? fullTextElement.innerHTML : '';
            
            // 显示完整文本
            responseDiv.innerHTML = fullText;
            
            // 移除展开按钮
            expandBtn.remove();
            
            // 滚动到底部
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (error) {
            console.error('展开回答时出错:', error);
            responseDiv.innerHTML = '<div class="error-message">无法显示完整回答，请重试。</div>';
        }
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
    const messageId = `message-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;
    messageElement.id = messageId;
    
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    
    // 为助手消息使用markdown解析
    if (role === 'assistant') {
        const markdownContent = parseMarkdown(content);
        contentElement.innerHTML = markdownContent;
    } else {
    contentElement.textContent = content;
    }
    
    messageElement.appendChild(contentElement);
    chatMessages.appendChild(messageElement);
    
    // 滚动到最新消息
    updateScroll();
    
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

/**
 * 生成分析总结
 * @param {NodeList} expertResults - 专家结果元素列表
 * @param {string} originalQuery - 原始用户问题
 * @returns {string} 分析总结内容
 */
function generateAnalysisSummary(expertResults, originalQuery) {
    const completedExperts = [];
    const analysis = {
        knowledge: null,
        sql: null,
        data: null,
        visualization: null
    };
    
    // 分析已完成的专家步骤
    expertResults.forEach(expertElement => {
        const expertName = expertElement.querySelector('strong').textContent;
        const isCompleted = expertElement.querySelector('.progress-bar.completed');
        const resultPreview = expertElement.querySelector('.result-preview');
        const hasVisualization = expertElement.querySelector('.visualization-preview');
        
        if (isCompleted) {
            completedExperts.push(expertName);
            
            // 根据专家类型归类结果
            if (expertName.includes('知识') || expertName.includes('行业')) {
                analysis.knowledge = resultPreview ? resultPreview.textContent : '已提供行业背景分析';
            } else if (expertName.includes('SQL') || expertName.includes('数据库')) {
                analysis.sql = resultPreview ? resultPreview.textContent : '已完成数据查询';
            } else if (expertName.includes('数据分析')) {
                analysis.data = resultPreview ? resultPreview.textContent : '已完成数据分析';
            } else if (expertName.includes('可视化')) {
                analysis.visualization = hasVisualization ? '已生成可视化图表' : '已完成可视化分析';
            }
        }
    });
    
    // 生成总结内容
    let summaryContent = `## 📊 分析总结\n\n针对您的问题"${originalQuery}"，我们的专家团队已完成以下分析：\n\n`;
    
    if (completedExperts.length === 0) {
        summaryContent += '分析过程尚未完成，建议重新尝试。';
    } else {
        summaryContent += `✅ **已完成的分析步骤** (${completedExperts.length}个)：\n`;
        completedExperts.forEach((expert, index) => {
            summaryContent += `${index + 1}. ${expert}\n`;
        });
        
        summaryContent += '\n**分析要点**：\n';
        
        if (analysis.knowledge) {
            summaryContent += `🎯 **行业洞察**：已提供美妆行业专业背景和分析框架\n`;
        }
        
        if (analysis.sql) {
            summaryContent += `🔍 **数据查询**：已获取相关销售数据\n`;
        }
        
        if (analysis.data) {
            summaryContent += `📈 **数据分析**：已完成销售数据的统计分析\n`;
        }
        
        if (analysis.visualization) {
            summaryContent += `📊 **可视化展示**：已生成直观的数据图表\n`;
        }
        
        summaryContent += '\n虽然分析过程被中断，但以上步骤的结果仍可为您的决策提供参考。';
        
        if (completedExperts.length < 4) {
            summaryContent += '\n\n💡 **建议**：您可以重新提问以获得完整的四专家协作分析。';
        }
    }
    
    return summaryContent;
}

/**
 * 简单的Markdown解析器，将markdown文本转换为HTML
 * @param {string} text - markdown文本
 * @returns {string} HTML文本
 */
function parseMarkdown(text) {
    if (!text) return '';
    
    let html = text;
    
    // 处理标题 (## 标题)
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // 处理加粗文本 (**文本** 或 __文本__)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');
    
    // 处理斜体文本 (*文本* 或 _文本_) - 但不影响列表标记
    html = html.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>');
    html = html.replace(/(?<!_)_([^_\n]+?)_(?!_)/g, '<em>$1</em>');
    
    // 处理代码块 (`代码`)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // 处理无序列表 (- 项目 或 * 项目) - 保持emoji和图标
    html = html.replace(/^[\s]*[-\*\+]\s+(.+$)/gim, '<li>$1</li>');
    
    // 处理有序列表 (1. 项目)
    html = html.replace(/^[\s]*(\d+\.)\s+(.+$)/gim, '<li><span class="list-number">$1</span> $2</li>');
    
    // 处理带图标的列表项（如 ✅ 或 🎯）
    html = html.replace(/^[\s]*([✅❌🎯📊🔍💡⚠️ℹ️]+)\s+(.+$)/gim, '<li><span class="list-icon">$1</span> $2</li>');
    
    // 将连续的<li>包装在<ul>中
    html = html.replace(/(<li>.*?<\/li>(?:\s*<li>.*?<\/li>)*)/gs, function(match) {
        return '<ul>' + match + '</ul>';
    });
    
    // 处理段落分隔 (双换行符)
    html = html.replace(/\n\s*\n/g, '</p><p>');
    
    // 处理单个换行符
    html = html.replace(/\n/g, '<br>');
    
    // 包装在段落中（如果不是以标题或列表开始）
    if (html && !html.match(/^(<h[1-6]|<ul|<ol|<p)/)) {
        html = '<p>' + html + '</p>';
    }
    
    // 清理多余的空白段落
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>\s*<br>\s*<\/p>/g, '');
    html = html.replace(/<p><br><\/p>/g, '');
    
    // 修复嵌套的<p>标签
    html = html.replace(/<p>(<h[1-6].*?<\/h[1-6]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>.*?<\/ul>)<\/p>/gs, '$1');
    html = html.replace(/<p>(<ol>.*?<\/ol>)<\/p>/gs, '$1');
    
    return html;
} 

// 添加图片点击放大功能
function addImageClickHandler() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('visualization-image') || 
            e.target.classList.contains('expert-viz-image')) {
            
            // 创建模态框
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                cursor: pointer;
            `;
            
            const img = document.createElement('img');
            img.src = e.target.src;
            img.style.cssText = `
                max-width: 95%;
                max-height: 95%;
                object-fit: contain;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            `;
            
            modal.appendChild(img);
            document.body.appendChild(modal);
            
            // 点击模态框关闭
            modal.addEventListener('click', function() {
                document.body.removeChild(modal);
            });
            
            // ESC键关闭
            document.addEventListener('keydown', function escHandler(e) {
                if (e.key === 'Escape') {
                    if (document.body.contains(modal)) {
                        document.body.removeChild(modal);
                    }
                    document.removeEventListener('keydown', escHandler);
                }
            });
        }
    });
}

// 在页面加载完成后添加事件处理器
document.addEventListener('DOMContentLoaded', function() {
    addImageClickHandler();
}); 