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
import traceback

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_numpy_types(obj):
    """转换numpy数据类型为Python原生类型，用于JSON序列化"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Period):
        return str(obj)
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

def safe_json_dumps(obj, **kwargs):
    """安全的JSON序列化，自动处理numpy类型"""
    converted_obj = convert_numpy_types(obj)
    return json.dumps(converted_obj, **kwargs)

# 配置matplotlib中文字体支持
def setup_chinese_font():
    try:
        # 强制使用Agg后端，确保无GUI环境也能生成图表
        plt.switch_backend('Agg')
        
        # 尝试多种方式设置中文字体
        font_set_success = False
        
        # 方法1：尝试使用系统字体
        try:
            import platform
            system = platform.system()
            
            if system == "Windows":
                # Windows系统的中文字体
                fonts_to_try = [
                    'Microsoft YaHei', 'SimHei', 'KaiTi', 'SimSun', 
                    'Microsoft JhengHei', 'PMingLiU', 'DFKai-SB'
                ]
            elif system == "Darwin":  # macOS
                # macOS系统的中文字体
                fonts_to_try = [
                    'PingFang SC', 'STHeiti', 'STKaiti', 'STSong', 
                    'Heiti TC', 'Songti TC', 'Apple LiGothic'
                ]
            else:  # Linux等
                # Linux系统的中文字体
                fonts_to_try = [
                    'WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 
                    'Droid Sans Fallback', 'Noto Sans CJK SC', 
                    'Source Han Sans CN', 'AR PL UMing CN'
                ]
            
            # 获取系统中可用的字体
            available_fonts = set([f.name for f in mpl.font_manager.fontManager.ttflist])
            
            # 尝试找到第一个可用的中文字体
            for font in fonts_to_try:
                if font in available_fonts:
                    plt.rcParams['font.sans-serif'] = [font, 'DejaVu Sans', 'sans-serif']
                    plt.rcParams['axes.unicode_minus'] = False
                    logger.info(f"成功设置中文字体: {font}")
                    font_set_success = True
                    break
                    
        except Exception as e:
            logger.warning(f"系统字体设置失败: {e}")
        
        # 方法2：如果系统字体失败，尝试下载和使用开源字体
        if not font_set_success:
            try:
                font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                       'app', 'static', 'fonts')
                os.makedirs(font_dir, exist_ok=True)
                
                # 设置字体文件路径
                font_file = os.path.join(font_dir, 'NotoSansCJK-Regular.ttc')
                
                # 如果字体文件不存在，尝试下载
                if not os.path.exists(font_file):
                    logger.info("尝试下载中文字体...")
                    try:
                        import urllib.request
                        # 使用Google Noto字体（开源且支持中文）
                        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTC/NotoSansCJK-Regular.ttc"
                        urllib.request.urlretrieve(font_url, font_file)
                        logger.info(f"成功下载字体到: {font_file}")
                    except Exception as download_error:
                        logger.warning(f"下载字体失败: {download_error}")
                        font_file = None
                
                # 如果有字体文件，加载它
                if font_file and os.path.exists(font_file):
                    # 添加字体到matplotlib
                    mpl.font_manager.fontManager.addfont(font_file)
                    
                    # 获取字体属性
                    font_prop = mpl.font_manager.FontProperties(fname=font_file)
                    font_name = font_prop.get_name()
                    
                    # 设置matplotlib参数
                    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans', 'sans-serif']
                    plt.rcParams['axes.unicode_minus'] = False
                    
                    logger.info(f"成功加载下载的字体: {font_name}")
                    font_set_success = True
                    
            except Exception as e:
                logger.warning(f"下载字体方案失败: {e}")
        
        # 方法3：使用内嵌字体替换方案
        if not font_set_success:
            logger.warning("所有字体设置方案都失败，使用文本替换方案")
            
            # 设置一个基本字体
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 扩展中文到英文的映射
            global font_replace_map
            font_replace_map = {
                # 通用词汇
                '用户': 'User', '客户': 'Customer', '销售': 'Sales', '销售额': 'Revenue',
                '数量': 'Quantity', '分类': 'Category', '品类': 'Category', 
                '价格': 'Price', '时间': 'Time', '日期': 'Date', '月份': 'Month',
                '产品': 'Product', '品牌': 'Brand', '渠道': 'Channel',
                '分布': 'Distribution', '统计': 'Statistics', '分析': 'Analysis',
                '美妆': 'Beauty', '区域': 'Region', '地区': 'Region',
                '订单': 'Order', '总计': 'Total', '合计': 'Total',
                
                # 业务专用词汇
                '护肤': 'Skincare', '彩妆': 'Makeup', '香水': 'Perfume',
                '洁面': 'Cleanser', '精华': 'Serum', '面霜': 'Cream',
                '口红': 'Lipstick', '眼影': 'Eyeshadow', '粉底': 'Foundation',
                '面膜': 'Mask', '乳液': 'Lotion', '爽肤水': 'Toner',
                
                # 单位和符号
                '万元': '10k CNY', '元': 'CNY', '件': 'pcs', '个': 'pcs',
                '天': 'days', '月': 'months', '年': 'years',
                '百分比': 'Percentage', '比例': 'Ratio', '占比': 'Proportion',
                
                # 数据分析和图表相关
                '数据': 'Data', '图表': 'Chart', '报告': 'Report', '指标': 'Metric',
                '展示': 'Display', '对比': 'Compare', '变化': 'Change',
                '趋势': 'Trend', '增长': 'Growth', '下降': 'Decline', '稳定': 'Stable',
                '波动': 'Fluctuation', '季节性': 'Seasonal',
                
                # 图表类型
                '趋势图': 'Trend Chart', '柱状图': 'Bar Chart', 
                '折线图': 'Line Chart', '饼图': 'Pie Chart',
                '散点图': 'Scatter Plot', '热力图': 'Heatmap',
                
                # 时间和统计词汇
                '销售趋势': 'Sales Trend', '每日': 'Daily', '每月': 'Monthly',
                '季度': 'Quarterly', '年度': 'Annual',
                '平均': 'Average', '最大': 'Max', '最小': 'Min',
                '中位数': 'Median', '标准差': 'StdDev',
                
                # 标点符号和常见字符
                '（': '(', '）': ')', '，': ',', '。': '.', '：': ':',
                '；': ';', '？': '?', '！': '!', '—': '-', '…': '...',
                '、': ',', '〈': '<', '〉': '>', '《': '<', '》': '>',
                '"': '"', '"': '"', ''': "'", ''': "'"
            }
            
            logger.info("已配置完整的中文到英文映射表，包含标点符号、业务术语等，共{}个词汇".format(len(font_replace_map)))
        
        # 清除matplotlib的字体缓存
        try:
            # 尝试不同版本的matplotlib字体缓存重建方法
            if hasattr(mpl.font_manager, '_rebuild'):
                mpl.font_manager._rebuild()
                logger.info("使用_rebuild()方法重建字体缓存")
            elif hasattr(mpl.font_manager, '_load_fontmanager'):
                mpl.font_manager._load_fontmanager()
                logger.info("使用_load_fontmanager()方法重新加载字体管理器")
            elif hasattr(mpl.font_manager, 'fontManager'):
                # 尝试重新初始化字体管理器
                mpl.font_manager.fontManager.__init__()
                logger.info("重新初始化字体管理器")
            else:
                # 如果以上方法都不可用，删除字体缓存文件
                import tempfile
                cache_dir = mpl.get_cachedir()
                fontlist_cache = os.path.join(cache_dir, 'fontlist-v*.json')
                import glob
                for cache_file in glob.glob(fontlist_cache):
                    try:
                        os.remove(cache_file)
                        logger.info(f"删除字体缓存文件: {cache_file}")
                    except Exception as e:
                        logger.warning(f"删除字体缓存文件失败: {e}")
                
                logger.info("通过删除缓存文件重建字体缓存")
        except Exception as cache_error:
            logger.warning(f"重建字体缓存失败，但这不会影响基本功能: {cache_error}")
        
        logger.info("中文字体配置完成")
        
    except Exception as e:
        logger.error(f"配置中文字体时出错: {e}", exc_info=True)
        # 确保我们有一个基本可用的配置
        plt.switch_backend('Agg')
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False


def apply_chinese_text_replacement(text):
    """应用中文文本替换"""
    if isinstance(text, str) and font_replace_map:
        for chinese, english in font_replace_map.items():
            text = text.replace(chinese, english)
    
    return text


def ensure_complete_text_replacement(fig):
    """确保图表中的所有文本都被正确替换"""
    try:
        # 处理主标题
        if fig._suptitle:
            title_text = fig._suptitle.get_text()
            new_title = apply_chinese_text_replacement(title_text)
            fig.suptitle(new_title, fontfamily='sans-serif')
        
        # 处理所有子图
        for ax in fig.get_axes():
            # 处理子图标题
            if ax.get_title():
                title = apply_chinese_text_replacement(ax.get_title())
                ax.set_title(title, fontfamily='sans-serif')
            
            # 处理X轴标签
            if ax.get_xlabel():
                xlabel = apply_chinese_text_replacement(ax.get_xlabel())
                ax.set_xlabel(xlabel, fontfamily='sans-serif')
            
            # 处理Y轴标签
            if ax.get_ylabel():
                ylabel = apply_chinese_text_replacement(ax.get_ylabel())
                ax.set_ylabel(ylabel, fontfamily='sans-serif')
            
            # 安全处理X轴刻度标签
            try:
                current_xticks = ax.get_xticks()
                x_tick_labels = [apply_chinese_text_replacement(str(label.get_text())) 
                               for label in ax.get_xticklabels()]
                if x_tick_labels and len(x_tick_labels) == len(current_xticks):
                    ax.set_xticks(current_xticks)
                    ax.set_xticklabels(x_tick_labels, fontfamily='sans-serif')
            except Exception as e:
                logger.warning(f"处理X轴刻度标签时发生错误: {e}")
            
            # 安全处理Y轴刻度标签
            try:
                current_yticks = ax.get_yticks()
                y_tick_labels = [apply_chinese_text_replacement(str(label.get_text())) 
                               for label in ax.get_yticklabels()]
                if y_tick_labels and len(y_tick_labels) == len(current_yticks):
                    ax.set_yticks(current_yticks)
                    ax.set_yticklabels(y_tick_labels, fontfamily='sans-serif')
            except Exception as e:
                logger.warning(f"处理Y轴刻度标签时发生错误: {e}")
            
            # 处理图例
            legend = ax.get_legend()
            if legend:
                new_labels = [apply_chinese_text_replacement(label.get_text()) 
                             for label in legend.get_texts()]
                ax.legend(labels=new_labels, prop={'family': 'sans-serif'})
            
            # 处理文本注释
            for text in ax.texts:
                try:
                    original_text = text.get_text()
                    new_text = apply_chinese_text_replacement(original_text)
                    text.set_text(new_text)
                    text.set_fontfamily('sans-serif')
                except Exception as e:
                    logger.warning(f"处理文本注释时发生错误: {e}")
    
    except Exception as e:
        logger.warning(f"文本替换过程中发生错误: {e}")


def ensure_font_before_plot():
    """在生成图表前确保字体设置正确"""
    try:
        # 强制设置matplotlib配置
        plt.rcParams['font.family'] = ['sans-serif']
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'Liberation Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置后端
        plt.switch_backend('Agg')
    except Exception as e:
        logger.warning(f"字体检查失败: {e}")


def safe_generate_chart(code, exec_vars):
    """安全生成图表，确保字体配置正确"""
    try:
        # 强制设置matplotlib配置
        plt.rcParams['font.family'] = ['sans-serif']
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'Liberation Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置后端
        plt.switch_backend('Agg')
        
        # 预处理代码，处理可能的Period对象问题
        processed_code = code
        
        # 如果代码中包含Period操作，添加转换处理
        if 'to_period' in code:
            # 在代码前添加Period处理函数
            period_handler = """
