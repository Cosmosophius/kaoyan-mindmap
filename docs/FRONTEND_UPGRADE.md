# 前端视觉升级规范（施工单）

> 对象：`kaoyan_mindmap/build_treechat_web.py`（唯一源文件，改完必须重新构建）
> 目标：把当前「所有卡片一个色、连线一种、顶栏只有书名」的简陋界面，升级成有层级、有信息、有反馈的 Material Design 3 思维导图。
> 执行者：Gemini。**本文件是施工单，不是建议书。Phase A 的每一条都必须落地。**

---

## 0. 铁律（违反任何一条视为未完成）

1. **只改 `build_treechat_web.py`**。`web/index.html`、根目录 `index.html`、`/sdcard/cccodroid/.../index.html` 都是构建产物，禁止手改。
2. **禁止修改布局引擎**。以下标识符一律不许动：
   `syncTree` `computeLayout` `ensureDom` `captureRects` `relayout` 的结构部分
   `n.fx / n.fy / n.fvx / n.fvy` `ALIGN_MODE` `SPRING_K` `SPRING_C`
   `.tn` `.tk` `.tc` 的 flex 规则
   > 布局刚经历过一次推倒重来，任何改动都会让卡片重新错位。
3. **禁止修改数据管道与 PWA**：`load_data` `export_paragraphs` `pwa_build.py` `sw.js`。
4. **禁止引入外部依赖**：不装库、不引字体、不发网络请求、不用 emoji。
5. **改字号必须成对改**：任何 `font-size` 改动，必须同步修改 `measureCardW()` 里对应的
   `const fs = ...`，否则卡片宽度按旧字号算，文字会被截断。**能不改字号就不改。**
6. **不留 TODO / 占位符 / 注释掉的死代码**。
7. **每完成一条，跑一次 `bash tools/verify_frontend.sh`**。出现 FAIL 必须修复重跑，禁止跳过或声称通过。
8. 输出必须逐条列出：任务编号 → 改了哪个锚点 → verify 输出。**禁止用「已完成」三个字代替证据。**

---

## 1. Phase A（必须全部完成）

### T1 三级配色，让层级一眼可辨

**问题**：根卡是绿色、章节卡是深绿、小节卡和知识点卡几乎同一个灰绿（`--sc-high` / `--sc`），三级从属关系看不出来。

**改动 1**：找到这一行（全文唯一）：
```css
.card.section{background:var(--sc-high);position:relative;}
```
替换为：
```css
.card.section{
  background:var(--tertiary-container);
  position:relative;
  border-color:color-mix(in oklch, var(--tertiary) 45%, var(--outline-var));
}
```

**改动 2**：找到这一行（全文唯一）：
```css
.card.kp{background:var(--sc);padding:2px 5px;border-color:transparent;box-shadow:none;}
```
替换为：
```css
.card.kp{
  background:var(--sc);
  padding:2px 5px;
  border-color:color-mix(in oklch,var(--outline-var) 70%,transparent);
  box-shadow:none;
}
```

> `.card.kp.hot`（考频高）保持金色，不要动。

**验收**：`.card.section` 规则内出现 `--tertiary-container`；`.card.kp` 规则内出现
`color-mix(in oklch,var(--outline-var) 70%,transparent)`。

---

### T2 卡片左侧层级色条（不占布局宽度）

**要求**：章节卡左侧 3px 次级色条，小节卡左侧 3px 三级色条。
**必须用 inset box-shadow 实现**，不要用 `::before` 或 `border-left`——那会改变卡片宽度，导致文字截断。

找到：
```css
.card.chapter{
  background:var(--secondary-container);
  border-color:var(--secondary);
}
```
替换为：
```css
.card.chapter{
  background:var(--secondary-container);
  border-color:var(--secondary);
  box-shadow:inset 3px 0 0 var(--secondary), 0 2px 8px rgba(0,0,0,.35);
}
```

