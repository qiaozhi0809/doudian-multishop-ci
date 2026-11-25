import { useQuery } from "@tanstack/react-query";
import { Select } from "@/components/arc/select/select";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { availablePoolItems, poolOptionLabel } from "./available-pool";

type PoolItem = components["schemas"]["PoolItem"];

interface PoolSelectProps {
  value: number | null;
  onChange: (id: number) => void;
  error?: string;
}

/** 从代理池里选一个可用代理（未被占用、未过期）。与代理池页共用同一份查询缓存。 */
export function PoolSelect({ value, onChange, error }: PoolSelectProps) {
  const pool = useQuery({ queryKey: queryKeys.proxyPool(), queryFn: () => api.get<PoolItem[]>("/api/proxy-pool") });
  const available = availablePoolItems(pool.data ?? []);

  if (pool.isError) return <p role="alert">读取代理池失败，请稍后重试</p>;
  if (pool.isSuccess && available.length === 0) return (
      <>
        <p>池里没有可用代理</p>
        {error && <p role="alert">{error}</p>}
      </>
    );

  return (
    <Select
      label="池里的代理"
      placeholder={pool.isPending ? "读取中…" : "请选择"}
      description={error}
      disabled={pool.isPending}
      value={value === null ? "" : String(value)}
      onValueChange={(v) => onChange(Number(v))}
      options={available.map((i) => ({ value: String(i.id), label: poolOptionLabel(i) }))}
    />
  );
}