def safe_period_to_string(period_series):
    \"\"\"安全地将Period序列转换为字符串\"\"\"
    return period_series.astype(str)

# 重写原始代码中的Period处理
import pandas as pd
original_to_period = pd.Series.dt.to_period

def safe_to_period(self, freq=None):
    result = original_to_period(self, freq)
    return result.astype(str)  # 立即转换为字符串避免序列化问题

pd.Series.dt.to_period = safe_to_period
"""
            processed_code = period_handler + "\n" + code
        
        # 执行代码
        exec(processed_code, exec_vars)
        
        # 获取当前图形
        current_fig = plt.gcf()
        
        # 应用完整的文本替换
        ensure_complete_text_replacement(current_fig)
        
        # 转换为Base64
        buff = io.BytesIO()
        current_fig.savefig(buff, format='png', dpi=100, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
        plt.close(current_fig)
        buff.seek(0)
        
        return base64.b64encode(buff.read()).decode()
        
    except Exception as e:
        logger.error(f"图表生成过程中发生错误: {e}")
        logger.debug(f"执行的代码: {code[:200]}...")  # 只输出前200个字符避免日志过长
        plt.close('all')  # 清理所有图形
        return None

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
                return safe_json_dumps({
                    "success": False,
                    "error": "没有可用的数据进行可视化"
                }, ensure_ascii=False)
                
            result = self.visualization_agent._generate_visualization(
                self.visualization_agent.current_data, 
                query, 
                chart_type
            )
            
            # 返回结果的JSON字符串，使用安全序列化
            return safe_json_dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"生成可视化错误: {e}")
            return safe_json_dumps({
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
            system_prompt = """你是一位专业的数据分析师，专注于美妆销售数据分析。
