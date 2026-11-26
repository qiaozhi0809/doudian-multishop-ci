import { describe, expect, it } from "vitest";
import {
  componentNotice,
  jobBadge,
  printGate,
  selectedWaybillIds,
  summarizePrint,
  type PrintJobLike,
  type WaybillPrintLike,
} from "./print-status";

const job = (over: Partial<PrintJobLike> = {}): PrintJobLike => ({
  id: 1,
  waybill_id: 10,
  printer_name: "A",
  status: "success",
  result_code: "success",
  result_detail: null,
  attempts: 1,
  created_at: "2026-11-25T00:00:00Z",
  finished_at: "2026-11-25T00:00:10Z",
  ...over,
});

const row = (over: Partial<WaybillPrintLike> = {}): WaybillPrintLike => ({
  waybill_id: 10,
  waybill_no: "79200000000001",
  waybill_status: "active",
  has_print_data: true,
  job: null,
  ...over,
});

describe("printGate", () => {
  it("只允许对已打单（待发货）的面单打印", () => {
    expect(printGate({ stage: "pending", selectedCount: 1, componentAvailable: true, busy: false }))
      .toEqual({ disabled: true, reason: "先打单，再到「待发货」里打印" });
  });

  it("组件未启动时禁用并提示原因", () => {
    expect(printGate({ stage: "labeled", selectedCount: 1, componentAvailable: false, busy: false }))
      .toEqual({ disabled: true, reason: "请先启动抖店官方打印组件" });
  });

  it("组件状态未知（探测中）时禁用并提示", () => {
    expect(printGate({ stage: "labeled", selectedCount: 1, componentAvailable: null, busy: false }))
      .toEqual({ disabled: true, reason: "正在检测打印组件" });
  });

  it("没有勾选或正在执行时禁用", () => {
    expect(printGate({ stage: "labeled", selectedCount: 0, componentAvailable: true, busy: false }).disabled).toBe(true);
    expect(printGate({ stage: "labeled", selectedCount: 1, componentAvailable: true, busy: true }).disabled).toBe(true);
  });

  it("没有勾选时提示先勾选订单", () => {
    expect(printGate({ stage: "labeled", selectedCount: 0, componentAvailable: true, busy: false }).reason)
      .toBe("先勾选订单");
  });

  it("组件可用且有勾选时放行", () => {
    expect(printGate({ stage: "labeled", selectedCount: 2, componentAvailable: true, busy: false }))
      .toEqual({ disabled: false, reason: null });
  });
});

describe("selectedWaybillIds", () => {
  it("只取勾选且有面单的订单", () => {
    const rows = [
      { id: 1, waybill: { id: 11 } },
      { id: 2, waybill: null },
      { id: 3, waybill: { id: 13 } },
    ];
    expect(selectedWaybillIds(new Set([1, 2]), rows)).toEqual([11]);
    expect(selectedWaybillIds(new Set([1, 3]), rows)).toEqual([11, 13]);
  });
});

describe("componentNotice", () => {
  it("组件在线不提示", () => {
    expect(componentNotice({ available: true, printers: [], default_printer: null, error: null, checked_at: "" })).toBeNull();
  });

  it("组件不在线给出启动引导", () => {
    const notice = componentNotice({ available: false, printers: [], default_printer: null, error: "x", checked_at: "" });
    expect(notice).toContain("打印组件未启动");
    expect(notice).toContain("托盘");
  });

  it("状态未知时不提示（等待探测）", () => {
    expect(componentNotice(undefined)).toBeNull();
  });
});

describe("jobBadge", () => {
  it("没有任务不显示徽章", () => {
    expect(jobBadge(null)).toBeNull();
  });

  it("排队中 / 成功 / 失败 / 无打印数据分别显示", () => {
    expect(jobBadge(job({ status: "queued" }))).toEqual({ label: "打印中", tone: "neutral" });
    expect(jobBadge(job({ status: "success" }))).toEqual({ label: "已打印", tone: "success" });
    expect(jobBadge(job({ status: "failed", result_code: "component_failed" })))
      .toEqual({ label: "打印失败", tone: "danger" });
    expect(jobBadge(job({ status: "failed", result_code: "no_print_data" })))
      .toEqual({ label: "需手动补打", tone: "warning" });
  });
});

describe("summarizePrint", () => {
  it("没有任务时不显示汇总", () => {
    expect(summarizePrint([row()])).toBeNull();
  });

  it("有排队任务时显示剩余张数", () => {
    expect(summarizePrint([row({ job: job({ status: "queued" }) })])).toBe("打印中：剩余 1 张面单");
  });

  it("结束后按成功 / 手动 / 失败汇总", () => {
    expect(summarizePrint([
      row({ waybill_id: 1, job: job({ status: "success" }) }),
      row({ waybill_id: 2, job: job({ status: "failed", result_code: "no_print_data" }) }),
      row({ waybill_id: 3, job: job({ status: "failed", result_code: "component_failed" }) }),
    ])).toBe("打印结束：成功 1，需手动补打 1，失败 1");
  });
});
