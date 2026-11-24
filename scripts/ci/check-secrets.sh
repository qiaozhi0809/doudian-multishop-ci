#!/usr/bin/env bash
# 敏感信息扫描：只扫生产代码、脚本与脱敏样本目录（engineering-rules 8.1）
set -uo pipefail
cd "$(dirname "$0")/../.."

dirs=()
for d in backend/app frontend/src scripts backend/tests/fixtures; do
  [ -d "$d" ] && dirs+=("$d")
done

patterns=(
  'sessionid=[^*<]'
  'sid_tt=[^*<]'
  '__token=[A-Za-z0-9]{8,}'
  '(^|[^0-9])1[3-9][0-9]{9}([^0-9]|$)'
)

fail=0
for p in "${patterns[@]}"; do
  # 本脚本自身含有规则文本，排除
  if grep -rEn --exclude='check-secrets.sh' --exclude-dir=node_modules --exclude-dir=.venv \
      --exclude-dir=__pycache__ -e "$p" "${dirs[@]}"; then
    echo "命中敏感信息规则: $p"
    fail=1
  fi
done
exit "$fail"
