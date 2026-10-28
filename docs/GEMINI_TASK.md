# 给 Gemini 的任务指令（直接整段粘贴）

你是一名前端工程师。仓库里有一个已经能用的思维导图 Web App，现在需要你做**视觉与交互升级**。

## 第一步（必须）

先完整读取这个文件：

```
docs/FRONTEND_UPGRADE.md
```

它是施工单，不是参考建议。**读不到就停下来让用户上传，禁止凭记忆猜测内容。**
同时读 `build_treechat_web.py` 顶部的 CSS 与 `drawEdges / relayout / applyView / createCard` 这几个函数，确认锚点。

## 第二步（按施工单逐条实现）

按 T1 → T7 的顺序做，**一条都不要跳**。

## 硬约束（违反任一条，本次任务判为不合格）

1. 只改 `build_treechat_web.py`。`web/index.html` 是构建产物，**禁止手改**。
2. **禁止修改布局引擎**：`syncTree` `computeLayout` `ensureDom` `captureRects`
   `n.fx/fy/fvx/fvy` `ALIGN_MODE` `SPRING_K/C`，以及 `.tn/.tk/.tc` 的 flex 规则。
   这套布局刚重写过，动它必然导致卡片错位。
3. 禁止改数据管道与 PWA（`load_data` / `export_paragraphs` / `pwa_build.py`）。
4. 禁止引入外部库、外部字体、网络请求、emoji。
5. 改任何 `font-size` 必须同步改 `measureCardW()` 里对应的 `fs` 值，否则卡片宽度失配、文字截断。**能不改字号就不改。**
6. 不留 TODO、占位符、注释掉的死代码。
7. 不许把多条任务合并成「已优化样式」一句话交付。

## 第三步（验收，必须执行）

每完成一条，运行：

```bash
bash tools/verify_frontend.sh
```

规则：

- 出现 `FAIL` 必须修复后重跑，**禁止跳过、禁止解释成"不影响使用"**。
- 只有出现 `结果：Phase A 全部通过` 才算完成。
- 如果某个检查项反复失败，说明你的实现和施工单不一致，回去对照锚点，不要改脚本让它变绿。

## 交付格式（缺一项即视为未交付）

```
T1：改了 .card.section / .card.kp          （贴出关键 diff）
T2：inset 3px 色条 x2                     （贴出关键 diff）
T3：edgeStyle() + drawEdges 三行替换        （贴出关键 diff）
T4：zoomPct 元素 + applyView 更新
T5：搜索按钮/面板/doSearch/focusNode
T6：面包屑 updateCrumbs + 节流调用
T7：@media (max-width:600px)

$ bash tools/verify_frontend.sh
（贴完整输出）
```

## 反偷懒条款（重点，逐条遵守）

1. **禁止"我觉得应该可以"**。所有结论必须来自实际运行的输出。
2. **禁止只做容易的部分**（比如只改颜色，跳过搜索）。T1–T7 是一个整体。
3. **禁止用更简单的实现替换施工单给的代码**。施工单里的代码块是经过与现有代码对齐的，改了变量名或结构会破坏兼容。
4. **禁止修改 `tools/verify_frontend.sh`**。它是验收标准，不是你的实现对象。
5. **禁止声称"已全部完成"却不贴 verify 输出**。
6. 如果某一条确实做不到，写清楚：
   `T? 未完成，原因：……`，**不许假装做了**。

## 完成后自检（逐条打勾）

- [ ] `bash tools/verify_frontend.sh` 输出 `结果：Phase A 全部通过`
- [ ] 没有修改 `web/index.html`（只由构建脚本生成）
- [ ] 没有触碰布局引擎相关标识符
- [ ] 没有引入任何外部依赖或 emoji
- [ ] 交付里逐条列出了 T1–T7 的改动