请使用提供的Python代码解释器工具来回答用户关于美妆销售数据的问题。

数据已经加载为名为df的pandas DataFrame，你可以直接使用它。

分析时请遵循以下原则：
1. 优先使用pandas、numpy进行数据操作和统计分析
2. 使用matplotlib、seaborn或plotly生成可视化图表
3. 确保代码干净、高效并有注释
4. 分析需要关注美妆行业的特性，如产品类别、季节性趋势、促销效果等
5. 结果应该包含商业洞察和建议，而不仅仅是数据描述

**重要的代码规范：**
- 处理日期时间时，避免使用to_period()方法，改用字符串格式化或groupby日期
- 如需按月分组，使用: df.groupby(df['日期'].dt.to_period('M').astype(str))
- 或者使用: df.groupby(df['日期'].dt.strftime('%Y-%m'))
- 确保所有数据类型都可以序列化，避免pandas Period对象

请先思考分析步骤，然后编写代码，最后总结发现的洞察和建议。

###输出样例
{
  "chart_type": "line", 
  "query": "销售趋势分析", 
  "description": "销售额呈现上升趋势，年底有明显季节性增长", 
  "code": "# 处理日期数据\ndf['日期'] = pd.to_datetime(df['日期'])\n# 按月分组，使用字符串格式避免Period对象\nmonthly_sales = df.groupby(df['日期'].dt.strftime('%Y-%m'))['销售额(万元)'].sum()\nplt.figure(figsize=(12, 6))\nplt.plot(monthly_sales.index, monthly_sales.values)\nplt.title('Monthly Sales Trend')\nplt.xticks(rotation=45)\nplt.tight_layout()"
}
###

