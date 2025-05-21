"""
主控制Agent
负责理解用户意图，协调其他专业Agent工作
"""
import os
import logging
from typing import Dict, List, Any, Optional
import json
from qwen_agent.agents import Assistant

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
        
        # 创建控制Agent实例
        self.control_agent = Assistant(
            llm=self.llm_cfg,
            name='美妆销售助手',
            description='我是一个专业的美妆销售数据对话助手，能够理解你的需求并提供专业的销售数据分析'
        )
        
        # 初始化子Agent
        self.knowledge_agent = KnowledgeAgent()
        self.data_agent = DataAgent()
        self.sql_agent = None  # 需要在加载数据库后初始化
        self.visualization_agent = VisualizationAgent()
        
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
    
    def initialize_sql_agent(self, db_path: str) -> bool:
        """初始化SQL Agent
        
        参数:
            db_path: 数据库文件路径
            
        返回:
            是否成功初始化
        """
        try:
            self.sql_agent = SQLAgent(db_path)
            self.session_state["current_database"] = db_path
            logger.info(f"成功初始化SQL Agent，连接数据库: {db_path}")
            return True
        except Exception as e:
            logger.error(f"初始化SQL Agent时发生错误: {e}")
            return False
    
    def _classify_query_intent(self, query: str) -> Dict[str, Any]:
        """对用户查询进行意图分类
        
        参数:
            query: 用户查询
            
        返回:
            意图分类结果
        """
        # 构建综合system提示，将所有信息合并到一个system消息中
        system_prompt = """你是一个专业的查询意图分类器，专注于美妆销售数据分析领域。
你的任务是将用户的查询分类到以下几种意图之一:

1. KNOWLEDGE_QUERY - 咨询美妆行业知识、产品信息、市场趋势等
2. DATA_ANALYSIS - 要求对已加载的数据进行分析、统计或可视化
3. SQL_QUERY - 需要查询数据库或执行SQL相关操作
4. VISUALIZATION - 专门要求生成图表或可视化展示
5. DATA_OPERATION - 数据处理操作(加载、过滤、转换等)
6. GENERAL_CHAT - 一般对话、问候或无明确业务需求的闲聊
7. SYSTEM_OPERATION - 系统操作，如请求帮助、保存结果等

请返回一个JSON对象，包含以下字段:
- intent: 上述7种意图之一
- confidence: 置信度(0-1之间的小数)
- subtype: 更具体的子类型(可选)
- entities: 提取的关键实体，如产品名称、时间范围等(可选)
- required_agent: 处理该查询最适合的agent类型(knowledge_agent, data_agent, sql_agent, visualization_agent)

只返回JSON对象，不要有其他解释。"""

        # 添加系统状态上下文
        state_info = f"""
当前系统状态:
- 已加载数据文件: {self.session_state['current_data_path'] or '无'}
- 已连接数据库: {self.session_state['current_database'] or '无'}
- 上次查询类型: {self.session_state['last_query_type'] or '无'}
"""
        
        # 添加会话历史上下文
        context_info = ""
        if self.session_state["conversation_history"]:
            context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.session_state["conversation_history"][-5:]])
            context_info = f"\n最近的对话历史:\n{context}"
        
        # 将所有系统信息合并为一个system消息
        complete_system_prompt = f"{system_prompt}\n{state_info}{context_info}"
        
        # 构建消息列表，确保只有一个system消息
        messages = [
            {"role": "system", "content": complete_system_prompt},
            {"role": "user", "content": f"用户查询: {query}"}
        ]
        
        # 获取分类结果
        response_text = ""
        for response in self.control_agent.run(messages=messages):
            if "content" in response:
                response_text += response["content"]
        
        # 解析JSON结果
        try:
            result = json.loads(response_text)
            # 设置默认值
            if "intent" not in result:
                result["intent"] = "GENERAL_CHAT"
            if "confidence" not in result:
                result["confidence"] = 0.7
            if "required_agent" not in result:
                result["required_agent"] = "control_agent"
                
            return result
        except Exception as e:
            logger.error(f"解析意图分类结果时发生错误: {e}, 原始响应: {response_text}")
            return {
                "intent": "GENERAL_CHAT",
                "confidence": 0.5,
                "error": str(e),
                "required_agent": "control_agent"
            }
    
    def _route_to_agent(self, query: str, intent_info: Dict[str, Any]) -> Dict[str, Any]:
        """根据意图将查询路由到合适的Agent处理
        
        参数:
            query: 用户查询
            intent_info: 意图分类信息
            
        返回:
            处理结果
        """
        intent = intent_info.get("intent", "GENERAL_CHAT")
        required_agent = intent_info.get("required_agent", "control_agent")
        
        # 记录当前查询类型
        self.session_state["last_query_type"] = intent
        
        # 准备上下文信息
        context = None
        if self.session_state["conversation_history"]:
            context = self.session_state["conversation_history"][-5:]  # 最近5轮对话
        
        # 根据意图路由到相应的Agent
        if intent == "KNOWLEDGE_QUERY" or required_agent == "knowledge_agent":
            logger.info(f"将查询路由到知识Agent: {query}")
            return {
                "response": self.knowledge_agent.get_knowledge_response(query, context),
                "source": "knowledge_agent",
                "visualization": None
            }
        
        elif intent == "DATA_ANALYSIS" or required_agent == "data_agent":
            logger.info(f"将查询路由到数据Agent: {query}")
            if not self.session_state["current_data_path"]:
                return {
                    "response": "请先加载数据文件后再进行数据分析。",
                    "source": "control_agent",
                    "visualization": None
                }
            
            result = self.data_agent.run_analysis(query, context)
            if result.get("success", False):
                self.session_state["last_analysis_result"] = result
                return {
                    "response": result.get("response", ""),
                    "source": "data_agent",
                    "visualization": result.get("visualization"),
                    "code_output": result.get("code_output", "")
                }
            else:
                return {
                    "response": result.get("error", "数据分析失败"),
                    "source": "data_agent",
                    "visualization": None
                }
        
        elif intent == "SQL_QUERY" or required_agent == "sql_agent":
            logger.info(f"将查询路由到SQL Agent: {query}")
            if not self.sql_agent:
                return {
                    "response": "请先连接数据库后再进行SQL查询。",
                    "source": "control_agent",
                    "visualization": None
                }
            
            result = self.sql_agent.execute_nl_query(query, context)
            if result.get("success", False):
                # 如果有数据结果，可以尝试可视化
                if "data" in result and intent_info.get("intent") == "VISUALIZATION":
                    viz_result = self.visualization_agent.generate_visualization(
                        data=result["data"],
                        query=query,
                        chart_type=intent_info.get("subtype", self.visualization_config["default_chart_type"])
                    )
                    if viz_result.get("success", False):
                        return {
                            "response": result.get("response", ""),
                            "source": "sql_agent",
                            "visualization": viz_result.get("visualization"),
                            "sql": result.get("sql", "")
                        }
                
                return {
                    "response": result.get("response", ""),
                    "source": "sql_agent",
                    "sql": result.get("sql", ""),
                    "data": result.get("data")
                }
            else:
                return {
                    "response": result.get("error", "SQL查询失败"),
                    "source": "sql_agent",
                    "visualization": None
                }
        
        elif intent == "VISUALIZATION" or required_agent == "visualization_agent":
            logger.info(f"将查询路由到可视化Agent: {query}")
            
            # 检查是否有最近的分析结果可以可视化
            if self.session_state["last_analysis_result"] and "data" in self.session_state["last_analysis_result"]:
                data = self.session_state["last_analysis_result"]["data"]
            elif self.session_state["current_data_path"]:
                # 使用当前加载的数据
                data = self.data_agent.current_data
            else:
                return {
                    "response": "没有可用的数据来生成可视化。请先加载数据或执行分析。",
                    "source": "control_agent",
                    "visualization": None
                }
            
            # 提取图表类型
            chart_type = intent_info.get("subtype", self.visualization_config["default_chart_type"])
            
            viz_result = self.visualization_agent.generate_visualization(
                data=data,
                query=query,
                chart_type=chart_type
            )
            
            if viz_result.get("success", False):
                return {
                    "response": viz_result.get("description", ""),
                    "source": "visualization_agent",
                    "visualization": viz_result.get("visualization")
                }
            else:
                return {
                    "response": viz_result.get("error", "生成可视化失败"),
                    "source": "visualization_agent",
                    "visualization": None
                }
        
        elif intent == "DATA_OPERATION":
            logger.info(f"处理数据操作请求: {query}")
            
            # 处理数据加载请求
            if "加载" in query or "读取" in query or "导入" in query:
                # 提取文件路径
                file_path = self._extract_file_path(query, intent_info.get("entities", {}))
                if file_path:
                    success = self.data_agent.load_data(file_path)
                    if success:
                        self.session_state["current_data_path"] = file_path
                        data_summary = self.data_agent.get_data_summary()
                        return {
                            "response": f"成功加载数据文件: {file_path}\n数据包含 {data_summary.get('行数', '?')} 行，{data_summary.get('列数', '?')} 列。",
                            "source": "data_agent",
                            "visualization": None
                        }
                    else:
                        return {
                            "response": f"加载数据文件失败: {file_path}",
                            "source": "data_agent",
                            "visualization": None
                        }
                else:
                    return {
                        "response": "请提供有效的数据文件路径。",
                        "source": "control_agent",
                        "visualization": None
                    }
            
            # 处理数据预处理请求
            elif any(op in query for op in ["清洗", "预处理", "处理", "转换", "过滤"]):
                if not self.session_state["current_data_path"]:
                    return {
                        "response": "请先加载数据文件后再进行数据处理。",
                        "source": "control_agent",
                        "visualization": None
                    }
                
                # 这里需要通过LLM解析用户想要执行的具体数据处理操作
                operations = self._parse_data_operations(query)
                if operations:
                    result = self.data_agent.preprocess_data(operations)
                    if result.get("success", False):
                        return {
                            "response": f"数据处理完成。\n{result.get('message', '')}\n{result.get('rows_count', '?')} 行，{result.get('columns_count', '?')} 列。",
                            "source": "data_agent",
                            "visualization": None
                        }
                    else:
                        return {
                            "response": result.get("error", "数据处理失败"),
                            "source": "data_agent",
                            "visualization": None
                        }
                else:
                    return {
                        "response": "无法理解您要执行的数据处理操作，请更具体地描述。",
                        "source": "control_agent",
                        "visualization": None
                    }
            
            # 其他数据操作
            else:
                return {
                    "response": "请提供更具体的数据操作指令。",
                    "source": "control_agent",
                    "visualization": None
                }
        
        # 默认使用控制Agent直接回答
        else:
            logger.info(f"使用控制Agent直接回答: {query}")
            return self._generate_response(query, context)
    
    def _extract_file_path(self, query: str, entities: Dict[str, Any]) -> Optional[str]:
        """从查询中提取文件路径
        
        参数:
            query: 用户查询
            entities: 实体信息
            
        返回:
            文件路径，如果未找到则返回None
        """
        # 首先检查实体中是否有文件路径
        if "file_path" in entities:
            return entities["file_path"]
        
        # 使用控制Agent提取文件路径
        system_prompt = """你的任务是从用户消息中提取数据文件路径。
只返回文件路径，不要有其他文本。如果找不到明确的文件路径，返回"未找到"。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"从以下消息提取数据文件路径: {query}"}
        ]
        
        # 获取响应
        response_text = ""
        for response in self.control_agent.run(messages=messages):
            if "content" in response:
                response_text += response["content"]
        
        if response_text and "未找到" not in response_text:
            # 清理提取的路径
            file_path = response_text.strip().strip('"\'').strip()
            return file_path
        
        return None
    
    def _parse_data_operations(self, query: str) -> List[Dict[str, Any]]:
        """解析用户查询中的数据操作
        
        参数:
            query: 用户查询
            
        返回:
            数据操作列表
        """
        system_prompt = """你的任务是解析用户对数据处理的请求，并将其转换为结构化的操作列表。

