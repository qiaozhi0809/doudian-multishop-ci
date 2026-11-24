export class ApiError extends Error {
  type: string;
  shopId: number | null;
  detail: unknown;
  status: number;

  constructor(init: { type: string; message: string; status: number; shopId?: number | null; detail?: unknown }) {
    super(init.message);
    this.name = "ApiError";
    this.type = init.type;
    this.status = init.status;
    this.shopId = init.shopId ?? null;
    this.detail = init.detail ?? null;
  }
}

export type QueryValue = string | number | boolean | null | undefined | Array<string | number>;
export type Query = Record<string, QueryValue>;

function buildUrl(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      if (value.length > 0) params.set(key, value.join(","));
    } else {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body?.error;
    if (e && typeof e.type === "string") {
      return new ApiError({
        type: e.type,
        message: typeof e.message === "string" ? e.message : res.statusText,
        status: res.status,
        shopId: e.shop_id,
        detail: e.detail,
      });
    }
  } catch {
    // 非 JSON 响应，回落到 HttpError
  }
  return new ApiError({ type: "HttpError", message: res.statusText || `HTTP ${res.status}`, status: res.status });
}

async function request<T>(method: string, path: string, query?: Query, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), init);
  } catch {
    throw new ApiError({ type: "NetworkError", message: "无法连接本地服务，请确认后端已启动", status: 0 });
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, query),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, undefined, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, undefined, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, undefined, body),
};