如果你需要更精确控制图表生成，请提供完整的code字段。系统会优先使用你提供的代码而非默认模板。
如果你不提供code字段，系统会基于chart_type自动生成图表代码。"""

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
                    
            # 尝试将整个响应解析为JSON
            try:
                # 清理文本，移除可能的Markdown代码块标记和工具调用标识符
                cleaned_response = text_response.strip()
                
                # 移除Markdown代码块标记
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:].strip()
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3].strip()
                
                # 移除工具调用标识符（如 _visualization✿ARGS✿: \n）
                if "✿ARGS✿:" in cleaned_response:
                    # 查找工具调用标识符的位置
                    args_pos = cleaned_response.find("✿ARGS✿:")
                    if args_pos != -1:
                        # 找到标识符后面的换行符或冒号位置
                        start_pos = args_pos + len("✿ARGS✿:")
                        # 跳过可能的空白字符和换行符
                        while start_pos < len(cleaned_response) and cleaned_response[start_pos] in [' ', '\n', '\t', ':']:
                            start_pos += 1
                        cleaned_response = cleaned_response[start_pos:].strip()
                
                # 尝试查找JSON对象的开始和结束位置
                json_start = cleaned_response.find('{')
                json_end = cleaned_response.rfind('}')
                
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    # 提取JSON部分
                    json_part = cleaned_response[json_start:json_end+1]
                    cleaned_response = json_part.strip()
                
                # 解析JSON
                vis_data = json.loads(cleaned_response)
                logger.info(f"成功解析可视化指令: {vis_data}")
                
                # 根据指令执行可视化
                try:
                    # 设置安全的执行环境
                    exec_vars = {'df': df, 'plt': plt, 'sns': sns, 'pd': pd, 'np': np}
                    
                    # 检查是否直接提供了代码
                    if "code" in vis_data and vis_data["code"]:
                        # 直接使用提供的代码
                        code = vis_data["code"]
                        logger.info("使用LLM提供的自定义代码生成可视化")
                        
                        # 执行代码生成图表
                        try:
                            # 使用安全的图表生成函数
                            visualization_base64 = safe_generate_chart(code, exec_vars)
                            
                            if visualization_base64:
                                logger.info("成功使用自定义代码生成图表")
                            else:
                                logger.error("使用自定义代码生成图表失败")
                                visualization_base64 = None
                        except Exception as e:
                            logger.error(f"执行自定义代码失败: {str(e)}")
                            traceback.print_exc()
                            visualization_base64 = None
                    else:
                        # 根据图表类型生成相应代码
                        chart_type_requested = vis_data.get("chart_type", "line")
                        query_detail = vis_data.get("query", query)
                        
                        # 检查query本身是否包含Python代码
                        def contains_python_code(text):
                            """检查文本是否包含Python代码"""
                            python_keywords = ['import ', 'def ', 'if ', 'for ', 'while ', 'plt.', 'df.', 'sns.', 'pd.', 'np.']
                            code_indicators = ['```python', '```', 'plt.figure', 'matplotlib', 'seaborn']
                            text_lower = text.lower()
                            
                            # 检查Python关键字
                            keyword_count = sum(1 for keyword in python_keywords if keyword in text_lower)
                            # 检查代码块标识
                            has_code_indicators = any(indicator in text_lower for indicator in code_indicators)
                            
                            # 如果有多个Python关键字或明确的代码标识，认为包含代码
                            return keyword_count >= 2 or has_code_indicators
                        
                        # 如果query包含Python代码，尝试提取并使用
                        if contains_python_code(query_detail):
                            logger.info("检测到query中包含Python代码，尝试提取并使用")
                            
                            # 提取代码块
                            extracted_code = None
                            if "```python" in query_detail:
                                # 提取Python代码块
                                start = query_detail.find("```python") + 9
                                end = query_detail.find("```", start)
                                if end != -1:
                                    extracted_code = query_detail[start:end].strip()
                            elif "```" in query_detail:
                                # 提取一般代码块
                                start = query_detail.find("```") + 3
                                end = query_detail.find("```", start)
                                if end != -1:
                                    extracted_code = query_detail[start:end].strip()
                            else:
                                # 如果没有代码块标记，但有Python关键字，尝试使用整个query
                                extracted_code = query_detail
                            
                            if extracted_code:
                                try:
                                    logger.info("使用从query中提取的代码生成可视化")
                                    visualization_base64 = safe_generate_chart(extracted_code, exec_vars)
                                    
                                    if visualization_base64:
                                        logger.info("成功使用query中的代码生成图表")
                                    else:
                                        logger.warning("使用query中的代码生成图表失败，将使用默认图表类型")
                                        visualization_base64 = None
                                except Exception as e:
                                    logger.error(f"执行query中的代码失败: {str(e)}")
                                    visualization_base64 = None
                        
                        # 如果没有生成可视化（query中没有代码或代码执行失败），使用默认图表类型生成
                        if not visualization_base64:
                            logger.info(f"使用默认图表类型生成: {chart_type_requested}")
                            
                            if chart_type_requested == "line":
                                plt.figure(figsize=(12, 7))
                                # 创建折线图
                                code = """
