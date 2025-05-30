"""
知识检索Agent
负责从美妆行业知识库中检索相关信息，为用户问题提供行业专业知识支持
"""
import os
import logging
from typing import List, Dict, Any, Optional
import json
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@register_tool('get_knowledge_response')
class GetKnowledgeTool(BaseTool):
    """知识检索工具类"""
    
    description = '获取美妆行业知识'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': '知识查询问题',
        'required': True
    }]
    
    def __init__(self, knowledge_agent):
        self.knowledge_agent = knowledge_agent
        super().__init__()
    
    def call(self, params: str, **kwargs) -> str:
        """调用知识检索"""
        try:
            params_dict = json.loads(params)
            query = params_dict['query']
            response = self.knowledge_agent._get_knowledge_response(query)
            return response
        except Exception as e:
            logger.error(f"知识检索工具调用错误: {e}")
            return f"知识检索过程中发生错误: {str(e)}"

class KnowledgeAgent:
    """知识检索Agent类，使用Qwen-Agent实现知识检索"""
    
    def __init__(self):
        """初始化知识检索Agent"""
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
        
        # 知识库路径
        self.kb_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')

        # 创建知识检索Assistant实例（用于外部工具调用）
        self.knowledge_assistant = Assistant(
            llm=self.llm_cfg,
            name='美妆行业知识专家',
            description='专精于美妆行业专业知识，能够提供行业见解和市场趋势分析',
            function_list=['get_knowledge_response']
        )
        
        # 创建纯LLM Assistant实例（用于内部直接LLM调用，避免循环调用）
        self.llm_assistant = Assistant(
            llm=self.llm_cfg,
            name='美妆行业分析师',
            description='专精于美妆行业专业知识，能够提供行业见解和市场趋势分析',
            function_list=[]  # 不包含任何工具，直接使用LLM
        )
        
        # 初始化知识库
        self.init_knowledge_base()
    
    def init_knowledge_base(self):
        """初始化美妆行业知识库"""
        try:
            # 检查知识库目录是否存在
            if not os.path.exists(self.kb_dir):
                os.makedirs(self.kb_dir, exist_ok=True)
                logger.warning("知识库目录不存在，已创建空目录")
                # 创建一个基础美妆行业知识文档
                self._create_base_knowledge()
                
            logger.info("知识库初始化完成")
                
        except Exception as e:
            logger.error(f"初始化知识库时发生错误: {e}")
    
    def _create_base_knowledge(self):
        """创建基础美妆行业知识文档"""
        base_knowledge = """
# 美妆行业知识

## 产品类别
1. **彩妆**
   - 粉底液/霜：提供面部均匀肤色，遮盖瑕疵
   - 遮瑕膏：集中遮盖痘印、黑眼圈等问题区域
   - 腮红：提供面部血色，增添健康感
   - 眼影：强调眼部轮廓，创造深度和立体感
   - 睫毛膏：使睫毛更浓密、卷翘
   - 眉笔/眉粉：定义和填充眉形
   - 口红/唇彩：为嘴唇增添颜色和光泽

2. **护肤品**
   - 洁面产品：清洁皮肤
   - 爽肤水/化妆水：平衡皮肤pH值，补充水分
   - 精华液：提供高浓度活性成分，针对特定皮肤问题
   - 面霜/乳液：锁住水分，保护皮肤屏障
   - 面膜：密集护理，解决特定肌肤问题
   - 防晒霜：保护皮肤免受紫外线伤害

3. **香水**
   - 淡香水(EDT)：香气持续2-3小时
   - 香水(EDP)：香气持续5-6小时
   - 浓香水(Parfum)：香气持续6-8小时或更长

4. **个人护理**
   - 洗发水/护发素
   - 身体乳/沐浴露
   - 除臭剂/止汗剂

## 消费者细分

1. **按年龄划分**
   - Z世代(1995-2010)：追求个性，关注社交媒体，注重成分透明度，偏好可持续品牌
   - 千禧一代(1980-1994)：注重品质与价值，偏好天然成分，愿意尝试创新产品
   - X世代(1965-1979)：注重品牌忠诚度，关注抗衰老产品，购买力较强
   - 婴儿潮一代(1946-1964)：关注品质，偏好奢侈品牌，注重功效性护肤

2. **按消费行为划分**
   - 奢侈型消费者：偏好高端品牌，注重品质与独特性
   - 品牌忠诚者：对特定品牌保持忠诚，长期复购
   - 潮流追随者：对新品敏感，易受社交媒体影响
   - 精打细算者：注重性价比，喜欢促销活动
   - 成分党：关注产品成分和功效，决策理性

## 销售渠道

1. **线下渠道**
   - 百货公司专柜：提供高端服务体验，主打高端品牌
   - 专营店：如丝芙兰(Sephora)、屈臣氏等，提供多品牌选择
   - 药妆店：如屈臣氏、大众点评等，主打功能性和药妆产品
   - 超市/大卖场：便利性高，主打大众品牌

2. **线上渠道**
   - 品牌官网：完整的产品线，独家优惠
   - 电商平台：如天猫、京东、拼多多等，大促活动多
   - 社交电商：如小红书、抖音等，KOL引导消费
   - 跨境电商：引入国外小众品牌

## 行业趋势

1. **成分趋势**
   - 清洁美容：无有害成分，如不含防腐剂、硅油等
   - 可持续发展：环保包装，可回收材料
   - 功效成分：如视黄醇、烟酰胺、透明质酸等科学证实有效的成分
   - 本土特色成分：如中草药提取物

2. **市场趋势**
   - 个性化定制：根据消费者具体需求定制产品
   - 男士美妆：男性护肤和彩妆市场迅速增长
   - 微针和功能性护肤：家用美容仪器与高浓度功效产品结合
   - 数字化诊断：通过AI和AR技术进行肤质检测和产品推荐

## 营销分析指标

1. **销售指标**
   - 销售额(Revenue)：总销售金额
   - 销售量(Sales Volume)：售出产品数量
   - 平均客单价(AOV)：每单平均金额
   - 同比增长率(YoY Growth)：与去年同期相比的增长率
   - 环比增长率(MoM Growth)：与上月相比的增长率

2. **渠道指标**
   - 渠道贡献率：各渠道销售额占总销售额的比例
   - 渠道转化率：访问-下单-付款转化率
   - 获客成本(CAC)：获取一位新客户的平均成本

3. **产品指标**
   - 产品热销榜：按销量/销售额排名
   - 库存周转率：销售速度与库存量的比值
   - 毛利率：(销售额-成本)/销售额
   - 回购率：重复购买同一产品的比例

4. **客户指标**
   - 客户终身价值(LTV)：客户整个生命周期的预期价值
   - 新客率：新客户占比
   - 客户流失率：不再购买的客户比例
   - 客户忠诚度：品牌忠诚度测量

## 营销策略

1. **价格策略**
   - 高端定价：强调产品稀缺性和奢华感
   - 大众定价：注重性价比和市场份额
   - 折扣促销：短期提高销量和清库存
   - 会员价格：增强客户忠诚度

2. **促销活动**
   - 季节性促销：如节日特卖、换季促销
   - 会员专享：会员日、生日礼遇
   - 赠品策略：购物满额赠品
   - 限时折扣：创造紧迫感

3. **营销传播**
   - KOL/KOC合作：利用意见领袖和内容创作者的影响力
   - 社交媒体营销：平台内容策略，短视频、直播等
   - 内容营销：产品教程、使用技巧分享
   - 口碑营销：鼓励用户评价和分享

## 产品生命周期管理

1. **产品开发**
   - 市场调研：了解消费者需求和竞争环境
   - 配方研发：根据目标功效开发产品配方
   - 包装设计：考虑品牌调性和使用便利性

2. **产品上市**
   - 新品发布：线上线下联动推广
   - 初期促销：提高产品知名度和试用率
   - 渠道铺货：确保产品可得性

3. **产品增长**
   - 扩大目标用户：拓展用户群体
   - 优化产品体验：根据用户反馈改进
   - 多样化营销：维持产品热度

4. **产品成熟**
   - 维护品牌忠诚度：会员运营
   - 产品改良：小幅更新保持竞争力
   - 深化渠道：提高市场渗透率

5. **产品衰退**
   - 产品退市：逐步减少投入
   - 清仓处理：价格策略清库存
   - 替代产品：推出升级版或替代品
"""
        # 创建基础知识文件
        kb_file_path = os.path.join(self.kb_dir, 'beauty_industry_knowledge.md')
        with open(kb_file_path, 'w', encoding='utf-8') as f:
            f.write(base_knowledge)
        
        logger.info("创建基础美妆行业知识文档完成")
    
    def _get_knowledge_response(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        """结合知识库改写和增强用户问题，添加行业背景和专业方法论
        
        参数:
            query: 用户原始问题
            context: 可选的上下文信息
            
        返回:
            增强后的问题或分析指导
        """
        try:
            # 构建系统提示 - 专注于问题改写和分析指导
            system_prompt = """你是一位美妆行业的专业分析师，擅长将用户的简单问题转化为专业的分析框架。

你的任务是：
1. 分析用户的原始问题，识别其核心关注点
2. 基于美妆行业知识，为这个问题提供专业的行业背景
3. 提出科学的数据分析方法论和关键指标
4. 给出具体的分析维度和建议的分析步骤

请输出格式化的分析指导，包含：
- 行业背景：相关的美妆行业知识和市场情况
- 关键指标：应该关注的核心数据指标
- 分析维度：从哪些角度进行分析
- 方法建议：推荐的分析方法和步骤

不要直接回答用户的问题，而是为后续的数据分析提供专业指导。"""
            
            # 准备包含知识库文件的内容
            content = [{"text": f"用户原始问题: {query}"}]
            
            # 如果有上下文，添加到内容中（限制长度）
            if context:
                # 限制上下文，只取最近的2条对话
                recent_context = context[-2:] if len(context) > 2 else context
                context_str = "\n".join([f"{msg['role']}: {msg['content'][:150]}{'...' if len(msg['content']) > 150 else ''}" for msg in recent_context])
                content.append({"text": f"最近对话:\n{context_str}"})
            
            # 添加知识库文件作为参考（限制文件数量）
            kb_files_added = 0
            max_kb_files = 3  # 限制最多添加3个知识库文件
            for root, dirs, filenames in os.walk(self.kb_dir):
                for filename in filenames:
                    if kb_files_added >= max_kb_files:
                        break
                    if filename.endswith('.md') or filename.endswith('.txt'):
                        file_path = os.path.join(root, filename)
                        content.append({"file": file_path})
                        kb_files_added += 1
                if kb_files_added >= max_kb_files:
                    break
            
            logger.info(f"为问题增强加载了 {kb_files_added} 个知识库文件")
            
            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ]
            
            # 使用LLM生成问题增强和分析指导
            enhanced_guidance = ""
            for response in self.llm_assistant.run(messages=messages):
                if "content" in response[0]:
                    enhanced_guidance += response[0]["content"]
            
            return enhanced_guidance
            
        except Exception as e:
            logger.error(f"增强问题时发生错误: {e}")
            return f"""基于美妆行业的基础分析框架：

行业背景：
美妆行业是一个快速发展的消费品行业，具有季节性强、品牌忠诚度高、渠道多样化等特点。

关键指标：
- 销售额和销量趋势
- 产品类别表现（护肤、彩妆、香水等）
- 客户画像和购买行为
- 渠道效率和ROI

分析维度：
- 时间维度：季节性、节假日效应
- 产品维度：类别、品牌、价格段
- 客户维度：年龄、地域、消费能力
- 渠道维度：线上线下、不同平台

方法建议：
1. 描述性统计分析
2. 趋势分析和同比环比
3. 细分市场分析
4. 关联性分析

原始问题: {query}"""
    
    def get_knowledge_response(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        """对外接口，结合知识库改写和增强用户问题，添加行业背景和专业方法论
        
        参数:
            query: 用户原始问题
            context: 可选的上下文信息
            
        返回:
            增强后的分析指导
        """
        return self._get_knowledge_response(query, context)
    
    def add_document_to_knowledge_base(self, title: str, content: str) -> bool:
        """添加新文档到知识库
        
        参数:
            title: 文档标题
            content: 文档内容
            
        返回:
            是否添加成功
        """
        try:
            # 创建文档文件
            file_name = f"{title.lower().replace(' ', '_')}.md"
            file_path = os.path.join(self.kb_dir, file_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"文档'{title}'已添加到知识库")
            return True
            
        except Exception as e:
            logger.error(f"添加文档到知识库时发生错误: {e}")
            return False 