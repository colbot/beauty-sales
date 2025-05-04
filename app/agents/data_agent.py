"""
数据处理Agent
负责对销售数据进行处理、分析和统计，提供数据洞察
"""
import os
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Union, Optional
from qwen_agent.agents import Assistant
from qwen_agent.tools import CodeInterpreter

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataAgent:
    """数据处理Agent类，处理美妆销售数据分析"""
    
    def __init__(self):
        """初始化数据处理Agent"""
        # 获取API密钥和模型名称
        api_key = os.getenv("QWEN_API_KEY")
        model_name = os.getenv("QWEN_MODEL", "qwen-max")
        
        # 基础LLM配置
        self.llm_cfg = {
            'model': model_name,
            'model_server': 'dashscope',
            'api_key': api_key,
        }
        
        # 创建代码解释器工具
        self.code_interpreter = CodeInterpreter()
        
        # 创建数据处理Assistant实例
        self.data_agent = Assistant(
            llm=self.llm_cfg,
            name='美妆数据分析专家',
            description='专精于美妆行业销售数据分析，能够提供数据洞察和业务建议',
            tools=[self.code_interpreter]
        )
        
        # 当前加载的数据
        self.current_data = None
        self.data_source = None
        
        # 分析历史
        self.analysis_history = []
    
    def load_data(self, data_path: str) -> bool:
        """加载数据文件
        
        参数:
            data_path: 数据文件路径
            
        返回:
            是否成功加载
        """
        try:
            file_ext = os.path.splitext(data_path)[1].lower()
            
            if file_ext == '.csv':
                self.current_data = pd.read_csv(data_path)
            elif file_ext in ['.xlsx', '.xls']:
                self.current_data = pd.read_excel(data_path)
            else:
                logger.error(f"不支持的文件格式: {file_ext}")
                return False
            
            self.data_source = data_path
            logger.info(f"成功加载数据: {data_path}，共 {len(self.current_data)} 行")
            
            # 设置代码解释器的变量
            self.code_interpreter.set_variable("df", self.current_data)
            
            return True
            
        except Exception as e:
            logger.error(f"加载数据时发生错误: {e}")
            return False
    
    def get_data_summary(self) -> Dict[str, Any]:
        """获取当前数据摘要
        
        返回:
            数据摘要信息字典
        """
        if self.current_data is None:
            return {"error": "未加载数据"}
        
        try:
            summary = {
                "数据源": self.data_source,
                "行数": len(self.current_data),
                "列数": len(self.current_data.columns),
                "列名": list(self.current_data.columns),
                "数据类型": {col: str(dtype) for col, dtype in self.current_data.dtypes.items()},
                "缺失值": {col: int(self.current_data[col].isna().sum()) for col in self.current_data.columns},
                "数值列统计": {}
            }
            
            # 计算数值列的统计信息
            numeric_cols = self.current_data.select_dtypes(include=['int', 'float']).columns
            for col in numeric_cols:
                summary["数值列统计"][col] = {
                    "均值": float(self.current_data[col].mean()),
                    "中位数": float(self.current_data[col].median()),
                    "最大值": float(self.current_data[col].max()),
                    "最小值": float(self.current_data[col].min()),
                    "标准差": float(self.current_data[col].std())
                }
            
            # 计算分类列的统计信息
            categorical_cols = self.current_data.select_dtypes(include=['object']).columns
            summary["分类列统计"] = {}
            for col in categorical_cols:
                if len(self.current_data[col].unique()) < 20:  # 只显示不超过20个唯一值的分类列
                    summary["分类列统计"][col] = self.current_data[col].value_counts().to_dict()
            
            return summary
            
        except Exception as e:
            logger.error(f"生成数据摘要时发生错误: {e}")
            return {"error": f"生成数据摘要失败: {e}"}
    
    def run_analysis(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """运行数据分析
        
        参数:
            query: 用户查询
            context: 对话上下文
            
        返回:
            分析结果
        """
        if self.current_data is None:
            return {"error": "未加载数据，请先加载数据文件"}
        
        try:
            # 构建系统提示
            system_prompt = """你是一位美妆行业的数据分析专家，精通数据处理和可视化。
请使用提供的Python代码解释器工具来回答用户关于美妆销售数据的问题。

数据已经加载为名为df的pandas DataFrame，你可以直接使用它。

分析时请遵循以下原则：
1. 优先使用pandas、numpy进行数据操作和统计分析
2. 使用matplotlib、seaborn或plotly生成可视化图表
3. 确保代码干净、高效并有注释
4. 分析需要关注美妆行业的特性，如产品类别、季节性趋势、促销效果等
5. 结果应该包含商业洞察和建议，而不仅仅是数据描述

请先思考分析步骤，然后编写代码，最后总结发现的洞察和建议。"""
            
            # 获取数据基本信息
            data_info = f"""
数据基本信息:
- 数据源: {self.data_source}
- 行数: {len(self.current_data)}
- 列数: {len(self.current_data.columns)}
- 列名: {', '.join(self.current_data.columns)}
"""
            
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{data_info}\n\n用户问题: {query}"}
            ]
            
            # 如果有上下文，添加到消息中
            if context:
                context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context])
                messages.insert(1, {"role": "system", "content": f"以下是之前的对话上下文:\n{context_str}"})
            
            # 使用LLM生成分析
            code_output = ""
            text_response = ""
            visualization = None
            
            for response in self.data_agent.run(messages=messages):
                if "content" in response:
                    text_response += response["content"]
                if "tool_calls" in response:
                    for tool_call in response["tool_calls"]:
                        if tool_call["type"] == "code_interpreter":
                            code_output = tool_call.get("output", "")
                            # 检查是否有可视化输出
                            if "image/png" in code_output:
                                visualization = code_output.get("image/png")
            
            # 记录分析历史
            analysis_record = {
                "query": query,
                "result": text_response,
                "code_output": code_output,
                "visualization": visualization is not None,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            self.analysis_history.append(analysis_record)
            
            return {
                "response": text_response,
                "code_output": code_output,
                "visualization": visualization,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"执行数据分析时发生错误: {e}")
            return {"error": f"数据分析失败: {e}", "success": False}
    
    def get_analysis_history(self) -> List[Dict[str, Any]]:
        """获取分析历史记录
        
        返回:
            分析历史记录列表
        """
        return self.analysis_history
    
    def preprocess_data(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """预处理数据
        
        参数:
            operations: 预处理操作列表，每个操作是一个字典
                {
                    "type": "操作类型", # fill_na, drop_na, drop_duplicates, filter, etc.
                    "params": {...} # 操作参数
                }
            
        返回:
            处理结果
        """
        if self.current_data is None:
            return {"error": "未加载数据，请先加载数据文件"}
        
        try:
            # 创建数据副本，避免修改原始数据
            processed_df = self.current_data.copy()
            results = []
            
            for op in operations:
                op_type = op.get("type")
                params = op.get("params", {})
                
                if op_type == "fill_na":
                    # 填充缺失值
                    column = params.get("column")
                    value = params.get("value")
                    method = params.get("method", "value")  # value, mean, median, mode, ffill, bfill
                    
                    if column and column in processed_df.columns:
                        if method == "value" and value is not None:
                            processed_df[column] = processed_df[column].fillna(value)
                        elif method == "mean":
                            processed_df[column] = processed_df[column].fillna(processed_df[column].mean())
                        elif method == "median":
                            processed_df[column] = processed_df[column].fillna(processed_df[column].median())
                        elif method == "mode":
                            processed_df[column] = processed_df[column].fillna(processed_df[column].mode()[0])
                        elif method in ["ffill", "bfill"]:
                            processed_df[column] = processed_df[column].fillna(method=method)
                        
                        results.append(f"列 '{column}' 的缺失值已使用 {method} 方法填充")
                    else:
                        results.append(f"错误: 列 '{column}' 不存在")
                
                elif op_type == "drop_na":
                    # 删除缺失值
                    column = params.get("column")
                    if column and column in processed_df.columns:
                        processed_df = processed_df.dropna(subset=[column])
                        results.append(f"已删除列 '{column}' 中包含缺失值的行")
                    else:
                        subset = params.get("subset", [])
                        if subset:
                            processed_df = processed_df.dropna(subset=subset)
                            results.append(f"已删除列 {subset} 中包含缺失值的行")
                        else:
                            processed_df = processed_df.dropna()
                            results.append("已删除所有包含缺失值的行")
                
                elif op_type == "drop_duplicates":
                    # 删除重复行
                    subset = params.get("subset", None)
                    keep = params.get("keep", "first")
                    
                    if subset:
                        processed_df = processed_df.drop_duplicates(subset=subset, keep=keep)
                        results.append(f"已根据列 {subset} 删除重复行，保留 {keep}")
                    else:
                        processed_df = processed_df.drop_duplicates(keep=keep)
                        results.append(f"已删除所有重复行，保留 {keep}")
                
                elif op_type == "filter":
                    # 过滤数据
                    column = params.get("column")
                    condition = params.get("condition")
                    value = params.get("value")
                    
                    if column and column in processed_df.columns and condition and value is not None:
                        if condition == "eq":
                            processed_df = processed_df[processed_df[column] == value]
                        elif condition == "ne":
                            processed_df = processed_df[processed_df[column] != value]
                        elif condition == "gt":
                            processed_df = processed_df[processed_df[column] > value]
                        elif condition == "lt":
                            processed_df = processed_df[processed_df[column] < value]
                        elif condition == "ge":
                            processed_df = processed_df[processed_df[column] >= value]
                        elif condition == "le":
                            processed_df = processed_df[processed_df[column] <= value]
                        elif condition == "in":
                            if isinstance(value, list):
                                processed_df = processed_df[processed_df[column].isin(value)]
                        elif condition == "not_in":
                            if isinstance(value, list):
                                processed_df = processed_df[~processed_df[column].isin(value)]
                        elif condition == "contains":
                            processed_df = processed_df[processed_df[column].str.contains(str(value), na=False)]
                        
                        results.append(f"已根据条件 '{column} {condition} {value}' 过滤数据")
                    else:
                        results.append(f"错误: 过滤参数不完整或列不存在")
                
                elif op_type == "sort":
                    # 排序数据
                    column = params.get("column")
                    ascending = params.get("ascending", True)
                    
                    if column and column in processed_df.columns:
                        processed_df = processed_df.sort_values(by=column, ascending=ascending)
                        direction = "升序" if ascending else "降序"
                        results.append(f"已根据列 '{column}' {direction}排序")
                    else:
                        results.append(f"错误: 列 '{column}' 不存在")
                
                elif op_type == "rename":
                    # 重命名列
                    mapping = params.get("mapping", {})
                    if mapping:
                        processed_df = processed_df.rename(columns=mapping)
                        results.append(f"已重命名列: {mapping}")
                    else:
                        results.append("错误: 未提供列映射")
                
                elif op_type == "create":
                    # 创建新列
                    column = params.get("column")
                    expression = params.get("expression")
                    
                    if column and expression:
                        try:
                            # 使用代码解释器执行表达式
                            self.code_interpreter.set_variable("df", processed_df)
                            self.code_interpreter.run(f"df['{column}'] = {expression}")
                            processed_df = self.code_interpreter.get_variable("df")
                            results.append(f"已创建新列 '{column}' 基于表达式 '{expression}'")
                        except Exception as e:
                            results.append(f"创建列 '{column}' 时发生错误: {e}")
                    else:
                        results.append("错误: 列名或表达式缺失")
                
                elif op_type == "convert_type":
                    # 转换数据类型
                    column = params.get("column")
                    data_type = params.get("data_type")
                    
                    if column and column in processed_df.columns and data_type:
                        try:
                            processed_df[column] = processed_df[column].astype(data_type)
                            results.append(f"已将列 '{column}' 转换为 {data_type} 类型")
                        except Exception as e:
                            results.append(f"转换列 '{column}' 类型时发生错误: {e}")
                    else:
                        results.append(f"错误: 列不存在或未指定类型")
                
                else:
                    results.append(f"不支持的操作类型: {op_type}")
            
            # 更新当前数据
            self.current_data = processed_df
            self.code_interpreter.set_variable("df", processed_df)
            
            return {
                "success": True,
                "message": "数据预处理完成",
                "operations_results": results,
                "rows_count": len(processed_df),
                "columns_count": len(processed_df.columns)
            }
            
        except Exception as e:
            logger.error(f"预处理数据时发生错误: {e}")
            return {
                "success": False,
                "error": f"数据预处理失败: {e}"
            }
    
    def extract_insights(self, data_summary: Dict[str, Any]) -> List[str]:
        """从数据摘要中提取业务洞察
        
        参数:
            data_summary: 数据摘要
            
        返回:
            洞察列表
        """
        try:
            if not data_summary or "error" in data_summary:
                return ["无法提取洞察: 数据摘要不完整或有错误"]
            
            # 构建提示
            system_prompt = """你是一位美妆行业的数据分析专家。
请分析提供的美妆销售数据摘要，提取关键业务洞察。
关注销售趋势、产品表现、客户行为模式等方面，提供有价值的业务观察。
提供3-5个最重要的洞察，每个洞察应该简洁明了并具有行业针对性。"""
            
            # 将数据摘要转换为文本
            summary_text = ""
            for key, value in data_summary.items():
                if isinstance(value, dict):
                    summary_text += f"{key}:\n"
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict):
                            summary_text += f"  {sub_key}:\n"
                            for k, v in sub_value.items():
                                summary_text += f"    {k}: {v}\n"
                        else:
                            summary_text += f"  {sub_key}: {sub_value}\n"
                else:
                    summary_text += f"{key}: {value}\n"
            
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下是美妆销售数据的摘要，请提取关键业务洞察:\n\n{summary_text}"}
            ]
            
            # 使用LLM生成洞察
            insights_text = ""
            for response in self.data_agent.run(messages=messages):
                if "content" in response:
                    insights_text += response["content"]
            
            # 分割洞察为列表
            insights_list = []
            for line in insights_text.split("\n"):
                line = line.strip()
                if line and (line.startswith("- ") or line.startswith("• ") or line.startswith("* ") or
                             line.startswith("1. ") or line.startswith("2. ") or line.startswith("3. ")):
                    # 删除项目符号
                    insight = line[2:].strip() if line[0] in ["-", "•", "*"] else line[3:].strip()
                    insights_list.append(insight)
            
            # 如果没有正确分割，返回整个文本
            if not insights_list and insights_text:
                insights_list = [insights_text]
            
            return insights_list
            
        except Exception as e:
            logger.error(f"提取业务洞察时发生错误: {e}")
            return [f"提取洞察过程中发生错误: {e}"]
    
    def generate_report(self, query: str) -> Dict[str, Any]:
        """生成数据分析报告
        
        参数:
            query: 用户请求的报告主题
            
        返回:
            报告内容
        """
        if self.current_data is None:
            return {"error": "未加载数据，请先加载数据文件"}
        
        try:
            # 获取数据摘要
            data_summary = self.get_data_summary()
            
            # 提取洞察
            insights = self.extract_insights(data_summary)
            
            # 构建系统提示
            system_prompt = """你是一位美妆行业的数据分析专家，负责根据分析数据生成专业报告。
请根据用户的报告主题需求，使用提供的数据摘要和洞察，生成一份结构化的美妆销售数据分析报告。

报告应包括以下部分：
1. 报告摘要: 简要概述报告的主要发现和建议
2. 数据概览: 描述数据集的基本情况
3. 关键发现: 详细分析数据中的重要模式和趋势
4. 业务建议: 基于数据分析提供具体的业务改进建议
5. 后续分析方向: 提出可以进一步深入分析的领域

报告应专业、简洁，并针对美妆行业的特点提供有价值的见解。"""
            
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""请根据以下信息生成一份关于"{query}"的美妆销售数据分析报告：

数据摘要：
{data_summary}

数据洞察：
{insights}

请确保报告结构清晰，内容专业，并针对美妆行业特点提供有价值的见解和建议。
报告内容应直接可用，无需额外编辑。"""}
            ]
            
            # 使用LLM生成报告
            report_text = ""
            for response in self.data_agent.run(messages=messages):
                if "content" in response:
                    report_text += response["content"]
            
            # 记录报告生成
            report_record = {
                "topic": query,
                "report": report_text,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            self.analysis_history.append(report_record)
            
            return {
                "success": True,
                "topic": query,
                "report": report_text,
                "insights": insights,
                "data_summary": data_summary
            }
            
        except Exception as e:
            logger.error(f"生成报告时发生错误: {e}")
            return {"error": f"报告生成失败: {e}", "success": False} 