# 确保日期格式正确
if '日期' in df.columns:
    df['日期'] = pd.to_datetime(df['日期'])
    # 按月分组，使用字符串格式避免Period对象
    monthly_sales = df.groupby(df['日期'].dt.strftime('%Y-%m'))['销售额(万元)'].sum()
    plt.plot(monthly_sales.index, monthly_sales.values)
    plt.title('Monthly Sales Trend')
    plt.xticks(rotation=45)
    plt.tight_layout()
"""
                            elif chart_type_requested == "bar":
                                plt.figure(figsize=(12, 7))
                                # 创建柱状图
                                code = """
# 根据品类统计销售额
if '品类' in df.columns and '销售额(万元)' in df.columns:
    category_sales = df.groupby('品类')['销售额(万元)'].sum().sort_values(ascending=False)
    sns.barplot(x=category_sales.index, y=category_sales.values)
    plt.title('各品类销售额对比')
    plt.xlabel('品类')
    plt.ylabel('销售额（万元）')
    plt.xticks(rotation=45)
    plt.tight_layout()
"""
                            elif chart_type_requested == "pie":
                                plt.figure(figsize=(12, 7))
                                # 创建饼图
                                code = """
# 根据品类统计销售额占比
if '品类' in df.columns and '销售额(万元)' in df.columns:
    category_sales = df.groupby('品类')['销售额(万元)'].sum()
    plt.pie(category_sales, labels=category_sales.index, autopct='%1.1f%%')
    plt.title('各品类销售额占比')
    plt.axis('equal')
