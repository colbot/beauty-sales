"""
可视化Agent
负责生成数据可视化图表，支持多种图表类型和自定义选项
"""
import os
import logging
import io
import base64
from typing import Dict, List, Any, Union, Optional
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置matplotlib中文字体支持
def setup_chinese_font():
    try:
        # 强制使用Agg后端，确保无GUI环境也能生成图表
        plt.switch_backend('Agg')
        
        # 构建与平台无关的路径，直接加载我们的中文字体
        project_font_path = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                'app', 'static', 'font', 'chinese_font.ttf'
            )
        )
        
        logger.info(f"检查字体文件路径: {project_font_path}")
        
        # 检查项目字体是否存在
        if os.path.exists(project_font_path):
            try:
                logger.info(f"加载项目目录字体: {project_font_path}")
                mpl.font_manager.fontManager.addfont(project_font_path)
                font_prop = mpl.font_manager.FontProperties(fname=project_font_path)
                font_name = font_prop.get_name()
                
                plt.rcParams['font.sans-serif'] = [font_name, 'SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
                
                logger.info(f"成功加载中文字体: {font_name}")
                return  # 字体加载成功，提前返回
            except Exception as e:
                logger.warning(f"加载中文字体失败: {e}")
        else:
            logger.warning(f"中文字体文件不存在: {project_font_path}")
        
        # 如果项目字体未找到或加载失败，使用备用策略
        logger.warning("未找到或无法加载中文字体，启用备用方案")
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 将某些常用中文替换为英文，避免乱码
        global font_replace_map
        font_replace_map = {
            '用户': 'User',
            '评分': 'Rating',
            '销售额': 'Sales',
            '数量': 'Quantity',
            '分类': 'Category',
            '价格': 'Price',
            '时间': 'Time',
            '日期': 'Date',
            '产品': 'Product',
            '品牌': 'Brand',
            '渠道': 'Channel',
            '分布': 'Distribution',
            '统计': 'Statistics',
            '月份': 'Month',
            '分析': 'Analysis',
            '美妆': 'Beauty',
            '区域': 'Region',
            '客户': 'Customer',
            '订单': 'Order',
            '总计': 'Total'
        }
        
        # 记录字体映射，供后续使用
        logger.info("已配置中文到英文的映射以避免字体问题")
    except Exception as e:
        logger.error(f"配置中文字体时出错: {e}", exc_info=True)
        # 确保我们有一个基本可用的后端
        plt.switch_backend('Agg')

# 初始化字体替换映射
font_replace_map = {}

# 执行字体设置
setup_chinese_font()

# 配置默认绘图风格
plt.style.use('seaborn-v0_8-whitegrid')

@register_tool('generate_visualization')
class GenerateVisualizationTool(BaseTool):
    """数据可视化生成工具"""
    
    description = '生成数据可视化图表'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': '可视化需求描述',
        'required': True
    }, {
        'name': 'chart_type',
        'type': 'string',
        'description': '图表类型，如bar, line, pie, scatter, heatmap等',
        'required': False
    }]
    
    def __init__(self, visualization_agent):
        self.visualization_agent = visualization_agent
        super().__init__()
    
    def call(self, params: str, **kwargs) -> str:
        """生成数据可视化"""
        try:
            params_dict = json.loads(params)
            query = params_dict['query']
            chart_type = params_dict.get('chart_type')
            
            if not self.visualization_agent.current_data is not None:
                return json.dumps({
                    "success": False,
                    "error": "没有可用的数据进行可视化"
                }, ensure_ascii=False)
                
            result = self.visualization_agent._generate_visualization(
                self.visualization_agent.current_data, 
                query, 
                chart_type
            )
            
            # 返回结果的JSON字符串
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"生成可视化错误: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)

