# 汉硕考研 · 全书思维导图

把 10 本汉硕考研教材（现代汉语、中国文化要略、引论、入门等）做成一张**可拖拽、可展开、可离线**的思维导图。每个小节都能就地展开教材全文，考点按真题命中情况分级高亮。

- **10 本教材** / **58 章** / **151 节** / **3618 条考点** / **25236 段正文**
- 纯前端单文件，无后端、无数据库、无 embedding
- PWA：可安装到桌面，断网可用

## 在线访问

开启 GitHub Pages 后访问：

```
https://<你的用户名>.github.io/<仓库名>/
```

首次打开会后台缓存 151 个正文分片（约 6.2 MB），进度显示在屏幕底部胶囊里。缓存完成后断网也能读全文。

## 本地运行

Service Worker 和 `fetch` 需要 http(s)，直接双击 `file://` 打开会退化为只能看骨架。

```bash
cd web
python3 -m http.server 8099
# 浏览器打开 http://127.0.0.1:8099/
```

## 交互

| 操作 | 效果 |
|---|---|
| 拖拽空白或卡片 | 平移画布 |
| 滚轮 / 双指 | 缩放（0.35×–2.6×） |
| 点击节点 | 展开 / 收起 |
| 卡片左上角四圆点 | 关闭 / 最小化到侧边 / 画布伪全屏 / 真全屏 |
| 侧边大头针胶囊 | 上下拖动换位置，点击还原窗口 |
| 窗口标题栏双击 | 真全屏 |

## 数据结构

```
out/mindmap.json          骨架：书 → 章 → 节（24 KB，内联进 HTML）
out/leaves/<section>.json 每节的知识点 + 完整正文段落（按需 fetch）
web/index.html            内联骨架的单文件应用（2.3 MB）
web/data/para/<id>.json   正文分片，151 个，展开时才拉
```

每个知识点都带 `para_id`，可回溯到教材原文段落。`quote` 字段是原文的**逐字子串**，由 `pipeline/stage3_validate.py` 强制校验，防止模型改写或幻觉。

## 重新构建

```bash
python3 build_treechat_web.py
```

会重新生成 `web/index.html`、`web/data/para/`、`web/sw.js`、`web/manifest.webmanifest` 与图标。

Service Worker 的版本号取 `index.html` 的内容哈希，重建即换缓存桶，旧缓存自动清理。

## 管线（可选，仅在需要重新抽取时用）

```
stage0_extract.py    docx → 逐段 jsonl
stage1_split.py      段落 → 章节树
stage2_prepare.py    生成 Gemini 请求包
stage2_run.py        批量调用 Gemini 抽取考点
stage3_validate.py   校验 + 防幻觉（quote 必须是原文子串）
stage4_weights.py    注入真题考频权重
```

需要 `GEMINI_API_KEY`。详见 `HANDOFF.md` 与 `SPEC.md`。

## 设计来源

交互与动效复刻自 [TreeChat Workbench](https://github.com/) 的 Compose 实现：

- `TreeGraphGeometry.kt` → 卡片挤出、最小分离轴、内容自适应缩放
- `TreeTopologyView.kt` → 弹簧参数（LowBouncy 0.6 / StiffnessMediumLow 400）、LOD 阈值 0.65
- `DictMindMap.kt` → 径向树布局、贝塞尔连线、点阵背景
- `SeedScheme.kt` → 种子色 `0xFF28C840` + M3 色调映射
- `Shape.kt` → 4/8/12/16/28dp 形状阶

渲染用 DOM + CSS `transform`（GPU 合成层），不用 Canvas 画文字，以保留选中、复制、搜索与无障碍。

## 许可

代码 MIT。教材内容版权归原书作者与出版方，本仓库仅作个人学习用途。
