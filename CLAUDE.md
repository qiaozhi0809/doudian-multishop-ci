# 仓库规则

## 仓库可见性与 CI（所有者规定，2026-11-25）

仓库默认**私有**。只有在私有状态下 GitHub Actions 无法运行（例如额度用尽、账单受限导致任务不启动），而又必须跑 CI 时，按以下步骤临时公开：

1. **公开前检查，任一不满足就不得公开，改为向所有者报告：**
   - 当前文件通过 `bash scripts/ci/check-secrets.sh`；
   - git 历史中没有凭证与个人信息：`git log -p --all | grep -nE '(?<![0-9])1[3-9][0-9]{9}(?![0-9])|sessionid=[^*<]|sid_tt=[^*<]|__token=[A-Za-z0-9]{8,}'`（用 `grep -P`）无命中；
   - `docs/gaps.md` 中 **DOC-13（历史中残留的真实姓名、手机号、地址）已处理**。未处理前一律不得公开。
2. 公开：`gh repo edit qiaozhi0809/doudian-multishop-admin --visibility public --accept-visibility-change-consequences`
3. 触发需要的 CI 并等待全部任务结束（`gh run watch`）。公开期间不推送新提交。
4. **立即改回私有**：`gh repo edit qiaozhi0809/doudian-multishop-admin --visibility private --accept-visibility-change-consequences`，
   再用 `gh api repos/qiaozhi0809/doudian-multishop-admin --jq .visibility` 确认结果为 `private`。
5. 在对应 PR 或会话里记录公开的起止时间与运行的 CI。

改回私有失败时，立即停止其他工作并通知所有者。
