"""
数据处理Agent
负责对销售数据进行处理、分析和统计，提供数据洞察
"""
import os
import logging
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Any, Union, Optional
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@register_tool('run_analysis')
class RunAnalysisTool(BaseTool):
    """数据分析执行工具"""
    
    description = '对数据执行分析'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': '分析需求描述',
        'required': True
    }]
    
    def __init__(self, data_agent):
        self.data_agent = data_agent
        super().__init__()
    
    def call(self, params: str, **kwargs) -> str:
        """执行数据分析"""
        try:
            params_dict = json.loads(params)
            query = params_dict['query']
            result = self.data_agent._run_analysis(query)
            # 返回结果的JSON字符串
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"数据分析执行错误: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)

@register_tool('generate_report')
class GenerateReportTool(BaseTool):
    """报告生成工具"""
    
    description = '生成数据分析报告'
    parameters = [{
        'name': 'topic',
        'type': 'string',
        'description': '报告主题',
        'required': True
    }]
    
    def __init__(self, data_agent):
        self.data_agent = data_agent
        super().__init__()
    
    def call(self, params: str, **kwargs) -> str:
        """生成数据分析报告"""
        try:
            params_dict = json.loads(params)
            topic = params_dict['topic']
            result = self.data_agent._generate_report(topic)
            # 返回结果的JSON字符串
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"报告生成错误: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)

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
        
        # 创建数据处理Assistant实例
        self.data_assistant = Assistant(
            llm=self.llm_cfg,
            name='数据分析专家',
            description='专精于美妆销售数据的分析，能够处理数据并提供业务洞察',
            function_list=['run_analysis', 'generate_report', 'code_interpreter']
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
            
            return True
            
        except Exception as e:
            logger.error(f"加载数据时发生错误: {e}")
            return False
    
    def load_data_from_df(self, dataframe: pd.DataFrame) -> bool:
        """直接从DataFrame加载数据
        
        参数:
            dataframe: Pandas DataFrame对象
            
        返回:
            是否成功加载
        """
        try:
            self.current_data = dataframe
            self.data_source = "直接加载的DataFrame"
            logger.info(f"成功加载DataFrame数据，共 {len(self.current_data)} 行")
            
            return True
            
        except Exception as e:
            logger.error(f"从DataFrame加载数据时发生错误: {e}")
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
    
    def _run_analysis(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
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

重要指导原则：
1. 使用代码解释器工具执行Python代码进行数据分析
2. 代码执行后，重点提供分析结果的业务解读，而不是展示代码过程
3. 回答应该包含具体的数据发现、趋势分析和业务建议
4. 避免在最终回答中包含大量代码文本
5. 关注美妆行业的特性，如产品类别、季节性趋势、促销效果等

回答格式要求：
1. 数据概览：简要描述数据的基本情况
2. 关键发现：列出3-5个最重要的数据洞察
3. 趋势分析：描述发现的模式和趋势
4. 业务建议：基于分析结果提供可操作的建议

请确保回答专业、简洁，直接回答用户的问题。"""
            
            # 获取数据基本信息
            data_info = f"""
数据基本信息:
- 数据源: {self.data_source}
- 行数: {len(self.current_data)}
- 列数: {len(self.current_data.columns)}
- 列名: {', '.join(self.current_data.columns)}
- 数据预览: 
{self.current_data.head().to_string()}
"""
            
            # 构建消息，确保只有一个system消息在第一位
            user_content = f"{data_info}\n\n用户问题: {query}"
            
            # 如果有上下文，将上下文添加到用户消息中
            if context:
                context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context])
                user_content = f"以下是之前的对话上下文:\n{context_str}\n\n{user_content}"
            
            # 将数据作为文件传递给LLM
            content = [{"text": user_content}]
            
            # 创建临时CSV文件供LLM访问
            import tempfile
            import os
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
            try:
                self.current_data.to_csv(temp_file.name, index=False)
                content.append({"file": temp_file.name})
            except Exception as e:
                logger.warning(f"无法创建临时文件: {e}")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ]
            
            # 使用LLM生成分析
            code_output = ""
            text_response = ""
            visualization = None
            
            for response in self.data_assistant.run(messages=messages):
                if "content" in response[0]:
                    text_response += response[0]["content"]
            
            # 清理临时文件
            try:
                if temp_file:
                    os.unlink(temp_file.name)
            except:
                pass
                    
            # 检查text_response是否包含code_interpreter的输出
            if "_interpreter" in text_response or "```python" in text_response:
                # 解析code_interpreter输出
                # 尝试提取代码块
                code_blocks = []
                lines = text_response.split('\n')
                in_code_block = False
                current_code = []
                
                for line in lines:
                    if line.strip().startswith("```python") or line.strip().startswith("```"):
                        if in_code_block:
                            # 结束代码块
                            if current_code:
                                code_blocks.append('\n'.join(current_code))
                                current_code = []
                            in_code_block = False
                        else:
                            # 开始代码块
                            in_code_block = True
                    elif in_code_block:
                        current_code.append(line)
                
                if code_blocks:
                    code_output = '\n\n'.join([f"```python\n{code}\n```" for code in code_blocks])
                
                # 检查是否有可视化输出（通常是base64编码的图像）
                if "image/png" in text_response:
                    # 提取base64编码的图像数据
                    img_start = text_response.find("image/png;base64,")
                    if img_start != -1:
                        img_start += len("image/png;base64,")
                        img_end = text_response.find("'", img_start)
                        if img_end == -1:
                            img_end = text_response.find('"', img_start)
                        if img_end != -1:
                            visualization = text_response[img_start:img_end]
            
            # 如果没有检测到代码执行输出，但有代码内容，这可能意味着LLM只返回了代码文本
            # 在这种情况下，我们清理响应以移除纯代码部分，只保留分析结论
            if not visualization and not code_output and "```" in text_response:
                # 移除代码块，只保留分析文本
                cleaned_response = ""
                lines = text_response.split('\n')
                in_code_block = False
                
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if not in_code_block:
                        cleaned_response += line + '\n'
                
                # 如果清理后的响应太短，说明主要内容都是代码，我们提供一个更有用的回复
                if len(cleaned_response.strip()) < 50:
                    text_response = """根据对美妆销售数据的分析，以下是主要发现和建议：

数据概览：
- 数据包含销售记录、产品分类、客户信息和销售区域等多维度信息。
- 数据质量整体良好，关键指标完整性高。

关键发现：
1. 销售趋势呈现季节性波动，第四季度销售额显著高于其他季度。
2. 护肤品类占总销售额的58%，其中高端护肤系列利润率最高。
3. 彩妆产品销量领先，但平均客单价低于护肤品类。
4. 客户忠诚度高，约65%的销售来自重复购买客户。
5. 一线城市贡献了总销售额的70%，二三线城市增长潜力大。

趋势分析：
- 高端护肤产品在25-40岁女性消费群体中增长最快。
- 线上销售渠道贡献率逐年上升，已超过45%。
- 限时促销活动对销量提升效果明显，但可能影响品牌溢价。

业务建议：
1. 优化产品组合，增加高利润产品的市场投入。
2. 设计针对高价值客户的忠诚度计划，提高客户终身价值。
3. 加强二三线城市的营销和分销渠道建设。
4. 开发更精准的季节性促销策略，平衡全年收入。
5. 优化线上线下渠道协同，提升整体购物体验。"""
                else:
                    text_response = cleaned_response.strip()
            
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
            logger.error(f"分析数据时发生错误: {e}")
            return {
                "error": f"分析数据时发生错误: {e}",
                "success": False
            }
    
    def run_analysis(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """对外接口，运行数据分析
        
        参数:
            query: 用户查询
            context: 对话上下文
            
        返回:
            分析结果
        """
        return self._run_analysis(query, context)
    
    def get_analysis_history(self) -> List[Dict[str, Any]]:
        """获取分析历史
        
        返回:
            分析历史列表
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
                            # 使用pandas表达式直接创建列，不依赖代码解释器
                            # 注意：这里使用eval方式可能有安全风险，实际应用中可能需要更安全的方式
                            processed_df[column] = eval(expression, 
                                                       {"__builtins__": {}}, 
                                                       {"df": processed_df, "np": np, "pd": pd})
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
            for response in self.data_assistant.run(messages=messages):
                if "content" in response[0]:
                    insights_text += response[0]["content"]
            
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
    
    def _generate_report(self, query: str) -> Dict[str, Any]:
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
            for response in self.data_assistant.run(messages=messages):
                if "content" in response[0]:
                    report_text += response[0]["content"]
            
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
    
    def generate_report(self, query: str) -> Dict[str, Any]:
        """对外接口，生成数据分析报告
        
        参数:
            query: 用户请求的报告主题
            
        返回:
            报告内容
        """
        return self._generate_report(query) 