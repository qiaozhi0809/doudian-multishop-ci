# Arc 源码来源

本目录是 Arc 组件库源码的**原样复制**，不修改。需要调整时在 `components/custom/` 里组合。

- 来源：本机 `uiarc-system/vendor`（见其 `NOTICE.md`）
  - Free：`uiarc-v2/uiarc`
  - Pro：`uiarc-pro-v3/uiarc-pro`
  - 下载日期 2026-11-03
- 布局与 Arc 安装后一致：组件在 `arc/<id>/`，区块在 `arc/blocks/<id>/`，共享件在 `arc/lib/`；组件间用相对路径 import。
- 不走 registry（registry 已要求 license key）；更新时从 uiarc-system 重新复制。

## 已复制的条目

| 条目 | 层级 | 来源路径（相对 vendor） |
|---|---|---|
| `foundation.css` | Free | `uiarc/registry/foundation.css` |
| `motion-tokens.ts` | Free | `uiarc/registry/motion-tokens.ts` |
| `lib/arc-provider.tsx`、`lib/motion-tokens.ts`、`lib/use-copy-feedback.ts`、`lib/use-today.ts` | Free | `uiarc/lib/` |
| `lib/clamp.ts` | Pro | `uiarc-pro/lib/clamp.ts` |
| `input/`、`password-field/`、`button/`、`alert/`、`card/`、`skeleton/` | Free | `uiarc/registry/components/<id>/`（Task 3：登录 / 初始化表单） |
| `multi-select/`、`dropdown-menu/`、`dialog/`、`popover/`、`badge/`、`tooltip/` | Free | `uiarc/registry/components/<id>/`（Task 4：App Shell） |
| `sortable-data-table/`、`empty-state/`、`drawer/`、`segmented-control/`、`textarea/` | Free | `uiarc/registry/components/<id>/`（Task 5：店铺与设置页） |
| `metric-card/`、`animated-counter/`、`pagination/`、`select/` | Free | `uiarc/registry/components/<id>/`（Task 6：订单列表页） |
| `hold-to-confirm/`、`checkbox/` | Free | `uiarc/registry/components/<id>/`（M2：打单台危险操作确认与跨页勾选） |

npm 依赖：`@radix-ui/react-dialog`（card、dialog）、`react-dropdown-menu`、`react-popover`、`react-tooltip`、`react-select`、
`@radix-ui/react-checkbox`（M2）。随任务增加，在此表追加。
