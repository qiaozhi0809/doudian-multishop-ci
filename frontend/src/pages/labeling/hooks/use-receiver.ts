import { useCallback, useState } from "react";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { actionErrorMessage } from "../logic/label-messages";

interface ReceiverState {
  orderId: number | null;
  data: components["schemas"]["ReceiverOut"] | null;
  message: string | null;
  pending: boolean;
}

const CLOSED: ReceiverState = { orderId: null, data: null, message: null, pending: false };

/** 按需查看收件人：明文只显示、不入库；429 时给出冷却提示（flows 7.3）。 */
export function useReceiver() {
  const [state, setState] = useState<ReceiverState>(CLOSED);

  const open = useCallback(async (orderId: number) => {
    setState({ orderId, data: null, message: null, pending: true });
    try {
      const data = await api.post<components["schemas"]["ReceiverOut"]>(
        `/api/orders/${orderId}/receiver`,
      );
      setState({ orderId, data, message: null, pending: false });
    } catch (e) {
      setState({ orderId, data: null, message: actionErrorMessage(e), pending: false });
    }
  }, []);

  return {
    ...state,
    open,
    close: () => setState((prev) => ({ ...prev, orderId: null })),
  };
}
