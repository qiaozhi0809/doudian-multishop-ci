/** 提示的状态色与图标 */
export type NoticeTone = "success" | "info" | "warning" | "danger";

/** 事件弹窗的种类（新订单、新售后、新消息、其他通知）：比操作结果提示多一条状态色左边线，并按种类换图标。 */
export type NoticeEvent = "order" | "aftersale" | "message" | "system";
