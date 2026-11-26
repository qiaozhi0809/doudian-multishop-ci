import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ensureNotificationPermission, notifyStrong } from "./alert-channel";

const item = { id: 7, title: "店A 登录失效", body: "请重新登录" } as Parameters<typeof notifyStrong>[0];

function stubAudio(play: () => Promise<void>) {
  const created: string[] = [];
  vi.stubGlobal(
    "Audio",
    class {
      constructor(src: string) {
        created.push(src);
      }
      play = play;
    },
  );
  return created;
}

function stubNotification(permission: NotificationPermission, requested: NotificationPermission = "granted") {
  const shown: Array<{ title: string; options: NotificationOptions }> = [];
  const requestPermission = vi.fn().mockResolvedValue(requested);
  class Fake {
    static permission = permission;
    static requestPermission = requestPermission;
    constructor(title: string, options: NotificationOptions) {
      shown.push({ title, options });
    }
  }
  vi.stubGlobal("Notification", Fake);
  return { shown, requestPermission };
}

describe("notifyStrong", () => {
  beforeEach(() => {
    stubAudio(() => Promise.resolve());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("Notification 未定义时不抛，只播放声音", async () => {
    vi.stubGlobal("Notification", undefined);
    await expect(notifyStrong(item, { muted: false, documentHidden: true })).resolves.toEqual({
      played: true,
      shown: false,
    });
  });

  it("权限 denied：不显示，也不再请求", async () => {
    const { shown, requestPermission } = stubNotification("denied");
    const result = await notifyStrong(item, { muted: false, documentHidden: true });
    expect(result.shown).toBe(false);
    expect(shown).toHaveLength(0);
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it("play 被拒：played=false，不抛", async () => {
    stubAudio(() => Promise.reject(new Error("NotAllowedError")));
    await expect(notifyStrong(item, { muted: false, documentHidden: false })).resolves.toEqual({
      played: false,
      shown: false,
    });
  });

  it("静音：不播放", async () => {
    const created = stubAudio(() => Promise.resolve());
    const result = await notifyStrong(item, { muted: true, documentHidden: false });
    expect(result.played).toBe(false);
    expect(created).toHaveLength(0);
  });

  it("页面在前台：不发系统通知，也不请求权限", async () => {
    const { shown, requestPermission } = stubNotification("granted");
    const result = await notifyStrong(item, { muted: false, documentHidden: false });
    expect(result.shown).toBe(false);
    expect(shown).toHaveLength(0);
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it("后台且已授权：发系统通知，tag 为通知 id", async () => {
    const { shown } = stubNotification("granted");
    const result = await notifyStrong(item, { muted: false, documentHidden: true });
    expect(result).toEqual({ played: true, shown: true });
    expect(shown).toEqual([{ title: "店A 登录失效", options: { body: "请重新登录", tag: "7" } }]);
  });

  it("后台且未决定：不请求权限，不显示", async () => {
    const { shown, requestPermission } = stubNotification("default", "granted");
    const result = await notifyStrong(item, { muted: false, documentHidden: true });
    expect(requestPermission).not.toHaveBeenCalled();
    expect(result.shown).toBe(false);
    expect(shown).toHaveLength(0);
  });
});

describe("ensureNotificationPermission", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("不支持 Notification：unsupported", async () => {
    vi.stubGlobal("Notification", undefined);
    await expect(ensureNotificationPermission()).resolves.toBe("unsupported");
  });

  it("default：请求一次并返回结果", async () => {
    const { requestPermission } = stubNotification("default", "granted");
    await expect(ensureNotificationPermission()).resolves.toBe("granted");
    expect(requestPermission).toHaveBeenCalledTimes(1);
  });

  it("已授权或已拒绝：不请求", async () => {
    const granted = stubNotification("granted");
    await expect(ensureNotificationPermission()).resolves.toBe("granted");
    expect(granted.requestPermission).not.toHaveBeenCalled();
    const denied = stubNotification("denied");
    await expect(ensureNotificationPermission()).resolves.toBe("denied");
    expect(denied.requestPermission).not.toHaveBeenCalled();
  });

  it("请求抛错：不抛", async () => {
    const { requestPermission } = stubNotification("default");
    requestPermission.mockRejectedValue(new Error("boom"));
    await expect(ensureNotificationPermission()).resolves.toBe("default");
  });
});
