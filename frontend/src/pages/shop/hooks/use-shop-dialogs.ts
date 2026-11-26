import { useState } from "react";

/** 店铺页各个对话框 / 抽屉当前对着哪家店（null = 关闭）。 */
export function useShopDialogs() {
  const [addOpen, setAddOpen] = useState(false);
  const [egressShopId, setEgressShopId] = useState<number | null>(null);
  const [baseShopId, setBaseShopId] = useState<number | null>(null);
  const [resumeShopId, setResumeShopId] = useState<number | null>(null);
  const [editShopId, setEditShopId] = useState<number | null>(null);
  const [disableShopId, setDisableShopId] = useState<number | null>(null);
  /** 正在确认「开启飞鸽消息」的店。 */
  const [imShopId, setImShopId] = useState<number | null>(null);
  return {
    addOpen, setAddOpen, egressShopId, setEgressShopId, baseShopId, setBaseShopId,
    resumeShopId, setResumeShopId, editShopId, setEditShopId, disableShopId, setDisableShopId,
    imShopId, setImShopId,
  };
}