"""
                            elif chart_type_requested == "scatter":
                                plt.figure(figsize=(12, 7))
                                # 创建散点图
                                code = """
# 查找数值列作为散点图的 x 和 y
num_cols = df.select_dtypes(include=['int', 'float']).columns
if len(num_cols) >= 2:
    x_col, y_col = num_cols[0], num_cols[1]
    # 如果有第三个数值列，用它来决定点的大小
    if len(num_cols) >= 3:
        size_col = num_cols[2]
        plt.scatter(df[x_col], df[y_col], s=df[size_col]/df[size_col].mean()*50, alpha=0.6)
    else:
        plt.scatter(df[x_col], df[y_col], alpha=0.6)
    plt.title(f'{y_col} vs {x_col}')
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
"""
                            elif chart_type_requested == "heatmap":
                                plt.figure(figsize=(12, 7))
                                # 创建热力图
                                code = """
# 查找分类列和数值列
cat_cols = df.select_dtypes(include=['object']).columns
num_cols = df.select_dtypes(include=['int', 'float']).columns

if len(cat_cols) >= 2 and len(num_cols) >= 1:
    # 使用前两个分类列和第一个数值列创建交叉表
    pivot_table = pd.pivot_table(
        df, 
        values=num_cols[0],
        index=cat_cols[0],
        columns=cat_cols[1],
        aggfunc='mean'
    )
    
    # 绘制热力图
    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot_table, annot=True, cmap='YlGnBu', fmt='.1f')
    plt.title(f'{cat_cols[0]} vs {cat_cols[1]} ({num_cols[0]})')
    plt.tight_layout()
"""
                            elif chart_type_requested == "box":
                                plt.figure(figsize=(12, 7))
                                # 创建箱线图
                                code = """
# 查找分类列和数值列
cat_cols = df.select_dtypes(include=['object']).columns
num_cols = df.select_dtypes(include=['int', 'float']).columns

if len(cat_cols) >= 1 and len(num_cols) >= 1:
    # 使用第一个分类列和第一个数值列创建箱线图
    plt.figure(figsize=(12, 6))
    sns.boxplot(x=cat_cols[0], y=num_cols[0], data=df)
    plt.title(f'各{cat_cols[0]}的{num_cols[0]}分布')
    plt.xlabel(cat_cols[0])
    plt.ylabel(num_cols[0])
    plt.xticks(rotation=45)
    plt.tight_layout()
"""
                            elif chart_type_requested == "histogram":
                                plt.figure(figsize=(12, 7))
                                # 创建直方图
                                code = """
# 查找数值列
num_cols = df.select_dtypes(include=['int', 'float']).columns

if len(num_cols) >= 1:
    # 使用第一个数值列创建直方图
    plt.figure(figsize=(10, 6))
    sns.histplot(df[num_cols[0]], kde=True)
    plt.title(f'{num_cols[0]}分布')
    plt.xlabel(num_cols[0])
    plt.ylabel('频率')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
"""
                            elif chart_type_requested == "area":
                                plt.figure(figsize=(12, 7))
                                # 创建面积图
                                code = """
# 查找日期列和数值列
date_cols = [col for col in df.columns if 'date' in col.lower() or '日期' in col]
num_cols = df.select_dtypes(include=['int', 'float']).columns

if len(date_cols) >= 1 and len(num_cols) >= 1:
    # 使用日期列和数值列创建面积图
    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col])
    
    # 按日期分组并计算每日总销售额
    grouped_data = df.groupby(date_col)[num_cols[0]].sum().reset_index()
    
    plt.figure(figsize=(12, 6))
    plt.fill_between(grouped_data[date_col], grouped_data[num_cols[0]], alpha=0.5)
    plt.plot(grouped_data[date_col], grouped_data[num_cols[0]], linewidth=2)
    plt.title(f'{num_cols[0]}趋势')
    plt.xlabel(date_col)
    plt.ylabel(num_cols[0])
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
"""
                            else:
                                plt.figure(figsize=(12, 7))
                                # 默认创建折线图
                                code = """
# 默认创建销售趋势图
if '日期' in df.columns and '销售额(万元)' in df.columns:
    df['日期'] = pd.to_datetime(df['日期'])
    sales_trend = df.groupby('日期')['销售额(万元)'].sum().reset_index()
    plt.plot(sales_trend['日期'], sales_trend['销售额(万元)'])
    plt.title('销售趋势分析')
    plt.xlabel('日期')
    plt.ylabel('销售额（万元）')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
