"""官方打印组件的连接参数（flows 10 节实测：HTTPS 页面必须 WSS）。"""

PRINT_COMPONENT_WSS_PORT = 13999
PRINT_COMPONENT_HTTP_PORT = 13888
PRINT_COMPONENT_URL = f"wss://localhost:{PRINT_COMPONENT_WSS_PORT}"
PRINT_COMPONENT_ORIGIN = "https://fxg.jinritemai.com"

# 探测超时：组件未启动时尽快返回，界面据此置灰打印按钮
PROBE_TIMEOUT_S = 2.0
# 打印回执超时：组件渲染 + 驱动打印机可能较慢
PRINT_RESULT_TIMEOUT_S = 20.0