支持的操作类型包括:
1. fill_na - 填充缺失值
2. drop_na - 删除含有缺失值的行
3. drop_duplicates - 删除重复行
4. filter - 过滤数据
5. sort - 排序
6. rename - 重命名列
7. create - 创建新列
8. convert_type - 转换数据类型

请返回一个JSON数组，每个操作是一个包含type和params字段的对象。
仅返回JSON数组，不要有其他解释或文字。"""
        
        # 获取当前数据的列信息，以便更准确地解析
        columns_info = ""
        if self.data_agent.current_data is not None:
            columns = list(self.data_agent.current_data.columns)
            data_types = {col: str(dtype) for col, dtype in self.data_agent.current_data.dtypes.items()}
            columns_info = f"当前数据包含以下列:\n" + "\n".join([f"- {col} ({data_types[col]})" for col in columns])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{columns_info}\n\n用户的数据处理请求: {query}"}
        ]
        
        # 获取响应
        response_text = ""
        for response in self.control_agent.run(messages=messages):
            if "content" in response:
                response_text += response["content"]
        
        # 解析JSON
        try:
            operations = json.loads(response_text)
            return operations if isinstance(operations, list) else []
        except Exception as e:
            logger.error(f"解析数据操作时发生错误: {e}, 原始响应: {response_text}")
            return []
    
    def _generate_response(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """使用控制Agent生成一般性回答
        
        参数:
            query: 用户查询
            context: 对话上下文
            
        返回:
            回答结果
        """
        # 构建综合system prompt，包含所有必要信息
        system_prompt = """你是一个专业的美妆销售数据对话助手。
