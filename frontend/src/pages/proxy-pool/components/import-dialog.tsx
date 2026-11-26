import { useMemo, useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog } from "@/components/arc/dialog/dialog";
import { AppDialogContent } from "@/components/custom/app-dialog/app-dialog-content";
import { DialogFooter } from "@/components/custom/dialog-footer/dialog-footer";
import { Textarea } from "@/components/arc/textarea/textarea";
import type { Failure, PoolImportOut } from "../hooks/use-proxy-pool";
import { previewImport } from "../logic/pool-import";
import styles from "../proxy-pool-page.module.css";

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onSubmit: (text: string) => Promise<PoolImportOut | Failure>;
}

export function ImportDialog({ open, onOpenChange, pending, onSubmit }: ImportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} busy={pending}>
      <AppDialogContent size="form" title="导入代理" description="每行一条，格式：IP|端口|账号|密码|到期日（YYYY-MM-DD）">
        {open && <ImportForm pending={pending} onSubmit={onSubmit} />}
      </AppDialogContent>
    </Dialog>
  );
}

function Summary({ result }: { result: PoolImportOut }) {
  return (
    <div className={styles.form}>
      <Alert
        tone={result.failed ? "warning" : "success"}
        title={`新增 ${result.added} 条，已存在 ${result.skipped} 条，失败 ${result.failed} 条`}
      />
      {result.failures.length > 0 && (
        <ul className={styles.lineList} aria-label="失败行">
          {result.failures.map((f) => (
            <li key={f.line}>{`第 ${f.line} 行：${f.reason}`}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ImportForm({ pending, onSubmit }: Pick<ImportDialogProps, "pending" | "onSubmit">) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<PoolImportOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const preview = useMemo(() => previewImport(text), [text]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (preview.total === 0) return setError("请先粘贴要导入的代理");
    setError(null);
    const out = await onSubmit(text);
    if ("error" in out) setError(out.error);
    else {
      setResult(out);
      setText("");
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <Textarea
        label="代理列表"
        rows={8}
        value={text}
        placeholder="1.2.3.4|8080|账号|密码|2026-12-31"
        onChange={(e) => {
          setText(e.target.value);
          setError(null);
          setResult(null);
        }}
      />
      {preview.total > 0 && (
        <p className={styles.previewLine}>{`共 ${preview.total} 行，格式正确 ${preview.valid} 行，有问题 ${preview.errors.length} 行`}</p>
      )}
      {preview.errors.length > 0 && (
        <ul className={styles.lineList} aria-label="格式有问题的行">
          {preview.errors.map((err) => (
            <li key={err.line}>{`第 ${err.line} 行：${err.reason}`}</li>
          ))}
        </ul>
      )}
      {error && <Alert tone="danger" title={error} />}
      {result && <Summary result={result} />}
      <DialogFooter busy={pending}>
        <Button type="submit" loading={pending}>
          导入
        </Button>
      </DialogFooter>
    </form>
  );
}
