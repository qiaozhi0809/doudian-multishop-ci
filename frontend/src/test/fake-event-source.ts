/** EventSource 替身：测试里用 emit 触发后端事件。 */
export class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  private listeners = new Map<string, Set<(e: Event) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: Event) => void) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name)!.add(fn);
  }
  removeEventListener(name: string, fn: (e: Event) => void) {
    this.listeners.get(name)?.delete(fn);
  }
  close() {
    this.closed = true;
  }
  emit(name: string, data?: unknown) {
    const event = data === undefined ? new Event(name) : Object.assign(new Event(name), { data: JSON.stringify(data) });
    this.listeners.get(name)?.forEach((fn) => fn(event));
  }

  /** 安装为全局 EventSource，返回清理函数。 */
  static install(): () => void {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    return () => vi.unstubAllGlobals();
  }
  static latest(): FakeEventSource {
    return FakeEventSource.instances[FakeEventSource.instances.length - 1];
  }
}