并在 T1 的 `.card.section` 块内追加一行 `box-shadow`：
```css
  box-shadow:inset 3px 0 0 var(--tertiary), 0 1px 4px rgba(0,0,0,.28);
```

**验收**：全文件出现至少 2 处 `inset 3px 0 0`。

---

### T3 连线按层级分层，不再是同一种线

**问题**：现在所有连线都是 `var(--outline)` 1.1px，只有高频考点是高亮；层级关系在线上看不出来。

**改动 1**：在 `function drawEdges(){` 这一行**之前**插入：
```js
/* 连线按父节点层级分色：根→章 用次级色，章→节 用三级色，其余用描边色 */
function edgeStyle(parent){
  if(parent.kind === "root")    return { c:"var(--secondary)", w:1.6,  o:0.72 };
  if(parent.kind === "chapter") return { c:"var(--tertiary)",  w:1.25, o:0.55 };
  return { c:"var(--outline)", w:0.9, o:0.34 };
}
```

**改动 2**：找到这三行（在 `drawEdges` 内，紧跟在 `path.setAttribute("d", d);` 之后）：
```js
      const hot = (c.weight === "high");
      path.setAttribute("stroke", hot ? "var(--gold)" : "var(--outline)");
      path.setAttribute("stroke-width", hot ? "1.6" : "1.1");
      path.setAttribute("opacity", hot ? "0.72" : "0.42");
```
替换为：
```js
      const st = edgeStyle(n);
      const hot = (c.weight === "high");
      path.setAttribute("stroke", hot ? "var(--gold)" : st.c);
      path.setAttribute("stroke-width", String(hot ? st.w + 0.35 : st.w));
      path.setAttribute("opacity", String(hot ? Math.min(0.9, st.o + 0.25) : st.o));
```
> 这里的 `n` 是当前循环的父节点，`c` 是子节点，不要改成别的变量。

**验收**：文件内出现 `function edgeStyle(`，且 `drawEdges` 内出现 `edgeStyle(n)`。

---

### T4 缩放百分比指示

**改动 1**：在 `<div id="tools">` 这一行**之前**插入：
```html
<div id="zoomPct">100%</div>
```

**改动 2**：在 CSS 区任意位置（建议紧跟 `#tools{...}` 规则之后）插入：
```css
#zoomPct{
  position:fixed;right:14px;bottom:calc(env(safe-area-inset-bottom) + 118px);z-index:20;
  font-size:11px;font-variant-numeric:tabular-nums;color:var(--on-surface-var);
  background:var(--sc-high);border:1px solid var(--outline-var);border-radius:var(--r-sm);
  padding:2px 8px;pointer-events:none;
}
```

**改动 3**：在 `function applyView(){` 的函数体**开头**插入：
```js
  const _zp = document.getElementById("zoomPct");
  if(_zp) _zp.textContent = Math.round(view.s * 100) + "%";
```

**验收**：文件内出现 `id="zoomPct"` 与 `_zp.textContent`。

---

### T5 搜索（3618 个考点不能只靠手拖）

**改动 1**：在 `<div id="tools">` 之前插入面板：
```html
<div id="searchPanel" hidden>
  <input id="searchInput" placeholder="搜索章节 / 小节 / 考点" autocomplete="off">
  <div id="searchList"></div>
</div>
```

**改动 2**：在顶栏 `.tb-row` 内、`id="btnCollapseAll"` 的按钮**之前**插入搜索按钮：
```html
<button class="ibtn" id="btnSearch" title="搜索">
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 4a6 6 0 104.47 10.03l4.25 4.25 1.41-1.41-4.25-4.25A6 6 0 0010 4zm0 2a4 4 0 110 8 4 4 0 010-8z"/></svg>
</button>
```

