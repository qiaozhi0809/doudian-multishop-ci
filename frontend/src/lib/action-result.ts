/** 写操作的结果：失败时带给用户看的原因（对话框就地显示）。放在 api-client 之外，展示组件也能引用这个类型。 */
export type ActionResult = { ok: true } | { ok: false; error: string };
