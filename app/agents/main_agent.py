"""
主控制Agent
负责理解用户意图，协调其他专业Agent工作
"""
import os
import logging
from typing import Dict, List, Any, Optional
import json
from qwen_agent.agents import Router

# 导入各个专业Agent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.data_agent import DataAgent
from app.agents.sql_agent import SQLAgent
from app.agents.visualization_agent import VisualizationAgent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainAgent:
    """主控制Agent，理解用户意图并协调其他Agent工作"""
    
    def __init__(self):
        """初始化主控制Agent"""
        # 获取API密钥和模型名称
        api_key = os.getenv("QWEN_API_KEY")
        model_name = os.getenv("QWEN_MODEL", "qwen-max")
        
        # 基础LLM配置
        self.llm_cfg = {
            'model': model_name,
            'model_server': 'dashscope',
            'api_key': api_key,
        }
        
        # 初始化子Agent
        self.knowledge_agent = KnowledgeAgent()
        self.data_agent = DataAgent()
        self.visualization_agent = VisualizationAgent()
        # 初始化SQL Agent，但不连接数据库
        self.sql_agent = SQLAgent()  
        
        # 获取各个Agent的Assistant实例，用于Router
        knowledge_assistant = self.knowledge_agent.knowledge_assistant
        data_assistant = self.data_agent.data_assistant
        visualization_assistant = self.visualization_agent.visualization_assistant
        sql_assistant = self.sql_agent.sql_assistant
        
        # 创建Router Agent，集成所有专业助手
        self.control_agent = Router(
            llm=self.llm_cfg,
            agents=[knowledge_assistant, data_assistant, visualization_assistant, sql_assistant],
            name='美妆销售助手',
            description='一个专业的美妆销售数据分析对话助手，能够理解您的需求并提供多方面的专业分析'
        )
        
        # 会话状态
        self.session_state = {
            "current_data_path": None,
            "current_database": None,
            "conversation_history": [],
            "last_query_type": None,
            "last_analysis_result": None
        }
        
        # 可视化配置
        self.visualization_config = {
            "default_chart_type": "bar",
            "color_theme": "default",
            "show_data_labels": True
        }
    
    def _sync_data_between_agents(self):
        """同步各个Agent之间的数据"""
        if self.data_agent.current_data is not None:
            self.visualization_agent.current_data = self.data_agent.current_data
            logger.info("已将数据同步到可视化Agent")
    
    def connect_database(self, db_path: str) -> bool:
        """连接到数据库
        
        参数:
            db_path: 数据库文件路径
            
        返回:
            是否成功连接
        """
        try:
            # 构造数据库连接参数
            db_params = {"path": db_path}
            
            # 连接数据库
            connection_success = self.sql_agent.connect_db(db_params)
            
            if connection_success:
                self.session_state["current_database"] = db_path
                logger.info(f"成功连接到数据库: {db_path}")
            else:
                logger.error(f"连接数据库失败: {db_path}")
                
            return connection_success
                
        except Exception as e:
            logger.error(f"连接数据库时发生错误: {e}")
            return False
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """处理用户查询
        
        参数:
            query: 用户查询文本
            
        返回:
            处理结果
        """
        # 记录当前查询到会话历史
        self.session_state["conversation_history"].append({"role": "user", "content": query})
        
        # 准备系统提示，包含当前状态信息
        system_prompt = f"""你是一个专业的美妆销售数据对话助手。请根据用户的问题，提供专业、准确、友好的回应。

当前系统状态:
- 已加载数据文件: {self.session_state['current_data_path'] or '无'}
- 已连接数据库: {self.session_state['current_database'] or '无'}

你需要先分析用户问题的意图，根据用户的核心需求转交给合适的专家去解决。你可以请求帮助的专家有以下几个:
1. 美妆行业知识专家: 提供美妆行业专业知识
2. SQL专家: 将自然语言转换为SQL查询
3. 数据分析专家: 美妆销售数据的分析
4. 数据可视化专家: 将美妆销售数据转化为直观的图表

请根据用户需求，选择合适的专家来回答问题。如果你觉得有些问题与这些专家的能力无关，那么就由自己直接回答
对于数据分析和数据库查询，需要先确保数据已加载或数据库已连接。

请在回复的开头明确指出你选择了哪个专家来回答这个问题，格式为：'[专家类型]：回答内容'。
例如：'[美妆行业知识专家]：这是关于美妆行业的回答...'
"""
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        # 使用Router处理查询来确定应该使用哪个专业Agent
        router_response_text = ""
        visualization = None
        code_output = ""
        source_agent = "router"
        
        for response in self.control_agent.run(messages):
            if "content" in response[0]:
                router_response_text += response[0]["content"]
            
            # 处理工具调用
            if "tool_calls" in response[0]:
                for tool_call in response[0]["tool_calls"]:
                    # 处理代码解释器调用
                    if tool_call["type"] == "code_interpreter":
                        code_output = tool_call.get("output", "")
                        # 检查是否有可视化输出
                        if isinstance(code_output, dict) and "image/png" in code_output:
                            visualization = code_output.get("image/png")
        
        # 根据Router的回复确定应该使用哪个专业Agent
        selected_agent = None
        response_text = router_response_text
        specialist_result = None
        
        # 从回复中分析出应该使用哪个专家
        lower_response = router_response_text.lower()
        
        # 检查是否明确指出了专家类型（按Router回复的格式来分析）
        if '[美妆行业知识专家]' in router_response_text or '知识专家' in lower_response:
            logger.info("Router选择了知识检索Agent处理查询")
            selected_agent = "knowledge"
            # 调用知识专家处理查询
            specialist_result = self.knowledge_agent.get_knowledge_response(query, self.session_state["conversation_history"])
            source_agent = "knowledge"
            response_text = specialist_result
            
        elif '[SQL专家]' in router_response_text or 'sql专家' in lower_response or '数据库' in lower_response:
            logger.info("Router选择了SQL Agent处理查询")
            selected_agent = "sql"
            # 调用SQL专家处理查询
            if self.session_state["current_database"]:
                specialist_result = self.sql_agent.execute_nl_query(query, self.session_state["conversation_history"])
                source_agent = "sql"
                if specialist_result["success"]:
                    response_text = specialist_result["response"]
                    # 检查是否有可视化需求，如果有则将数据传递给可视化Agent
                    if len(specialist_result.get("data", [])) > 0:
                        # 可以在这里添加自动可视化的逻辑
                        pass
                else:
                    response_text = f"SQL查询失败: {specialist_result.get('error', '未知错误')}"
            else:
                response_text = "无法执行SQL查询，因为尚未连接数据库。请先连接数据库后再尝试。"
            
        elif '[数据分析专家]' in router_response_text or '数据分析' in lower_response:
            logger.info("Router选择了数据分析Agent处理查询")
            selected_agent = "data"
            # 调用数据分析专家处理查询
            if self.session_state["current_data_path"]:
                specialist_result = self.data_agent.run_analysis(query, self.session_state["conversation_history"])
                source_agent = "data"
                response_text = specialist_result.get("response", "")
                visualization = specialist_result.get("visualization")
                code_output = specialist_result.get("code_output", "")
            else:
                response_text = "无法执行数据分析，因为尚未加载数据。请先加载数据后再尝试。"
            
        elif '[数据可视化专家]' in router_response_text or '可视化' in lower_response or '图表' in lower_response:
            logger.info("Router选择了可视化Agent处理查询")
            selected_agent = "visualization"
            # 调用可视化专家处理查询
            if self.data_agent.current_data is not None:
                specialist_result = self.visualization_agent.create_visualization(query)
                source_agent = "visualization"
                response_text = specialist_result.get("description", "")
                visualization = specialist_result.get("visualization")
            else:
                response_text = "无法创建可视化，因为尚未加载数据。请先加载数据后再尝试。"
        
        # 如果没有明确指定专家或Router自己回答了问题，则使用Router的回复
        if not selected_agent:
            logger.info("Router直接回答了问题，无需专业Agent介入")
        
        # 记录回复到会话历史
        self.session_state["conversation_history"].append({"role": "assistant", "content": response_text})
        
        # 限制会话历史长度
        if len(self.session_state["conversation_history"]) > 20:
            self.session_state["conversation_history"] = self.session_state["conversation_history"][-20:]
        
        result = {
            "response": response_text,
            "source": source_agent,
            "visualization": visualization,
            "code_output": code_output
        }
        
        return result
    
    def reset_session(self) -> None:
        """重置会话状态"""
        self.session_state = {
            "current_data_path": None,
            "current_database": None,
            "conversation_history": [],
            "last_query_type": None,
            "last_analysis_result": None
        }
        logger.info("已重置会话状态")
        
    def update_visualization_config(self, config: Dict[str, Any]) -> None:
        """更新可视化配置
        
        参数:
            config: 新的配置项
        """
        self.visualization_config.update(config)
        logger.info(f"已更新可视化配置: {config}") 