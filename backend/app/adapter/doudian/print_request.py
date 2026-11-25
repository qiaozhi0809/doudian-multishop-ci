"""补打面单数据请求体（flows 10 节：POST /shopuser/olSend/batchGetPrintInfos）。

公共参数（appid / __token 等）由 FxgClient 注入，这里只拼业务字段。
"""

from collections.abc import Sequence

# 空串 = 不限模板；有值时平台按模板过滤
TEMPLATE_CODE_ANY = ""


def print_infos_body(tracking_nos: Sequence[str]) -> dict:
    return {"trackInfos": [str(no) for no in tracking_nos], "templateCode": TEMPLATE_CODE_ANY}
