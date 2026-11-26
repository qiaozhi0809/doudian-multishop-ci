"""飞鸽已读拦截（docs/api/flybird.md §4）：注入脚本只丢两种上行帧，路由只中止已读请求。

脚本用本机 Node 跑，WebSocket 是假的（只记录原 send 收到了什么）；没有 Node 时跳过。
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from playwright._impl.isomorphic.url_match import url_matches

from app.adapter.flybird import endpoints, read_guard
from tests.adapter.flybird_parse_test import cmd_frame, outer_frame, pb, varint

WS_URL = "wss://ws.fxg.jinritemai.com/ws/v2?token=test-token&aid=1383"
OTHER_URL = "wss://frontier.snssdk.com/ws/v2"
MARK_READ_URL = "https://fxg.jinritemai.com/pigeon_im/v3/conversation/mark_read"


class FakeContext:
    def __init__(self):
        self.scripts: list[str] = []
        self.routes: list[tuple] = []

    async def add_init_script(self, script=None, path=None):
        self.scripts.append(script)

    async def route(self, pattern, handler):
        self.routes.append((pattern, handler))


class FakeRoute:
    """记录处理函数在 route 上调用过的任何方法。"""

    def __init__(self):
        self.calls: list[str] = []

    def __getattr__(self, name):
        async def record(*_args, **_kwargs):
            self.calls.append(name)

        return record


async def installed() -> FakeContext:
    context = FakeContext()
    await read_guard.install(context)
    return context


# ---- 安装与 HTTP 兜底 ----


async def test_install_injects_rendered_script():
    context = await installed()

    assert context.scripts == [read_guard.render_script()]


async def test_route_handler_only_aborts():
    context = await installed()
    [(_, handler)] = context.routes
    route = FakeRoute()

    await handler(route)

    assert route.calls == ["abort"]
    assert read_guard.blocked_count(context) == 1


async def test_blocked_count_is_per_context():
    first, second = await installed(), await installed()
    [(_, first_handler)], [(_, second_handler)] = first.routes, second.routes

    await first_handler(FakeRoute())
    await second_handler(FakeRoute())
    await second_handler(FakeRoute())

    assert read_guard.blocked_count(first) == 1
    assert read_guard.blocked_count(second) == 2
    assert read_guard.blocked_count(FakeContext()) == 0  # 没装过拦截


async def test_failed_abort_is_not_counted():
    context = await installed()
    [(_, handler)] = context.routes

    class Broken:
        async def abort(self):
            raise RuntimeError("route closed")

    with pytest.raises(RuntimeError):
        await handler(Broken())

    assert read_guard.blocked_count(context) == 0


@pytest.mark.parametrize("url", [
    MARK_READ_URL,
    f"{MARK_READ_URL}?aid=1383&a_bogus=test%2Fsign",
    f"{MARK_READ_URL}?aid=1383&a_bogus=test/sign",  # 签名里的斜杠未转义
    "https://fxg.jinritemai.com/pigeon_im/v1/conversation/mark_read?aid=1383",
])
async def test_route_pattern_covers_mark_read(url):
    [(pattern, _)] = (await installed()).routes

    assert url_matches(None, url, pattern)


@pytest.mark.parametrize("url", [
    "https://fxg.jinritemai.com/pigeon_im/v3/message/get_by_conversation?aid=1383",
    "https://fxg.jinritemai.com/pigeon_im/v3/message/get_user_message",
    "https://fxg.jinritemai.com/pigeon_im/v2/conversation/create",
])
async def test_route_pattern_leaves_other_requests(url):
    [(pattern, _)] = (await installed()).routes

    assert not url_matches(None, url, pattern)


# ---- 注入脚本 ----


def test_script_has_drop_cmds_from_endpoints(monkeypatch):
    monkeypatch.setattr(endpoints, "DROP_CMDS", frozenset({4242, 4343}))
    monkeypatch.setattr(endpoints, "WS_HOST", "ws.example.test")

    script = read_guard.render_script()

    for expected in ("4242", "4343", "ws.example.test"):
        assert expected in script
    assert "__" not in script  # 占位符都已填上


def test_script_template_has_no_literal_constants():
    template = read_guard.SCRIPT_PATH.read_text(encoding="utf-8")

    for literal in ("2002", "2031", "jinritemai"):
        assert literal not in template


HARNESS = """
const calls = [];
globalThis.WebSocket = class {
  constructor(url) { this.url = url; }
  send(data) { calls.push({ socket: this, data }); return "original"; }
};
__SCRIPT__
const build = {
  buffer: (bytes) => Uint8Array.from(bytes).buffer,
  view: (bytes) => Uint8Array.from(bytes),
  offset: (bytes) => new Uint8Array(Uint8Array.from([255, 255, 255, ...bytes, 255]).buffer,
                                    3, bytes.length),
  dataview: (bytes) => new DataView(Uint8Array.from(bytes).buffer),
  text: (bytes) => String.fromCharCode(...bytes),
};
const results = CASES.map(({ url, kind, bytes }) => {
  const socket = new WebSocket(url);
  const data = build[kind](bytes);
  const before = calls.length;
  const returned = socket.send(data);
  if (calls.length === before) return "dropped";
  const call = calls[calls.length - 1];
  const intact = call.socket === socket && call.data === data && returned === "original";
  return intact ? "sent" : "altered";
});
console.log(JSON.stringify(results));
"""


def run_script(tmp_path: Path, cases: list[tuple[str, str, bytes]]) -> list[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("本机没有 node")
    payload = [{"url": url, "kind": kind, "bytes": list(raw)} for url, kind, raw in cases]
    source = f"const CASES = {json.dumps(payload)};\n" + HARNESS.replace(
        "__SCRIPT__", read_guard.render_script()
    )
    script = tmp_path / "harness.js"
    script.write_text(source, encoding="utf-8")
    done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_script_drops_mark_read_frame(tmp_path):
    results = run_script(tmp_path, [
        (WS_URL, "buffer", cmd_frame(2002)),
        (WS_URL, "buffer", cmd_frame(16001)),
    ])

    assert results == ["dropped", "sent"]


@pytest.mark.parametrize("kind", ["buffer", "view", "offset", "dataview"])
def test_script_reads_every_binary_shape(tmp_path, kind):
    results = run_script(tmp_path, [
        (WS_URL, kind, cmd_frame(2002)),
        (WS_URL, kind, cmd_frame(2031)),
        (WS_URL, kind, cmd_frame(2000)),
    ])

    assert results == ["dropped", "dropped", "sent"]


def test_script_drops_frame_with_request_body_and_fixed_width_fields(tmp_path):
    fixed = varint(20 << 3 | 1) + bytes(8) + varint(21 << 3 | 5) + bytes(4)
    with_body = outer_frame(pb(1, 2002) + pb(8, pb(604, pb(1, "conv-test-1"))))

    results = run_script(tmp_path, [
        (WS_URL, "view", with_body),
        (WS_URL, "view", fixed + cmd_frame(2002)),
    ])

    assert results == ["dropped", "dropped"]


def test_script_only_touches_flybird_host(tmp_path):
    results = run_script(tmp_path, [(OTHER_URL, "buffer", cmd_frame(2002))])

    assert results == ["sent"]


def test_script_sends_whatever_it_cannot_read(tmp_path):
    frame = cmd_frame(2002)
    cases = [
        (WS_URL, "text", b"hi"),
        (WS_URL, "view", b""),
        (WS_URL, "view", b"\xff\xff"),
        (WS_URL, "view", b"\x08" + b"\xff" * 11),  # varint 超过 10 字节
        (WS_URL, "view", outer_frame(b"")),
        (WS_URL, "view", outer_frame(pb(6, "x") + pb(1, 2002))),  # cmd 不是首字段
        (WS_URL, "view", outer_frame(pb(1, "2002"))),  # cmd 不是 varint
        (WS_URL, "view", pb(8, 2002)),  # 字段 8 不是 length-delimited
        (WS_URL, "view", b"\x0b" + frame),  # 未知 wire type
    ]
    cases += [(WS_URL, "view", frame[:end]) for end in range(len(frame))]

    assert run_script(tmp_path, cases) == ["sent"] * len(cases)