**改动 3**：CSS 追加：
```css
#searchPanel{
  position:fixed;left:50%;top:calc(env(safe-area-inset-top) + 70px);transform:translateX(-50%);
  width:min(560px,calc(100vw - 32px));max-height:60vh;z-index:40;
  background:var(--sc-high);border:1px solid var(--outline-var);border-radius:var(--r-lg);
  box-shadow:0 12px 40px rgba(0,0,0,.5);display:flex;flex-direction:column;overflow:hidden;
}
#searchPanel[hidden]{display:none;}
#searchInput{
  background:transparent;border:0;border-bottom:1px solid var(--outline-var);
  color:var(--on-surface);font-size:15px;padding:14px 16px;outline:none;
}
#searchList{overflow:auto;padding:6px;}
.sr{display:flex;flex-direction:column;gap:2px;padding:8px 10px;border-radius:var(--r-sm);cursor:pointer;}
.sr:hover{background:var(--sc-highest);}
.sr b{font-size:13px;font-weight:600;color:var(--on-surface);}
.sr span{font-size:11px;color:var(--on-surface-var);}
```

**改动 4**：在主 `<script>` 的**末尾**（最后一个 `</script>` 之前）追加：
```js
/* ---------- 搜索 ---------- */
const searchPanel = document.getElementById("searchPanel");
const searchInput = document.getElementById("searchInput");
const searchList  = document.getElementById("searchList");
const btnSearch   = document.getElementById("btnSearch");

function pathOf(n){
  const out = [];
  let p = n;
  while(p){ out.unshift(p); p = p.parent; }
  return out;
}

function focusNode(n){
  for(const a of pathOf(n)){ if(a !== n && !a.open) setOpen(a, true); }
  relayout();
  const cx = stage.clientWidth / 2, cy = stage.clientHeight / 2;
  const s  = Math.max(view.s, 1.1);
  animateViewTo(cx - (n.tx + n.w / 2) * s, cy - (n.ty + n.h / 2) * s, s);
}

function doSearch(q){
  q = (q || "").trim().toLowerCase();
  const hits = [];
  for(const n of NODES){
    if(!n.label || n.kind === "more") continue;
    if(q && n.label.toLowerCase().indexOf(q) < 0) continue;
    hits.push(n);
    if(hits.length >= 40) break;
  }
  searchList._hits = hits;
  searchList.innerHTML = hits.length
    ? hits.map((n, i) =>
        '<div class="sr" data-i="' + i + '"><b>' + esc(n.label) + '</b><span>' +
        esc(pathOf(n).slice(0, -1).map(x => x.label).join(" › ")) + '</span></div>').join("")
    : '<div class="sr"><span>没有匹配结果</span></div>';
}

function openSearch(show){
  searchPanel.hidden = !show;
  if(show){ searchInput.value = ""; doSearch(""); searchInput.focus(); }
}

if(btnSearch) btnSearch.addEventListener("click", () => openSearch(searchPanel.hidden));
if(searchInput) searchInput.addEventListener("input", () => doSearch(searchInput.value));
if(searchList) searchList.addEventListener("click", e => {
  const row = e.target.closest(".sr");
  if(!row || row.dataset.i == null) return;
  const n = searchList._hits[+row.dataset.i];
  if(!n) return;
  openSearch(false);
  focusNode(n);
});
```

**验收**：出现 `id="btnSearch"`、`id="searchPanel"`、`function focusNode(`、`function doSearch(`。

---

### T6 面包屑：随时知道自己在哪一章哪一节

**改动 1**：在 `<div id="tools">` 之前插入：
```html
<div id="crumbs"></div>
```

**改动 2**：CSS 追加：
```css
#crumbs{
  position:fixed;left:12px;bottom:calc(env(safe-area-inset-bottom) + 16px);z-index:15;
  display:flex;gap:6px;align-items:center;max-width:calc(100vw - 120px);
  font-size:12px;color:var(--on-surface-var);overflow:hidden;
}
#crumbs button{
  background:transparent;border:0;color:inherit;font:inherit;cursor:pointer;
  padding:2px 4px;border-radius:6px;white-space:nowrap;
}
#crumbs button:hover{background:var(--sc-high);}
#crumbs .sep{opacity:.4;flex:none;}
```