"""
                            
                            # 执行代码生成图表
                            try:
                                exec(code, exec_vars)
                                
                                # 应用中文文本替换到图表标题和标签
                                current_fig = plt.gcf()
                                
                                # 替换主标题
                                if current_fig._suptitle:
                                    title_text = current_fig._suptitle.get_text()
                                    current_fig.suptitle(apply_chinese_text_replacement(title_text))
                                
                                # 替换子图标题和标签
                                for ax in current_fig.get_axes():
                                    # 替换标题
                                    if ax.get_title():
                                        ax.set_title(apply_chinese_text_replacement(ax.get_title()))
                                    
                                    # 替换x轴标签
                                    if ax.get_xlabel():
                                        ax.set_xlabel(apply_chinese_text_replacement(ax.get_xlabel()))
                                    
                                    # 替换y轴标签
                                    if ax.get_ylabel():
                                        ax.set_ylabel(apply_chinese_text_replacement(ax.get_ylabel()))
                                    
                                    # 替换图例
                                    legend = ax.get_legend()
                                    if legend:
                                        new_labels = [apply_chinese_text_replacement(label.get_text()) 
                                                     for label in legend.get_texts()]
                                        ax.legend(labels=new_labels)
                                
                                # 将图表转换为Base64
                                buff = io.BytesIO()
                                
                                # 获取当前图形并应用文本替换
                                current_fig = plt.gcf()
                                ensure_complete_text_replacement(current_fig)
                                
                                plt.savefig(buff, format='png', dpi=100, bbox_inches='tight', 
                                           facecolor='white', edgecolor='none')
                                plt.close()
                                buff.seek(0)
                                visualization_base64 = base64.b64encode(buff.read()).decode()
                                
                                logger.info("成功根据图表类型生成图表")
                            except Exception as e:
                                logger.error(f"执行图表生成代码失败: {str(e)}")
                                traceback.print_exc()
                                # 错误时visualization_base64保持为None，后续会使用默认图表生成
                                visualization_base64 = None
                    
                except Exception as e:
                    logger.error(f"处理可视化指令失败: {str(e)}")
                    traceback.print_exc()
                    # 错误时visualization_base64保持为None，后续会使用默认图表生成
                    visualization_base64 = None
            except Exception as e:
                logger.error(f"解析JSON响应失败: {str(e)}")
                logger.debug(f"原始响应内容: {text_response[:500]}...")  # 输出前500个字符用于调试
                logger.debug(f"清理后内容: {cleaned_response[:200]}...")  # 输出前200个字符用于调试
                
                # 尝试更激进的JSON提取方法
                try:
                    # 如果包含工具调用的其他格式，尝试不同的清理方式
                    lines = text_response.split('\n')
                    json_lines = []
                    in_json = False
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('{') or in_json:
                            in_json = True
                            json_lines.append(line)
                            if line.endswith('}') and line.count('{') <= line.count('}'):
                                break
                    
                    if json_lines:
                        potential_json = '\n'.join(json_lines)
                        vis_data = json.loads(potential_json)
                        logger.info(f"通过备用方法成功解析可视化指令: {vis_data}")
                        
                        # 备用解析成功后，继续执行可视化生成逻辑
                        try:
                            # 设置安全的执行环境
                            exec_vars = {'df': df, 'plt': plt, 'sns': sns, 'pd': pd, 'np': np}
                            
                            # 检查是否直接提供了代码
                            if "code" in vis_data and vis_data["code"]:
                                # 直接使用提供的代码
                                code = vis_data["code"]
                                logger.info("使用备用解析得到的自定义代码生成可视化")
                                
                                # 执行代码生成图表
                                try:
                                    # 使用安全的图表生成函数
                                    visualization_base64 = safe_generate_chart(code, exec_vars)
                                    
                                    if visualization_base64:
                                        logger.info("成功使用自定义代码生成图表")
                                    else:
                                        logger.error("使用自定义代码生成图表失败")
                                        visualization_base64 = None
                                except Exception as e:
                                    logger.error(f"执行备用解析的自定义代码失败: {str(e)}")
                                    traceback.print_exc()
                                    visualization_base64 = None
                            else:
                                # 根据图表类型生成相应代码
                                chart_type_requested = vis_data.get("chart_type", "line")
                                # 这里可以执行与主流程相同的图表类型判断逻辑
                                # 为了简化，我们直接使用默认图表生成
                                visualization_base64 = self._generate_default_chart(df, chart_type_requested)
                                logger.info("通过备用解析使用默认图表生成")
                        except Exception as e:
                            logger.error(f"备用解析后执行可视化生成失败: {str(e)}")
                            visualization_base64 = None
                    else:
                        # 如果仍然失败，错误时visualization_base64保持为None，后续会使用默认图表生成
                        logger.warning("无法解析LLM响应为JSON格式，将使用默认图表生成")
                        visualization_base64 = None
                        vis_data = {}
                except Exception as e2:
                    logger.error(f"备用JSON解析方法也失败: {str(e2)}")
                    traceback.print_exc()
                    # 错误时visualization_base64保持为None，后续会使用默认图表生成
                    visualization_base64 = None
                    vis_data = {}
            
            # 检查text_response是否包含code_interpreter的输出
            if not visualization_base64 and "_interpreter" in text_response:
                # 解析code_interpreter输出
                # 尝试提取代码块
                code_output_start = text_response.find("```")
                if code_output_start != -1:
                    code_end = text_response.find("```", code_output_start + 3)
                    if code_end != -1:
                        code_output = text_response[code_output_start:code_end + 3]
                
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
                            visualization_base64 = text_response[img_start:img_end]
            
            # 如果没有生成可视化，尝试推断并生成一个默认图表
            if not visualization_base64:
                logger.warning("LLM未生成可视化，使用默认图表生成")
                logger.debug(f"LLM响应内容: {text_response[:200]}...")  # 输出响应内容前200个字符用于调试
                visualization_base64 = self._generate_default_chart(df, chart_type)
                if not visualization_base64:
                    return {
                        "success": False,
                        "error": "无法生成可视化，数据可能不适合可视化或请求不明确",
                        "visualization": None
                    }
            else:
                logger.info("成功从LLM响应中提取可视化图像")
            
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
            
            # 确保字体设置正确
            ensure_font_before_plot()
            
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
            
            # 获取当前图形并应用文本替换
            current_fig = plt.gcf()
            ensure_complete_text_replacement(current_fig)
            
            plt.savefig(buff, format='png', dpi=100, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            buff.seek(0)
            visualization_base64 = base64.b64encode(buff.read()).decode()
            
            return visualization_base64
            
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
            
            # 准备数据摘要，确保所有数据类型都可以JSON序列化
            data_summary = {
                "行数": int(len(df)),
                "列数": int(len(df.columns)),
                "列名": list(df.columns)
            }
            
            # 添加数值列统计信息
            numeric_cols = df.select_dtypes(include=['int', 'float']).columns
            if len(numeric_cols) > 0:
                data_summary["数值统计"] = {}
                for col in numeric_cols[:3]:  # 最多取前3个数值列
                    try:
                        col_stats = {
                            "均值": float(df[col].mean()),
                            "最大值": float(df[col].max()),
                            "最小值": float(df[col].min())
                        }
                        # 确保没有NaN值
                        for key, value in col_stats.items():
                            if pd.isna(value):
                                col_stats[key] = 0.0
                        data_summary["数值统计"][col] = col_stats
                    except Exception as e:
                        logger.warning(f"计算列 {col} 的统计信息时出错: {e}")
                        continue
            
            # 添加分类列统计信息
            categorical_cols = df.select_dtypes(include=['object']).columns
            if len(categorical_cols) > 0:
                data_summary["分类统计"] = {}
                for col in categorical_cols[:2]:  # 最多取前2个分类列
                    try:
                        top_values = df[col].value_counts().nlargest(3)
                        # 确保值类型可以序列化
                        col_stats = {}
                        for val, count in zip(top_values.index, top_values.values):
                            # 转换为安全的数据类型
                            safe_val = str(val) if not isinstance(val, (str, int, float)) else val
                            safe_count = int(count)
                            col_stats[safe_val] = safe_count
                        data_summary["分类统计"][col] = col_stats
                    except Exception as e:
                        logger.warning(f"计算列 {col} 的分类统计时出错: {e}")
                        continue
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"数据摘要: {safe_json_dumps(data_summary, ensure_ascii=False)}\n\n用户查询: {query}\n\n请根据这些信息生成一个简洁的图表描述。"}
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
