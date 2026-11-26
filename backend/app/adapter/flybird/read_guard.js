// 飞鸽已读拦截脚本（docs/api/flybird.md §4）：页面加载前注入。
// 只丢弃发往飞鸽长连接、cmd 在名单里的上行帧；其余原样发送，读不懂的也照常发送。
// 常量由 read_guard.py 从 endpoints.py 填入。
(() => {
  const config = __READ_GUARD_CONFIG__;
  const dropCmds = new Set(config.dropCmds);

  // protobuf wire type
  const VARINT = 0;
  const FIXED64 = 1;
  const LENGTH = 2;
  const FIXED32 = 5;
  const VARINT_MAX_BYTES = 10;

  const toBytes = (data) => {
    if (data instanceof ArrayBuffer) return new Uint8Array(data);
    if (ArrayBuffer.isView(data)) {
      return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    }
    return null;
  };

  // 超过 2^53 的值会丢精度，只影响用不到的 seq 一类字段
  const readVarint = (bytes, pos) => {
    let value = 0;
    for (let i = 0; i < VARINT_MAX_BYTES && pos + i < bytes.length; i += 1) {
      const byte = bytes[pos + i];
      value += (byte & 0x7f) * 2 ** (7 * i);
      if (byte < 0x80) return [value, pos + i + 1];
    }
    throw new Error("varint 不完整");
  };

  // 读一个字段：varint 给出数值，length-delimited 给出内容，定长字段给 null
  const readField = (bytes, start) => {
    const [tag, afterTag] = readVarint(bytes, start);
    const number = Math.floor(tag / 8);
    const wire = tag % 8;
    if (wire === VARINT) {
      const [value, next] = readVarint(bytes, afterTag);
      return { number, wire, value, next };
    }
    let from = afterTag;
    let size;
    if (wire === LENGTH) [size, from] = readVarint(bytes, afterTag);
    else if (wire === FIXED64) size = 8;
    else if (wire === FIXED32) size = 4;
    else throw new Error("未知 wire type");
    const next = from + size;
    if (next > bytes.length) throw new Error("长度越界");
    const value = wire === LENGTH ? bytes.subarray(from, next) : null;
    return { number, wire, value, next };
  };

  // 外层帧的 payload 字段里第一个字段就是 cmd
  const frameCmd = (bytes) => {
    let pos = 0;
    while (pos < bytes.length) {
      const field = readField(bytes, pos);
      if (field.number === config.payloadField && field.wire === LENGTH) {
        const first = readField(field.value, 0);
        return first.number === config.cmdField && first.wire === VARINT ? first.value : null;
      }
      pos = field.next;
    }
    return null;
  };

  const shouldDrop = (socket, data) => {
    if (!String(socket.url).includes(config.wsHost)) return false;
    const bytes = toBytes(data);
    return bytes !== null && dropCmds.has(frameCmd(bytes));
  };

  // Proxy 包原生函数，toString 仍显示原生
  WebSocket.prototype.send = new Proxy(WebSocket.prototype.send, {
    apply(target, socket, args) {
      try {
        if (shouldDrop(socket, args[0])) return undefined;
      } catch {
        // 解析异常一律照常发送
      }
      return Reflect.apply(target, socket, args);
    },
  });
})();
