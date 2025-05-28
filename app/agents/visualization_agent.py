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
import re
import platform

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

def fix_json_string(json_str):
    """修复JSON字符串中的转义问题，特别是code字段中的Python代码"""
    try:
        # 首先尝试直接解析
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败，尝试修复: {e}")
        
        try:
            import re
            
            # 方法1: 手动解析关键字段（最可靠的方法）
            result = {}
            
            # 提取chart_type
            chart_type_match = re.search(r'"chart_type"\s*:\s*"([^"]*)"', json_str)
            if chart_type_match:
                result['chart_type'] = chart_type_match.group(1)
            
            # 提取query
            query_match = re.search(r'"query"\s*:\s*"([^"]*)"', json_str)
            if query_match:
                result['query'] = query_match.group(1)
            
            # 提取description - 使用更宽松的匹配
            desc_match = re.search(r'"description"\s*:\s*"([^"]*?)"(?=\s*,\s*"code")', json_str, re.DOTALL)
            if desc_match:
                result['description'] = desc_match.group(1)
            
            # 提取code - 采用分段方式
            code_start_match = re.search(r'"code"\s*:\s*"', json_str)
            if code_start_match:
                code_start_pos = code_start_match.end()
                
                # 寻找code字段的结束位置
                # 通过计算引号和转义字符来找到正确的结束位置
                pos = code_start_pos
                escaped = False
                while pos < len(json_str):
                    char = json_str[pos]
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char == '"':
                        # 检查下一个字符是否是逗号、换行或结束符
                        if pos + 1 < len(json_str) and json_str[pos + 1] in ['\n', ' ', '\t', ',', '}']:
                            # 找到了结束位置
                            code_content = json_str[code_start_pos:pos]
                            
                            # 基本的反转义处理
                            code_content = code_content.replace('\\"', '"')
                            code_content = code_content.replace("\\'", "'")  
                            code_content = code_content.replace('\\n', '\n')
                            code_content = code_content.replace('\\t', '\t')
                            code_content = code_content.replace('\\\\', '\\')
                            
                            result['code'] = code_content
                            break
                    pos += 1
            
            if len(result) >= 3:  # 至少有chart_type, query, description
                logger.info("使用手动解析成功解析JSON字段")
                return result
            else:
                logger.warning(f"手动解析只获得了{len(result)}个字段，不足以生成图表")
                return None
                
        except Exception as parse_error:
            logger.error(f"手动JSON解析失败: {parse_error}")
            return None

