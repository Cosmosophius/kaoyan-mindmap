#!/usr/bin/env bash
# 前端改造成果的客观验收。任何一项 FAIL 都表示任务未完成。
# 用法：bash tools/verify_frontend.sh
set -u
cd "$(dirname "$0")/.." || exit 1

fail=0
pass=0

ok(){   pass=$((pass+1)); printf 'PASS  %s\n' "$1"; }
bad(){  fail=$((fail+1)); printf 'FAIL  %s\n' "$1"; }
has(){  if grep -qF -- "$2" "$3"; then ok "$1"; else bad "$1  (缺少: $2)"; fi; }

echo "== 1. 构建 =="
if python3 build_treechat_web.py > tools/.build.log 2>&1; then
  ok "build"
else
  bad "build"; tail -20 tools/.build.log; echo; echo "构建失败，后续检查无意义"; exit 1
fi
[ -s web/index.html ] && ok "artifact web/index.html" || bad "artifact 缺失"

echo
echo "== 2. 语法 =="
python3 - <<'PY'
import re, io
s = io.open("web/index.html", encoding="utf-8").read()
blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', s, re.S)
io.open("tools/.check_app.js", "w", encoding="utf-8").write(max(blocks, key=len))
PY
if node --check tools/.check_app.js > tools/.check.log 2>&1; then
  ok "node --check"
else
  bad "node --check"; tail -5 tools/.check.log
fi

echo
echo "== 3. 布局引擎未被破坏（守卫项）=="
has "guard: syncTree 仍在"        "function syncTree"                     web/index.html
has "guard: flex 树规则仍在"      ".tn{display:flex;align-items:center;}" web/index.html
has "guard: FLIP 弹簧仍在"        "n.fvx"                                 web/index.html
has "guard: 对齐自检徽标仍在"     "updateBadge"                           web/index.html

echo
echo "== 4. Phase A 任务 =="
area_out=$(python3 - <<'PY'
import re
s = open("web/index.html", encoding="utf-8").read()

def block(sel):
    m = re.search(re.escape(sel) + r"\s*\{", s)
    if not m: return ""
    i = m.end(); depth = 1; j = i
    while j < len(s) and depth:
        if s[j] == "{": depth += 1
        elif s[j] == "}": depth -= 1
        j += 1
    return s[i:j-1]

sec = block(".card.section")
kp  = block(".card.kp")

checks = [
  ("T1 小节卡改三级容器色", "--tertiary-container" in sec),
  ("T1 知识点卡加描边",     "color-mix(in oklch,var(--outline-var) 70%,transparent)" in kp),
  ("T2 层级色条 >=2 处",    s.count("inset 3px 0 0") >= 2),
  ("T3 edgeStyle 定义",     "function edgeStyle(" in s),
  ("T3 edgeStyle 调用",     "edgeStyle(n)" in s),
  ("T4 缩放百分比元素",     'id="zoomPct"' in s),
  ("T4 缩放百分比更新",     "_zp.textContent" in s),
  ("T5 搜索按钮",           'id="btnSearch"' in s),
  ("T5 搜索面板",           'id="searchPanel"' in s),
  ("T5 doSearch",           "function doSearch(" in s),
  ("T5 focusNode",          "function focusNode(" in s),
  ("T6 面包屑元素",         'id="crumbs"' in s),
  ("T6 updateCrumbs",       "function updateCrumbs(" in s),
  ("T6 节流调用",           "updateCrumbsThrottled()" in s),
  ("T7 小屏适配",           "@media (max-width:600px)" in s),
]
for name, okv in checks:
    print(("PASS  " if okv else "FAIL  ") + name)
PY
)
echo "$area_out"
pass=$((pass + $(echo "$area_out" | grep -c '^PASS')))
fail=$((fail + $(echo "$area_out" | grep -c '^FAIL')))

echo
echo "================================"
echo "PASS $pass  /  FAIL $fail"
if [ "$fail" -ne 0 ]; then
  echo "结果：未完成（$fail 项未通过）"
  exit 1
fi
echo "结果：Phase A 全部通过"