**改动 3**：主脚本末尾追加（与 T5 同一段即可）：
```js
/* ---------- 面包屑 ---------- */
const crumbsEl = document.getElementById("crumbs");
let _crumbT = 0;

function updateCrumbs(){
  if(!crumbsEl) return;
  const vw = stage.clientWidth, vh = stage.clientHeight;
  let best = null, bd = Infinity;
  for(const n of NODES){
    if(!n.visible) continue;
    const sx = n.tx * view.s + view.px, sy = n.ty * view.s + view.py;
    const d = Math.hypot(sx + n.w * view.s / 2 - vw / 2, sy + n.h * view.s / 2 - vh / 2);
    if(d < bd){ bd = d; best = n; }
  }
  if(!best){ crumbsEl.innerHTML = ""; return; }
  crumbsEl.innerHTML = pathOf(best).map((x, i) =>
    (i ? '<span class="sep">›</span>' : '') +
    '<button data-id="' + esc(x.id) + '">' +
    esc(x.label.length > 12 ? x.label.slice(0, 12) + "…" : x.label) + '</button>'
  ).join("");
}

function updateCrumbsThrottled(){
  const t = performance.now();
  if(t - _crumbT < 120) return;
  _crumbT = t;
  updateCrumbs();
}

if(crumbsEl) crumbsEl.addEventListener("click", e => {
  const b = e.target.closest("button");
  if(!b) return;
  const n = NODES.find(x => x.id === b.dataset.id);
  if(n) focusNode(n);
});
```

**改动 4**：在 `function applyView(){` 的函数体**末尾**追加一行：
```js
  updateCrumbsThrottled();
```
> 必须放在函数末尾（`applyView` 内的 `--lod` 处理之后），不要放在开头。

**验收**：出现 `id="crumbs"`、`function updateCrumbs(`、`updateCrumbsThrottled()`。

---

### T7 小屏适配（只调尺寸，不碰字号）

**改动**：CSS 末尾追加：
```css
@media (max-width:600px){
  .tb-title{font-size:14px;}
  .chip{padding:5px 9px;font-size:12px;}
  .fab{width:40px;height:40px;border-radius:12px;}
  #tools{gap:8px;right:10px;}
  #crumbs{font-size:11px;max-width:calc(100vw - 96px);}
  #zoomPct{bottom:calc(env(safe-area-inset-bottom) + 106px);}
}
```
> **禁止**在这个 media query 里改 `.card` 的 `font-size`，否则卡片宽度计算会失配。

**验收**：文件内出现 `@media (max-width:600px)`。

---

## 2. Phase B（Phase A 全部通过后才做，可跳过）

- **B1 连线生长动画**：新出现的边 `stroke-dasharray = len; stroke-dashoffset = len`，
  下一帧过渡到 0（220ms `--ease-emphasized`）。注意 `vector-effect:non-scaling-stroke` 下长度按世界坐标算。
- **B2 入场错峰**：新卡片 `n.alpha` 的增速按兄弟序号延迟 12ms（最多 8 个）。
- **B3 选中路径高亮**：点击卡片时，其祖先链的连线 `opacity` 提到 0.9、`stroke-width` +0.4，其余降到 0.15。
- **B4 空状态**：`NODES.length === 0` 时显示居中提示。

---

## 3. 交付格式（缺一项即视为未交付）

```
T1 已改 .card.section / .card.kp        → 见 diff
T2 已加 inset 3px 色条（2 处）
...
T7 已加 @media (max-width:600px)

$ bash tools/verify_frontend.sh
PASS build
PASS artifact
PASS syntax
PASS T1 ...
（把完整输出贴出来）
```

**严禁**：
- 只改一半就说完成
- 用「应该可以」「理论上」代替实际运行结果
- 跳过 verify 直接交付
- 把多个任务合并成一句"已优化样式"

如果某条确实做不了，必须写明「T? 未完成，原因：…」，**不许假装做了**。