# 配置matplotlib中文字体支持
def setup_chinese_font():
    try:
        # 强制使用Agg后端，确保无GUI环境也能生成图表
        plt.switch_backend('Agg')
        
        # 重置matplotlib配置
        plt.rcdefaults()
        
        # 尝试多种方式设置中文字体
        font_set_success = False
        loaded_font_name = None
        
        # 方法1：优先检查并使用预下载的字体文件
        try:
            # 构建字体文件路径 - 使用更精确的路径定位
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            font_dir = os.path.join(project_root, 'app', 'static', 'fonts')
            font_file = os.path.join(font_dir, 'NotoSansCJK-Regular.ttc')
            
            # 也尝试相对路径和其他可能的路径
            possible_paths = [
                font_file,
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'static', 'fonts', 'NotoSansCJK-Regular.ttc'),
                os.path.join('.', 'app', 'static', 'fonts', 'NotoSansCJK-Regular.ttc'),
                os.path.join('app', 'static', 'fonts', 'NotoSansCJK-Regular.ttc'),
                './app/static/fonts/NotoSansCJK-Regular.ttc'
            ]
            
            font_file_found = None
            for path in possible_paths:
                if os.path.exists(path):
                    font_file_found = path
                    logger.info(f"找到字体文件: {path}")
                    break
            
            if font_file_found:
                logger.info(f"使用字体文件: {font_file_found}")
                
                # 验证文件大小（字体文件通常较大）
                file_size = os.path.getsize(font_file_found)
                logger.info(f"字体文件大小: {file_size / (1024*1024):.1f} MB")
                
                if file_size > 1024 * 1024:  # 至少1MB，确保是完整的字体文件
                    try:
                        # 清除现有字体缓存并重新加载
                        import matplotlib.font_manager as fm
                        
                        # 清除字体缓存
                        try:
                            # 删除字体缓存文件
                            cache_dir = mpl.get_cachedir()
                            fontlist_cache = os.path.join(cache_dir, 'fontlist-v330.json')
                            if os.path.exists(fontlist_cache):
                                os.remove(fontlist_cache)
                                logger.info("已清除matplotlib字体缓存")
                        except Exception as cache_error:
                            logger.warning(f"清除字体缓存时出错: {cache_error}")
                        
                        # 重新加载字体管理器
                        fm._load_fontmanager(try_read_cache=False)
                        
                        # 添加字体到matplotlib
                        fm.fontManager.addfont(font_file_found)
                        logger.info("字体文件已添加到matplotlib")
                        
                        # 获取字体属性 - 尝试多种方法
                        try:
                            # 方法1: 直接从文件创建FontProperties
                            font_prop = fm.FontProperties(fname=font_file_found)
                            font_name = font_prop.get_name()
                            logger.info(f"通过FontProperties检测到的字体名称: {font_name}")
                        except Exception as prop_error:
                            logger.warning(f"FontProperties方法失败: {prop_error}")
                            # 方法2: 从字体管理器中查找
                            font_name = None
                            for font in fm.fontManager.ttflist:
                                if font.fname == font_file_found:
                                    font_name = font.name
                                    logger.info(f"从fontManager找到字体名称: {font_name}")
                                    break
                            
                            # 方法3: 使用常见的Noto Sans CJK名称
                            if not font_name:
                                font_name = "Noto Sans CJK SC"
                                logger.info(f"使用默认Noto Sans CJK名称: {font_name}")
                        
                        if font_name:
                            # 检查字体是否正确加载
                            available_fonts = set([f.name for f in fm.fontManager.ttflist])
                            logger.info(f"系统可用字体数量: {len(available_fonts)}")
                            
                            # 尝试几个可能的字体名称
                            possible_names = [
                                font_name,
                                "Noto Sans CJK SC",
                                "Noto Sans CJK SC Regular",
                                "NotoSansCJK-Regular",
                                "Noto Sans SC",
                                "Noto Sans"
                            ]
                            
                            successful_font_name = None
                            for name in possible_names:
                                if name in available_fonts:
                                    successful_font_name = name
                                    logger.info(f"成功匹配字体名称: {name}")
                                    break
                            
                            if successful_font_name:
                                # 设置matplotlib参数
                                plt.rcParams['font.sans-serif'] = [successful_font_name, 'DejaVu Sans', 'Arial', 'sans-serif']
                                plt.rcParams['axes.unicode_minus'] = False
                                plt.rcParams['font.family'] = ['sans-serif']
                                
                                # 强制更新字体缓存
                                plt.rcParams.update(plt.rcParams)
                                
                                logger.info(f"成功加载本地字体: {successful_font_name}")
                                loaded_font_name = successful_font_name
                                font_set_success = True
                                
                                # 测试字体是否能正确显示中文
                                try:
                                    test_fig, test_ax = plt.subplots(figsize=(1, 1))
                                    test_ax.text(0.5, 0.5, '测试中文字体显示', fontfamily='sans-serif', fontsize=12)
                                    test_ax.text(0.5, 0.3, '美妆销售数据分析', fontfamily='sans-serif', fontsize=10)
                                    # 测试完成后立即关闭图形
                                    plt.close(test_fig)
                                    logger.info("本地字体中文显示测试通过")
                                except Exception as test_error:
                                    logger.warning(f"字体显示测试失败: {test_error}")
                            else:
                                logger.warning("在可用字体列表中未找到匹配的字体名称")
                                # 尝试直接使用文件路径设置字体
                                plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans', 'Arial', 'sans-serif']
                                plt.rcParams['axes.unicode_minus'] = False
                                plt.rcParams['font.family'] = ['sans-serif']
                                loaded_font_name = "Noto Sans CJK SC"
                                font_set_success = True
                                logger.info("使用默认中文字体名称设置")
                        else:
                            logger.warning("无法获取字体名称")
                        
                    except Exception as font_load_error:
                        logger.error(f"加载本地字体时出错: {font_load_error}")
                        font_set_success = False
                else:
                    logger.warning(f"字体文件大小异常，可能不完整: {file_size} bytes")
            else:
                logger.info("未找到本地字体文件，将尝试系统字体")
                
        except Exception as e:
            logger.warning(f"检查本地字体时出错: {e}")
        
        # 方法2：如果本地字体失败，尝试使用系统字体
        if not font_set_success:
            try:
                import platform
                system = platform.system()
                
                logger.info(f"本地字体加载失败，尝试使用系统字体，系统类型: {system}")
            
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
                logger.info(f"系统可用字体数量: {len(available_fonts)}")
            
                # 尝试找到第一个可用的中文字体
                for font in fonts_to_try:
                    if font in available_fonts:
                        plt.rcParams['font.sans-serif'] = [font, 'DejaVu Sans', 'Arial', 'sans-serif']
                        plt.rcParams['axes.unicode_minus'] = False
                        plt.rcParams['font.family'] = ['sans-serif']
                        logger.info(f"成功设置系统中文字体: {font}")
                        loaded_font_name = font
                        font_set_success = True
                        break
                    
            except Exception as e:
                logger.warning(f"系统字体设置失败: {e}")
        
        # 方法3：使用文本替换方案作为最后备选
        if not font_set_success:
            logger.warning("所有字体设置方案都失败，使用文本替换方案")
            
            # 设置一个基本字体
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            plt.rcParams['font.family'] = ['sans-serif']
            
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
                '防晒': 'Sunscreen', '卸妆': 'Makeup Remover', '保湿': 'Moisturizing',
                '美白': 'Whitening', '抗衰老': 'Anti-aging', '修复': 'Repair',
                '滋润': 'Nourishing', '控油': 'Oil Control', '补水': 'Hydrating',
                '去角质': 'Exfoliating', '紧致': 'Firming', '提亮': 'Brightening',
                '遮瑕': 'Concealer', '腮红': 'Blush', '睫毛膏': 'Mascara',
                '眉笔': 'Eyebrow Pencil', '唇膏': 'Lip Balm', '指甲油': 'Nail Polish',
                
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
        
        # 最终验证并设置全局字体信息
        if font_set_success:
            logger.info(f"中文字体配置成功完成，使用字体: {loaded_font_name}")
            # 保存成功加载的字体名称供后续使用
            global current_font_name
            current_font_name = loaded_font_name
        else:
            logger.info("中文字体配置完成（使用文本替换方案）")
            current_font_name = None
        
        # 输出最终的字体配置信息
        logger.info(f"最终字体配置: {plt.rcParams['font.sans-serif']}")
        
    except Exception as e:
        logger.error(f"配置中文字体时出错: {e}", exc_info=True)
        # 确保我们有一个基本可用的配置
        plt.switch_backend('Agg')
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.family'] = ['sans-serif']


def apply_chinese_text_replacement(text):
    """应用中文文本替换"""
    if isinstance(text, str) and font_replace_map:
        for chinese, english in font_replace_map.items():
            text = text.replace(chinese, english)
    
    return text


