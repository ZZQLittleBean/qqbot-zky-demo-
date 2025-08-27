import json
import os
import logging

class IdentityManager:
    def __init__(self, config_path='identity_config.json', logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.config_path = config_path
        
        # 先初始化默认身份配置
        self.default_identity = {
            "name": "朋友",
            "role": "普通用户",
            "personality": "你与他是一般朋友关系。当他提问时，你可以用友好但保持一定距离的语气回应，避免过于亲密的表达。",
            "special_privileges": [],
            "is_special": False,  # 新增特殊用户标记
            "is_admin": False,     # 新增管理员标记
            "applicable_rules": []  # 默认没有规则
        }
        
        # 然后加载身份配置
        self.identities = self.load_identities()
        
        self.logger.info(f"身份管理器初始化完成，加载了 {len(self.identities)} 个身份配置")
        self.logger.info(f"身份管理器初始化，配置文件: {config_path}")
        self.logger.info(f"加载身份数量: {len(self.identities)}")
        
        # 记录所有加载的身份
        for user_id, identity in self.identities.items():
            self.logger.info(f"用户 {user_id}: {identity.get('name', '未知')} - 规则: {identity.get('applicable_rules', [])}")
    
    def load_identities(self):
        """从配置文件加载身份配置"""
        try:
            # 如果配置文件不存在，创建空文件
            if not os.path.exists(self.config_path):
                self.logger.warning(f"创建空身份配置文件: {self.config_path}")
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                identities = json.load(f)
                self.logger.info(f"成功加载 {len(identities)} 个身份配置")
                return identities
        except Exception as e:
            self.logger.error(f"加载身份配置失败: {str(e)}")
            return {}
    
    def get_identity(self, user_openid):
        """获取用户身份信息"""
        identity = self.identities.get(user_openid, self.default_identity)
        self.logger.debug(f"获取身份: {user_openid} -> {identity.get('name', '未知')}")

        # 确保所有必要字段存在
        identity.setdefault("is_special", False)
        identity.setdefault("is_admin", False)
        identity.setdefault("special_privileges", [])
        identity.setdefault("applicable_rules", [])
        
        return identity
    
    def format_identity_for_prompt(self, user_openid):
        """格式化身份信息用于提示词"""
        identity = self.get_identity(user_openid)
        formatted = "\n".join([
            f"姓名: {identity['name']}",
            f"角色: {identity['role']}",
            f"特殊权限: {', '.join(identity['special_privileges']) if identity['special_privileges'] else '无'}",
            f"特殊用户: {'是' if identity['is_special'] else '否'}",
            f"管理员: {'是' if identity['is_admin'] else '否'}",
            f"适用规则: {', '.join(identity['applicable_rules']) if identity['applicable_rules'] else '无'}"
        ])
        self.logger.debug(f"格式化身份信息: {formatted}")
        return formatted
    
    def add_rule_to_user(self, user_openid, rule_name):
        """为用户添加特定规则"""
        identity = self.get_identity(user_openid)
        if rule_name not in identity["applicable_rules"]:
            identity["applicable_rules"].append(rule_name)
            self.identities[user_openid] = identity
            self.save_identities()
            self.logger.info(f"为用户 {user_openid} 添加规则: {rule_name}")
            return True
        return False
    
    def add_special_user(self, user_openid, name, role, personality, is_admin=False, privileges=[]):
        """添加特殊用户配置"""
        self.identities[user_openid] = {
            "name": name,
            "role": role,
            "personality": personality,
            "is_special": True,
            "is_admin": is_admin,
            "special_privileges": privileges
        }
        self.save_identities()
        self.logger.info(f"添加特殊用户: {name} ({user_openid})")
    
    def save_identities(self):
        """保存身份配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.identities, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存身份配置失败: {str(e)}")
            return False