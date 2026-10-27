# 汉硕考研全书思维导图 — 实现规格 v1

> 本文是给编码方（人或 Agent）的**唯一权威规格**。
> 角色边界：**代码负责一切确定性工作，Gemini 只负责 Stage 2 的文本结构化。**

---

## 0. 铁律（违反即视为实现错误）

1. **Gemini 不得改写原文。** 它只做「抽取 + 归类」，产出必须包含 `quote` 字段，
   该字段必须是原文段落的**逐字子串**（仅允许空白归一化）。Stage 3 用代码校验，不通过即拒绝。
2. **Gemini 不写代码、不做推理、不补充外部知识。** 它的输入是纯文本 + schema，输出是纯 JSON。
3. **原文是唯一事实来源。** 任何 kp（知识点）必须能回溯到 `doc` + `para_id` 范围。
4. **运行时不得解析 docx。** docx 只在 Stage 0 解析一次。
5. **前端不得用 Canvas 渲染文字。** 用 DOM + CSS transform（见 §6）。

---

## 1. 输入（实测，勿假设）

源目录：`/sdcard/Documents/RAG`（10 个 .docx，全部含文字层，**无需 OCR**）

| 文件 | 文字量(字) | 图片数 | 备注 |
|---|---|---|---|
| 中国文化要略(第四版) | 636,814 | 122 | 30.4MB 图片，正文完整 |
| 对外汉语教学入门 第3版 | 478,919 | 63 | |
| 对外汉语教育学引论 | 363,708 | 36 | |
| 南师大汉硕10-23真题带答案 | 266,000 | 307 | 真题+答案 |
| 现代汉语通论下册 | 186,445 | 16 | |
| 现代汉语通论上册 | 162,827 | 16 | |
| 夸克扫描王_汉硕考研网 | 42,987 | 5 | 资料汇总 |
| 24南京师范大学354+445真题和答案 | 18,478 | 26 | |
| 2026年南京师范大学334+445真题 | 1,357 | 0 | |
| 25南京师范大学354+445真题 | 928 | 0 | |

合计 ≈ 2,158,463 字（≈144 万 token）。
**结论**：单本可进 1M 上下文，**全部不可**。必须按章节分片送 Gemini。

---

## 2. 流水线

```
Stage 0  代码     docx → paragraphs.jsonl（带稳定 para_id）
Stage 1  代码     规则识别章节树 → skeleton.json
Stage 2  Gemini   逐章抽取知识点 → kp_raw/<chapter_id>.json
Stage 3  代码     校验 + 防幻觉 + 覆盖率 → kp_clean.jsonl
Stage 4  代码     真题权重注入 → mindmap.json（骨架 + 惰性叶子）
Stage 5  代码     前端（DOM 画布 + 虚拟化）
```

### Stage 0 — 提取（代码，`stage0_extract.py`）
- 解析 `word/document.xml`，按 `<w:p>` 取段，合并 `<w:t>`。
- 记录 `pStyle`（识别 Heading1/2/3）。
- 清理：去页眉页脚重复行、去零宽字符、合并被折断的行（行尾无标点且下一行非标题时合并）。
- 输出 `out/paragraphs/<doc_id>.jsonl`，每行：
  `{"doc":"culture","para_id":123,"style":"Heading1","text":"第二章 地理概况"}`
- **`para_id` 一经生成不可变**，后续所有回溯依赖它。

### Stage 1 — 章节树（代码，`stage1_split.py`）
正则识别，优先级从高到低：
- 章：`^第[一二三四五六七八九十百零]+章`
- 节：`^第[一二三四五六七八九十百零]+节`
- 三级：`^[一二三四五六七八九十]+、` 或 `^（[一二三四五六七八九十]+）`
- 兜底：`pStyle` 为 Heading* 时按层级归入

输出 `out/skeleton.json`：
```json
{"doc":"culture","title":"中国文化要略","chapters":[
  {"chapter_id":"culture-c02","title":"第二章 地理概况","para_range":[120,300],
   "sections":[{"section_id":"culture-c02-s01","title":"第一节 地理环境与行政区划","para_range":[121,240]}]}]}
```
**人工抽检 3 本**，章节数与原书目录一致才算通过。

### Stage 2 — Gemini（唯一的 LLM 环节）
- 输入：`skeleton.json` 中**单个 section** 的原文（按 `para_range` 切片）+ `prompts/gemini_extract.md` + `schema/kp.schema.json`。
- 分片上限：单次输入 ≤ 60,000 字（约 4 万 token），保证弱模型也能稳定。
- 输出：`out/kp_raw/<section_id>.json`，符合 schema。
- **必须**用 structured output / JSON mode；解析失败直接重试，最多 3 次，仍失败则记入 `out/failed.jsonl` 交人工。