def ensure_complete_text_replacement(fig):
    """确保图表中的所有文本都使用正确的字体显示"""
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import platform
    
    # 检查是否有中文字体可用
    available_fonts = set([f.name for f in mpl.font_manager.fontManager.ttflist])
    system = platform.system()
    
    chinese_fonts = []
    if system == "Windows":
        chinese_fonts = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'SimSun']
    elif system == "Darwin":  # macOS
        chinese_fonts = ['PingFang SC', 'STHeiti', 'STKaiti', 'STSong']
    else:  # Linux等
        chinese_fonts = ['WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
    
    # 检查是否有中文字体可用
    has_chinese_font = any(font in available_fonts for font in chinese_fonts)
    
    # 中英文映射（只在没有中文字体时使用）
    chinese_to_english = {
        '销售': 'Sales',
        '利润': 'Profit',
        '月份': 'Month',
        '年份': 'Year',
        '数量': 'Quantity',
        '金额': 'Amount',
        '类别': 'Category',
        '产品': 'Product',
        '客户': 'Customer',
        '日期': 'Date',
        '时间': 'Time',
        '价格': 'Price',
        '成本': 'Cost',
        '收入': 'Revenue',
        '支出': 'Expense',
        '百分比': 'Percentage',
        '总计': 'Total',
        '平均': 'Average',
        '最大': 'Maximum',
        '最小': 'Minimum',
        '分析': 'Analysis',
        '报告': 'Report',
        '图表': 'Chart',
        '统计': 'Statistics',
    }
    
    # 只在没有中文字体时才进行文本替换
    if not has_chinese_font:
        print("未找到中文字体，将中文标签替换为英文")
        
        # 遍历所有文本对象并替换中文
        for text_obj in fig.findobj(match=lambda x: hasattr(x, 'get_text')):
            original_text = text_obj.get_text()
            if original_text and any('\u4e00' <= char <= '\u9fff' for char in original_text):
                # 替换文本中的中文词汇
                new_text = original_text
                for chinese, english in chinese_to_english.items():
                    new_text = new_text.replace(chinese, english)
                
                if new_text != original_text:
                    text_obj.set_text(new_text)
                    print(f"Text replaced: '{original_text}' -> '{new_text}'")
    else:
        print("找到中文字体，保持中文标签")
    
    return fig


def ensure_font_before_plot():
    """在生成图表前确保字体设置正确"""
    try:
        # 强制设置matplotlib配置
        plt.rcParams['font.family'] = ['sans-serif']
        
        # 如果有成功加载的字体，使用它
        if 'current_font_name' in globals() and current_font_name:
            # 确保使用的是实际加载成功的字体名称
            plt.rcParams['font.sans-serif'] = [current_font_name, 'DejaVu Sans', 'Arial', 'sans-serif']
            logger.debug(f"使用成功加载的字体: {current_font_name}")
        else:
            # 如果没有成功加载的字体，则启用文本替换模式
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
            logger.debug("使用默认字体并启用文本替换模式")
        
        plt.rcParams['axes.unicode_minus'] = False
        
        # 设置后端
        plt.switch_backend('Agg')
        
        logger.debug(f"图表生成前字体设置: {plt.rcParams['font.sans-serif']}")
        
    except Exception as e:
        logger.warning(f"字体检查失败: {e}")
        # 在错误情况下设置最基本的配置
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.family'] = ['sans-serif']


def safe_generate_chart(code, exec_vars):
    """安全生成图表，确保字体配置正确"""
    try:
        # 在代码执行前确保字体设置
        ensure_font_before_plot()
        
        # 预处理代码，处理可能的Period对象问题和数字格式化问题
        processed_code = code
        
        # 清理和修复代码缩进问题
        def clean_code_indentation(code_text):
            """清理和修复代码缩进问题"""
            lines = code_text.split('\n')
            cleaned_lines = []
            
            # 更智能的缩进处理
            for i, line in enumerate(lines):
                # 移除所有前导空格，重新处理缩进
                stripped_line = line.strip()
                
                if not stripped_line:
                    cleaned_lines.append('')
                    continue
                
                # 注释行直接添加，不需要缩进
                if stripped_line.startswith('#'):
                    cleaned_lines.append(stripped_line)
                    continue
                
                # 确保控制结构语句保持冒号
                control_keywords = ['for ', 'if ', 'elif ', 'else:', 'while ', 'with ', 'try:', 'except', 'finally:', 'def ', 'class ']
                is_control_structure = any(stripped_line.startswith(keyword) for keyword in control_keywords)
                
                # 如果是控制结构但缺少冒号，添加冒号
                if is_control_structure and not stripped_line.endswith(':'):
                    # 检查是否应该有冒号（排除某些不需要冒号的情况）
                    if not any(stripped_line.startswith(kw) for kw in ['except ', 'finally']):
                        # 对于 for, if, while, with, def, class 等，确保有冒号
                        if not stripped_line.endswith((':', '\\', '(', '[', '{')):  # 如果不是以这些字符结尾
                            stripped_line += ':'
                
                # 检查这一行是否应该有缩进
                should_indent = False
                
                # 如果前一行是以冒号结尾的语句，当前行应该缩进
                if cleaned_lines:
                    prev_line = cleaned_lines[-1].strip()
                    if prev_line.endswith(':') and not prev_line.startswith('#'):
                        should_indent = True
                
                # 特殊处理：某些关键词应该减少缩进
                dedent_keywords = ['else:', 'elif ', 'except', 'except:', 'finally:', 'def ', 'class ']
                is_dedent = any(stripped_line.startswith(keyword) for keyword in dedent_keywords)
                
                # 特殊处理：某些语句应该保持在顶级
                top_level_keywords = ['import ', 'from ', 'def ', 'class ', 'if __name__']
                is_top_level = any(stripped_line.startswith(keyword) for keyword in top_level_keywords)
                
                if is_top_level:
                    # 顶级语句不缩进
                    cleaned_lines.append(stripped_line)
                elif should_indent and not is_dedent:
                    # 需要缩进的行
                    cleaned_lines.append('    ' + stripped_line)
                else:
                    # 正常的语句
                    cleaned_lines.append(stripped_line)
            
            # 第二轮处理：检查并修复明显的缩进错误
            final_lines = []
            indent_level = 0
            
            for i, line in enumerate(cleaned_lines):
                if not line.strip():
                    final_lines.append('')
                    continue
                
                stripped = line.strip()
                
                # 特殊情况：某些关键词应该在顶级
                if any(stripped.startswith(kw) for kw in ['import ', 'from ', 'def ', 'class ']):
                    indent_level = 0
                    final_lines.append(stripped)
                    if stripped.endswith(':'):
                        indent_level = 1
                elif any(stripped.startswith(kw) for kw in ['else:', 'elif ', 'except', 'except:', 'finally:']):
                    # 这些关键字应该与对应的 if/try 保持相同缩进级别
                    current_indent = max(0, indent_level - 1)
                    final_lines.append('    ' * current_indent + stripped)
                    if stripped.endswith(':'):
                        indent_level = current_indent + 1
                else:
                    # 其他语句使用当前缩进级别
                    final_lines.append('    ' * indent_level + stripped)
                    if stripped.endswith(':') and not stripped.startswith('#'):
                        indent_level += 1
                    elif stripped in ['pass', 'break', 'continue'] or stripped.startswith('return'):
                        # 这些语句后通常会减少缩进
                        if indent_level > 0:
                            indent_level -= 1
            
            return '\n'.join(final_lines)
        
        # 应用代码清理
        processed_code = clean_code_indentation(processed_code)
        
        # 添加专门的语法错误修复
        def fix_syntax_errors(code_text):
            """修复常见的Python语法错误"""
            lines = code_text.split('\n')
            fixed_lines = []
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    fixed_lines.append(line)
                    continue
                
                # 修复 for 循环缺少冒号的问题
                if stripped.startswith('for ') and ' in ' in stripped and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 if 语句缺少冒号的问题  
                elif stripped.startswith(('if ', 'elif ')) and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 while 循环缺少冒号的问题
                elif stripped.startswith('while ') and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 with 语句缺少冒号的问题
                elif stripped.startswith('with ') and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 def 函数定义缺少冒号的问题
                elif stripped.startswith('def ') and '(' in stripped and ')' in stripped and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 class 定义缺少冒号的问题
                elif stripped.startswith('class ') and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                # 修复 try/except 块缺少冒号的问题
                elif stripped in ['try', 'finally'] and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                elif stripped.startswith('except') and not stripped.endswith(':'):
                    line = line.rstrip() + ':'
                    
                fixed_lines.append(line)
            
            return '\n'.join(fixed_lines)
        
        # 应用语法修复
        processed_code = fix_syntax_errors(processed_code)
        
        # 修复常见的语法错误
        # 修复: 诸如 f'{height.1f}万' 这样的无效数字格式
        # 使用更强大的正则表达式来处理各种无效小数点格式
        processed_code = re.sub(r"(\{[^{}]+?)\.(\d+)f", r"\1:.2f", processed_code)
        
        # 修复其他可能的格式化问题，如 f'{value.2万}' 或 f'{sales.1}万'
        processed_code = re.sub(r"(\{[^{}]+?)\.(\d+)([^f\d{}]+?\})", r"\1:.2f\3", processed_code)
        
        # 修复像 f'增长了{growth.1%}' 这样的格式化
        processed_code = re.sub(r"(\{[^{}]+?)\.(\d+)(%\})", r"\1:.2f\3", processed_code)
        
        # 修复Seaborn palette警告问题
        # 将 sns.barplot(..., palette='xxx') 修复为合适的格式
        processed_code = re.sub(
            r"sns\.barplot\(([^)]*?)palette=(['\"][^'\"]*['\"])([^)]*?)\)",
            r"sns.barplot(\1color='skyblue'\3)",
            processed_code
        )
        
        # 修复字符串格式化问题
        # 确保格式化表达式正确
        processed_code = re.sub(r"f'{([^}]+)}\.(\d+)f'", r"f'{\1:.2f}'", processed_code)
        processed_code = re.sub(r"'{([^}]+)}\.(\d+)f'", r"'{\1:.2f}'", processed_code)
        
        # 修复可能导致格式化错误的表达式
        processed_code = re.sub(r"f'{([^}]+):.2f}\.(\d+)f'", r"f'{\1:.2f}'", processed_code)
        
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
            processed_code = period_handler + "\n" + processed_code
        
        # 添加智能日期解析函数
        date_parsing_code = """
# 智能日期解析函数
def smart_date_parsing(df, date_columns=None):
    \"\"\"智能日期解析，自动检测并转换日期格式\"\"\"
    import pandas as pd
    import re
    
    if date_columns is None:
        # 自动检测可能的日期列
        date_columns = [col for col in df.columns if 
                       '日期' in col or 'date' in col.lower() or 
                       '时间' in col or 'time' in col.lower()]
    
    for col in date_columns:
        if col in df.columns and df[col].dtype == 'object':
            try:
                # 获取第一个非空值作为样本
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if sample:
                    sample_str = str(sample)
                    
                    # 检测日期格式并应用相应的解析方法
                    if re.match(r'\\d{1,2}/\\d{1,2}/\\d{4}', sample_str):
                        # 可能是 DD/MM/YYYY 或 MM/DD/YYYY 格式
                        day_month = sample_str.split('/')[0]
                        if int(day_month) > 12:
                            # 第一个数字大于12，肯定是日期在前
                            df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
                        else:
                            # 尝试日期在前的格式，如果失败则用月份在前
                            try:
                                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='raise')
                            except:
                                df[col] = pd.to_datetime(df[col], format='%m/%d/%Y', errors='coerce')
                    elif re.match(r'\\d{4}-\\d{1,2}-\\d{1,2}', sample_str):
                        # YYYY-MM-DD 格式
                        df[col] = pd.to_datetime(df[col], format='%Y-%m-%d', errors='coerce')
                    elif re.match(r'\\d{1,2}-\\d{1,2}-\\d{4}', sample_str):
                        # DD-MM-YYYY 或 MM-DD-YYYY 格式
                        day_month = sample_str.split('-')[0]
                        if int(day_month) > 12:
                            df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='coerce')
                        else:
                            try:
                                df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='raise')
                            except:
                                df[col] = pd.to_datetime(df[col], format='%m-%d-%Y', errors='coerce')
                    else:
                        # 使用pandas的智能解析，优先日期在前
                        df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                    
                    print(f"已成功解析日期列: {col}")
                    
            except Exception as e:
                print(f"解析日期列 {col} 时发生错误: {e}")
                # 如果解析失败，尝试最通用的方法
                try:
                    df[col] = pd.to_datetime(df[col], infer_datetime_format=True, errors='coerce')
                except:
                    print(f"无法解析日期列 {col}，保持原始格式")
    
    return df

# 自动对数据进行日期解析
df = smart_date_parsing(df)
"""
        
        # 在代码中添加字体设置
        font_setup_code = f"""
# 确保字体设置正确
import matplotlib.pyplot as plt
import matplotlib as mpl
import re
import platform

plt.switch_backend('Agg')
plt.rcParams['font.family'] = ['sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 设置合理的图表尺寸，确保不超过matplotlib限制
# 最大像素限制：每个方向不能超过 65536 像素 (2^16)
# 使用合适的尺寸和DPI组合
max_width_inches = 20  # 最大20英寸宽度
max_height_inches = 15  # 最大15英寸高度
safe_dpi = 150  # 安全的DPI设置

# 计算像素尺寸确保不超限
max_pixels_width = max_width_inches * safe_dpi  # 20 * 150 = 3000 像素
max_pixels_height = max_height_inches * safe_dpi  # 15 * 150 = 2250 像素

plt.rcParams['figure.figsize'] = [max_width_inches, max_height_inches]
plt.rcParams['figure.dpi'] = safe_dpi
plt.rcParams['savefig.dpi'] = safe_dpi

# 设置合适的字体大小
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
plt.rcParams['legend.fontsize'] = 12

print(f"图表尺寸设置: {{max_width_inches}}x{{max_height_inches}} 英寸, DPI: {{safe_dpi}}")
print(f"像素尺寸: {{max_pixels_width}}x{{max_pixels_height}} 像素")

# 尝试设置中文字体
chinese_font_found = False
system = platform.system()

if system == "Windows":
    # Windows系统的中文字体
    fonts_to_try = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'SimSun']
elif system == "Darwin":  # macOS
    # macOS系统的中文字体
    fonts_to_try = ['PingFang SC', 'STHeiti', 'STKaiti', 'STSong']
else:  # Linux等
    # Linux系统的中文字体
    fonts_to_try = ['WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']

# 获取系统中可用的字体
available_fonts = set([f.name for f in mpl.font_manager.fontManager.ttflist])

# 尝试找到第一个可用的中文字体
for font in fonts_to_try:
    if font in available_fonts:
        plt.rcParams['font.sans-serif'] = [font, 'DejaVu Sans', 'Arial', 'sans-serif']
        chinese_font_found = True
        print(f"使用中文字体: {{font}}")
        break

if not chinese_font_found:
    # 如果没有找到中文字体，使用默认字体
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    print("未找到中文字体，使用默认字体")
"""
        
        # 如果有成功加载的字体，添加字体设置
        if 'current_font_name' in globals() and current_font_name:
            font_setup_code += f"""
plt.rcParams['font.sans-serif'] = ['{current_font_name}', 'DejaVu Sans', 'Arial', 'sans-serif']
print(f"正在使用字体: {current_font_name}")
"""
        else:
            font_setup_code += """
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
print("使用默认字体，将启用文本替换模式")
"""
        
        font_setup_code += """
plt.rcParams['axes.unicode_minus'] = False

# 字体替换函数
def replace_chinese_text(text):
    if isinstance(text, str):
        font_replace_map = {
            '美妆': 'Beauty', '销售': 'Sales', '数据': 'Data', '分析': 'Analysis',
            '产品': 'Product', '类型': 'Type', '销售额': 'Revenue', '对比': 'Compare',
            '护肤品': 'Skincare', '彩妆': 'Makeup', '香水': 'Perfume', '面膜': 'Mask',
            '洁面': 'Cleanser', '万元': '10k CNY', '占比': 'Proportion', '品类': 'Category',
            '利润率': 'Profit Rate', '销售表现': 'Sales Performance', '分析': 'Analysis',
            '价格': 'Price', '数量': 'Quantity', '时间': 'Time', '日期': 'Date',
            '月份': 'Month', '品牌': 'Brand', '地区': 'Region', '客户': 'Customer'
        }
        for chinese, english in font_replace_map.items():
            text = text.replace(chinese, english)
    return text

# 重写matplotlib的中文处理
def safe_chinese_text(text):
    \"\"\"安全处理中文文本\"\"\"
    return replace_chinese_text(str(text)) if text else ""
"""
        
        # 合并代码
        final_code = font_setup_code + "\n" + date_parsing_code + "\n" + processed_code
        
        # 最后一次清理：确保没有语法问题
        final_code = final_code.replace("plt.show()", "# plt.show() - removed for web display")
        
        # 记录处理后的代码日志
        logger.debug(f"处理后的代码：{final_code[:500]}...")
        
        # 安全地执行代码
        try:
            exec(final_code, exec_vars)
        except (SyntaxError, ValueError, IndentationError) as e:
            # 捕获语法错误、值错误和缩进错误，尝试进一步修复
            logger.warning(f"代码执行错误: {e}")
            error_message = str(e)
            
            if "unexpected indent" in error_message or "IndentationError" in error_message:
                # 缩进错误的特殊处理
                logger.warning("检测到缩进错误，尝试重新格式化代码")
                
                # 更激进的代码清理
                lines = final_code.split('\n')
                cleaned_lines = []
                indent_level = 0
                
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        cleaned_lines.append('')
                        continue
                    
                    if stripped.startswith('#'):
                        cleaned_lines.append(stripped)
                        continue
                    
                    # 减少缩进的情况
                    if any(stripped.startswith(keyword) for keyword in ['except', 'elif', 'else', 'finally']):
                        indent_level = max(0, indent_level - 1)
                    
                    # 添加适当的缩进
                    cleaned_lines.append('    ' * indent_level + stripped)
                    
                    # 增加缩进的情况
                    if (stripped.endswith(':') and not stripped.startswith('#')):
                        indent_level += 1
                    
                    # 减少缩进的情况（处理函数、类等结束）
                    if stripped in ['pass', 'break', 'continue', 'return'] or stripped.startswith('return '):
                        indent_level = max(0, indent_level - 1)
                
                # 重新组合代码
                fallback_code = '\n'.join(cleaned_lines)
                logger.info("已重新格式化代码，尝试重新执行")
                exec(fallback_code, exec_vars)
                
            elif "invalid decimal literal" in error_message:
                # 更具体地修复无效小数点格式
                error_line_num = int(re.search(r"line (\d+)", error_message).group(1)) if re.search(r"line (\d+)", error_message) else 0
                lines = final_code.split('\n')
                if 0 < error_line_num <= len(lines):
                    # 修复特定行的格式问题
                    line = lines[error_line_num - 1]
                    # 查找并修复类似 f'{value.123}' 这样的格式
                    fixed_line = re.sub(r"(\{[^{}]+?)\.(\d+)([^f\d{}]*?)\}", r"\1:.2f}\3", line)
                    lines[error_line_num - 1] = fixed_line
                    final_code = '\n'.join(lines)
                    logger.info(f"修复了无效小数点格式: {line} -> {fixed_line}")
                    # 重新尝试执行
                    exec(final_code, exec_vars)
            elif "Invalid format specifier" in error_message:
                # 字符串格式化错误的特殊处理
                logger.warning(f"字符串格式化错误，尝试修复格式化表达式: {error_message}")
                
                # 修复字符串格式化问题
                fallback_code = final_code
                
                # 修复各种格式化问题
                fallback_code = re.sub(r"f'{([^}]+)}\.(\d+)f'", r"f'{\1:.1f}'", fallback_code)
                fallback_code = re.sub(r"f'{([^}]+):.2f}\.(\d+)f'", r"f'{\1:.1f}'", fallback_code)
                fallback_code = re.sub(r"'{([^}]+):.2f}\.(\d+)f'", r"'{\1:.1f}'", fallback_code)
                
                # 替换有问题的文本格式化为简单的字符串连接
                fallback_code = re.sub(
                    r"plt\.text\(([^,]+),\s*([^,]+),\s*f'{([^}]+):.2f}([^']*)',",
                    r"plt.text(\1, \2, str(round(\3, 1)) + '\4',",
                    fallback_code
                )
                
                # 重新尝试执行
                exec(fallback_code, exec_vars)
            elif "time data" in error_message and "doesn't match format" in error_message:
                # 日期解析错误的特殊处理
                logger.warning(f"日期解析错误，尝试使用更通用的日期处理方法: {error_message}")
                
                # 替换代码中的日期处理部分
                fallback_code = final_code
                
                # 替换 pd.to_datetime 调用为更安全的版本
                fallback_code = re.sub(
                    r"pd\.to_datetime\([^)]+\)",
                    "pd.to_datetime(df['日期'], dayfirst=True, errors='coerce')",
                    fallback_code
                )
                
                # 替换 dt.to_period 调用
                fallback_code = re.sub(
                    r"\.dt\.to_period\([^)]*\)\.astype\(str\)",
                    ".dt.strftime('%Y-%m')",
                    fallback_code
                )
                
                # 重新尝试执行
                exec(fallback_code, exec_vars)
            else:
                # 其他错误，重新抛出
                raise
        
        # 获取当前图形
        current_fig = plt.gcf()
        
        # 应用完整的文本替换（如果字体不支持中文）
        if not ('current_font_name' in globals() and current_font_name):
            ensure_complete_text_replacement(current_fig)
        
        # 转换为Base64 - 使用合理的DPI设置
        buff = io.BytesIO()
        
        # 使用安全的DPI设置，确保图片质量的同时不超过像素限制
        save_dpi = 200  # 200 DPI保证高质量
        
        current_fig.savefig(buff, format='png', dpi=save_dpi, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
        plt.close(current_fig)
        buff.seek(0)
        
        logger.info(f"图表保存DPI: {save_dpi}")
        
        return base64.b64encode(buff.read()).decode()
        
    except Exception as e:
        logger.error(f"图表生成过程中发生错误: {e}")
        logger.debug(f"执行的代码: {code[:200]}...")  # 只输出前200个字符避免日志过长
        plt.close('all')  # 清理所有图形
        return None
# 初始化字体替换映射和当前字体名称
font_replace_map = {}
current_font_name = None

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
            'generate_cfg': {
                'max_input_tokens': 12000,  # 增加最大输入token数
                'max_output_tokens': 4000   # 增加最大输出token数
            }
        }

        # 创建可视化Assistant实例
        self.visualization_assistant = Assistant(
            llm=self.llm_cfg,
            name='数据可视化专家',
            description='专精于将美妆销售数据转化为直观的图表，突出关键趋势和洞察',
            function_list=['generate_visualization', 'code_interpreter']
        )

        # 创建纯LLM Assistant实例（用于内部直接LLM调用，避免循环调用）
        self.llm_assistant = Assistant(
            llm=self.llm_cfg,
            name='数据可视化专家',
            description='专精于将美妆销售数据转化为直观的图表，突出关键趋势和洞察',
            function_list=['code_interpreter']
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
                "description": "请先加载数据后再尝试生成可视化",
                "intermediate_message": "❌ 无法生成可视化：缺少数据源"
            }
        
        # 调用内部生成方法
        result = self._generate_visualization(self.current_data, query, chart_type)
        
        # 如果成功生成了图表，添加中间步骤的简化消息
        if result.get("success") and result.get("visualization"):
            result["intermediate_message"] = "✅ 可视化图表已生成完成，将在最终结果中展示"
        elif result.get("success") and not result.get("visualization"):
            result["intermediate_message"] = "⚠️ 可视化处理完成，但未生成图表"
        else:
            result["intermediate_message"] = f"❌ 可视化生成失败：{result.get('error', '未知错误')}"
            
        return result
    
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

            # 本地保存一份数据用于后续操作和生成备用图表
            self.current_data = df
            
            # 构建系统提示 - 直接生成Python代码
            system_prompt = """你是一位专业的数据可视化专家，专注于美妆销售数据分析。

重要指导原则：
1. 分析用户的可视化需求，生成最合适的Python可视化代码
2. 直接输出完整可执行的Python代码，无需任何解释文字
3. 使用matplotlib、seaborn等库生成清晰、美观的图表
4. 图表必须足够大，便于查看细节
5. 优先使用中文标签，系统会自动处理字体显示问题
6. 数据已经加载为名为df的pandas DataFrame，你可以直接使用它

技术要求：
- 必须使用plt.figure(figsize=(32, 24), dpi=150)设置超大尺寸图表
- 使用大号字体：标题用fontsize=24，轴标签用fontsize=18，刻度标签用fontsize=16
- 确保代码完整可执行，包含所有必要的数据处理步骤
- 使用plt.tight_layout()优化布局
- 可以使用中文标题和标签，如：
  * 各品类销售分析
  * 销售额（万元）
  * 销量（件）
  * 美妆产品对比
- 使用适合的颜色和样式，确保图表美观

输出格式：
只输出Python代码，不要有任何markdown标记、解释文字或其他内容。
代码应该能够直接执行并生成超大清晰的图表。

示例输出格式：
plt.figure(figsize=(32, 24), dpi=150)
sns.barplot(x='品类', y='销售额(万元)', data=df, color='steelblue')
plt.title('美妆品类销售额对比分析', fontsize=24, pad=30)
plt.xlabel('产品品类', fontsize=18)
plt.ylabel('销售额（万元）', fontsize=18)
plt.xticks(fontsize=16, rotation=45)
plt.yticks(fontsize=16)
plt.tight_layout()"""

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
            
            for response in self.llm_assistant.run(messages=messages):
                if "content" in response[0]:
                    text_response += response[0]["content"]
                    
            # 清理响应，提取代码
            code = self._extract_code_from_response(text_response)
            
            if code:
                logger.info("LLM生成了可视化代码，开始执行...")
                
                # 设置安全的执行环境
                exec_vars = {'df': df, 'plt': plt, 'sns': sns, 'pd': pd, 'np': np}
                
                # 执行代码生成图表
                try:
                    # 使用安全的图表生成函数
                    visualization_base64 = safe_generate_chart(code, exec_vars)
                    
                    if visualization_base64:
                        logger.info("成功生成可视化图表")
                    else:
                        logger.error("代码执行后未生成图表")
                        visualization_base64 = None
                except Exception as e:
                    logger.error(f"执行可视化代码失败: {str(e)}")
                    traceback.print_exc()
                    visualization_base64 = None
            else:
                logger.warning("无法从LLM响应中提取可执行代码")
                visualization_base64 = None
                        
            # 如果LLM生成的代码失败，使用默认图表生成
            if not visualization_base64:
                logger.warning("LLM代码执行失败，使用默认图表生成")
                visualization_base64 = self._generate_default_chart(df, chart_type)
                if not visualization_base64:
                    return {
                        "success": False,
                        "error": "无法生成可视化，数据可能不适合可视化或请求不明确",
                        "visualization": None
                    }
            
            # 生成图表描述
            chart_description = self._generate_chart_description(df, query, text_response)
        
            # 如果仍然没有图表描述，使用默认描述
            if not chart_description:
                chart_description = "此图表展示了数据的可视化分析结果，呈现了关键的业务指标和趋势。"
            
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
            # 捕获所有异常并提供友好的错误响应
            logger.error(f"生成可视化时发生错误: {e}")
            
            # 尝试生成一个非常简单的图表作为最后的回退方案
            try:
                visualization_base64 = self._generate_simple_fallback_chart(df)
                chart_description = "基本数据图表，用于展示数据概况。由于复杂图表生成失败，系统提供了这个简化版图表。"
                
                return {
                    "success": True,
                    "visualization": visualization_base64,
                    "description": chart_description,
                    "fallback": True
                }
            except Exception as fallback_error:
                logger.error(f"生成回退图表也失败了: {fallback_error}")
                
            return {
                "success": False,
                "error": f"生成可视化失败: {e}",
                "visualization": None,
                "description": "无法生成可视化图表，请尝试不同的数据或查询。"
            }
    
    def _extract_code_from_response(self, response: str) -> str:
        """从LLM响应中提取Python代码
        
        参数:
            response: LLM响应文本
            
        返回:
            提取的Python代码
        """
        if not response:
            return ""
        
        # 清理响应文本
        cleaned_response = response.strip()
        
        # 移除可能的markdown代码块标记
        if cleaned_response.startswith("```python"):
            cleaned_response = cleaned_response[9:].strip()
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:].strip()
        
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3].strip()
        
        # 确保换行符正确处理
        # 如果代码包含\n但没有实际换行，需要替换
        if '\\n' in cleaned_response and '\n' not in cleaned_response:
            cleaned_response = cleaned_response.replace('\\n', '\n')
        
        # 修复常见的代码格式问题
        cleaned_response = self._fix_code_formatting(cleaned_response)
        
        # 检查是否包含有效的Python代码关键词
        python_keywords = ['plt.', 'sns.', 'pd.', 'np.', 'df.', 'import ', 'matplotlib', 'seaborn']
        has_python_code = any(keyword in cleaned_response for keyword in python_keywords)
        
        if has_python_code:
            return cleaned_response
        else:
            logger.warning("响应中未检测到有效的Python代码")
            return ""
    
    def _fix_code_formatting(self, code: str) -> str:
        """修复代码格式问题
        
        参数:
            code: 原始代码
            
        返回:
            修复后的代码
        """
        if not code:
            return code
        
        # 如果代码是一行但包含多个语句，尝试分割
        lines = code.split('\n')
        fixed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查一行中是否包含多个Python语句（没有正确换行）
            # 查找常见的语句分隔符
            import re
            
            # 处理类似 "statement1ax = ..." 的情况
            line = re.sub(r'(\)|\])([a-zA-Z_][a-zA-Z0-9_]*\s*=)', r'\1\n\2', line)
            
            # 处理类似 "statement1plt." 的情况
            line = re.sub(r'(\)|\])(plt\.|sns\.|ax\.|ax2\.)', r'\1\n\2', line)
            
            # 处理类似 "statement1import" 的情况
            line = re.sub(r'(\)|\])(import\s)', r'\1\n\2', line)
            
            # 处理缺少换行的函数调用
            line = re.sub(r'(\))([a-zA-Z_][a-zA-Z0-9_]*\()', r'\1\n\2', line)
            
            # 如果修复后的行包含换行符，分割它们
            if '\n' in line:
                fixed_lines.extend(line.split('\n'))
            else:
                fixed_lines.append(line)
        
        # 重新组合代码
        result = '\n'.join(line for line in fixed_lines if line.strip())
        
        # 确保代码有适当的缩进
        result = self._fix_indentation(result)
        
        return result
    
    def _fix_indentation(self, code: str) -> str:
        """修复代码缩进问题
        
        参数:
            code: 代码字符串
            
        返回:
            修复缩进后的代码
        """
        lines = code.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # 大多数可视化代码应该在顶级，不需要缩进
            # 除非是控制结构内部
            fixed_lines.append(stripped)
        
        return '\n'.join(fixed_lines)
    
    def _generate_simple_fallback_chart(self, df: pd.DataFrame) -> Optional[str]:
        """生成一个非常简单的回退图表，在所有其他方法失败时使用
        
        参数:
            df: 数据
            
        返回:
            Base64编码的图表图像
        """
        try:
            # 确保有数据可用
            if len(df) == 0 or len(df.columns) == 0:
                return None
                
            # 设置matplotlib后端
            plt.switch_backend('Agg')
            
            # 设置合理的图表尺寸，确保不超过matplotlib限制
            safe_width = 12  # 12英寸宽度
            safe_height = 8  # 8英寸高度
            safe_dpi = 150   # 150 DPI
            
            # 像素计算: 12*150=1800, 8*150=1200，都在安全范围内
            plt.figure(figsize=(safe_width, safe_height), dpi=safe_dpi)
            
            logger.info(f"简单图表尺寸: {safe_width}x{safe_height}英寸, DPI: {safe_dpi}")
            logger.info(f"像素尺寸: {safe_width*safe_dpi}x{safe_height*safe_dpi}")
            
            # 简单的表格展示
            plt.axis('off')  # 不显示坐标轴
            
            # 只显示前5行，最多8列
            display_df = df.iloc[:5, :8].copy()
            
            # 转换所有列为字符串类型，避免显示问题
            for col in display_df.columns:
                display_df[col] = display_df[col].astype(str)
                # 截断长字符串
                display_df[col] = display_df[col].apply(lambda x: x[:10] + '...' if len(x) > 10 else x)
            
            # 创建表格
            cell_text = []
            for row in range(len(display_df)):
                cell_text.append(display_df.iloc[row].tolist())
                
            table = plt.table(
                cellText=cell_text,
                colLabels=display_df.columns,
                loc='center',
                cellLoc='center',
                colColours=['#f2f2f2'] * len(display_df.columns)
            )
            
            # 调整表格样式
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1.2, 1.5)
            
            # 添加标题
            plt.title('Data Preview', fontsize=14, pad=20)
            
            # 添加数据集信息
            plt.figtext(0.5, 0.01, f'Dataset: {len(df)} rows × {len(df.columns)} columns', 
                      ha='center', fontsize=10, bbox={'facecolor':'#f2f2f2', 'alpha':0.5, 'pad':5})
            
            # 转换为Base64
            buff = io.BytesIO()
            
            # 使用合理的DPI保存
            save_dpi = 150  # 适中的DPI设置
            
            plt.savefig(buff, format='png', dpi=save_dpi, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            buff.seek(0)
            
            logger.info(f"简单图表保存DPI: {save_dpi}")
            
            return base64.b64encode(buff.read()).decode()
            
        except Exception as e:
            logger.error(f"生成简单回退图表时发生错误: {e}")
            plt.close('all')  # 清理所有图形
            return None
    
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
            
            # 设置合理的图表尺寸，确保不超过matplotlib限制
            safe_width = 16  # 16英寸宽度
            safe_height = 12  # 12英寸高度  
            safe_dpi = 150   # 150 DPI
            
            # 像素计算: 16*150=2400, 12*150=1800，都在安全范围内
            plt.figure(figsize=(safe_width, safe_height), dpi=safe_dpi)
            
            logger.info(f"默认图表尺寸: {safe_width}x{safe_height}英寸, DPI: {safe_dpi}")
            logger.info(f"像素尺寸: {safe_width*safe_dpi}x{safe_height*safe_dpi}")
            
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
                if num_col is not None:
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
                    # 如果没有足够的数值列，尝试使用简单的表格图
                    return self._generate_simple_fallback_chart(df)
                
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
                    # 如果没有足够的分类列，尝试使用简单的表格图
                    return self._generate_simple_fallback_chart(df)
                
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
                # 不支持的图表类型，使用简单的表格图
                return self._generate_simple_fallback_chart(df)
            
            # 将图表转换为Base64
            buff = io.BytesIO()
            
            # 获取当前图形并应用文本替换
            current_fig = plt.gcf()
            ensure_complete_text_replacement(current_fig)
            
            # 使用合理的DPI保存，确保质量和文件大小平衡
            save_dpi = 200  # 200 DPI提供高质量
            
            plt.savefig(buff, format='png', dpi=save_dpi, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            buff.seek(0)
            
            logger.info(f"默认图表保存DPI: {save_dpi}")
            
            visualization_base64 = base64.b64encode(buff.read()).decode()
            
            return visualization_base64
            
        except Exception as e:
            logger.error(f"生成默认图表时发生错误: {e}")
            # 尝试最简单的表格图作为最后的回退
            try:
                return self._generate_simple_fallback_chart(df)
            except:
                plt.close('all')  # 清理所有图形
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
            for response in self.llm_assistant.run(messages=messages):
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


def fix_string_formatting_errors(code_text):
    """修复字符串格式化错误"""
    import re
    
    # 修复各种格式化错误
    patterns = [
        # 修复 f'{value:.1f}%' 类型的错误
        (r"f'{([^}]+)}\.(\d+)f([^']*)'", r"f'{\1:.1f\3}'"),
        
        # 修复百分比格式化问题
        (r"f'{([^}]+?)\.(\d+)f%}'", r"f'{\1:.1f}%'"),
        
        # 修复 .format() 方法的错误
        (r"\.format\(([^)]+?)\.(\d+)f\)", r".format({\1:.1f})"),
        
        # 修复字符串连接中的格式化错误
        (r"str\(([^)]+?)\)\.(\d+)f", r"f'{{\1:.1f}}'"),
        
        # 修复seaborn参数问题
        (r"palette=(['\"][^'\"]*['\"])", r"color='steelblue'"),
        
        # 修复font size参数
        (r"font size", r"fontsize"),
        
        # 修复figure设置
        (r"plt\.figure\(\)", r"plt.figure(figsize=(24, 18), dpi=150)"),
        (r"plt\.subplots\(\)", r"plt.subplots(figsize=(24, 18), dpi=150)"),
    ]
    
    fixed_code = code_text
    try:
        for pattern, replacement in patterns:
            fixed_code = re.sub(pattern, replacement, fixed_code)
    except Exception as e:
        logger.warning(f"修复格式化错误时出现问题: {e}")
        return code_text
    
    return fixed_code
