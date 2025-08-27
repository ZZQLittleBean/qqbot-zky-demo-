# qqbot-zky-demo-
从QQ机器人官网文档改编，添加了AI问答功能，其中由main.py完成主要工作。
## 文件分类
### 1、文件夹
此处均为原版内容或预设内容，不需要进行修改
### 2、其他文件
#### 1）main.py
处理机器人的基本功能。对于预设消息可适当添加新内容
#### 2）api_utils.py
对机器人AI问答进行设定
#### 3）config.py
对机器人AI问答的API进行设定（当前仅适用DeepSeek，请自行在DeepSeek开放平台申请API并填入）
#### 4）config.yaml
与QQ机器人官方对接的部分（请自行创建机器人并记录appid、secret；这里添加了特殊用户标记的功能，需要填入对应的openid）
#### 5）keyword_dictioary.json
机器人的关键词词典（可按原有格式进行修改）
#### 6）identity_config.json
记录机器人AI问答的特殊用户表，与身份管理器联动（可按原有格式进行修改）
#### 7）identity_manager.py
身份管理器
#### 8）prompt_config.py
系统提示词（可按原有格式进行修改）
