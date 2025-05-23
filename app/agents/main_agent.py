"""
主控制Agent
负责理解用户意图，协调其他专业Agent工作
"""
import os
import logging
from typing import Dict, List, Any, Optional, Generator, Callable
import json
from qwen_agent.agents import Router
import pandas as pd

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
    
    def process_query(self, query: str):
        """处理用户查询，支持多专家协作处理复杂问题，实时流式输出过程与结果"""
        # 记录当前查询到会话历史
        self.session_state["conversation_history"].append({"role": "user", "content": query})
        
        # 准备系统提示，引导Router规划任务和执行顺序
        system_prompt = f"""你是一个专业的美妆销售数据对话助手。请根据用户的问题，提供专业、准确、友好的回应。

当前系统状态:
- 已加载数据文件: {self.session_state['current_data_path'] or '无'}
- 已连接数据库: {self.session_state['current_database'] or '无'}

对于复杂问题，你需要规划一个执行计划，按顺序调用一个或者多个专家。请分析用户问题，并确定需要哪些专家以及他们的调用顺序。可用的专家有:

1. 美妆行业知识专家: 提供美妆行业专业知识
2. SQL专家: 将自然语言转换为SQL查询
3. 数据分析专家: 美妆销售数据的分析
4. 数据可视化专家: 将美妆销售数据转化为直观的图表

回复格式：首先提供执行计划，格式为: "执行计划: [专家1] -> [专家2] -> ...". 然后详细描述每位专家将执行的任务
回复样例如下:
执行计划: [美妆行业知识专家] -> [数据分析专家] -> [数据可视化专家]
1. 美妆行业知识专家: 提供美妆行业专业知识
2. 数据分析专家: 分析3月销售数据趋势
3. 数据可视化专家:根据分析结果创建趋势图表

如果问题简单，只需一位专家即可解决，则只列出该专家
如果你认为问题与任何专家都无关，那么可以直接回答用户的问题
"""
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        # 步骤1: 使用Router生成执行计划
        yield {"type": "thinking", "content": "正在规划分析步骤..."}
        execution_plan = ""
        for response in self.control_agent.run(messages):
            if "content" in response[0]:
                execution_plan += response[0]["content"]
                yield {"type": "plan", "content": execution_plan}
        
        # 步骤2: 解析执行计划，提取专家序列
        expert_sequence = self._parse_execution_plan(execution_plan)
        yield {"type": "experts", "content": [expert["name"] for expert in expert_sequence]}
        
        # 步骤3: 按顺序执行专家任务
        yield from self._execute_expert_sequence_streaming(query, expert_sequence)
        
        # 返回完整的最终结果
        final_result = self._get_final_result_from_streaming(query, expert_sequence, execution_plan)
        
        # 记录回复到会话历史
        self.session_state["conversation_history"].append({"role": "assistant", "content": final_result["response"]})
        
        # 限制会话历史长度
        if len(self.session_state["conversation_history"]) > 20:
            self.session_state["conversation_history"] = self.session_state["conversation_history"][-20:]
        
        yield {"type": "final", "content": final_result}

    def _generate_execution_plan(self, messages: List[Dict[str, str]]) -> str:
        """使用Router生成执行计划"""
        execution_plan = ""
        for response in self.control_agent.run(messages):
            if "content" in response[0]:
                execution_plan += response[0]["content"]
        return execution_plan

    def _parse_execution_plan(self, execution_plan: str) -> List[Dict[str, Any]]:
        """解析执行计划，提取专家序列和任务说明"""
        expert_sequence = []
        
        # 查找执行计划行
        import re
        plan_match = re.search(r"执行计划:\s*(.+?)$", execution_plan, re.MULTILINE)
        
        if plan_match:
            # 提取专家序列
            plan_line = plan_match.group(1)
            experts_str = re.findall(r"\[(.*?)\]", plan_line)
            
            # 将专家名称映射到agent类型
            for expert in experts_str:
                if "知识专家" in expert or "行业知识" in expert:
                    expert_sequence.append({"type": "knowledge", "name": expert})
                elif "SQL" in expert or "数据库" in expert:
                    expert_sequence.append({"type": "sql", "name": expert})
                elif "数据分析" in expert:
                    expert_sequence.append({"type": "data", "name": expert})
                elif "可视化" in expert or "图表" in expert:
                    expert_sequence.append({"type": "visualization", "name": expert})
        else:
            # 如果没有找到明确的执行计划，通过内容分析确定专家
            lower_text = execution_plan.lower()
            if "知识专家" in lower_text or "行业知识" in lower_text:
                expert_sequence.append({"type": "knowledge", "name": "美妆行业知识专家"})
            if "sql" in lower_text or "数据库" in lower_text:
                expert_sequence.append({"type": "sql", "name": "SQL专家"})
            if "数据分析" in lower_text:
                expert_sequence.append({"type": "data", "name": "数据分析专家"})
            if "可视化" in lower_text or "图表" in lower_text:
                expert_sequence.append({"type": "visualization", "name": "数据可视化专家"})
        
        # 如果没有识别到任何专家，默认使用Router自己回答
        if not expert_sequence:
            expert_sequence.append({"type": "router", "name": "主助手"})
        
        return expert_sequence

    def _execute_expert_sequence(self, query: str, expert_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """按顺序执行专家任务，传递中间结果"""
        current_query = query
        intermediate_results = {}
        final_response = ""
        visualization = None
        code_output = ""
        source_agent = "router"
        
        logger.info(f"执行专家序列: {[expert['name'] for expert in expert_sequence]}")
        
        # 依次执行每个专家的任务
        for i, expert in enumerate(expert_sequence):
            expert_type = expert["type"]
            expert_name = expert["name"]
            
            logger.info(f"正在调用专家 {i+1}/{len(expert_sequence)}: {expert_name}")
            
            # 根据专家类型调用相应的Agent
            result = None
            
            if expert_type == "knowledge":
                # 调用知识专家
                result = self.knowledge_agent.get_knowledge_response(current_query, self.session_state["conversation_history"])
                intermediate_results["knowledge"] = result
                source_agent = "knowledge"
                
            elif expert_type == "sql":
                # 调用SQL专家
                if self.session_state["current_database"]:
                    result = self.sql_agent.execute_nl_query(current_query, self.session_state["conversation_history"])
                    if result["success"]:
                        intermediate_results["sql"] = result["data"]
                        intermediate_results["sql_response"] = result["response"]
                        source_agent = "sql"
                    else:
                        intermediate_results["sql_error"] = result.get("error", "未知错误")
                else:
                    intermediate_results["sql_error"] = "未连接数据库"
                
            elif expert_type == "data":
                # 调用数据分析专家
                if self.session_state["current_data_path"] or intermediate_results.get("sql"):
                    # 如果有SQL查询结果，可以将其传递给数据分析专家
                    if "sql" in intermediate_results:
                        # 将SQL结果加载到数据分析专家
                        sql_df = pd.DataFrame(intermediate_results["sql"])
                        self.data_agent.load_data_from_df(sql_df)
                        # 同步数据到可视化专家
                        self._sync_data_between_agents()
                    
                    # 执行分析
                    result = self.data_agent.run_analysis(current_query, self.session_state["conversation_history"])
                    intermediate_results["data_analysis"] = result.get("response", "")
                    intermediate_results["data_visualization"] = result.get("visualization")
                    source_agent = "data"
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    
                    # 如果有代码输出，保存它
                    if result.get("code_output"):
                        code_output = result.get("code_output", "")
                        
                    # 更新当前查询，加入分析结果上下文
                    if i < len(expert_sequence) - 1 and expert_sequence[i+1]["type"] == "visualization":
                        current_query = f"基于以下分析结果创建可视化: {result.get('response', '')}"
                else:
                    intermediate_results["data_error"] = "未加载数据"
                
            elif expert_type == "visualization":
                # 调用可视化专家
                if self.data_agent.current_data is not None:
                    # 如果有上一步的分析结果，可以考虑传递它
                    if "data_analysis" in intermediate_results:
                        # 可以将分析结果作为上下文传入
                        context_query = f"{current_query}\n基于之前的分析: {intermediate_results['data_analysis']}"
                        result = self.visualization_agent.create_visualization(context_query)
                    else:
                        result = self.visualization_agent.create_visualization(current_query)
                    
                    intermediate_results["visualization_description"] = result.get("description", "")
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    source_agent = "visualization"
                else:
                    intermediate_results["visualization_error"] = "没有可用数据进行可视化"
            
            else:  # 默认使用Router的回答
                intermediate_results["router_response"] = execution_plan
                source_agent = "router"
            
            # 更新当前结果，用于传递给下一个专家
            if result and isinstance(result, str):
                final_response += f"\n\n[{expert_name}]: {result}"
            elif result and isinstance(result, dict) and "response" in result:
                final_response += f"\n\n[{expert_name}]: {result['response']}"
        
        # 整合最终结果
        if not final_response and "router_response" in intermediate_results:
            final_response = intermediate_results["router_response"]
        
        # 移除多余的前导换行符
        final_response = final_response.lstrip("\n")
        
        return {
            "response": final_response,
            "source": source_agent,
            "visualization": visualization,
            "code_output": code_output,
            "intermediate_results": intermediate_results
        }

    def _execute_expert_sequence_streaming(self, query: str, expert_sequence: List[Dict[str, Any]]):
        """按顺序执行专家任务，实时流式输出中间结果"""
        current_query = query
        intermediate_results = {}
        final_response = ""
        visualization = None
        code_output = ""
        source_agent = "router"
        
        logger.info(f"执行专家序列: {[expert['name'] for expert in expert_sequence]}")
        
        # 依次执行每个专家的任务
        for i, expert in enumerate(expert_sequence):
            expert_type = expert["type"]
            expert_name = expert["name"]
            
            logger.info(f"正在调用专家 {i+1}/{len(expert_sequence)}: {expert_name}")
            
            # 根据专家类型调用相应的Agent
            result = None
            
            yield {"type": "expert_start", "content": {
                "expert_name": expert_name,
                "expert_type": expert_type,
                "step": i+1,
                "total_steps": len(expert_sequence)
            }}
            
            if expert_type == "knowledge":
                # 调用知识专家
                result = self.knowledge_agent.get_knowledge_response(current_query, self.session_state["conversation_history"])
                intermediate_results["knowledge"] = result
                source_agent = "knowledge"
                
            elif expert_type == "sql":
                # 调用SQL专家
                if self.session_state["current_database"]:
                    result = self.sql_agent.execute_nl_query(current_query, self.session_state["conversation_history"])
                    if result["success"]:
                        intermediate_results["sql"] = result["data"]
                        intermediate_results["sql_response"] = result["response"]
                        source_agent = "sql"
                    else:
                        intermediate_results["sql_error"] = result.get("error", "未知错误")
                else:
                    intermediate_results["sql_error"] = "未连接数据库"
                
            elif expert_type == "data":
                # 调用数据分析专家
                if self.session_state["current_data_path"] or intermediate_results.get("sql"):
                    # 如果有SQL查询结果，可以将其传递给数据分析专家
                    if "sql" in intermediate_results:
                        # 将SQL结果加载到数据分析专家
                        sql_df = pd.DataFrame(intermediate_results["sql"])
                        self.data_agent.load_data_from_df(sql_df)
                        # 同步数据到可视化专家
                        self._sync_data_between_agents()
                    
                    # 执行分析
                    result = self.data_agent.run_analysis(current_query, self.session_state["conversation_history"])
                    intermediate_results["data_analysis"] = result.get("response", "")
                    intermediate_results["data_visualization"] = result.get("visualization")
                    source_agent = "data"
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    
                    # 如果有代码输出，保存它
                    if result.get("code_output"):
                        code_output = result.get("code_output", "")
                        
                    # 更新当前查询，加入分析结果上下文
                    if i < len(expert_sequence) - 1 and expert_sequence[i+1]["type"] == "visualization":
                        current_query = f"基于以下分析结果创建可视化: {result.get('response', '')}"
                else:
                    intermediate_results["data_error"] = "未加载数据"
                
            elif expert_type == "visualization":
                # 调用可视化专家
                if self.data_agent.current_data is not None:
                    # 如果有上一步的分析结果，可以考虑传递它
                    if "data_analysis" in intermediate_results:
                        # 可以将分析结果作为上下文传入
                        context_query = f"{current_query}\n基于之前的分析: {intermediate_results['data_analysis']}"
                        result = self.visualization_agent.create_visualization(context_query)
                    else:
                        result = self.visualization_agent.create_visualization(current_query)
                    
                    intermediate_results["visualization_description"] = result.get("description", "")
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    source_agent = "visualization"
                else:
                    intermediate_results["visualization_error"] = "没有可用数据进行可视化"
            
            else:  # 默认使用Router的回答
                intermediate_results["router_response"] = execution_plan
                source_agent = "router"
            
            # 更新当前结果，用于传递给下一个专家
            if result and isinstance(result, str):
                final_response += f"\n\n[{expert_name}]: {result}"
            elif result and isinstance(result, dict) and "response" in result:
                final_response += f"\n\n[{expert_name}]: {result['response']}"
            
            # 实时流式输出中间结果
            yield {
                "type": "intermediate",
                "content": {
                    "expert_name": expert_name,
                    "result": result,
                    "source": source_agent,
                    "visualization": visualization,
                    "code_output": code_output,
                    "step": i+1,
                    "total_steps": len(expert_sequence)
                }
            }
    
    def _get_final_result_from_streaming(self, query: str, expert_sequence: List[Dict[str, Any]], execution_plan: str) -> Dict[str, Any]:
        """基于执行过程中的结果生成最终结果"""
        current_query = query
        intermediate_results = {}
        final_response = ""
        visualization = None
        code_output = ""
        source_agent = "router"
        
        # 依次执行每个专家的任务
        for i, expert in enumerate(expert_sequence):
            expert_type = expert["type"]
            expert_name = expert["name"]
            
            # 根据专家类型调用相应的Agent
            result = None
            
            if expert_type == "knowledge":
                # 调用知识专家
                result = self.knowledge_agent.get_knowledge_response(current_query, self.session_state["conversation_history"])
                intermediate_results["knowledge"] = result
                source_agent = "knowledge"
                
            elif expert_type == "sql":
                # 调用SQL专家
                if self.session_state["current_database"]:
                    result = self.sql_agent.execute_nl_query(current_query, self.session_state["conversation_history"])
                    if result["success"]:
                        intermediate_results["sql"] = result["data"]
                        intermediate_results["sql_response"] = result["response"]
                        source_agent = "sql"
                    else:
                        intermediate_results["sql_error"] = result.get("error", "未知错误")
                else:
                    intermediate_results["sql_error"] = "未连接数据库"
                
            elif expert_type == "data":
                # 调用数据分析专家
                if self.session_state["current_data_path"] or intermediate_results.get("sql"):
                    # 执行分析
                    result = self.data_agent.run_analysis(current_query, self.session_state["conversation_history"])
                    intermediate_results["data_analysis"] = result.get("response", "")
                    intermediate_results["data_visualization"] = result.get("visualization")
                    source_agent = "data"
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    
                    # 如果有代码输出，保存它
                    if result.get("code_output"):
                        code_output = result.get("code_output", "")
                        
                    # 更新当前查询，加入分析结果上下文
                    if i < len(expert_sequence) - 1 and expert_sequence[i+1]["type"] == "visualization":
                        current_query = f"基于以下分析结果创建可视化: {result.get('response', '')}"
                else:
                    intermediate_results["data_error"] = "未加载数据"
                
            elif expert_type == "visualization":
                # 调用可视化专家
                if self.data_agent.current_data is not None:
                    # 如果有上一步的分析结果，可以考虑传递它
                    if "data_analysis" in intermediate_results:
                        # 可以将分析结果作为上下文传入
                        context_query = f"{current_query}\n基于之前的分析: {intermediate_results['data_analysis']}"
                        result = self.visualization_agent.create_visualization(context_query)
                    else:
                        result = self.visualization_agent.create_visualization(current_query)
                    
                    intermediate_results["visualization_description"] = result.get("description", "")
                    
                    # 如果有可视化结果，保存它
                    if result.get("visualization"):
                        visualization = result.get("visualization")
                    source_agent = "visualization"
                else:
                    intermediate_results["visualization_error"] = "没有可用数据进行可视化"
            
            else:  # 默认使用Router的回答
                intermediate_results["router_response"] = execution_plan
                source_agent = "router"
            
            # 更新当前结果，用于传递给下一个专家
            if result and isinstance(result, str):
                final_response += f"\n\n[{expert_name}]: {result}"
            elif result and isinstance(result, dict) and "response" in result:
                final_response += f"\n\n[{expert_name}]: {result['response']}"
        
        # 整合最终结果
        if not final_response and "router_response" in intermediate_results:
            final_response = intermediate_results["router_response"]
        
        # 移除多余的前导换行符
        final_response = final_response.lstrip("\n")
        
        return {
            "response": final_response,
            "source": source_agent,
            "visualization": visualization,
            "code_output": code_output,
            "intermediate_results": intermediate_results
        }
    
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