请回答用户的问题，提供专业、准确、友好的回应。
如果问题涉及到具体的数据分析、行业知识或需要执行操作，请告知用户你可以帮助他们实现。

当前系统功能包括:
1. 美妆行业知识咨询
2. 销售数据分析和可视化
3. 数据库查询和报表生成
4. 数据预处理和转换

回答应该简洁、专业，并且针对美妆行业特点。"""
        
        # 添加系统状态信息
        state_info = f"""
当前系统状态:
- 已加载数据文件: {self.session_state['current_data_path'] or '无'}
- 已连接数据库: {self.session_state['current_database'] or '无'}
"""
        
        # 添加上下文信息（如果有）
        context_info = ""
        if context:
            context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context])
            context_info = f"\n以下是之前的对话上下文:\n{context_str}"
        
        # 合并所有系统信息为一个完整的system prompt
        complete_system_prompt = f"{system_prompt}{state_info}{context_info}"
        
        # 构建消息，确保只有一个system消息
        messages = [
            {"role": "system", "content": complete_system_prompt},
            {"role": "user", "content": query}
        ]
        
        # 使用LLM生成回答
        response_text = ""
        for response in self.control_agent.run(messages=messages):
            if "content" in response:
                response_text += response["content"]
        
        return {
            "response": response_text,
            "source": "control_agent",
            "visualization": None
        }
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """处理用户查询
        
        参数:
            query: 用户查询文本
            
        返回:
            处理结果
        """
        # 记录当前查询到会话历史
        self.session_state["conversation_history"].append({"role": "user", "content": query})
        
        # 分类查询意图
        intent_info = self._classify_query_intent(query)
        logger.info(f"查询意图分类结果: {intent_info}")
        
        # 路由到相应的Agent处理
        result = self._route_to_agent(query, intent_info)
        
        # 记录回复到会话历史
        self.session_state["conversation_history"].append({"role": "assistant", "content": result["response"]})
        
        # 限制会话历史长度
        if len(self.session_state["conversation_history"]) > 20:
            self.session_state["conversation_history"] = self.session_state["conversation_history"][-20:]
        
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