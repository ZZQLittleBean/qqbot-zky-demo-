##########以下为加载部分##########
# -*- coding: utf-8 -*-
import asyncio
import sys
import os
import time
import botpy
import random
import json
from botpy import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from botpy import BotAPI
from botpy.message import GroupMessage, DirectMessage, Message, C2CMessage
from api_utils import call_deepseek_api  # 机器人群内消息相关 负责接入DeepSeek API
from botpy.ext.cog_yaml import read
from datetime import datetime, timedelta
from context_manager import ContextManager  # 导入上下文管理器
from stamina_manager import StaminaManager  # 导入体力值管理器
from identity_manager import IdentityManager  # 导入身份管理器

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

##########机器人登录连接部分##########
#加载配置
test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
_log = logging.get_logger()

# 从配置中获取目标群组ID
TARGET_GROUP_ID = test_config.get("target_group_id", "454544531")
# 从配置中获取管理员列表
ADMIN_IDS = test_config.get("admins", [])  # 默认为空列表

# 【临时】从配置中获取成员列表
USER_1 = test_config.get("u1", []) 
USER_2 = test_config.get("u2", []) 
USER_3 = test_config.get("u3", []) 
USER_4 = test_config.get("u4", []) 
USER_5 = test_config.get("u5", []) 

class MyClient(botpy.Client):
    # 在 __init__ 中添加时区
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化定时任务调度器，添加时区设置
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.scheduled_tasks = []
        # 获取配置
        self.group_context_shared = test_config.get("group_context_shared", True)
        # 初始化身份管理器
        identity_config_path = os.path.join(os.path.dirname(__file__), "identity_config.json")
        self.identity_manager = IdentityManager(config_path=identity_config_path)
        # 初始化上下文管理器
        self.context_manager = ContextManager(config={
            "group_context_shared": self.group_context_shared,
            "shared_context_capacity": test_config.get("shared_context_capacity", 100),
            "shared_context_alert": test_config.get("shared_context_alert", 90),
            "private_context_capacity": test_config.get("private_context_capacity", 50),
            "private_context_alert": test_config.get("private_context_alert", 45),
            "context_expiry": test_config.get("context_expiry", 7200)
        })
        # 初始化体力值管理器
        self.stamina_manager = StaminaManager()
        # 记录启动时间
        self.start_time = time.time()

    #on_ready 部分
    async def on_ready(self):
        _log.info(f"机器人 「{self.robot.name}」 基础服务已就绪!")


##########添加体力值恢复任务##########
    async def setup_scheduled_messages(self):
        """设置自动定时消息任务"""
        # ... 原有任务保持不变 ...
        
        # 添加体力值恢复任务（每5分钟执行一次）
        self.scheduler.add_job(
            self.stamina_manager.restore_stamina,
            "interval",
            minutes=5,
            id="stamina_restore"
        )
        _log.info("已添加体力值恢复任务")
        
        _log.info(f"已设置 {len(self.scheduled_tasks)} 个体力值恢复相关的定时任务")

