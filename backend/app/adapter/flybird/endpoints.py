"""飞鸽工作台的地址、字段名与帧字段号（docs/api/flybird.md，2026-11-26 实测）。"""

# 工作台（§1）：不带任何参数
WORKSPACE_URL = "https://im.jinritemai.com/pc_seller_v2/main/workspace"

# 会话列表（§2）：页面自己请求，必须是 pigeon 主机
CONV_LIST_HOST = "pigeon.jinritemai.com"
CONV_LIST_PATH = "/chat/api/backstage/conversation/get_current_conversation_list"
CONV_LIST_OK = 0
CONV_FIELDS = {
    "key": "subConversationId",
    "short_id": "parentConShortId",
    "last_at": "coreInfo.versionTime",
}
ERR_VERSION_TOO_LOW = 11001

# 长连接（§3）
WS_HOST = "ws.fxg.jinritemai.com"

# 外层帧字段号
FRAME_SERVICE = 3
FRAME_METHOD = 4
FRAME_PAYLOAD_TYPE = 7  # payload 的格式标记
FRAME_PAYLOAD = 8
PAYLOAD_TYPE_PB = b"pb"
PAYLOAD_TYPE_JSON = b"json"

# 业务帧 payload（pb）字段号与 cmd
PAYLOAD_CMD = 1
PAYLOAD_PUSH = 6  # 下行推送体 {cmd: {...}}
CMD_MESSAGE = 500
CMD_NOTIFY = 504  # 只带编号，不带正文
NEW_MESSAGE_CMDS = frozenset({CMD_MESSAGE, CMD_NOTIFY})

# 消息体：payload 字段 6 → 字段 500 → 字段 5
PUSH_MESSAGE = 5
MSG_FIELDS = {
    "message_id": 3,
    "conversation_id": 5,  # 会话 short ID，对应会话列表 parentConShortId
    "type": 6,
    "text": 8,
    "ext": 9,
    "sent_at_ms": 10,
}
EXT_KEY = 1
EXT_VALUE = 2
CHAT_MSG_TYPE = 1000  # 其他类型是系统命令

# 增量拉取（§2）：页面自己每 30 秒、以及收到 504 通知后请求；响应体与业务帧 payload 同构
# （字段 1 = cmd 12048，字段 6 = {12048: {...}}）。长连接断开期间与重连后的消息只从这里来
MSG_PULL_HOST = "fxg.jinritemai.com"
MSG_PULL_PATHS = frozenset({"/pigeon_im/v3/message/get_user_message"})
CMD_PULL = 12048
PULL_CONVERSATIONS = 1  # 重复：{1: 游标, 2: 会话}
PULL_CONV = 2
PULL_CONV_MESSAGES = 2  # 会话里重复的消息体，字段同 MSG_FIELDS
PULL_EXTRA = 2  # 另一组：{1: 重复的消息体}，实测为系统命令
PULL_EXTRA_MESSAGES = 1

# 发送方：扩展键 sender_role；没有该键是平台消息
ROLE_EXT_KEY = "sender_role"
ROLE_BY_VALUE = {"1": "buyer", "2": "agent", "4": "robot"}
# 买家昵称：买家消息的扩展键（推送与拉取都有）。个人信息，只留在内存
BUYER_NAME_EXT_KEY = "uname"

# 平台等待提醒（§3）：只记录结构，不作为计时来源
ATTENTION_SERVICE = 1
ATTENTION_METHOD = 5
ATTENTION_PAYLOAD_TYPE = PAYLOAD_TYPE_JSON
ATTENTION_TIME_FIELD = "attention_time"  # 位于 data 下，单位秒

# 拦截（§4），只给 read_guard.py 用：标记已读、输入状态
DROP_CMDS = frozenset({2002, 2031})
MARK_READ_PATH = "/pigeon_im/*/conversation/mark_read"
