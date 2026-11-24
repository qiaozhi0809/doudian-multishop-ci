#!/usr/bin/env bash
# 前端分层守门（engineering-rules 2.1 / 第三节）。在任意目录运行均可。
#   1. ESLint 分层规则（logic 不引 react、components 不引 api-client）
#   2. index.tsx ≤ 80 行；*.ts / *.tsx ≤ 300 行（生成文件与 components/arc 除外）
#   3. hooks/ 下非测试文件不得是 .tsx（hooks 不返回 JSX）
#   4. 文件名 kebab-case
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/frontend"
fail=0

echo "[layers] eslint 分层规则"
pnpm exec eslint src --max-warnings 0 || fail=1

# 兼容 macOS 自带 bash 3.2（无 mapfile）
files=()
while IFS= read -r f; do files+=("$f"); done < <(find src -type f \( -name '*.ts' -o -name '*.tsx' \) \
  -not -path 'src/components/arc/*' -not -path 'src/lib/api-types.ts' | sort)

echo "[layers] 行数上限"
for f in "${files[@]}"; do
  lines=$(wc -l < "$f" | tr -d ' ')
  if [[ "$(basename "$f")" == "index.tsx" && "$lines" -gt 80 ]]; then
    echo "  index.tsx 超过 80 行: $f ($lines)"; fail=1
  fi
  if [[ "$lines" -gt 300 ]]; then
    echo "  文件超过 300 行: $f ($lines)"; fail=1
  fi
done

echo "[layers] hooks 不得是 .tsx"
for f in "${files[@]}"; do
  if [[ "$f" == */hooks/* && "$f" == *.tsx && "$f" != *.test.tsx ]]; then
    echo "  hooks 下不应有 .tsx（不得返回 JSX）: $f"; fail=1
  fi
done

echo "[layers] 文件名 kebab-case"
for f in "${files[@]}"; do
  name="$(basename "$f")"
  base="${name%%.*}"
  if [[ ! "$base" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "  文件名需 kebab-case: $f"; fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then echo "分层守门失败"; exit 1; fi
echo "分层守门通过"