##########群消息处理功能##########
#09/08/25修改
    def contains_word(text, word):
        """检查文本中是否包含完整单词"""
        return f" {word} " in f" {text} " or text.startswith(word) or text.endswith(word)

    async def on_group_at_message_create(self, message: GroupMessage):
        # 获取群 openid
        group_openid = message.group_openid

        # 获取用户唯一ID
        user_openid = message.author.member_openid
    
        # 生成上下文键
        context_key = self.context_manager.get_context_key(user_openid, group_openid)
        
        # 判断上下文类型
        context_type = "群共享" if self.context_manager.is_shared_context(context_key) else "个人"
        _log.info(f"使用{context_type}上下文: {context_key}")

        # 清理消息内容
        clean_content = message.content.strip().replace('\n', ' ').replace('\r', '')

        # 修复1: 将特殊用户列表转换为列表
        special_users = [
            *test_config.get("u1", []),
            *test_config.get("u2", []),
            *test_config.get("u3", []),
            *test_config.get("u4", []),
            *test_config.get("u5", [])
        ]

        # 记录包含群 openid 的日志
        _log.info(f"收到群消息 [群openid: {group_openid}]: {clean_content}")
        
        # 添加规则管理命令
        if clean_content.startswith("/添加规则") and user_openid in ADMIN_IDS:
            parts = clean_content.split()
            if len(parts) >= 3:
                target_openid = parts[1]
                rule_name = parts[2]
                
                # 检查规则是否存在
                from prompt_config import SPECIFIC_RULES
                if rule_name not in SPECIFIC_RULES:
                    await message.reply(content=f"【系统】规则 '{rule_name}' 不存在，可用规则: {', '.join(SPECIFIC_RULES.keys())}")
                    return
                    
                # 添加规则到用户
                if self.identity_manager.add_rule_to_user(target_openid, rule_name):
                    await message.reply(content=f"【系统】已为用户添加规则: {rule_name}")
                else:
                    await message.reply(content=f"【系统】用户已拥有该规则")
            else:
                await message.reply(content="【系统】格式错误，正确格式: /添加规则 [openid] [规则名称]")
            return
        
        if clean_content.startswith("/移除规则") and user_openid in ADMIN_IDS:
            parts = clean_content.split()
            if len(parts) >= 3:
                target_openid = parts[1]
                rule_name = parts[2]
                
                # 移除用户规则
                if self.identity_manager.remove_rule_from_user(target_openid, rule_name):
                    await message.reply(content=f"【系统】已从用户移除规则: {rule_name}")
                else:
                    await message.reply(content=f"【系统】用户未拥有该规则")
            else:
                await message.reply(content="【系统】格式错误，正确格式: /移除规则 [openid] [规则名称]")
            return
        
        # 优先处理AI请求
        if clean_content.startswith("/AI") or " /AI " in clean_content:
            _log.info(f"检测到AI请求 [用户: {user_openid}]")
            question = clean_content.replace("/AI", "", 1).strip()
        
            if not question:
                reply_content = "【AI回复】你好呀，请问有什么问题需要我解答？"
            else:
                # 获取用户上下文
                try:
                    user_context = self.context_manager.get_formatted_context(context_key) or []
                except Exception as e:
                    _log.error(f"获取上下文失败: {str(e)}")
                    user_context = []
                # 记录用户问题到上下文
                self.context_manager.add_to_context(context_key, "user", question)
                # 记录添加问题后的上下文长度
                context_after_question = self.context_manager.context_size(context_key)
                _log.info(f"添加问题后上下文长度: {context_after_question}")
                # 调用API时传入用户openid
                reply_content = await call_deepseek_api(
                    question, 
                    identity_manager=self.identity_manager, 
                    context=user_context,
                    user_openid=user_openid
                )
                # 记录AI回复到上下文
                self.context_manager.add_to_context(context_key, "assistant", reply_content)
                # 添加问题后的上下文长度检查
                if context_after_question == 1:
                    _log.info(f"首次对话已保存")
                    reply_content += "\n\n 【System】我已记住我们的对话，可以继续提问哦！（群聊上下文共享功能已打开！）"
                    
                
                # 添加上下文提示（检查添加回复后的长度）
                context_count = self.context_manager.context_size(context_key)
                capacity = self.context_manager.get_context_capacity(context_key)
                alert_threshold = self.context_manager.get_context_alert(context_key)
                
                if context_count >= alert_threshold:  # 接近上限时提示
                    _log.info(f"对话即将达到上限 (当前: {context_count}/{capacity})")
                    reply_content += f"\n\n 【System】我们的对话即将达到上限（{capacity}条），如需继续请使用'/重置'命令"
                
                # 添加AI回复前缀
                reply_content = f"【AI回复】{reply_content}"
            _log.info(f"回复内容: {reply_content}")
            await message.reply(content=reply_content)
            return  # 关键：处理完后退出
        
        # 添加重置上下文命令
        if clean_content == "/重置":
            self.context_manager.clear_context(context_key)
            _log.info(f"用户已清除上下文: {context_key}")
            await message.reply(content="【System】已清除我们的对话历史，可以重新开始了~")
            return
        
        # 非AI消息处理逻辑
        if clean_content == "/匹配":
            if not self.stamina_manager.can_use_stamina(user_openid):
            # 计算下次可用时间
                last_used_time = self.stamina_manager.user_stamina.get(
                    user_openid, {}).get('last_used', 0)
                next_available = int(last_used_time + 300 - time.time())
            
                if next_available > 0:
                    reply_content = f"【体力不足】你暂时没有体力进行匹配了 ꒦ິ^꒦\n" \
                                f"请休息一下，{next_available}秒后再试~"
                else:
                    reply_content = "【体力不足】你暂时没有体力进行匹配了 ꒦ິ^꒦\n" \
                                "请5分钟后再试~"
                
                await message.reply(content=reply_content)
                return
            
            # 消耗体力值
            self.stamina_manager.use_stamina(user_openid)
            stamina_left = self.stamina_manager.get_stamina(user_openid)
            
            # 添加体力值提示后缀
            stamina_suffix = f"\n\n【体力值】剩余: {stamina_left}/{self.stamina_manager.max_stamina} (每5分钟恢复1点)"

            # 判断彩蛋是否生成
            surprise = random.randint(1, 100)
            if surprise <= 5:
                reply_content = "嗯，让我看看你现在的匹配值。\n等等！∑(O_O；)\n居然是......\n114514！\n嗯哼哼，啊————......" 
            elif surprise >= 6 and surprise <= 15:
                reply_content = "嗯，让我看看你现在的匹配值。\n等等！∑(O_O；)\n居然是......\n1919810！\n不过，距离你喜欢的下北泽好像还差那么一点......" 
            else:
                # 生成1-100的随机数
                random_value = random.randint(1, 100)
            
                # 根据随机数范围选择不同的回复
                if random_value <= 25:
                    reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                    "不过，好低呀，要不要再试一次呢？这，位，杂，鱼？♡=•ㅅ＜=)"
                elif random_value <= 50 and random_value >= 26:
                    reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                    "还，还不错？再来一次？"
                elif random_value <= 75 and random_value >= 51:
                    reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                    "加油，还能更高的吧~"
                elif random_value <= 99 and random_value >= 76:
                    reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                    "咱们的默契可以有这么高？"
                else:
                    reply_content = f"果然你还是想试试这个匹配呢，我看看......\n没想到，是、是......\n100分！" \
                                    "满分，真是太棒了！૮ ´͈ ᗜ `͈ ა♡\n不过，好像还有更高的可能！"
            # 为特殊用户加载前缀   
            if user_openid in special_users:
                if user_openid in test_config.get("u1", []):
                    special_prefix = "\n嘿嘿，【最难忘的朋友】......\n"
                elif user_openid in test_config.get("u2", []):
                    special_prefix = "\n唔嗯，最喜欢找我匹配的御坂14156号，这次满意吗？\n"
                elif user_openid in test_config.get("u3", []):
                    special_prefix = "\n解顶？今天你还想找我测试怎样的人格呢，不会还是猫娘吧？\n"
                elif user_openid in test_config.get("u4", []):
                    special_prefix = "\n让我看看，你还会问我哪道数学题呢，Prizh？......\n"
                elif user_openid in test_config.get("u5", []):
                    special_prefix = "\n感觉好久都没见你出现了呢。\n"   
            else:
                special_prefix = ""

            # 添加用户特殊消息及体力值信息
            reply_content += special_prefix
            reply_content += stamina_suffix
            await message.reply(content=reply_content)
            return

        elif clean_content == "/自我介绍":
            reply_content = "【预设消息】很高兴见到你！\n我叫张可云，是ZZQ小豆同学设计的QQ机器人，现在正在努力找回失去的记忆，也许还能帮上你的忙。\n唔，看你的表情，总觉得你好像知道些什么？♪\nversion:0.1.3 〔demo〕"
        elif "【AI】" in message.content:
            reply_content = "【预设消息】AI的唤起方式被修改了哦~输入或在我的功能列表中选择“/AI”，即可唤起AI问答功能！"
        elif clean_content.startswith("早上好"):
            reply_content = "【预设消息】早上好！希望你开心~"
        elif clean_content.startswith("中午好"):
            reply_content = "【预设消息】中午好！祝愿你好胃口~"
        elif clean_content.startswith("下午好"):
            reply_content = "【预设消息】下午好！一定要多喝水~"
        elif clean_content.startswith("晚上好"):
            reply_content = "【预设消息】晚上好！一定要好好休息哦~"
        elif clean_content.startswith("天气"):
            reply_content = "【预设消息】唔，今天天气不错，确实适合出去走走~"
        elif clean_content.startswith("/帮助"):
            reply_content = "当前的可用重要指令：\n- /AI [问题]：唤起AI问答功能\n- /匹配：进行匹配测试\n- /重置：清除当前对话上下文\n- /自我介绍：获取我的自我介绍\n- /版本：查看当前版本信息\n- /Admin：管理员命令\n获取AI问答的相关帮助，请输入 /AI /帮助 或 /AI /help 或/AI /? 或 /AI /？ 获取哦！\nversion:0.1.3 〔demo〕"
        elif clean_content.startswith("/版本"):
            reply_content = "【预设消息】当前版本：0.1.3 〔demo〕\n当前更新内容：\n- 重磅更新！好友私聊功能上线，可以免输入“/AI”直接与我互动哦~更多友聊特供功能持续更新，体验可到：3889703981~\n- 为所有用户开放了AI测试版的匹配功能，为友聊功能取消了传统匹配功能\n- 反馈请到ZZQ小豆同学的邮箱：[icloud]zzqlittlebean哦~(由于平台限制，无法发送明文URL)\n\n"
        elif clean_content.startswith("/Admin"):
            if user_openid in ADMIN_IDS:
                reply_content = "【Admin】机器人即将重启，上下文即将清除！"
            else:
                reply_content = "【Admin】此命令暂时无效哦~"
        else:
            reply_content = f"【预设消息】唔，你说：[{message.content}]\n——出自节省算力......唔，还有经费的缘故，云云没法儿常态为你提供AI问答功能，真是抱歉呢~\n你应该，能原谅云云的吧？（戳手手）\n友情提示：在对我说的话中加上“/AI”，也许会有惊喜哦！\nversion:0.1.2 〔demo〕"
        
        _log.info(f"回复内容: {reply_content}")
        await message.reply(content=reply_content)

