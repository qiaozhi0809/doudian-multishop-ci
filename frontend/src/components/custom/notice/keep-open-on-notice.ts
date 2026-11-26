/** 浮动提示容器上的标记 */
export const NOTICE_ROOT = "data-notice-root";

/**
 * 对话框、抽屉的 `onInteractOutside`：点右下角提示（如关掉一条常驻的新售后）不算点到弹窗外面，弹窗不关。
 */
export function keepOpenOnNotice(event: { target: EventTarget | null; preventDefault: () => void }) {
  if (event.target instanceof Element && event.target.closest(`[${NOTICE_ROOT}]`)) event.preventDefault();
}
