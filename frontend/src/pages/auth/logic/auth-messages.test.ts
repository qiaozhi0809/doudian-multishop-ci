import { ApiError } from "@/lib/api-client";
import { authErrorMessage, validatePassword } from "./auth-messages";

const err = (status: number, type = "X") => new ApiError({ type, message: "m", status });

describe("validatePassword", () => {
  it("少于 8 位提示，8 位及以上通过", () => {
    expect(validatePassword("1234567")).toBe("密码至少 8 位");
    expect(validatePassword("")).toBe("密码至少 8 位");
    expect(validatePassword("12345678")).toBeNull();
  });
});

describe("authErrorMessage", () => {
  it("登录 401 为账号或密码错误", () => {
    expect(authErrorMessage("login", err(401))).toBe("账号或密码错误");
  });
  it("登录 423 为锁定提示", () => {
    expect(authErrorMessage("login", err(423))).toBe("尝试次数过多，请 5 分钟后再试");
  });
  it("初始化 409 提示已有管理员", () => {
    expect(authErrorMessage("setup", err(409))).toBe("管理员已创建，请直接登录");
  });
  it("网络不通沿用客户端给出的说明", () => {
    const e = new ApiError({ type: "NetworkError", message: "无法连接本地服务，请确认后端已启动", status: 0 });
    expect(authErrorMessage("login", e)).toBe("无法连接本地服务，请确认后端已启动");
  });
  it("其他错误给出原因与下一步", () => {
    expect(authErrorMessage("login", err(500))).toBe("登录失败，请稍后重试");
    expect(authErrorMessage("changePassword", new Error("boom"))).toBe("修改密码失败，请稍后重试");
  });
});
