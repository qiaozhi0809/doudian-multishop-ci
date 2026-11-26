/** 滚动条平时隐藏、滚动时显示：给正在滚动的元素加 data-scrolling，停下 HIDE_AFTER_MS 后去掉。
 *  全站只挂一个捕获阶段的监听，样式在 styles.css。 */

export const HIDE_AFTER_MS = 800;
const ATTR = "data-scrolling";

export function installScrollReveal(doc: Document = document): () => void {
  const timers = new WeakMap<Element, ReturnType<typeof setTimeout>>();

  const onScroll = (event: Event) => {
    const target = event.target;
    const el = target instanceof Element ? target : doc.documentElement;
    el.setAttribute(ATTR, "");
    const previous = timers.get(el);
    if (previous !== undefined) clearTimeout(previous);
    timers.set(el, setTimeout(() => {
      el.removeAttribute(ATTR);
      timers.delete(el);
    }, HIDE_AFTER_MS));
  };

  doc.addEventListener("scroll", onScroll, { capture: true, passive: true });
  return () => doc.removeEventListener("scroll", onScroll, { capture: true });
}