### Stage 3 — 校验（代码，`stage3_validate.py`）
逐条检查，任一失败则该 kp 进 `out/rejected.jsonl`：
1. schema 合规（`jsonschema`）。
2. `doc` / `para_id` 存在且落在该 section 的 `para_range` 内。
3. **防幻觉**：`quote` 去空白后必须是源段落文本的子串；`answer` 中的每个 `point` 也须能在 `quote` 或同 section 原文中找到依据（子串或 ≥80% 字符覆盖率）。
4. 去重：同 section 内 `normalize(title)` 重复者合并。
5. 统计覆盖率：`kp 覆盖的 para 数 / section 总 para 数`，低于 40% 报警（可能漏抽）。

### Stage 4 — 权重注入（代码）
从 `kaoyan_pwa/data/exam_papers.json`（12 套 264 题）与 `all_subjects_data.json`
（2176 条，已含 `frequency` / `exam_years` / `importance_score`）匹配 kp：
- 匹配键：`normalize(title)` 精确 → 再去标点 → 再 bigram 覆盖率 ≥0.8。
- 权重分三档，**不要一刀切**：
  - `high`：真题命中 ≥1 次
  - `mid`：教材标为高频但真题未命中
  - `normal`：其余（含未考但属核心概念）
- 每个 kp 存 `evidence`：`["2019 354 名词解释","2023 445 简答"]`，供 UI hover 展示。

### Stage 5 — 前端（见 §6）

---

## 3. 输出数据契约

`mindmap.json`（骨架，目标 < 800 KB，首屏只加载它）
```json
{"version":1,"books":[{"doc":"culture","title":"中国文化要略",
  "chapters":[{"id":"culture-c02","title":"第二章 地理概况","weight":"high",
    "sections":[{"id":"culture-c02-s01","title":"第一节 地理环境与行政区划",
      "kp_count":18,"weight":"high"}]}]}]}
```

`leaves/<section_id>.json`（按需加载，每个 < 50 KB）
```json
{"section_id":"culture-c02-s01","kps":[
  {"id":"kp-0012","title":"地理环境","type":"名词解释",
   "points":["...","..."],"quote":"...","para_id":128,
   "weight":"high","evidence":["2019 354 名词解释"]}]}
```

---

## 4. 给编码方的验收标准

| # | 标准 | 判定方式 |
|---|---|---|
| 1 | Stage 0 产出 10 个 jsonl，总字数与 §1 表误差 < 3% | 脚本自检 |
| 2 | 章节树与 3 本原书目录一致 | 人工抽检 |
| 3 | Stage 3 拒绝率 < 15% | 统计 |
| 4 | 每个 kp 的 `quote` 均通过子串校验 | 100% 通过 |
| 5 | 首屏 FCP < 1.5s（中端手机，4G） | Lighthouse |
| 6 | 拖动 60fps，主线程无长任务 > 50ms | DevTools Performance |
| 7 | 5000 节点全展开，DOM 节点数 < 1500 | 虚拟化生效 |

---

## 5. 目录结构

```
kaoyan_mindmap/
├── SPEC.md
├── prompts/gemini_extract.md      # 交给 Gemini 的唯一提示词
├── schema/kp.schema.json          # 输出 schema（strict）
├── pipeline/
│   ├── stage0_extract.py
│   ├── stage1_split.py
│   ├── stage3_validate.py
│   └── stage4_weights.py
├── web/                            # Stage 5 前端
└── out/
```

---

## 6. 前端实现要点（Stage 5）

**画布**
- 容器 `.viewport` + 内层 `.canvas`，拖动/缩放**只改** `transform: translate3d() scale()`。
- 指针事件用 `pointerdown/move/up` + `setPointerCapture`；拖动期间 `will-change: transform`。
- 惯性：`requestAnimationFrame` 里做速度衰减（0.92/帧），到阈值停止。
- 缩放锚点跟随指针位置，范围 0.25x–3x。

**节点渲染**
- 树布局用「紧凑正交树」：x 由深度决定，y 由前序累计高度决定，连线用 SVG path（贝塞尔）。
- **虚拟化**：只渲染视口 + 200px 缓冲内的节点；`content-visibility: auto` 兜底。
- **LOD**：缩放 < 0.5 只画章节标题；0.5–1.0 画 kp 标题；> 1.0 才画 points 正文。

**展开收起**
- 节点默认折叠到「章」层。展开时向 `leaves/<section_id>.json` 拉取（带缓存）。
- 动画用 `max-height` + `opacity` 的 CSS transition（180ms, cubic-bezier(.2,.8,.2,1)），**不要 JS 逐帧**。

**重点标亮**
- `weight=high` → 左侧 3px 强调色条 + 标题加粗；`mid` → 淡色条。
- hover 显示 `evidence` tooltip（"2019 354 名词解释"）。

**性能红线**
- 中文字体：**只用系统字体栈**（`-apple-system, "Noto Sans CJK SC", sans-serif`），不加载 Web 字体。
- 数据分片：`mindmap.json` 首屏加载，`leaves/` 按需；禁止一次性加载全部。
- 不用 Canvas / WebGL 渲染文字。

---

## 7. 不做的事

- 不做 OCR（全部 docx 已有文字层）。
- 不做向量 embedding（本场景术语检索已足够；后续可加，接口预留）。
- 不让 Gemini 生成代码或自由发挥。
- 不做全书一次性进上下文。
