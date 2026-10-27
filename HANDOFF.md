# 交接说明 — 谁干什么

> 一句话：**代码已经全部写好了，Gemini 只需要做文本抽取，不需要写任何代码。**

---

## 你要跑的命令（按顺序，共 5 步）

```bash
cd kaoyan_mindmap
export GEMINI_API_KEY=你的key

# ① 补全章节树（4 个请求，约 1 分钟）
python3 pipeline/stage1_toc_run.py status     # 先看缺哪些
python3 pipeline/stage1_toc_run.py prepare
python3 pipeline/stage1_toc_run.py run
python3 pipeline/stage1_split.py              # 应用补全结果
python3 pipeline/stage2_prepare.py            # 重新生成抽取请求

# ② 批量抽取知识点（91 个请求，约 5~10 分钟）
python3 pipeline/stage2_run.py --limit 3      # 先试 3 个，确认效果
python3 pipeline/stage2_run.py                # 全量跑（断点续跑）

# ③ 校验 + 权重（秒级）
python3 pipeline/stage3_validate.py
python3 pipeline/stage4_weights.py
```

跑完把 `out/rejected.jsonl` 给我看，我判断是模型改写太多还是提示词要调。

---

## 新增的 3 个文件（Gemini 不会写，已备好）

| 文件 | 作用 |
|---|---|
| `pipeline/stage2_run.py` | **批量调用 Gemini**。断点续跑、重试退避、限速、强制 JSON+schema、温度 0.1 |
| `pipeline/stage1_toc_run.py` | **用 Gemini 补全章节树**。`prepare` 生成请求，`run` 调用并写 `toc_override.json`，`status` 看缺口 |
| `prompts/gemini_toc.md` | 目录还原提示词，禁止编造章节，缺章必须报 `missing` |

`stage2_run.py` 的常用参数：
```bash
--limit 3                        # 只跑前 3 个
--model gemini-2.5-flash         # 换模型
--sleep 2                        # 加大限速间隔，避免 429
--dry-run                        # 只检查请求完整性，不联网
```

---

## 当前进度（已实测跑通）

| 阶段 | 负责 | 状态 | 产出 |
|---|---|---|---|
| Stage 0 提取 | 代码 | ✅ 完成 | `out/paragraphs/*.jsonl` 10 个，26106 段 / 214.6 万字（偏差 0.6%） |
| Stage 1 章节树 | 代码 | ⚠️ 部分完成 | `out/skeleton.json` 41 章 77 节 |
| Stage 2 抽取 | **Gemini** | ⏸ 待你执行 | `out/requests/*.json` 91 个请求已备好 |
| Stage 3 校验 | 代码 | ✅ 就绪 | 等 `out/kp_raw/` 产出即可运行 |
| Stage 4 权重 | 代码 | ✅ 就绪 | 等 `kp_clean.jsonl` 即可运行 |
| Stage 5 前端 | 代码 | ⏸ 未开始 | 规格见 SPEC.md §6 |

---

## Gemini 要做的唯一一件事

对 `out/requests/` 下的每个 JSON，取它的 `input` 字段作为提示词发给模型，
把返回的 JSON 存为 `out/kp_raw/<同名>.json`。

**不要让它写代码、不要让它改提示词、不要让它看 SPEC.md 以外的文件。**

### 请求文件结构
```json
{
  "task": "extract_kp",
  "section_id": "culture-c02-s01",
  "chapter": "第二章 地理概况",
  "book": "中国文化要略（第四版）",
  "para_range": [172, 240],
  "chars": 4832,
  "response_schema": { ... },   // 传给 generationConfig.responseSchema
  "system": "你是结构化抽取器。只输出符合 schema 的 JSON，禁止改写原文。",
  "input": "...完整提示词 + 原文（含 [pNNN] 段号）..."
}
```

### 调用方式（Gemini API）
```bash
export GEMINI_API_KEY=...        # 需要你自己提供，当前环境没有可用 key
MODEL=gemini-2.5-flash           # 用便宜快的即可，这是纯抽取任务

for f in out/requests/*.json; do
  out="out/kp_raw/$(basename "$f")"
  [ -f "$out" ] && continue                       # 断点续跑
  python3 - "$f" <<'PY' > /tmp/payload.json
import json,sys
d=json.load(open(sys.argv[1]))
print(json.dumps({"contents":[{"parts":[{"text":d["input"]}]}],
 "generationConfig":{"responseMimeType":"application/json",
                     "responseSchema":d["response_schema"],
                     "temperature":0.1}}))
PY
  curl -s "https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/payload.json \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['candidates'][0]['content']['parts'][0]['text'])" \
    > "$out"
  echo "done $(basename "$f")"
done
```

**关键参数**：`temperature: 0.1`（越低越不会改写）、`responseMimeType: application/json`、`responseSchema`（强制结构）。

---

## 跑完之后

```bash
python3 pipeline/stage3_validate.py   # 校验 + 防幻觉，拒绝率需 <15%
python3 pipeline/stage4_weights.py    # 注入真题权重，产出 mindmap.json + leaves/
```

Stage 3 会**逐条验证 `quote` 是否为原文逐字子串**。任何被 Gemini 改写的句子都会被拒收并记入 `out/rejected.jsonl`。这是防止模型编造内容的核心防线。

---

## 需要你决策的 3 件事

### 1. 章节树补全（影响最大）
当前 41 章 77 节，但两本不达标：

| 书 | 识别到 | 原书 |
|---|---|---|
| 中国文化要略 | 6 章 | **18 章** |
| 现代汉语通论（下） | 1 章 | **5 章** |

原因：这批 docx **没有 Heading 样式**，且正文里的章标题大量缺失或被合并进目录段。
我已在 `stage1_split.py` 留好人工修正入口 —— 建 `out/toc_override.json` 即可覆盖：

```json
{
  "culture": [
    {"no": 1, "title": "第一章 简论", "sections": [{"no": 1, "title": "第一节 文化与中国文化"}]},
    {"no": 2, "title": "第二章 地理概况", "sections": []}
  ]
}
```
**建议**：先人工把这两本的目录填进去（照着纸质书或原 docx 目录），再重跑 stage1。
或者也可以让 Gemini 从目录段里整理出章节表——这属于「文本内容」，不违反分工。

### 2. 技术栈
`SPEC.md §6` 我按 **DOM + CSS transform + 虚拟化**写的（不用 Canvas 渲染文字）。
若你坚持 Canvas/WebGL 画布，告诉我，前端方案要改。

### 3. 前端还没开始
Stage 5 只有规格，没有代码。等你确认技术栈后我再写。

---

## 铁律（再强调一次）

1. **Gemini 不得改写原文**，`quote` 必须是逐字子串 —— Stage 3 会强制校验。
2. **Gemini 不写代码**，代码已经全部就位。
3. **不要一次把整本书塞进上下文**，91 个请求已经按 6 万字切好，逐个跑即可。
4. **`para_id` 不可变**，它是回溯原文的唯一锚点。