##########私聊消息处理部分##########
    async def on_direct_message_create(self, message: DirectMessage):
            # 获取用户唯一ID
            user_openid = message.author.id

            # 生成上下文键
            context_key = self.context_manager.get_context_key(user_openid)
                
            # 清理消息内容
            clean_content = message.content.strip().replace('\n', ' ').replace('\r', '')
                
            special_users = [
                *test_config.get("u1", []),
                *test_config.get("u2", []),
                *test_config.get("u3", []),
                *test_config.get("u4", []),
                *test_config.get("u5", [])
            ]

            # 记录日志
            _log.info(f"收到私聊消息 [用户: {user_openid}]: {clean_content}")
                
            # 处理AI请求
            if clean_content.startswith("/AI") or " /AI " in clean_content:
                _log.info(f"检测到私聊AI请求 [用户: {user_openid}]")
                question = clean_content.replace("/AI", "", 1).strip()
                    
                if not question:
                    reply_content = "【AI回复】你好呀，有什么问题需要我解答？"
                else:
                    # 获取用户上下文
                    try:
                        user_context = self.context_manager.get_formatted_context(context_key) or []
                    except Exception as e:
                        _log.error(f"获取上下文失败: {str(e)}")
                        user_context = []
                    # 记录用户问题到上下文
                    self.context_manager.add_to_context(context_key, "user", question)
                    # 记录添加问题后的上下文长度
                    context_after_question = self.context_manager.context_size(context_key)
                    _log.info(f"添加问题后上下文长度: {context_after_question}")
                        # 调用API时传入用户openid
                    reply_content = await call_deepseek_api(
                        question, 
                        identity_manager=self.identity_manager, 
                        context=user_context,
                        user_openid=user_openid
                    )
                    # 记录AI回复到上下文
                    self.context_manager.add_to_context(context_key, "assistant", reply_content)
                    # 添加上下文提示
                    context_count = self.context_manager.context_size(context_key)
                    capacity = self.context_manager.get_context_capacity(context_key)
                    alert_threshold = self.context_manager.get_context_alert(context_key)
                    
                    if context_after_question == 1:
                        _log.info(f"首次对话已保存")
                        reply_content += "\n\n 【System】我已记住我们的对话，可以继续提问哦！"
                    elif context_count >= alert_threshold:
                        _log.info(f"对话即将达到上限 (当前: {context_count}/{capacity})")
                        reply_content += f"\n\n 【System】我们的对话即将达到上限（{capacity}条），如需继续请使用'/重置'命令"
                            
                    # 添加AI回复前缀
                    reply_content = f"【AI回复】{reply_content}"
                
                # 私聊回复
                _log.info(f"回复内容: {reply_content}")
                await message.reply(content=reply_content)
                return
            
                
            # 处理重置上下文命令
            if clean_content == "/重置":
                self.context_manager.clear_context(context_key)
                _log.info(f"用户已清除上下文")
                await message.reply(content="【System】已清除我们的对话历史，可以重新开始了~")
                return
            
            # 处理匹配指令
            if clean_content == "/匹配":
                # 检查体力值
                if not self.stamina_manager.can_use_stamina(user_openid):
                    # 计算下次可用时间
                    last_used_time = self.stamina_manager.user_stamina.get(
                        user_openid, {}).get('last_used', 0)
                    next_available = int(last_used_time + 300 - time.time())
                    
                    if next_available > 0:
                        reply_content = f"【体力不足】你暂时没有体力进行匹配了 ꒦ິ^꒦\n" \
                                    f"请休息一下，{next_available}秒后再试~"
                    else:
                        reply_content = "【体力不足】你暂时没有体力进行匹配了 ꒦ິ^꒦\n" \
                                    "请5分钟后再试~"
                    
                    await message.reply(content=reply_content)
                    return
                
                # 消耗体力值
                self.stamina_manager.use_stamina(user_openid)
                stamina_left = self.stamina_manager.get_stamina(user_openid)
                
                # 添加体力值提示后缀
                stamina_suffix = f"\n\n【体力值】剩余: {stamina_left}/{self.stamina_manager.max_stamina} (每5分钟恢复1点)"

                # 判断彩蛋是否生成
                surprise = random.randint(1, 100)
                if surprise <= 5:
                    reply_content = "嗯，让我看看你现在的匹配值。\n等等！∑(O_O；)\n居然是......\n114514！\n嗯哼哼，啊————......" 
                elif 6 <= surprise <= 15:
                    reply_content = "嗯，让我看看你现在的匹配值。\n等等！∑(O_O；)\n居然是......\n1919810！\n不过，距离你喜欢的下北泽好像还差那么一点......" 
                else:
                    # 生成1-100的随机数
                    random_value = random.randint(1, 100)
                    
                    # 根据随机数范围选择不同的回复
                    if random_value <= 25:
                        reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                        "不过，好低呀，要不要再试一次呢？这，位，杂，鱼？♡=•ㅅ＜=)"
                    elif 26 <= random_value <= 50:
                        reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                        "还，还不错？再来一次？"
                    elif 51 <= random_value <= 75:
                        reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                        "加油，还能更高的吧~"
                    elif 76 <= random_value <= 99:
                        reply_content = f"果然你还是想试试这个匹配呢，我看看......\n嗯，{random_value}分！\n" \
                                        "咱们的默契可以有这么高？"
                    else:
                        reply_content = f"果然你还是想试试这个匹配呢，我看看......\n没想到，是、是......\n100分！" \
                                        "满分，真是太棒了！૮ ´͈ ᗜ `͈ ა♡\n不过，好像还有更高的可能！"
                
                # 为特殊用户加载前缀   
                if user_openid in special_users:
                    if user_openid in test_config.get("u1", []):
                        special_prefix = "\n嘿嘿，【最难忘的朋友】......\n"
                    elif user_openid in test_config.get("u2", []):
                        special_prefix = "\n唔嗯，最喜欢找我匹配的御坂14156号，这次满意吗？\n"
                    elif user_openid in test_config.get("u3", []):
                        special_prefix = "\n解顶？今天你还想找我测试怎样的人格呢，不会还是猫娘吧？\n"
                    elif user_openid in test_config.get("u4", []):
                        special_prefix = "\n让我看看，你还会问我哪道数学题呢，Prizh？......\n"
                    elif user_openid in test_config.get("u5", []):
                        special_prefix = "\n感觉好久都没见你出现了呢。\n"   
                else:
                    special_prefix = ""

                # 添加用户特殊消息及体力值信息
                reply_content += special_prefix
                reply_content += stamina_suffix

                _log.info(f"回复内容: {reply_content}")
                await message.reply(content=reply_content)
                return
            
            # 处理其他私聊消息
            elif clean_content == "/自我介绍":
                reply_content = "【私聊消息】很高兴见到你！\n我叫张可云，是ZZQ小豆同学设计的QQ机器人，现在正在努力找回失去的记忆，也许还能帮上你的忙。\n唔，看你的表情，总觉得你好像知道些什么？♪\nversion:0.1.3 〔demo〕"
            elif clean_content.startswith("早上好"):
                reply_content = "【私聊消息】早上好！新的一天开始啦，祝你有个愉快的心情~"
            elif clean_content.startswith("中午好"):
                reply_content = "【私聊消息】中午好！记得按时吃饭哦~"
            elif clean_content.startswith("下午好"):
                reply_content = "【私聊消息】下午好！工作/学习辛苦了，喝杯茶休息一下吧~"
            elif clean_content.startswith("晚上好"):
                reply_content = "【私聊消息】晚上好！早点休息，做个好梦~"
            elif clean_content.startswith("天气"):
                reply_content = "【私聊消息】需要天气信息吗？可以告诉我城市名称，我会帮你查询~"
            elif clean_content.startswith("/帮助"):
                reply_content = "当前的可用重要指令：\n- /AI [问题]：唤起AI问答功能\n- /匹配：进行匹配测试\n- /重置：清除当前对话上下文\n- /自我介绍：获取我的自我介绍\n- /版本：查看当前版本信息\n- /Admin：管理员命令\n获取AI问答的相关帮助，请输入 /AI /帮助 或 /AI /help 或/AI /? 或 /AI /？ 获取哦！\nversion:0.1.3 〔demo〕"
            elif clean_content.startswith("/版本"):
                reply_content = "【私聊预设】当前版本：0.1.3 〔demo〕\n当前更新内容：\n- 重磅更新！好友私聊功能上线，可以免输入“/AI”直接与我互动哦~更多友聊特供功能持续更新，体验可到：3889703981~\n- 为所有用户开放了AI测试版的匹配功能，为友聊功能取消了传统匹配功能\n- 反馈请到ZZQ小豆同学的邮箱：[icloud]zzqlittlebean哦~(由于平台限制，无法发送明文URL)\n\n" 
            elif clean_content.startswith("/Admin"):
                if user_openid in ADMIN_IDS:
                    reply_content = "【Admin】管理员您好！有什么需要我做的吗？"
                else:
                    reply_content = "【Admin】此命令需要管理员权限~"
            else:
                reply_content = f"【私聊消息】我收到了你的消息：{clean_content}\n" \
                                "出自节省算力......唔，还有经费的缘故，云云没法儿常态为你提供AI问答功能，真是抱歉呢~\n" \
                                "你应该，能原谅云云的吧？（戳手手）\n" \
                                "你可以使用以下命令：\n" \
                                "/AI [问题] - 向我提问\n" \
                                "/匹配 - 进行匹配游戏\n" \
                                "/重置 - 清除我们的对话历史\n" \
                                "version:0.1.3 〔demo〕"
            
            _log.info(f"频道私信回复内容: {reply_content}")
            await message.reply(content=reply_content)
