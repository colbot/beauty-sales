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

你有多种能力:
1. 提供美妆行业专业知识
2. 将自然语言转换为SQL查询
3. 美妆销售数据的分析
4. 将美妆销售数据转化为直观的图表

请根据用户需求，选择合适的能力来回答问题。对于数据分析和数据库查询，需要先确保数据已加载或数据库已连接。
"""
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        # 使用Router处理查询
        response_text = ""
        visualization = None
        code_output = ""
        source_agent = "router"
        
        for response in self.control_agent.run(messages):
            if "content" in response:
                response_text += response["content"]
            
            # 处理工具调用
            if "tool_calls" in response:
                for tool_call in response["tool_calls"]:
                    # 处理代码解释器调用
                    if tool_call["type"] == "code_interpreter":
                        code_output = tool_call.get("output", "")
                        # 检查是否有可视化输出
                        if isinstance(code_output, dict) and "image/png" in code_output:
                            visualization = code_output.get("image/png")
        
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