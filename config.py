# -*- coding: utf-8 -*-
#Basic config section
BOT_CLIENT_NAME = ""
BOT_APP_ID = 10086 # Integer
BOT_APP_HASH = ""
BOT_NAME = ""

BOT_TOKEN = ""

WHITELIST_USER = ['114514',] # String to Integer
WHITELIST_GROUP = ['-1919810',] # String to Integer

# Chat Func Section
conversation_histories = {}
MAX_CONTEXT_LENGTH = 4096 * 4

MAX_SIZE_MB = 5 # Table message size limit
MAX_SIZE_DB = 50 # Database size limit

UPDATE_INTERVAL = 1.3 # Message edit times in seconds
CHAT_CONFIG = {
    "DEEPSEEK_API_KEY": "sk-{YOUR_API_KEY}",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "DEEPSEEK_MODEL_TYPE": "deepseek-chat"
}

default_promptes = '{Replace , your default prompts}'

# Image Predict Section

GD_client = "SmilingWolf/wd-tagger"
GD_model = "SmilingWolf/wd-swinv2-tagger-v3"
GD_general_thresh = 0.35
GD_character_thresh = 0.85

# Extractor section
gelbooru_endpoint = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&api_key={YOUR_KEY_HERE}&user_id={YOUR_USERID}&id=" # API key must be included
yandere_endpoint = "https://yande.re/post.json?tags=id:"

misskey_api_endpoint = "https://misskey.io/api/notes/show"

baraag_endpoint = "https://baraag.net/api/v1/statuses/"

nhnetai_endpoint = "https://nhentai.net/api/gallery/"

pixiv_refresh_token = "{YOUR_PIXIV_TOKEN}"

e_hentai_endpoint = "https://e-hentai.org/api.php"
exhentai_endpoint = "https://exhentai.org/api.php"
exhentai_config = {
    "cookie" : "{YOUR_COOKIE_HERE}",
    "threads" : 3,
    "retru_count" : 8,
    "delay_time" : 9
}
r2_config = {
    "account_id":"",
    "bucket_name":"",
    "access_key":"",
    "secret_key":"",
    "domain":""
}

discord_token = ''

# Handler
REACTION_LIST = ['🙉','👾','🍌','🍾','🎄','👏','😢','🕊','👀','😱','😘','🥴','🎅','🔥','👻','🤪','😁','🤩','🤝','💘','⚡','🌭','🤗','💯','🎃','💋','😭','🤷‍♂️','👨‍💻','💅','🤓','🌚','👌','🎉','🙏','❤','🙈','🤯','🤷','😴','😇','🥰','😍','😈','😎','🙊','🐳','🆒','🍓','👍','🏆','🦄','🤷‍♀️','🥱']

STICKER_TRIGGER_COUNT = 3

ACTION_TRIGGER_RATE = 2

# Opt 1Panel API
panel_sail_token = ""
panel_sail_url = ""
panel_nas_token = ""
panel_nas_url = ""
# Fanbox Config section
FANBOX_CONFIG = {
    "account1":"{YOUR_FANBOX_SESSION_COOKIE}",
}
fanbox_max_file_limit_gb = 2
fanbox_max_file_count = 6
fanbox_single_file_limit_mb = 4
fanbox_max_retries = 5
fanbox_download_thread = 4
fanbox_proxies = {
            "http": "",
            "https": ""
        }
api_proxy = ""

# for hitomi or Exhnetai
MINIO_CONFIG = {
        'endpoint_url': '',
        'access_key': '',
        'secret_key': '',
        'bucket_name': ''
    }

# Other
COMMAND_INFO_TEXT = (
    "     指令：\n"
    "     /start - 显示此信息\n"
    "     /chat - 聊天功能\n"
    "     /prompts [content]- 提示词修改\n"
    "     /prompts_query - 查询当前提示词\n"
    "     /prompts_upload - 上传当前提示词\n"
    "     /prompts_delete [PromptsID] - 删除自己的某个提示词\n"
    "     /prompts_check - 查看自己上传过的所有提示词\n"
    "     /prompts_explore - 查看公共提示词库\n"
    "     /prompts_view [PromptsID] - 查看某个提示词内容\n"
    "     /newchat - 清空对话\n"
    "     /get_tags [Image] - 查询二次元图片tag\n"
    "     /trans [Content] - 好好说话(缩写翻译)\n"
    "     /kemomimi - 随机kemomimi美图\n"
    "     /kemomimi_update - 更新kemomimi数据库\n"
    "     /more - (管理员)查看更多指令\n"
    "========================\n"
    # Defined by userconfig
    # "     Extractor支持的站点：\n"
    # "     x.com or twitter.com\n"
    # "     misskey.io\n"
    # "     baraag.net\n"
    # "     yande.re\n"
    # "     gelbooru.com\n"
    # "     kemono.cr\n"
    # "     plurk.com\n"
    # "     nhentai.net\n"
    # "     hitomi.la\n"
    # "     fanbox.cc [白名单用户限制]\n"
    # "     pixiv.net [仅限私聊]\n"
    # "     exhentai.org or e-hentai.org [白名单群组限制]\n"
    # "     discord.com [出于安全考虑，管理员限制访问]\n"
)
START_INFO_TEXT =(
    "========================\n"
    "YOUR INTRODUCTION HERE \n"
)