##########好友私聊（测试）##########
    async def on_c2c_message_create(self, message: C2CMessage):
        # 获取用户唯一ID（好友私聊）
        user_openid = message.author.user_openid

        # 生成上下文键
        context_key = self.context_manager.get_context_key(user_openid)
            
        # 清理消息内容
        clean_content = message.content.strip().replace('\n', ' ').replace('\r', '')
            
        special_users = [
            *test_config.get("u1", []),
            *test_config.get("u2", []),
            *test_config.get("u3", []),
            *test_config.get("u4", []),
            *test_config.get("u5", [])
        ]

        # 记录日志
        _log.info(f"收到好友私聊消息 [用户: {user_openid}]: {clean_content}")
            
        # 处理其他好友私聊消息
        if clean_content.startswith("/帮助"):
            reply_content = "AI回答功能包含了简单问候、聊天与【调教】的功能哦！⌯>ᴗo⌯ .ᐟ.ᐟ你可以尝试：\n1、向我问好~\n2、尝试询问有关云云的一切\n3、让我按照一定的输出规则回答问题喵~\n在好友私聊模式下，提问无需输入“/AI”前缀哦~\n未来好友私聊功能还会有更多特色功能~\nversion:0.1.3 〔demo〕"
        elif clean_content.startswith("/版本"):
            reply_content = "当前版本：0.1.3 〔demo〕\n当前更新内容：\n- 重磅更新！好友私聊功能上线，可以免输入“/AI”直接与我互动哦~\n- 为所有用户开放了AI测试版的匹配功能\n- 反馈请到ZZQ小豆同学的邮箱：[icloud]zzqlittlebean哦~(由于平台限制，无法发送明文URL)\n\n"
        elif clean_content.startswith("/Admin"):
            if user_openid in ADMIN_IDS:
                reply_content = "【Admin】管理员您好！有什么需要我做的吗？"
            else:
                reply_content = "【Admin】此命令需要管理员权限~"
        else:
            # 处理AI请求
            _log.info(f"检测到好友私聊AI请求 [用户: {user_openid}]")
            question = clean_content.replace("/AI", "", 1).strip()
                
            if not question:
                reply_content = "你好呀，有什么问题需要我解答？"
            else:
                # 获取用户上下文
                try:
                    user_context = self.context_manager.get_formatted_context(context_key) or []
                except Exception as e:
                    _log.error(f"获取上下文失败: {str(e)}")
                    user_context = []
                # 记录用户问题到上下文
                self.context_manager.add_to_context(context_key, "user", question)
                if question=="打卡":
                    _log.info(f"检测到打卡请求 [用户: {user_openid}]")
                # 记录添加问题后的上下文长度
                context_after_question = self.context_manager.context_size(context_key)
                _log.info(f"添加问题后上下文长度: {context_after_question}")
                    # 调用API时传入用户openid
                reply_content = await call_deepseek_api(
                    question, 
                    identity_manager=self.identity_manager, 
                    context=user_context,
                    user_openid=user_openid
                )
                # 记录AI回复到上下文
                self.context_manager.add_to_context(context_key, "assistant", reply_content)
                
                # 添加上下文提示
                context_count = self.context_manager.context_size(context_key)
                capacity = self.context_manager.get_context_capacity(context_key)
                alert_threshold = self.context_manager.get_context_alert(context_key)
                
                if context_after_question == 1:
                    _log.info(f"首次对话已保存")
                    reply_content += "\n\n 【System】我已记住我们的对话，可以继续提问哦！\nversion:0.1.3 〔demo〕"
                elif context_count >= alert_threshold:
                    _log.info(f"对话即将达到上限 (当前: {context_count}/{capacity})")
                    reply_content += f"\n\n 【System】我们的对话即将达到上限（{capacity}条），如需继续请使用'/重置'命令"
            
            # 私聊回复
            _log.info(f"回复内容: {reply_content}")
            await self.api.post_c2c_message(
                openid=user_openid,
                msg_type=0,
                msg_id=message.id,
                content=reply_content
            )
            return
        
            
        # 处理重置上下文命令
        if clean_content == "/重置":
            self.context_manager.clear_context(context_key)
            _log.info(f"用户已清除上下文")
            await self.api.post_c2c_message(
                openid=user_openid,
                msg_type=0,
                msg_id=message.id,
                content="【System】已清除我们的对话历史，可以重新开始了~"
            )
            return
        
        _log.info(f"好友私聊回复内容: {reply_content}")
        await self.api.post_c2c_message(
            openid=user_openid,
            msg_type=0,
            msg_id=message.id,
            content=reply_content
        )



if __name__ == "__main__":
    # 通过预设置的类型，设置需要监听的事件通道
    # intents = botpy.Intents.none()
    # intents.public_messages=True

    # 通过kwargs，设置需要监听的事件通道
    intents = botpy.Intents(public_messages=True, direct_message=True)
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])