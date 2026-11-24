#!/usr/bin/env bash
# 后端分层守门（engineering-rules 2.2 / 7）
set -uo pipefail
cd "$(dirname "$0")/../.."

fail=0
scan() { # <目录> <说明> <ERE>
  [ -d "$1" ] || return 0
  if grep -rEn --include='*.py' -e "$3" "$1"; then
    echo "违规: $2"
    fail=1
  fi
}

imp() { echo "^[[:space:]]*(import|from)[[:space:]]+($1)([[:space:].]|$)"; }

scan backend/app/domain "domain 不得依赖框架或 IO 库" \
  "$(imp 'fastapi|sqlalchemy|curl_cffi|playwright')"
scan backend/app/domain "domain 不得 import store/adapter/service/api" \
  "$(imp 'app\.(store|adapter|service|api)')"
scan backend/app/store "store 不得 import adapter/service/api" \
  "$(imp 'app\.(adapter|service|api)')"
scan backend/app/adapter "adapter 不得 import store/service/api" \
  "$(imp 'app\.(store|service|api)')"
scan backend/app/api "api 不得 import sqlalchemy 或 app.store" "$(imp 'sqlalchemy|app\.store')"
exit "$fail"
