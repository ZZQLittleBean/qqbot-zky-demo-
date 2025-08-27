import aiohttp
import time
import json
import os
import botpy
from dotenv import load_dotenv
# 导入所有需要的提示词变量
from prompt_config import SYSTEM_PROMPT, USER_PROMPT, BASIC_PERSONA, RESPONSE_REQUIREMENTS, SPECIFIC_RULES
from botpy import logging
from identity_manager import IdentityManager

class MyClient(botpy.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity_manager = IdentityManager()

# 正确加载环境变量
load_dotenv()  # 添加括号
_log = logging.get_logger()

def load_keyword_dictionary():
    """加载关键词词典（增加空值保护）"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dictionary_path = os.path.join(current_dir, "keyword_dictionary.json")
    
    if not os.path.exists(dictionary_path):
        _log.warning(f"创建空词典文件: {dictionary_path}")
        try:
            with open(dictionary_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return {}
        except Exception as e:
            _log.error(f"创建词典失败: {str(e)}")
            return {}
    
    try:
        with open(dictionary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log.error(f"加载词典失败: {str(e)}")
        return {}  # 确保返回空字典而不是None

KEYWORD_DICTIONARY = load_keyword_dictionary()

async def call_deepseek_api(question: str, identity_manager: IdentityManager, context: list = None, user_openid: str = None) -> str:
    """调用DeepSeek API（增加身份管理器参数）"""
    api_key = "your_api_key"  # 请替换为您的API密钥
    if not api_key:
        return "⚠️ API密钥未配置"
    
    # 安全加载关键词词典
    dictionary_list = "无关键词"
    try:
        dictionary_list = "\n".join(
            [f"- {keyword}: {data.get('description', '')}" 
             for keyword, data in (KEYWORD_DICTIONARY or {}).items()]
        )
    except Exception as e:
        _log.error(f"格式化词典失败: {str(e)}")

    # 设置默认值
    identity_info = "无身份信息"
    personality_instructions = "默认个性：友好且乐于助人的助手"
    applicable_rules = "无特殊规则"
    identity_data = {}  # 确保identity_data有默认值

    # 身份信息验证
    if user_openid and identity_manager:
        try:
            _log.info(f"处理用户: {user_openid}")
            
            # 获取身份信息
            identity_info = identity_manager.format_identity_for_prompt(user_openid)
            identity_data = identity_manager.get_identity(user_openid)
            
            _log.info(f"用户身份信息: {identity_info}")  #功能仅供debug使用 常态请加井号避免消息覆盖
            #_log.info(f"用户身份数据: {json.dumps(identity_data, indent=2, ensure_ascii=False)}")  #功能仅供debug使用 常态请加井号避免消息覆盖

            # 应用特殊用户的个性化设置
            personality_instructions = identity_data.get("personality", personality_instructions)

            # 构建适用规则描述
            rule_descriptions = []
            for rule_name in identity_data.get("applicable_rules", []):
                if rule_name in SPECIFIC_RULES:
                    rule_descriptions.append(f"- {rule_name}: {SPECIFIC_RULES[rule_name]}")
            
            applicable_rules = "\n".join(rule_descriptions) if rule_descriptions else "无特殊规则"
            
            # 特殊用户指令处理：当管理员要求特定方式回答时
            if identity_data.get("is_admin", False) and "特定方式" in question:
                return "提示词配置成功"
                
        except Exception as e:
            _log.error(f"处理身份信息时出错: {str(e)}", exc_info=True)
            # 使用默认值继续处理
            identity_info = "身份信息处理错误，使用默认配置"
    else:
        _log.warning("缺少用户openid或identity_manager实例，使用默认配置")
    

    # 安全构建提示词数据
    system_prompt_data = {
        "current_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "dictionary_list": dictionary_list,
        "user_identity": identity_info,
        "personality_instructions": personality_instructions,
        "basic_persona": BASIC_PERSONA,
        "response_requirements": RESPONSE_REQUIREMENTS,
        "applicable_rules": applicable_rules  
    }
    
    # 安全构建系统提示词
    try:
        system_prompt = SYSTEM_PROMPT.format(**system_prompt_data)
    except KeyError as e:
        _log.error(f"提示词格式化错误: 缺失字段 {str(e)}")
        system_prompt = SYSTEM_PROMPT.format(
            current_time=system_prompt_data["current_time"],
            dictionary_list=dictionary_list,
            user_identity=identity_info,
            personality_instructions=personality_instructions,
            basic_persona=BASIC_PERSONA,
            response_requirements=RESPONSE_REQUIREMENTS,
            applicable_rules=applicable_rules
        )
    #_log.info(f"完整系统提示词:\n{system_prompt}") #功能仅供debug使用 常态请加井号避免消息覆盖

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]
    
    # 添加上下文（如果有）
    if context:
        messages.extend(context)
    
    # 添加当前问题
    try:
        user_prompt = USER_PROMPT.format(question=question)
        messages.append({"role": "user", "content": user_prompt})
    except Exception as e:
        _log.error(f"用户提示词格式化失败: {str(e)}")
        messages.append({"role": "user", "content": question})

    # 关键词检测（增加空字典保护）
    found_keywords = []
    for keyword, data in KEYWORD_DICTIONARY.items():
        if keyword.lower() in question.lower():
            found_keywords.append((keyword, data))
    
    if found_keywords:
        keyword_prompt = "检测到以下关键词：\n"
        for keyword, data in found_keywords:
            keyword_prompt += f"- {keyword}: {data.get('response', '')}\n"
            if 'word_limit' in data:
                keyword_prompt += f"  字数限制: {data['word_limit']}字\n"
        
        # 将关键词提示作为系统消息插入
        messages.insert(1, {"role": "system", "content": keyword_prompt})
    
    # 记录调试信息
    _log.debug(f"用户身份信息: {identity_info}")
    _log.debug(f"个性化指令: {personality_instructions}")
    _log.debug(f"适用规则: {applicable_rules}")
    _log.debug(f"完整系统提示词:\n{system_prompt}")
    
    # API请求
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
        "stop": ["\n\n"]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                return f"❌ API错误: HTTP {response.status}"
    except Exception as e:
        _log.error(f"API请求异常: {str(e)}")
        return f"⚠️ 服务暂时不可用，请稍后再试"