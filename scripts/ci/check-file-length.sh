#!/usr/bin/env bash
# 文件长度硬上限（engineering-rules 3.2）：*.py 400、*.ts/tsx 300、index.tsx 80、docs/**/*.md 600
set -euo pipefail
cd "$(dirname "$0")/../.."

fail=0
check() { # <limit> <file>
  local n
  n=$(($(wc -l < "$2")))
  if [ "$n" -gt "$1" ]; then
    echo "超限: $2 ($n 行 > $1)"
    fail=1
  fi
}

while IFS= read -r f; do
  case "$f" in
    */index.tsx) check 80 "$f" ;;
    *.py) check 400 "$f" ;;
    *.ts | *.tsx) check 300 "$f" ;;
    docs/*.md) check 600 "$f" ;;
  esac
done < <(find . \( -name node_modules -o -name .venv -o -name .git -o -name dist -o -name data \) -prune \
  -o -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.md' \) -print | sed 's|^\./||')

exit "$fail"
