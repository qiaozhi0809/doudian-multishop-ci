# 仓库规则

## 仓库可见性与 CI（所有者规定，2026-11-25 更新）

主仓库 `qiaozhi0809/doudian-multishop-admin` **始终私有**。账号账单问题导致私有仓库的 GitHub Actions 无法启动，
因此 CI 改在**公开的 CI 专用镜像** `qiaozhi0809/doudian-multishop-ci` 上运行（公开仓库 Actions 免费）。

不直接公开主仓库的原因：已合并 PR 的只读引用 `refs/pull/*` 仍含历史中的真实个人信息（gaps DOC-13），无法删除。

跑 CI 的步骤：

1. 推送前检查要推的分支：`bash scripts/ci/check-secrets.sh` 通过；
   `git log -p <分支> | grep -P '(?<![0-9])1[3-9][0-9]{9}(?![0-9])'` 除虚构示例号码 `15600001234` 外无命中；
   不含 cookie、token、代理账号密码、真实姓名地址。
2. 只推分支，不推 PR 引用：`git push https://github.com/qiaozhi0809/doudian-multishop-ci.git origin/<分支>:refs/heads/<短名>`
3. `gh run list -R qiaozhi0809/doudian-multishop-ci` 查看结果；某个工作流没被触发时，用同一提交推到临时分支名重新触发，跑完删除临时分支。
4. 镜像里只放代码与文档，**永远不放**脱敏样本以外的抖店真实数据。