class VisualizationAgent:
    """可视化Agent类，负责生成数据可视化图表"""
    
    def __init__(self):
        """初始化可视化Agent"""
        # 获取API密钥和模型名称
        api_key = os.getenv("QWEN_API_KEY")
        model_name = os.getenv("QWEN_MODEL", "qwen-max")
        
        # 基础LLM配置
        self.llm_cfg = {
            'model': model_name,
            'model_server': 'dashscope',
            'api_key': api_key,
        }

        # 创建可视化Assistant实例
        self.visualization_assistant = Assistant(
            llm=self.llm_cfg,
            name='数据可视化专家',
            description='专精于将美妆销售数据转化为直观的图表，突出关键趋势和洞察',
            function_list=['generate_visualization', 'code_interpreter']
        )
        
        # 当前数据
        self.current_data = None
        
        # 支持的图表类型
        self.supported_chart_types = {
            "bar": "柱状图",
            "line": "折线图",
            "pie": "饼图",
            "scatter": "散点图",
            "heatmap": "热力图",
            "box": "箱线图",
            "histogram": "直方图",
            "area": "面积图",
            "stacked_bar": "堆叠柱状图",
            "bubble": "气泡图",
            "radar": "雷达图",
            "treemap": "树图"
        }
        
        # 可视化历史
        self.visualization_history = []
    
    def create_visualization(self, query: str, chart_type: Optional[str] = None) -> Dict[str, Any]:
        """对外接口，创建数据可视化
        
        参数:
            query: 用户可视化需求
            chart_type: 可选的图表类型
            
        返回:
            可视化结果
        """
        if self.current_data is None:
            return {
                "success": False,
                "error": "没有可用的数据进行可视化",
                "visualization": None,
                "description": "请先加载数据后再尝试生成可视化"
            }
            
        return self._generate_visualization(self.current_data, query, chart_type)
    
    def _generate_visualization(self, data: Union[pd.DataFrame, Dict, List], query: str, 
                              chart_type: Optional[str] = None) -> Dict[str, Any]:
        """生成数据可视化
        
        参数:
            data: 要可视化的数据，可以是DataFrame、字典或列表
            query: 用户查询或可视化请求
            chart_type: 可选的指定图表类型
            
        返回:
            可视化结果
        """
        try:
            # 确保数据是DataFrame格式
            if isinstance(data, dict) or isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            # 注意：不直接使用code_interpreter，它会在LLM调用时被正确使用
            # 本地保存一份数据用于后续操作和生成备用图表
            self.current_data = df
            
            # 构建系统提示
            system_prompt = """你是一位专业的数据可视化专家，精通美妆销售数据的可视化表达。
请使用提供的Python代码解释器工具来根据用户需求创建可视化图表。

数据已经加载为名为df的pandas DataFrame，你可以直接使用它。

可视化时请遵循以下原则：
1. 根据数据特点和用户需求选择最合适的图表类型
2. 使用matplotlib、seaborn或plotly创建专业且美观的图表
3. 确保图表清晰易读，包含必要的标题、标签和图例
4. 针对美妆销售数据设计合适的配色方案和样式
5. 突出显示关键数据点和趋势
6. 图表应该传达清晰的业务洞察

请先分析数据特点和用户需求，然后编写可视化代码，最后提供简短的图表解释。"""

            # 获取数据基本信息
            data_info = f"""
数据基本信息:
- 行数: {len(df)}
- 列数: {len(df.columns)}
- 列名: {', '.join(df.columns)}
- 数据类型: {', '.join([f"{col}({str(df[col].dtype)})" for col in df.columns])}
"""
            # 构建消息
            chart_type_info = ""
            if chart_type:
                chart_name = self.supported_chart_types.get(chart_type, chart_type)
                chart_type_info = f"\n请使用 {chart_name} 类型的图表。"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{data_info}\n\n用户可视化需求: {query}{chart_type_info}"}
            ]
            
            # 使用LLM生成可视化代码
            visualization_base64 = None
            code_output = ""
            text_response = ""
            
            for response in self.visualization_assistant.run(messages=messages):
                if "content" in response[0]:
                    text_response += response[0]["content"]
                if "tool_calls" in response[0]:
                    for tool_call in response[0]["tool_calls"]:
                        if tool_call["type"] == "code_interpreter":
                            code_output = tool_call.get("output", "")
                            # 检查是否有可视化输出
                            if "image/png" in code_output:
                                visualization_base64 = code_output.get("image/png")
            
            # 如果没有生成可视化，尝试推断并生成一个默认图表
            if not visualization_base64:
                logger.warning("LLM未生成可视化，使用默认图表生成")
                visualization_base64 = self._generate_default_chart(df, chart_type)
                if not visualization_base64:
                    return {
                        "success": False,
                        "error": "无法生成可视化，数据可能不适合可视化或请求不明确",
                        "visualization": None
                    }
            
            # 生成图表描述
            chart_description = self._generate_chart_description(df, query, text_response)
            
            # 记录可视化历史
            visualization_record = {
                "query": query,
                "chart_type": chart_type,
                "description": chart_description,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            self.visualization_history.append(visualization_record)
            
            return {
                "success": True,
                "visualization": visualization_base64,
                "description": chart_description,
                "code_output": code_output
            }
            
        except Exception as e:
            logger.error(f"生成可视化时发生错误: {e}")
            return {
                "success": False,
                "error": f"生成可视化失败: {e}",
                "visualization": None
            }
    
    def _generate_default_chart(self, df: pd.DataFrame, chart_type: Optional[str] = None) -> Optional[str]:
        """生成默认图表
        
        参数:
            df: 数据
            chart_type: 图表类型
            
        返回:
            Base64编码的图表图像
        """
        try:
            if len(df) == 0 or len(df.columns) == 0:
                return None
            
            # 强制使用Agg后端确保无GUI环境下也能工作
            plt.switch_backend('Agg')
            
            # 处理列名中的中文，避免乱码
            column_map = {}
            translated_df = df.copy()
            for col in df.columns:
                # 如果列名含有中文，转为英文或拼音表示
                if any('\u4e00' <= c <= '\u9fff' for c in col):
                    # 简单替换一些常见词汇
                    new_col = col
                    for zh, en in {
                        '用户': 'User', '客户': 'Customer', '销售': 'Sales', 
                        '价格': 'Price', '数量': 'Quantity', '产品': 'Product',
                        '品牌': 'Brand', '类别': 'Category', '日期': 'Date',
                        '时间': 'Time', '评分': 'Rating', '地区': 'Region',
                        '月份': 'Month', '年': 'Year', '季度': 'Quarter'
                    }.items():
                        new_col = new_col.replace(zh, en)
                    
                    # 如果还有中文字符，用col_{index}替代
                    if any('\u4e00' <= c <= '\u9fff' for c in new_col):
                        new_col = f"col_{df.columns.get_loc(col)}"
                    
                    column_map[col] = new_col
                    translated_df = translated_df.rename(columns={col: new_col})
            
            # 记录列名转换
            if column_map:
                logger.info(f"列名转换映射: {column_map}")
            
            plt.figure(figsize=(10, 6))
            
            # 推断最适合的图表类型
            if not chart_type:
                numeric_cols = translated_df.select_dtypes(include=['int', 'float']).columns
                categorical_cols = translated_df.select_dtypes(include=['object']).columns
                
                if len(numeric_cols) >= 2:
                    # 两个或更多数值列，使用散点图
                    chart_type = "scatter"
                elif len(numeric_cols) == 1 and len(categorical_cols) >= 1:
                    # 一个数值列和一个分类列，使用柱状图
                    chart_type = "bar"
                elif len(categorical_cols) >= 2:
                    # 两个分类列，使用热力图或计数柱状图
                    chart_type = "count"
                else:
                    # 默认使用柱状图
                    chart_type = "bar"
            
            # 根据图表类型生成图表
            if chart_type == "bar":
                # 使用第一个分类列和第一个数值列
                cat_col = translated_df.select_dtypes(include=['object']).columns[0] if len(translated_df.select_dtypes(include=['object']).columns) > 0 else translated_df.columns[0]
                num_col = translated_df.select_dtypes(include=['int', 'float']).columns[0] if len(translated_df.select_dtypes(include=['int', 'float']).columns) > 0 else translated_df.columns[1] if len(translated_df.columns) > 1 else translated_df.columns[0]
                
                # 如果分类值太多，只取前10个
                if len(translated_df[cat_col].unique()) > 10:
                    top_values = translated_df.groupby(cat_col)[num_col].sum().nlargest(10).index
                    plot_df = translated_df[translated_df[cat_col].isin(top_values)]
                else:
                    plot_df = translated_df
                
                # 绘制柱状图
                sns.barplot(x=cat_col, y=num_col, data=plot_df)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # 添加标题和标签，确保不使用中文
                plt.title(f"Bar Chart: {num_col} by {cat_col}")
                plt.xlabel(cat_col)
                plt.ylabel(num_col)
                
            elif chart_type == "line":
                # 使用第一个时间/序号列和第一个数值列
                if any(pd.api.types.is_datetime64_any_dtype(translated_df[col]) for col in translated_df.columns):
                    time_col = [col for col in translated_df.columns if pd.api.types.is_datetime64_any_dtype(translated_df[col])][0]
                else:
                    time_col = translated_df.select_dtypes(include=['int', 'float']).columns[0] if len(translated_df.select_dtypes(include=['int', 'float']).columns) > 0 else translated_df.columns[0]
                
                num_col = translated_df.select_dtypes(include=['int', 'float']).columns[0] if len(translated_df.select_dtypes(include=['int', 'float']).columns) > 0 else translated_df.columns[1] if len(translated_df.columns) > 1 else translated_df.columns[0]
                
                # 绘制折线图
                plt.plot(translated_df[time_col], translated_df[num_col])
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # 添加标题和标签，确保不使用中文
                plt.title(f"Line Chart: {num_col} over {time_col}")
                plt.xlabel(time_col)
                plt.ylabel(num_col)
                
            elif chart_type == "pie":
                # 使用第一个分类列和第一个数值列
                cat_col = translated_df.select_dtypes(include=['object']).columns[0] if len(translated_df.select_dtypes(include=['object']).columns) > 0 else translated_df.columns[0]
                num_col = translated_df.select_dtypes(include=['int', 'float']).columns[0] if len(translated_df.select_dtypes(include=['int', 'float']).columns) > 0 else translated_df.columns[1] if len(translated_df.columns) > 1 else None
                
                # 如果有数值列，按数值聚合；否则按计数
                if num_col:
                    pie_data = translated_df.groupby(cat_col)[num_col].sum()
                else:
                    pie_data = translated_df[cat_col].value_counts()
                
                # 如果分类太多，只显示前7个和"其他"
                if len(pie_data) > 7:
                    top_categories = pie_data.nlargest(6)
                    others_sum = pie_data[~pie_data.index.isin(top_categories.index)].sum()
                    plot_data = pd.concat([top_categories, pd.Series({"Others": others_sum})])
                else:
                    plot_data = pie_data
                
                # 绘制饼图
                plt.pie(plot_data, labels=plot_data.index, autopct='%1.1f%%')
                plt.axis('equal')
                
                # 添加标题，确保不使用中文
                plt.title(f"Pie Chart: Distribution of {cat_col}")
                
            elif chart_type == "scatter":
                # 使用前两个数值列
                num_cols = translated_df.select_dtypes(include=['int', 'float']).columns
                if len(num_cols) >= 2:
                    x_col, y_col = num_cols[0], num_cols[1]
                    
                    # 绘制散点图
                    plt.scatter(translated_df[x_col], translated_df[y_col])
                    
                    # 添加标题和标签，确保不使用中文
                    plt.title(f"Scatter Plot: {y_col} vs {x_col}")
                    plt.xlabel(x_col)
                    plt.ylabel(y_col)
                    
                else:
                    # 如果没有足够的数值列，回退到柱状图
                    return self._generate_default_chart(df, "bar")
                
            elif chart_type == "heatmap":
                # 使用前两个分类列创建交叉表
                cat_cols = translated_df.select_dtypes(include=['object']).columns
                if len(cat_cols) >= 2:
                    x_col, y_col = cat_cols[0], cat_cols[1]
                    
                    # 找一个数值列作为值，如果没有则用计数
                    num_cols = translated_df.select_dtypes(include=['int', 'float']).columns
                    if len(num_cols) > 0:
                        val_col = num_cols[0]
                        cross_tab = pd.crosstab(translated_df[x_col], translated_df[y_col], values=translated_df[val_col], aggfunc='mean')
                    else:
                        cross_tab = pd.crosstab(translated_df[x_col], translated_df[y_col])
                    
                    # 如果交叉表太大，只取前10行和前10列
                    if cross_tab.shape[0] > 10 or cross_tab.shape[1] > 10:
                        cross_tab = cross_tab.iloc[:10, :10]
                    
                    # 绘制热力图
                    sns.heatmap(cross_tab, annot=True, cmap="YlGnBu")
                    plt.tight_layout()
                    
                    # 添加标题，确保不使用中文
                    plt.title(f"Heatmap: {x_col} vs {y_col}")
                    
                else:
                    # 如果没有足够的分类列，回退到柱状图
                    return self._generate_default_chart(df, "bar")
                
            elif chart_type == "count":
                # 使用第一个分类列
                cat_col = translated_df.select_dtypes(include=['object']).columns[0] if len(translated_df.select_dtypes(include=['object']).columns) > 0 else translated_df.columns[0]
                
                # 如果分类值太多，只取前10个
                value_counts = translated_df[cat_col].value_counts()
                if len(value_counts) > 10:
                    plot_data = value_counts.nlargest(10)
                else:
                    plot_data = value_counts
                
                # 绘制计数柱状图
                plt.bar(plot_data.index, plot_data.values)
                plt.xticks(rotation=45, ha='right')
                plt.ylabel('Count')
                plt.tight_layout()
                
                # 添加标题，确保不使用中文
                plt.title(f"Count Chart: Frequency of {cat_col}")
            
            else:
                # 不支持的图表类型，使用柱状图
                return self._generate_default_chart(df, "bar")
            
            # 将图表转换为Base64
            buff = io.BytesIO()
            plt.savefig(buff, format='png', dpi=100)
            plt.close()
            buff.seek(0)
            img_str = base64.b64encode(buff.read()).decode()
            
            return img_str
            
        except Exception as e:
            logger.error(f"生成默认图表时发生错误: {e}")
            return None
    
    def _generate_chart_description(self, df: pd.DataFrame, query: str, llm_response: str) -> str:
        """生成图表描述
        
        参数:
            df: 数据
            query: 用户查询
            llm_response: LLM的回复
            
        返回:
            图表描述
        """
        # 首先尝试从LLM响应中提取描述
        if llm_response:
            # 过滤掉代码块
            lines = []
            in_code_block = False
            for line in llm_response.split('\n'):
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                if not in_code_block:
                    lines.append(line)
            
            filtered_response = '\n'.join(lines).strip()
            if filtered_response:
                return filtered_response
        
        # 如果没有从LLM响应中获取描述，使用控制LLM生成一个
        try:
            system_prompt = """你是一位数据可视化解读专家，擅长根据数据和图表类型提供简洁的图表描述。
请根据提供的数据信息和用户查询，生成一段简明扼要的图表描述。
描述应该简洁明了，突出图表中的关键趋势和洞察。
不要超过3句话。不要使用"此图表展示了"等表述。"""
            
            # 准备数据摘要
            data_summary = {
                "行数": len(df),
                "列数": len(df.columns),
                "列名": list(df.columns)
            }
            
            # 添加数值列统计信息
            numeric_cols = df.select_dtypes(include=['int', 'float']).columns
            if len(numeric_cols) > 0:
                data_summary["数值统计"] = {}
                for col in numeric_cols[:3]:  # 最多取前3个数值列
                    data_summary["数值统计"][col] = {
                        "均值": float(df[col].mean()),
                        "最大值": float(df[col].max()),
                        "最小值": float(df[col].min())
                    }
            
            # 添加分类列统计信息
            categorical_cols = df.select_dtypes(include=['object']).columns
            if len(categorical_cols) > 0:
                data_summary["分类统计"] = {}
                for col in categorical_cols[:2]:  # 最多取前2个分类列
                    top_values = df[col].value_counts().nlargest(3)
                    data_summary["分类统计"][col] = {val: count for val, count in zip(top_values.index, top_values.values)}
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"数据摘要: {json.dumps(data_summary, ensure_ascii=False)}\n\n用户查询: {query}\n\n请根据这些信息生成一个简洁的图表描述。"}
            ]
            
            # 获取描述
            description = ""
            for response in self.visualization_assistant.run(messages=messages):
                if "content" in response[0]:
                    description += response[0]["content"]
            
            return description if description else "此图表展示了数据的可视化分析结果。"
            
        except Exception as e:
            logger.error(f"生成图表描述时发生错误: {e}")
            return "此图表展示了数据的可视化分析结果。"
    
    def get_supported_chart_types(self) -> Dict[str, str]:
        """获取支持的图表类型
        
        返回:
            图表类型字典
        """
        return self.supported_chart_types
    
    def get_visualization_history(self) -> List[Dict[str, Any]]:
        """获取可视化历史记录
        
        返回:
            可视化历史记录列表
        """
        return self.visualization_history 