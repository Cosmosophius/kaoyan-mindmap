#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把考研教材数据渲染成 TreeChat Workbench 同款思维导图 Web 版。

复刻自 TreeChatWorkbench_v1.41.32 源码：
  - ui/tree/TreeGraphGeometry.kt   → 卡片挤出/最小分离轴/内容自适应缩放
  - ui/tree/TreeTopologyView.kt    → graphicsLayer 缩放平移、弹簧参数、LOD 阈值
  - etymology/ui/DictMindMap.kt    → 径向树布局、bezierPath、点阵背景、卡片规格
  - ui/theme/SeedScheme.kt         → 种子色 0xFF28C840 + M3 色调映射
  - ui/theme/Shape.kt              → 4/8/12/16/28dp 形状阶

关键参数（逐条来自源码，不是拍脑袋）：
  Spring.DampingRatioLowBouncy = 0.6, Spring.StiffnessMediumLow = 400
  tween 220ms 入场 / 180~200ms LOD / scale 阈值 0.65
  bezier: dx = max(|ex-sx|, 60) * 0.5, cubicTo(sx+dx, sy, ex-dx, ey)
  画布缩放 0.35~2.6，自适应缩放 0.35~1.3，自适应 padding 90px
  点阵 36px 网格 / 半径 1.2 / alpha 0.22
  卡片圆角 root 14 其他 10，描边 1.5/1，阴影 6/2
  布局 rootX=60 col1=190 col2=240 rowSpacing=80 branchSpacing=40
"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")
WEB = os.path.join(BASE, "web")

# ---------------------------------------------------------------------------
# 1. 读数据，抽出轻量骨架（正文另存为按需拉取的分片）
# ---------------------------------------------------------------------------

def load_data():
    mm = json.load(open(os.path.join(OUT, "mindmap.json"), encoding="utf-8"))
    books = []
    for b in mm["books"]:
        chapters = []
        for c in b["chapters"]:
            sections = []
            for s in c["sections"]:
                kps = []
                leaf_path = os.path.join(OUT, "leaves", s["id"] + ".json")
                if os.path.exists(leaf_path):
                    leaf = json.load(open(leaf_path, encoding="utf-8"))
                    for kp in leaf.get("kps", []):
                        kps.append({
                            "t": kp.get("title", ""),
                            "y": kp.get("type", ""),
                            "p": kp.get("points", []),
                            "q": kp.get("quote", ""),
                            "w": kp.get("weight", "normal"),
                            "e": kp.get("evidence", []) or [],
                        })
                sections.append({
                    "id": s["id"],
                    "t": s["title"],
                    "w": s.get("weight", "normal"),
                    "n": len(kps),
                    "k": kps,
                })
            chapters.append({
                "id": c["id"],
                "t": c["title"],
                "w": c.get("weight", "normal"),
                "s": sections,
            })
        books.append({"d": b["doc"], "t": b["title"], "c": chapters})
    return books


def export_paragraphs():
    """把每节正文单独导出，前端展开"本节正文"时按需 fetch，避免首屏背 11MB。"""
    dst = os.path.join(WEB, "data", "para")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst, exist_ok=True)
    src = os.path.join(OUT, "leaves")
    total = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".json"):
            continue
        leaf = json.load(open(os.path.join(src, fn), encoding="utf-8"))
        paras = leaf.get("paragraphs", [])
        slim = [{"i": p.get("para_id"), "t": p.get("text", "")} for p in paras]
        p = os.path.join(dst, fn)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, separators=(",", ":"))
        total += len(slim)
    return len(os.listdir(dst)), total


# ---------------------------------------------------------------------------
# 2. 前端模板
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0d1310">
<title>汉硕考研 · 全书思维导图</title>

<!-- PWA：可安装、可离线 -->
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon-192.png" sizes="192x192" type="image/png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="考研导图">
<meta name="description" content="10 本教材 / 58 章 / 151 节 / 3618 条考点，可离线使用的交互式思维导图。">
<script>(function(){try{var t=localStorage.getItem("theme");if(t==="dark")document.documentElement.setAttribute("data-theme","dark");}catch(_){}})();</script>
<style>
/* ============================================================
   M3 配色：种子色 0xFF28C840（TreeChat ThemePalette.DEFAULT_GREEN）
   用 OKLCH 复现 HCT Tonal Spot 映射，深色主题下
   primary=tone80 / primaryContainer=tone30 / surface=tone6 这一套配对
   ============================================================ */
:root{
  /* ---------- 温暖手账质感配色 (Warm Journal Paper & Morandi Notes) ---------- */
  --h:85;

  /* 根卡：复古焦糖书皮手账 */
  --primary:            oklch(52% 0.11 55);
  --on-primary:         oklch(98% 0.01 55);
  --primary-container:  oklch(90.5% 0.042 60);
  --on-primary-cont:    oklch(26% 0.08 50);

  /* 章节卡：莫兰迪鼠尾草植物绿便签 */
  --secondary:          oklch(56% 0.08 140);
  --on-secondary:       oklch(98% 0.01 140);
  --secondary-container:oklch(91.8% 0.035 140);
  --on-secondary-cont:  oklch(25% 0.06 140);

  /* 小节卡：莫兰迪暖杏奶白便签 */
  --tertiary:           oklch(62% 0.07 75);
  --tertiary-container: oklch(93.8% 0.028 75);
  --on-tertiary-cont:   oklch(28% 0.06 65);

  /* 真题高频：复古麦穗金高亮便签 */
  --gold:               oklch(68% 0.16 85);
  --gold-container:     oklch(92.5% 0.08 88);

  /* 纸张底色：温暖象牙米白和纸（护眼哑光不刺眼） */
  --surface:            oklch(96.8% 0.016 88);
  --sc-lowest:          oklch(98.5% 0.008 88);
  --sc-low:             oklch(95.5% 0.018 88);
  --sc:                 oklch(94.2% 0.020 88);
  --sc-high:            oklch(92.0% 0.024 88);
  --sc-highest:         oklch(88.5% 0.028 88);

  /* 墨水文字色：浓郁复古钢笔墨水棕黑（极具手写温度） */
  --on-surface:         oklch(22% 0.025 55);
  --on-surface-var:     oklch(46% 0.035 55);
  --outline:            oklch(76% 0.030 80);
  --outline-var:        oklch(86% 0.020 85);

  /* Shape.kt：4/8/12/16/28 */
  --r-xs:4px; --r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:28px;

  /* Compose MotionScheme 对应曲线 */
  --ease-standard: cubic-bezier(0.2,0,0,1);
  --ease-emphasized: cubic-bezier(0.05,0.7,0.1,1);
}

/* ---------- 暗色模式：复古深黛皮革手账 (Dark Leather Journal) ---------- */
[data-theme="dark"]{
  --primary:            oklch(76% 0.14 55);
  --on-primary:         oklch(20% 0.06 55);
  --primary-container:  oklch(30% 0.08 55);
  --on-primary-cont:    oklch(92% 0.05 55);

  --secondary:          oklch(78% 0.08 140);
  --on-secondary:       oklch(20% 0.04 140);
  --secondary-container:oklch(32% 0.05 140);
  --on-secondary-cont:  oklch(92% 0.03 140);

  --tertiary:           oklch(80% 0.09 75);
  --tertiary-container: oklch(32% 0.06 75);
  --on-tertiary-cont:   oklch(93% 0.04 75);

  --gold:               oklch(85% 0.15 85);
  --gold-container:     oklch(34% 0.08 85);

  --surface:            oklch(14% 0.015 60);
  --sc-lowest:          oklch(11% 0.012 60);
  --sc-low:             oklch(16% 0.016 60);
  --sc:                 oklch(19% 0.018 60);
  --sc-high:            oklch(23% 0.020 60);
  --sc-highest:         oklch(28% 0.024 60);

  --on-surface:         oklch(93% 0.012 85);
  --on-surface-var:     oklch(78% 0.022 85);
  --outline:            oklch(52% 0.025 75);
  --outline-var:        oklch(32% 0.018 70);
}
[data-theme="dark"] #grid{
  background-image:radial-gradient(circle, color-mix(in oklch, var(--outline) 30%, transparent) 1.2px, transparent 1.2px);
}
[data-theme="dark"] .card{
  box-shadow:0 1px 3px rgba(0,0,0,.35), 0 4px 12px rgba(0,0,0,.25);
}
[data-theme="dark"] .card.chapter::after{
  background:rgba(255, 255, 255, 0.22);
  border-color:rgba(255, 255, 255, 0.12);
}
[data-theme="dark"] .card.section::after{
  background:rgba(255, 255, 255, 0.20);
  border-color:rgba(255, 255, 255, 0.10);
}

*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{height:100%;overflow:hidden;background:var(--surface);}
body{
  font-family:-apple-system,"HarmonyOS Sans SC","Noto Sans CJK SC","Source Han Sans SC",
              "PingFang SC","Microsoft YaHei",sans-serif;
  color:var(--on-surface);
  font-size:14px;
  -webkit-font-smoothing:antialiased;
  user-select:none;
}

/* ---------- 画布舞台 ---------- */
#stage{position:fixed;inset:0;overflow:hidden;touch-action:none;cursor:grab;background:var(--surface);}
#stage.dragging{cursor:grabbing;}

/* 点阵背景：28px 手账点阵纸，跟随平移但不参与缩放重绘 */
#grid{
  position:absolute;inset:-72px;
  background-image:radial-gradient(circle, color-mix(in oklch, var(--outline) 40%, transparent) 1.2px, transparent 1.2px);
  background-size:28px 28px;
  will-change:transform;
  pointer-events:none;
}

/* 唯一合成层：所有平移缩放都只改这一层的 transform，不触发重排 */
#world{
  position:absolute;left:0;top:0;
  transform-origin:0 0;
  will-change:transform;
  backface-visibility:hidden;
}
#edges{position:absolute;left:0;top:0;overflow:visible;pointer-events:none;}
#edges path{
  fill:none;stroke-linecap:round;stroke-linejoin:round;
  vector-effect:non-scaling-stroke;
}
#nodes{position:absolute;left:0;top:0;display:flex;align-items:flex-start;}
/* 嵌套 flex 树：对齐交给浏览器，JS 不再计算坐标 */
.tn{display:flex;align-items:center;}
.tc{flex:none;position:relative;}
.tk{display:flex;flex-direction:column;}

/* ---------- 卡片：实体手账便签质感 ---------- */
.card{
  position:relative;
  box-sizing:border-box;          /* 让 COL_W 是含 padding 的实际宽度 */
  border-radius:var(--r-md);
  background:var(--sc-high);
  border:1px solid color-mix(in oklch, var(--outline-var) 85%, transparent);
  padding:3px 7px;
  box-shadow:0 1px 2px rgba(90, 75, 60, 0.08), 0 3px 8px rgba(90, 75, 60, 0.05);
  will-change:transform,opacity;
  contain:layout style;
  transform-origin:0 50%;         /* 树向右生长：从左侧顶点长出 */
  transition:background .18s var(--ease-standard),
             border-color .18s var(--ease-standard),
             box-shadow .22s var(--ease-standard);
}
/* 便签轻微抬升效果 */
@media (hover:hover) and (pointer:fine){
  .card:hover{
    box-shadow:0 3px 8px rgba(90, 75, 60, 0.12), 0 8px 18px rgba(90, 75, 60, 0.08);
    border-color:color-mix(in oklch,var(--outline) 65%, var(--outline-var));
  }
}
/* 键盘可达性：MD3 focus ring */
.card:focus-visible{
  outline:2px solid var(--primary);
  outline-offset:2px;
}
/* 分页哨兵：虚线胶囊 */
.card.more{
  background:transparent;
  border:1px dashed color-mix(in oklch,var(--primary) 42%, var(--outline-var));
  box-shadow:none;
  padding:6px 10px;
}
.card.more .label{
  color:var(--primary);font-size:12px;font-weight:600;
  -webkit-line-clamp:1;text-align:center;letter-spacing:.02em;
}
.card.more:hover{background:color-mix(in oklch,var(--primary) 9%, transparent);}
/* 量宽态：label 强制单行 nowrap，让 max-content 能得到真实文本宽度。
   量完立刻移除，用户看不到这一帧。 */
.card.measuring{width:max-content!important;max-width:none!important;}
.card.measuring .label{
  display:block!important;-webkit-line-clamp:unset!important;
  white-space:nowrap!important;overflow:visible!important;flex:none!important;
}
.card.root{
  border-radius:14px;
  background:var(--primary-container);
  border:1.5px solid var(--primary);
  box-shadow:0 4px 14px rgba(70, 45, 25, 0.16), inset 0 1px 0 rgba(255,255,255,0.45);
  padding:10px 13px;
}
.card.chapter{
  background:var(--secondary-container);
  border-color:var(--secondary);
  box-shadow:inset 3px 0 0 var(--secondary), 0 2px 8px rgba(80, 65, 50, 0.08);
}
.card.section{
  background:var(--tertiary-container);
  position:relative;
  border-color:color-mix(in oklch, var(--tertiary) 45%, var(--outline-var));
  box-shadow:inset 3px 0 0 var(--tertiary), 0 1px 4px rgba(80, 65, 50, 0.06);
}
/* section 的两个操作按钮改为「悬停浮现」：绝对定位到卡片右缘外侧，
   不占文档流宽度。实测它们常驻时占 36px，25 张 section 卡合计 900px，
   而 win/doc 属于低频操作，常驻显示纯属浪费面积。 */
.card.section .ibtn.act{
  position:absolute;top:50%;transform:translateY(-50%);
  opacity:0;pointer-events:none;
  background:var(--sc-highest);
  box-shadow:0 1px 3px rgba(0,0,0,.45);
  transition:opacity .16s var(--ease-standard),background .16s var(--ease-standard);
}
.card.section .ibtn.act[data-act="win"]{ right:-19px; }
.card.section .ibtn.act[data-act="para"]{ right:-37px; }
@media (hover:hover) and (pointer:fine){
  .card.section:hover .ibtn.act,
  .card.section:focus-within .ibtn.act{ opacity:1;pointer-events:auto; }
}
/* 触屏没有 hover，直接常驻显示（否则按钮永远点不到） */
@media (hover:none){
  .card.section .ibtn.act{ opacity:.85;pointer-events:auto;position:static;transform:none;right:auto;box-shadow:none;background:transparent; }
}

/* 和纸胶带贴纸：半透明手撕纸胶带，带微小角度贴角，赋予手账本手作感 */
.card.chapter::after{
  content:"";
  position:absolute; top:-5px; right:12px; width:26px; height:8px;
  background:rgba(255, 255, 255, 0.65);
  border:1px solid rgba(130, 150, 130, 0.28);
  box-shadow:0 1px 2px rgba(80, 65, 50, 0.08);
  transform:rotate(-2.5deg);
  pointer-events:none;
}
.card.section::after{
  content:"";
  position:absolute; top:-4px; right:10px; width:20px; height:7px;
  background:rgba(255, 255, 255, 0.7);
  border:1px solid rgba(170, 150, 130, 0.22);
  box-shadow:0 1px 2px rgba(80, 65, 50, 0.06);
  transform:rotate(1.8deg);
  pointer-events:none;
}
.card.kp{
  background:var(--sc);
  padding:2px 5px;
  border-color:color-mix(in oklch,var(--outline-var) 70%,transparent);
  box-shadow:none;
}
.card.kp.hot{
  background:var(--gold-container);
  border-color:var(--gold);
}
/* 真题高频：左侧 2px 金色竖条。
   原来用「真题」文字徽标，36px × 3,229 张 = 116,244px，
   占 kp 卡全部装饰宽度的 76.3%。竖条横向不占位，颜色同样能一眼分辨。 */
.card.kp.hot::before{
  content:"";position:absolute;left:0;top:3px;bottom:3px;width:2px;
  border-radius:2px;background:var(--gold);
}

.row{display:flex;align-items:center;gap:2px;}
.label{
  flex:1;min-width:0;
  overflow:hidden;
  /* 两行截断：中文标题不再被压成一行省略号 */
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  white-space:normal;
  word-break:break-word;
  line-height:1.18;
  font-weight:500;letter-spacing:0;
}
.card.root .label{font-size:15px;font-weight:700;color:var(--on-primary-cont);letter-spacing:.02em;}
.card.chapter .label{font-size:13px;font-weight:700;color:var(--on-secondary-cont);}
.card.section .label{font-size:12.5px;font-weight:600;}
.card.kp .label{font-size:13px;font-weight:500;}

.badge{
  flex:none;font-size:8.5px;line-height:1;padding:0 3px;border-radius:var(--r-xs);
  background:var(--tertiary-container);color:var(--on-tertiary-cont);
  letter-spacing:.02em;font-weight:600;
}
.badge.gold{background:var(--gold-container);color:var(--gold);}

/* 纯矢量图标按钮（无 emoji） */
.ibtn{
  flex:none;width:16px;height:16px;border:0;border-radius:50%;
  background:transparent;color:var(--on-surface-var);
  display:grid;place-items:center;cursor:pointer;
  transition:background .16s var(--ease-standard),color .16s var(--ease-standard);
}
.ibtn:hover{background:color-mix(in oklch,var(--on-surface) 10%,transparent);}
.ibtn:active{background:color-mix(in oklch,var(--on-surface) 16%,transparent);}
.ibtn svg{width:16px;height:16px;display:block;}
.ibtn.chev svg{transition:transform .22s var(--ease-standard);}
.card.open > .row > .ibtn.chev svg{transform:rotate(90deg);}

/* 详情行：随 LOD 淡出（源码 tween 180ms，阈值 scale 0.65） */
/* 详情行默认折叠：3,618 张知识点卡片若全部展开要点行，
   画布高度会被放大 3~4 倍，且低缩放下只是 opacity:0 —— 看不见却占着高度。
   现在默认只显示标题，点击才展开。 */
.detail{display:none;}
.card.open > .detail{
  display:block;
  margin-top:3px;font-size:11px;line-height:1.5;color:var(--on-surface-var);
}
.detail .pt{display:flex;gap:6px;margin-top:2px;}
.detail .pt::before{
  content:"";flex:none;width:3px;height:3px;border-radius:50%;
  background:var(--primary);margin-top:8px;
}
.card.kp.hot .detail .pt::before{background:var(--gold);}
.detail .quote{
  margin-top:6px;padding:6px 8px;border-radius:var(--r-sm);
  background:color-mix(in oklch,var(--on-surface) 5%,transparent);
  color:color-mix(in oklch,var(--on-surface) 72%,transparent);
  font-size:11px;line-height:1.6;
  border-left:2px solid var(--outline-var);
}
/* 正文：展开后直接在画布内变宽变高，不弹窗 */
.para{
  margin-top:10px;padding-top:10px;
  border-top:1px solid var(--outline-var);
  font-size:12.5px;line-height:1.9;
  color:color-mix(in oklch,var(--on-surface) 88%,transparent);
  max-height:min(520px, 62vh);
  overflow-y:auto;overscroll-behavior:contain;
  user-select:text;cursor:text;
  /* 阅读排版：两端对齐 + 首行缩进 2 字，中文长文更好读 */
  text-align:justify;text-justify:inter-ideograph;
  hanging-punctuation:allow-end;
}
.para p{
  margin-bottom:10px;
  text-indent:2em;                /* 中文首行缩进 */
  padding-left:34px;              /* 给悬挂的段号留位 */
  text-indent:0;
}
.para p:first-child{margin-top:2px;}
.para .pid{
  display:inline-block;width:30px;margin-left:-34px;
  font-size:9.5px;color:var(--outline);
  font-variant-numeric:tabular-nums;
  vertical-align:baseline;
}
/* 继续加载按钮 */
.para-more{
  display:block;width:100%;margin:10px 0 2px;
  padding:9px 12px;border-radius:var(--r-sm);
  border:1px dashed color-mix(in oklch,var(--primary) 45%, var(--outline-var));
  background:transparent;color:var(--primary);
  font-size:12px;font-weight:600;cursor:pointer;
  font-family:inherit;
  transition:background .16s var(--ease-standard);
}
.para-more:hover{background:color-mix(in oklch,var(--primary) 10%, transparent);}
.para-more:active{background:color-mix(in oklch,var(--primary) 18%, transparent);}

/* ---- 紧凑模式（小屏）---- */
.compact .card{padding:9px 11px;border-radius:10px;}
.compact .card.root .label{font-size:15.5px;}
.compact .card.chapter .label{font-size:13.5px;}
.compact .card.section .label{font-size:13px;}
.compact .card.kp .label{font-size:12.5px;}
.compact .para{font-size:12px;line-height:1.82;max-height:min(440px,58vh);}
.compact .row{gap:6px;}
.compact .badge{font-size:9px;padding:2px 5px;}
.tiny .card{padding:8px 10px;}
.tiny .ibtn{width:22px;height:22px;}
.tiny .ibtn svg{width:14px;height:14px;}
.para::-webkit-scrollbar{width:4px;}
.para::-webkit-scrollbar-thumb{background:var(--outline-var);border-radius:2px;}

/* ---------- 侧边停靠坞（复刻 TreeChat WindowDockBar） ---------- */
#dock{position:fixed;inset:0;pointer-events:none;z-index:9000;}
.dockpin{
  position:absolute;pointer-events:auto;
  display:flex;align-items:center;gap:6px;
  padding:8px 9px;max-width:210px;
  background:var(--sc-high);
  border:1px solid var(--outline-var);
  box-shadow:0 3px 10px rgba(0,0,0,.45);
  cursor:grab;touch-action:none;user-select:none;
  transition:box-shadow .16s var(--ease-standard),transform .16s var(--ease-standard);
}
.dockpin:active{cursor:grabbing;}
.dockpin.dragging{box-shadow:0 9px 24px rgba(0,0,0,.62);transform:scale(.96);}
/* 贴边那侧方、靠内侧两角圆，视觉上"挂"在屏幕边缘 */
.dockpin.right{right:0;border-radius:16px 0 0 16px;border-right:0;}
.dockpin.left {left:0; border-radius:0 16px 16px 0;border-left:0;}
.dockpin svg{flex:none;width:12px;height:12px;display:block;}
.dockpin .dp-t{
  font-size:11.5px;font-weight:600;color:var(--on-surface);
  max-width:76px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.dockpin .dp-x{
  flex:none;width:18px;height:18px;padding:0;border:0;border-radius:50%;
  background:transparent;color:var(--on-surface-var);
  display:grid;place-items:center;cursor:pointer;
  transition:background .16s var(--ease-standard);
}
.dockpin .dp-x:hover{background:color-mix(in oklch,var(--on-surface) 14%,transparent);}
.dockpin .dp-x svg{width:10px;height:10px;}

/* ---------- 顶栏：手账封顶与书签标签 ---------- */
#topbar{
  position:fixed;left:0;right:0;top:0;z-index:20;
  padding:calc(env(safe-area-inset-top) + 10px) 12px 10px;
  background:color-mix(in oklch,var(--surface) 90%,transparent);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  border-bottom:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);
  box-shadow:0 1px 4px rgba(80, 65, 50, 0.05);
  display:flex;flex-direction:column;gap:9px;
  transition:transform .26s var(--ease-emphasized);
}
#topbar.hide{transform:translateY(-100%);}
.tb-row{display:flex;align-items:center;gap:10px;}
.tb-title{
  font-size:15px;font-weight:700;letter-spacing:.02em;flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
#books{
  display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;
  padding-bottom:2px;-webkit-overflow-scrolling:touch;
}
#books::-webkit-scrollbar{display:none;}
.chip{
  flex:none;border:1px solid color-mix(in oklch,var(--outline-var) 85%,transparent);border-radius:var(--r-sm);
  background:var(--sc-lowest);color:var(--on-surface-var);
  padding:6px 12px;font-size:12.5px;font-weight:500;white-space:nowrap;cursor:pointer;
  box-shadow:0 1px 2px rgba(80, 65, 50, 0.04);
  transition:background .2s var(--ease-standard),color .2s var(--ease-standard),border-color .2s var(--ease-standard),box-shadow .2s var(--ease-standard);
}
.chip.on{
  background:var(--secondary-container);color:var(--on-secondary-cont);
  border-color:var(--secondary);font-weight:700;
  box-shadow:0 2px 6px rgba(80, 65, 50, 0.08);
}

/* ---------- 右下工具列 ---------- */
#tools{
  position:fixed;right:12px;bottom:calc(env(safe-area-inset-bottom) + 16px);z-index:20;
  display:flex;flex-direction:column;gap:10px;
}
.fab{
  width:44px;height:44px;border:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);border-radius:var(--r-lg);
  background:var(--sc-lowest);color:var(--on-surface);
  display:grid;place-items:center;cursor:pointer;
  box-shadow:0 2px 6px rgba(80, 65, 50, 0.09), 0 6px 16px rgba(80, 65, 50, 0.05);
  transition:background .18s var(--ease-standard),transform .18s var(--ease-emphasized),box-shadow .18s var(--ease-standard);
}
.fab:active{transform:scale(.92);}
.fab svg{width:20px;height:20px;display:block;}
.fab.primary{background:var(--primary);color:var(--on-primary);border-color:var(--primary);}

/* ---------- 加载态 ---------- */
#hint{
  position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom) + 22px);
  transform:translateX(-50%);z-index:15;
  padding:8px 16px;border-radius:var(--r-xl);
  background:var(--sc-highest);color:var(--on-surface-var);
  font-size:12px;white-space:nowrap;
  transition:opacity .4s var(--ease-standard);
  pointer-events:none;
}
#hint.gone{opacity:0;}

/* ============================================================
   悬浮小窗（FloatingWindowCard.kt / FloatingWindowManager.kt 复刻）
   小窗 16dp 圆角 + 阴影；真全屏 / 画布伪全屏一律 radius 0、elevation 0
   ============================================================ */
.win{
  position:fixed; left:0; top:0; z-index:40;
  display:flex; flex-direction:column;
  width:400px; height:520px;
  background:var(--sc-high);
  border:1px solid var(--outline-var);
  border-radius:16px;
  box-shadow:0 20px 44px rgba(0,0,0,.52), 0 4px 12px rgba(0,0,0,.34);
  overflow:hidden;
  will-change:transform,opacity;
  contain:layout style;
  transform-origin:50% 50%;
}
.win.full,.win.canvas-full{
  border-radius:0; border-width:0; box-shadow:none;
}

/* 真全屏：元素进入浏览器 top layer，直接铺满物理屏幕。
   这里用 !important 压过 applyWin() 每帧写的 inline transform / width / height，
   否则 JS 的弹簧会把全屏元素又缩回窗口尺寸。 */
.win:fullscreen,
.win:-webkit-full-screen{
  left:0!important; top:0!important;
  width:100%!important; height:100%!important;
  transform:none!important;
  border-radius:0!important; border-width:0!important;
  box-shadow:none!important;
  background:var(--sc-low);
}
.win:fullscreen .rz,
.win:-webkit-full-screen .rz{display:none;}
.win:fullscreen .win-title,
.win:-webkit-full-screen .win-title{cursor:default;}

/* 标题栏 46dp：拖动把手 + 双击进真全屏 */
.win-title{
  flex:none; height:46px;
  display:flex; align-items:center; gap:6px;
  padding:0 10px;
  background:var(--sc-highest);
  border-bottom:1px solid var(--outline-var);
  cursor:grab; touch-action:none; user-select:none;
}
.win-title:active{cursor:grabbing;}
.win.full .win-title,.win.canvas-full .win-title{cursor:default;}
.win-title .t{
  flex:1; min-width:0; font-size:13px; font-weight:600;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.win-title .ibtn{width:28px;height:28px;}
.win-title .ibtn svg{width:16px;height:16px;}
.win-title .ibtn.on{background:var(--primary-container);color:var(--on-primary-cont);}

/* 左上角四个 macOS 风格圆点（关闭 / 收起 / 画布全屏 / 真全屏） */
.win-dots{
  flex:none; display:flex; align-items:center; gap:7px;
  margin-right:6px; padding-left:2px;
}
.dot{
  width:11px; height:11px; padding:0; border:0; border-radius:50%;
  cursor:pointer; flex:none;
  transition:transform .16s var(--ease-standard),
             filter .16s var(--ease-standard),
             box-shadow .16s var(--ease-standard);
}
.dot:hover{transform:scale(1.2);filter:brightness(1.18);}
.dot:active{transform:scale(.9);}
.dot-close {background:oklch(68% 0.19 25);}
.dot-min   {background:oklch(82% 0.16 85);}
.dot-canvas{background:oklch(76% 0.15 150);}
.dot-full  {background:oklch(72% 0.14 235);}
.dot.on{box-shadow:0 0 0 2px color-mix(in oklch,var(--on-surface) 60%,transparent);}

/* 收起：只留标题栏 */
.win.collapsed .win-body{display:none;}
.win.collapsed .rz{display:none;}
.win.collapsed{box-shadow:0 8px 22px rgba(0,0,0,.5);}

/* 内容区 */
.win-body{
  flex:1; min-height:0;
  overflow-y:auto; overscroll-behavior:contain;
  padding:12px 14px 20px;
  user-select:text; cursor:text;
  -webkit-overflow-scrolling:touch;
}
.win-body::-webkit-scrollbar{width:5px;}
.win-body::-webkit-scrollbar-thumb{background:var(--outline-var);border-radius:3px;}
.win-body h4{
  font-size:11.5px; font-weight:700; color:var(--primary);
  margin:14px 0 8px; letter-spacing:.06em;
}
.win-body h4:first-child{margin-top:2px;}
.win-body .para p{
  margin-bottom:9px; font-size:13px; line-height:1.86;
  color:color-mix(in oklch,var(--on-surface) 88%,transparent);
}
.win-body .para .pid{
  font-size:10px; color:var(--outline); margin-right:6px;
  font-variant-numeric:tabular-nums;
}
.win-body .kpitem{
  border:1px solid var(--outline-var); border-radius:10px;
  padding:9px 11px; margin-bottom:9px; background:var(--sc);
}
.win-body .kpitem.hot{background:var(--gold-container);border-color:var(--gold);}
.win-body .kpitem .kt{
  font-size:13px; font-weight:700; margin-bottom:6px;
  display:flex; align-items:center; gap:6px; flex-wrap:wrap;
}
.win-body .kpitem .ky{
  font-size:10px; padding:2px 6px; border-radius:4px; font-weight:600;
  background:var(--tertiary-container); color:var(--on-tertiary-cont);
}
.win-body .kpitem.hot .ky{background:var(--gold-container);color:var(--gold);}
.win-body .kpitem .kp-pt{
  font-size:12px; line-height:1.72; color:var(--on-surface-var);
  display:flex; gap:6px; margin-top:3px;
}
.win-body .kpitem .kp-pt::before{
  content:""; flex:none; width:3px; height:3px; border-radius:50%;
  background:var(--primary); margin-top:7px;
}
.win-body .kpitem.hot .kp-pt::before{background:var(--gold);}
.win-body .loading{color:var(--outline);font-size:12.5px;}

/* 边缘缩放热区：右 8dp / 下 8dp / 右下角 16dp（源码热区收窄避免吃掉选词） */
.rz{position:absolute;z-index:3;touch-action:none;}
.rz-r{top:48px;bottom:32px;right:0;width:8px;cursor:ew-resize;}
.rz-b{left:32px;right:32px;bottom:0;height:8px;cursor:ns-resize;}
.rz-c{right:0;bottom:0;width:16px;height:16px;cursor:nwse-resize;}
.rz::after{
  content:"";position:absolute;background:var(--outline);
  opacity:0;transition:opacity .16s var(--ease-standard);
}
.rz-r::after{right:3px;top:50%;transform:translateY(-50%);width:3px;height:28px;border-radius:1.5px;}
.rz-b::after{bottom:3px;left:50%;transform:translateX(-50%);height:3px;width:28px;border-radius:1.5px;}
.rz-c::after{right:6px;bottom:6px;width:10px;height:10px;border-radius:2px;}
.win:hover .rz::after{opacity:.55;}
.win.full .rz,.win.canvas-full .rz{display:none;}

/* 吸附预览：Windows 同款影子，从窗口当前位置长出来 */
#snapGhost{
  position:fixed; z-index:38; pointer-events:none;
  border:1.5px solid var(--primary);
  background:color-mix(in oklch,var(--primary) 15%,transparent);
  border-radius:16px; opacity:0;
  transition:opacity .16s var(--ease-standard),
    left .22s var(--ease-emphasized), top .22s var(--ease-emphasized),
    width .22s var(--ease-emphasized), height .22s var(--ease-emphasized);
}
#snapGhost.on{opacity:1;}

/* ---------- 离线包状态胶囊 ---------- */
#pwaChip{
  position:fixed; left:50%; bottom:calc(18px + env(safe-area-inset-bottom,0px));
  transform:translateX(-50%);
  z-index:44; display:flex; align-items:center; gap:8px;
  padding:8px 16px 8px 12px;
  border-radius:var(--r-full);
  background:var(--sc-high); color:var(--on-surface-var);
  border:1px solid var(--outline-var);
  box-shadow:0 2px 6px rgba(0,0,0,.36), 0 8px 24px rgba(0,0,0,.30);
  font-size:12px; line-height:1;
  pointer-events:none;
  opacity:0; transition:opacity .28s var(--ease-standard),
                          transform .28s var(--ease-emphasized);
}
#pwaChip.on{opacity:1;}
#pwaChip[hidden]{display:none;}
#pwaChip .pwa-ico{display:flex;width:16px;height:16px;flex:none;}
#pwaChip .pwa-ico svg{width:16px;height:16px;display:block;}
#pwaChip.ready{color:var(--primary);border-color:color-mix(in oklch,var(--primary) 40%,transparent);}
#pwaChip.offline{color:var(--tertiary);border-color:color-mix(in oklch,var(--tertiary) 45%,transparent);}

/* ---------- 缩放指示 ---------- */
#zoomPct{
  position:fixed;right:14px;bottom:calc(env(safe-area-inset-bottom) + 118px);z-index:20;
  font-size:11px;font-variant-numeric:tabular-nums;color:var(--on-surface-var);
  background:var(--sc-lowest);border:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);border-radius:var(--r-sm);
  padding:2px 8px;pointer-events:none;
  box-shadow:0 1px 3px rgba(80,65,50,0.06);
}

/* ---------- 搜索面板：手账收纳抽屉 ---------- */
#searchPanel{
  position:fixed;left:50%;top:calc(env(safe-area-inset-top) + 70px);transform:translateX(-50%);
  width:min(560px,calc(100vw - 32px));max-height:60vh;z-index:40;
  background:var(--sc-lowest);border:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);border-radius:var(--r-lg);
  box-shadow:0 12px 32px rgba(80,65,50,0.14), 0 2px 6px rgba(80,65,50,0.08);display:flex;flex-direction:column;overflow:hidden;
}
#searchPanel[hidden]{display:none;}
#searchInput{
  background:transparent;border:0;border-bottom:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);
  color:var(--on-surface);font-size:15px;padding:14px 16px;outline:none;
}
#searchList{overflow:auto;padding:6px;}
.sr{display:flex;flex-direction:column;gap:2px;padding:8px 10px;border-radius:var(--r-sm);cursor:pointer;}
.sr:hover{background:var(--sc-high);}
.sr b{font-size:13px;font-weight:600;color:var(--on-surface);}
.sr span{font-size:11px;color:var(--on-surface-var);}

/* ---------- 面包屑：手账书签便签条 ---------- */
#crumbs{
  position:fixed;left:12px;bottom:calc(env(safe-area-inset-bottom) + 16px);z-index:15;
  display:flex;gap:6px;align-items:center;max-width:calc(100vw - 120px);
  font-size:12px;color:var(--on-surface-var);overflow:hidden;
  background:color-mix(in oklch,var(--surface) 92%,transparent);
  padding:4px 8px;border-radius:var(--r-sm);
  border:1px solid color-mix(in oklch,var(--outline-var) 80%,transparent);
  box-shadow:0 1px 3px rgba(80,65,50,0.05);
}
#crumbs button{
  background:transparent;border:0;color:inherit;font:inherit;cursor:pointer;
  padding:2px 4px;border-radius:4px;white-space:nowrap;
}
#crumbs button:hover{background:var(--sc-high);}
#crumbs .sep{opacity:.4;flex:none;}

/* ---------- 小屏适配 ---------- */
@media (max-width:600px){
  .tb-title{font-size:14px;}
  .chip{padding:5px 9px;font-size:12px;}
  .fab{width:40px;height:40px;border-radius:12px;}
  #tools{gap:8px;right:10px;}
  #crumbs{font-size:11px;max-width:calc(100vw - 96px);}
  #zoomPct{bottom:calc(env(safe-area-inset-bottom) + 106px);}
}
</style>
</head>
<body>

<div id="stage">
  <div id="grid"></div>
  <div id="world">
    <svg id="edges"></svg>
    <div id="nodes"></div>
  </div>
</div>

<div id="topbar">
  <div class="tb-row">
    <div class="tb-title" id="tbTitle">汉硕考研 · 全书思维导图</div>
    <span id="buildTag" style="margin-left:10px;font-size:11px;opacity:.5;font-variant-numeric:tabular-nums;white-space:nowrap">__BUILD__</span>
    <button id="btnAlign" title="切换对齐方式" style="margin-left:8px;font-size:11px;line-height:18px;padding:0 8px;border-radius:9px;border:1px solid var(--outline-var);background:transparent;color:var(--on-surface-var);cursor:pointer">对齐:顶部</button>
    <button class="ibtn" id="btnSearch" title="搜索">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 4a6 6 0 104.47 10.03l4.25 4.25 1.41-1.41-4.25-4.25A6 6 0 0010 4zm0 2a4 4 0 110 8 4 4 0 010-8z"/></svg>
    </button>
    <button class="ibtn" id="btnCollapseAll" title="全部收起">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 8l-6 6 1.4 1.4L12 10.8l4.6 4.6L18 14z"/></svg>
    </button>
    <button class="ibtn" id="btnTheme" title="切换暗色/亮色手账模式">
      <svg id="themeIco" viewBox="0 0 24 24" fill="currentColor"><path d="M12.3 2a10 10 0 00-1.9 19.8 10 10 0 0011.6-11.6A10 10 0 0012.3 2zm-1.8 17.8A8 8 0 0110 4.1a8.2 8.2 0 001.3 4.2 8 8 0 008.6 4.1 8 8 0 01-9.4 7.4z"/></svg>
    </button>
    <button class="ibtn" id="btnToggleBar" title="收起顶栏">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7.4 15.4L12 10.8l4.6 4.6L18 14l-6-6-6 6z"/></svg>
    </button>
  </div>
  <div id="books"></div>
</div>

<div id="searchPanel" hidden>
  <input id="searchInput" placeholder="搜索章节 / 小节 / 考点" autocomplete="off">
  <div id="searchList"></div>
</div>
<div id="crumbs"></div>
<div id="zoomPct">100%</div>

<div id="tools">
  <button class="fab" id="btnIn" title="放大">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z"/></svg>
  </button>
  <button class="fab" id="btnOut" title="缩小">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13H5v-2h14z"/></svg>
  </button>
  <button class="fab primary" id="btnFit" title="自适应视图">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15 3l2.3 2.3-2.9 2.9 1.4 1.4 2.9-2.9L21 9V3zM3 9l2.3-2.3 2.9 2.9 1.4-1.4-2.9-2.9L9 3H3zm6 12l-2.3-2.3 2.9-2.9-1.4-1.4-2.9 2.9L3 15v6zm12-6l-2.3 2.3-2.9-2.9-1.4 1.4 2.9 2.9L15 21h6z"/></svg>
  </button>
</div>

<div id="hint">拖拽平移 · 双指或滚轮缩放 · 点击节点展开</div>

<div id="snapGhost"></div>

<!-- 侧边停靠坞：最小化的小窗收成大号大头针标签 -->
<div id="dock"></div>

<!-- 离线包状态：打包进度 / 离线就绪 / 断网提示 -->
<div id="pwaChip" hidden>
  <span class="pwa-ico" id="pwaIco"></span>
  <span class="pwa-txt" id="pwaTxt"></span>
</div>

<script>
"use strict";
const BUILD_ID = "__BUILD__";

const DATA = __DATA__;

/* =====================================================================
   1. 物理参数（逐条对应 Compose 源码）
   ===================================================================== */
const SPRING_K   = 400;   // Spring.StiffnessMediumLow
const SPRING_C   = 24;    // DampingRatioLowBouncy 0.6 → c = 2*0.6*sqrt(400)
const TWEEN_FAST = 180;   // LOD tween
const TWEEN_BASE = 220;   // 入场 tween
const LOD_SCALE  = 0.65;  // 语义缩放阈值
const SCALE_MIN  = 0.35;
const SCALE_MAX  = 2.6;
const FIT_MIN    = 0.35;
const FIT_MAX    = 1.3;
/* 横向填满宽度时的缩放上限。
   光栅实测（1440×900，按真实像素统计卡片覆盖，2px 网格）：
     FILL_MAX=1.6 → 视口占用 31.7%，s=1.578，字 20.5px
     FILL_MAX=2.0 → 视口占用 39.6%，s=2.000，字 26.0px
     FILL_MAX=2.4 → 视口占用 40.0%，s=2.047，字 26.6px  ← 最优
     FILL_MAX=2.8 → 与 2.4 完全相同（已被 byW 自然限住）
   1.6 让内容只占屏幕三成，四周大片留白；放到 2.4 后屏幕被用到四成，
   且重叠恒为 0%。再往上没有收益，因为宽度已拟合满。 */
const FILL_MAX   = 2.4;
/* 字号可读下限：取景缩放跌破它就宁可少展，不可看不清。
   autoFill 与 fitView 共用，因此必须是模块级，不能留在函数内。 */
const READABLE_MIN = 0.72;
/* autoFill 的字号地板：低于 0.85（≈11px 字）就不再展开。
   注意不能用绝对缩放阈值判断"该不该展"——
   实测 768 屏首屏缩放本来只有 1.3、1024 屏 1.425，
   若要求 >= 1.45 则一章都展不开（19 张卡、屏幕占用仅 27%）。
   真正的判据是"展开后屏幕占用是否上升"，见 autoFill 内部。 */
const FONT_FLOOR = 0.85;
let   FIT_PAD    = 16;

/* 布局常量（DictMindMap.computeMindMapLayout） */
/* ---- 响应式度量：按视口实时计算，小屏不再溢出 ---- */
const COL_W_BASE = [212, 230, 246, 264];  // 桌面基准列宽（收紧后 1024 屏可横排）
const W_PARA_BASE = 520;

/* 小屏纵向缩进布局（TreeChat 窄屏模式）：横排四列在 360px 上必然缩到 0.4 倍，
   文字不可读，因此窄屏改为自上而下缩进，只沿纵向滚动 */
let VERTICAL   = false;   // 是否纵向布局
let INDENT_V   = 22;      // 每层缩进
let PAD_V      = 12;      // 左右安全边距
let GAP_Y_V    = 3;       // 纵向卡片间距
let COL_W_V    = [];      // 纵向各层卡片宽度
/* 卡片最小宽度（自适应下限）。
   实测 3,618 条知识点标题：中位仅 3 个汉字（≈39px 文字），
   P90 也只有 6 个字。原下限 96px 会把 82.8% 的卡强行撑宽，
   总共浪费 82,031px 宽度（平均每张 22.7px，单卡 60% 是空背景）。
   降到 56px 后浪费归零，同时仍能容纳最短 2 字标题 + 箭头按钮。 */
const MIN_CARD_W = 56;
const KP_CHUNK   = 20;                 // 每节首屏挂载的知识点数
const PARA_CHUNK = 80;                 // 正文首屏渲染的段落数

let TARGET_ASPECT = 1.6;   // 视口宽高比：布局据此决定每层拆几列
let COL_W  = COL_W_BASE.slice();
let GAP_X  = 12;
let GAP_Y  = 3;
/* 对齐方式：top = 父卡与首个子卡顶端对齐；center = 父卡居中于子块。
   两种都在 place() 的同一次调用内用子块高度算出，不依赖任何回读值。 */
let ALIGN_MODE = "center";
try{ ALIGN_MODE = localStorage.getItem("alignMode") || "center"; }catch(_){}
let W_PARA = W_PARA_BASE;
let IS_COMPACT = false;

function computeMetrics(){
  const W = innerWidth, H = innerHeight;
  const tiny    = W < 420;
  const compact = W < 720 || H < 620;
  IS_COMPACT = compact;
  /* 布局用：让包围盒形状贴近视口，才能把屏幕用满 */
  TARGET_ASPECT = (stage.clientWidth || W) / Math.max(1, (stage.clientHeight || H));

  /* 列宽按屏宽收缩，但守住可读下限（再窄中文标题就没法两行了） */
  const k = tiny ? 0.60 : compact ? 0.76 : 1;
  const floor = tiny ? 188 : compact ? 210 : 0;
  /* 先算出"横向布局"的列宽，作为方向判据的唯一依据。
     注意不能直接读 COL_W —— 纵向模式下 COL_W 已被改写，
     重复调用会自我污染，得出"越来越窄"的错误结论。 */
  const COL_W_H = COL_W_BASE.map(w => Math.max(floor, Math.round(w * k)));

  GAP_X = tiny ? 6 : compact ? 7 : 8;
  GAP_Y = compact ? 2 : 2;
  W_PARA = Math.min(W_PARA_BASE, Math.max(280, W - 48));
  FIT_PAD = compact ? 8 : 16;

  /* 方向判据：横排放进屏宽后，缩放比还够不够读？
     只看"放不放得下"会把 1440 桌面也判成纵向（四列共 1512px）。
     真正该问的是 fitView 缩放后字号是否还可读，阈值 0.72。 */
  const hNeed   = COL_W_H.reduce((a, b) => a + b, 0) + GAP_X * 3;
  const fitNeed = (W * 0.92) / hNeed;
  VERTICAL = fitNeed < 0.72;

  if(VERTICAL){
    INDENT_V = tiny ? 14 : 18;
    PAD_V    = tiny ? 8 : 12;
    GAP_Y_V  = tiny ? 2 : 3;
    /* 每层可用宽度 = 屏宽 - 两侧边距 - 该层缩进；守住可读下限 200 */
    COL_W_V = COL_W_BASE.map((_, d) =>
      Math.max(180, Math.min(340, W - PAD_V * 2 - d * INDENT_V)));
    /* 纵向模式下卡片按自身层宽渲染 */
    COL_W = COL_W_V.slice();
    W_PARA = Math.min(W - PAD_V * 2, 440);
  }else{
    COL_W_V = [];
    /* 必须显式还原横向列宽：否则从纵向切回横向时会沿用上次的
       COL_W_V（[440,440,440,440]），四列总宽膨胀到 2096px 直接溢出 */
    COL_W = COL_W_H.slice();
    W_PARA = Math.min(W_PARA_BASE, Math.max(280, W - 48));
  }

  document.documentElement.classList.toggle("compact", compact);
  document.documentElement.classList.toggle("tiny", tiny);
}

/* =====================================================================
   2. 树构建
   ===================================================================== */
let NODES = [];          // 扁平节点表
let ROOT  = null;
let bookIdx = 0;

function makeNode(o){
  const n = Object.assign({
    id:"", kind:"kp", label:"", depth:0, parent:null, children:[],
    open:false, visible:false, hasPara:false, paraOpen:false, paraLoaded:false,
    w:COL_W[0], h:34,
    x:0, y:0, vx:0, vy:0, tx:0, ty:0,
    fx:0, fy:0, fvx:0, fvy:0, _anim:false,   /* FLIP：相对布局位置的瞬时偏移 */
    el:null, alpha:0, scaleIn:1,
    shown:null,        /* 已挂载的子节点数（null = 未截断） */
    moreNode:null,     /* "再显示 N 条"哨兵节点 */
    paraAll:null,      /* 全量正文段落 */
    paraShown:0        /* 已渲染的段落数 */
  }, o);
  return n;
}

/* ---- 子节点的唯一出口：分页截断都在这里，布局/连线/可见性统一走它 ---- */
const NO_KIDS = [];
function kidsOf(n){
  if(!n.open) return NO_KIDS;
  const c = n.children;
  if(!c.length) return c;

  /* 只有"节"节点的子节点（知识点）才可能海量 */
  const lim = (n.shown == null) ? (n.kind === "section" ? KP_CHUNK : c.length) : n.shown;
  if(lim >= c.length) return c;

  if(!n.moreNode){
    n.moreNode = makeNode({
      id: n.id + "@more", kind:"more", depth: n.depth + 1,
      parent: n, w: COL_W[Math.min(n.depth + 1, COL_W.length - 1)]
    });
    NODES.push(n.moreNode);
  }
  const remain = c.length - lim;
  n.moreNode.remain = remain;
  n.moreNode.label = "再显示 " + Math.min(KP_CHUNK, remain) + " 条 · 余 " + remain;
  return c.slice(0, lim).concat([n.moreNode]);
}

function buildTree(book){
  NODES = [];
  const root = makeNode({
    id:"root", kind:"root", label:book.t, depth:0, w:COL_W[0], open:true
  });
  NODES.push(root);

  book.c.forEach((ch, ci) => {
    const cn = makeNode({
      id:ch.id, kind:"chapter", label:ch.t, depth:1, parent:root,
      w:COL_W[1], weight:ch.w
    });
    root.children.push(cn); NODES.push(cn);

    ch.s.forEach(se => {
      const sn = makeNode({
        id:se.id, kind:"section", label:se.t, depth:2, parent:cn,
        w:COL_W[2], weight:se.w, hasPara:true, kpCount:se.n
      });
      cn.children.push(sn); NODES.push(sn);

      se.k.forEach((kp, ki) => {
        const kn = makeNode({
          id:se.id + "#" + ki, kind:"kp", label:kp.t, depth:3, parent:sn,
          w:COL_W[3], weight:kp.w, kp:kp
        });
        sn.children.push(kn); NODES.push(kn);
      });
    });
  });

  ROOT = root;
  return root;
}

/* =====================================================================
   3. 布局：tidy tree —— 叶子按累计高度排布，父节点取子节点中位
   ===================================================================== */
function ensureDom(n){
  if(n.tn) return;
  const tn = document.createElement("div"); tn.className = "tn";
  const tc = document.createElement("div"); tc.className = "tc";
  const tk = document.createElement("div"); tk.className = "tk";
  tn.appendChild(tc); tn.appendChild(tk);
  n.tn = tn; n.tc = tc; n.tk = tk;
}

/* 把节点的 DOM 挂到父节点的子列里，顺序即兄弟顺序。
   已经挂好的元素再次 appendChild 会移动到末尾 —— 正好用来排序。 */
function syncTree(){
  refreshVisible();
  ensureDom(ROOT);
  if(ROOT.tn.parentNode !== nodesLayer) nodesLayer.appendChild(ROOT.tn);
  ROOT.tn.style.display = "";
  (function walk(n){
    const kids = n.open ? kidsOf(n) : [];
    const vis = [];
    for(const c of kids){
      if(!c.visible){
        if(c.tn && c.tn.parentNode) c.tn.parentNode.removeChild(c.tn);
        continue;
      }
      ensureDom(c);
      if(!c.el) createCard(c);
      c.tn.style.display = "";
      vis.push(c);
    }
    n.tk.style.display       = vis.length ? "flex" : "none";
    n.tk.style.flexDirection = "column";
    n.tk.style.gap           = GAP_Y + "px";
    n.tk.style.marginLeft    = GAP_X + "px";
    n.tn.style.alignItems    = (ALIGN_MODE === "center") ? "center" : "flex-start";
    for(const c of vis) n.tk.appendChild(c.tn);
    for(const c of vis) walk(c);
  })(ROOT);
  for(const n of NODES){
    if(n.tn && !n.visible && n.tn !== ROOT.tn && n.tn.parentNode){
      n.tn.parentNode.removeChild(n.tn);
    }
  }
}

/* =====================================================================
   布局：交给浏览器
   ---------------------------------------------------------------------
   旧实现用 JS 算 ty/tx，再靠弹簧把卡片挪过去。真实浏览器里卡片高度
   与 JS 预估不一致（实测章节卡 204×40、小节卡 296×57），于是父子
   越排越偏 —— 这就是反复出现的"对不齐"。
   现在卡片是嵌套 flex：
     .tn{display:flex;align-items:center}    卡片垂直居中于子节点列
     .tk{display:flex;flex-direction:column} 子节点自上而下排列
   对齐由浏览器保证，然后把结果读回 tx/ty 供连线与取景使用。
   ALIGN_MODE="top" 时 .tn 改为 align-items:flex-start。
   ===================================================================== */
function computeLayout(){
  syncTree();
  const wr = world.getBoundingClientRect();
  const s  = view.s || 1;
  for(const n of NODES){
    if(!n.visible || !n.el || !n.el.isConnected) continue;
    const r = n.el.getBoundingClientRect();
    /* 宽高用 offsetWidth/Height：不受卡片自身 scale 动画影响 */
    n.w = n.el.offsetWidth  || n.w;
    n.h = n.el.offsetHeight || n.h;
    /* rect 里含 FLIP 的瞬时位移 fx/fy，扣掉才是真正的布局位置 */
    n.tx = (r.left - wr.left) / s - (n.fx || 0);
    n.ty = (r.top  - wr.top ) / s - (n.fy || 0);
    n.x  = n.tx; n.y = n.ty;
  }
}

/* 可见集合：自身可见 = 所有祖先都 open
   [重要] 必须遍历完整 children，不能用 kidsOf：
     kidsOf 在 !open 时直接返回 NO_KIDS，递归到已收起的节点就断了，
     它的子孙永远得不到 visible=false。后果有两个：
       ① 收起父节点后子卡片仍是 visible=true，relayout 里 display 保持 ""，
          于是"留在原处"收不掉；
       ② computeLayout 的 walkY 同样走 kidsOf，这些卡片不参与重排，
          保留上一轮的 tx/ty，展开别的节点时就压在同一位置重叠。 */
function refreshVisible(){
  const vis = [];
  (function walk(n, parentOpen){
    n.visible = parentOpen;
    if(n.visible) vis.push(n);
    const childOpen = parentOpen && n.open;
    /* 展开时走 kidsOf（含分页哨兵）；收起时走完整 children，
       并且要把 moreNode 一起带进去，否则分页哨兵同样收不掉 */
    const kids = n.open
      ? kidsOf(n)
      : (n.moreNode ? n.children.concat([n.moreNode]) : n.children);
    kids.forEach(c => walk(c, childOpen));
  })(ROOT, true);
  return vis;
}

/* =====================================================================
   4. DOM 构建
   ===================================================================== */
const nodesLayer = document.getElementById("nodes");
const edgeLayer  = document.getElementById("edges");
const stage      = document.getElementById("stage");
const world      = document.getElementById("world");
const grid       = document.getElementById("grid");

const SVG = {
  chev:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9.3 6.7L14.6 12l-5.3 5.3 1.4 1.4L17.4 12 10.7 5.3z"/></svg>',
  doc :'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zm-1 7V3.5L18.5 9zM8 13h8v2H8zm0 4h8v2H8z"/></svg>',
  fire:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1.5 4 5 5.5 5 9.5A5 5 0 017 11.5C7 8 10 6.5 12 2zm0 18a4 4 0 004-4c0-1.6-.9-2.7-2-3.6.2 1.4-.4 2.4-1.3 2.8.3-2.2-1-3.6-2.2-4.6C9 12 8 13.3 8 15a4 4 0 004 5z"/></svg>',
  win :'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2zM14 3v2h3.6l-9.8 9.8 1.4 1.4L19 6.4V10h2V3z"/></svg>'
};

function esc(s){
  return String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

function createCard(n){
  const el = document.createElement("div");
  el.className = "card " + n.kind + (n.weight === "high" ? " hot" : "");
  el.dataset.id = n.id;
  /* 关键：绝对定位元素的可用宽度是 0，必须显式给宽，
     否则 shrink-to-fit 会把中文压成一字一行（即"长条"） */
  const capW = n.paraOpen ? W_PARA : n.w;
  el.style.width = capW + "px";

  const hasKids = n.children.length > 0;
  /* 知识点详情行默认折叠，因此需要自己的展开箭头 */
  const hasDetail = !!(n.kind === "kp" && n.kp &&
                       ((n.kp.p && n.kp.p.length) || n.kp.y));
  const chev = (hasKids || n.hasPara || hasDetail)
    ? '<button class="ibtn chev" data-act="toggle">' + SVG.chev + '</button>' : '';

  /* 不再生成「N节 / N点」徽标。
     实测 1440 屏：chapter 卡装饰宽 60px、section 卡 100px，
     其中徽标固定占 32px（30 + gap），43 张卡合计 1,376px 宽度。
     而这些数字展开后就能看到，属于纯冗余；移出后卡宽直接收窄 32px。 */
  let badge = "";
  /* 真题标记不再用「真题」徽标。
     实测：3,618 张 kp 卡里有 3,229 张是高频，徽标各占 36px，
     合计 116,244px，占全部装饰宽度的 76.3%，去掉后整卡宽度减少 37.1%。
     而且人人都有标 = 没有区分度。改为左侧 2px 金色竖条（CSS），
     横向零占用，靠颜色一眼分辨。 */

  let detail = "";
  if(n.kind === "kp" && n.kp){
    const kp = n.kp;
    if(kp.p && kp.p.length){
      detail += '<div class="detail">' +
        kp.p.map(p => '<div class="pt"><span>' + esc(p) + '</span></div>').join("") +
        '</div>';
    }
    if(kp.y) detail += '<div class="detail" style="margin-top:5px;opacity:.75">题型：' + esc(kp.y) + '</div>';
  }

  el.innerHTML =
    '<div class="row">' +
      '<span class="label">' + esc(n.label) + '</span>' +
      badge +
      (n.kind === "section"
        ? '<button class="ibtn act" data-act="win" title="在窗口中打开">' + SVG.win + '</button>' +
          '<button class="ibtn act" data-act="para" title="画布内展开正文">' + SVG.doc + '</button>'
        : '') +
      chev +
    '</div>' + detail;

  ensureDom(n);
  n.tc.appendChild(el);
  n.el = el;

  /* ---- 自适应卡宽：先量自然宽，再收敛 ----
     固定列宽会让"10 个字 + 268px 卡"留下 60% 空背景，
     这是截图里最刺眼的面积浪费。改为让卡片刚好包住内容。 */
  measureCardW(n);

  /* 一次性量高，之后布局不再触发重排 */
  n.h = Math.max(22, el.offsetHeight);
  return el;
}

/* =====================================================================
   5. 视图变换（唯一合成层，只改 transform）
   ===================================================================== */
const view = { px:0, py:0, s:1, tpx:0, tpy:0, ts:1, springing:false };

function applyView(){
  const _zp = document.getElementById("zoomPct");
  if(_zp) _zp.textContent = Math.round(view.s * 100) + "%";
  world.style.transform =
    "translate3d(" + view.px.toFixed(2) + "px," + view.py.toFixed(2) + "px,0) scale(" + view.s.toFixed(4) + ")";
  /* 点阵跟随平移，取模避免数值无限增长 */
  const gx = ((view.px % 36) + 36) % 36;
  const gy = ((view.py % 36) + 36) % 36;
  grid.style.transform = "translate3d(" + gx.toFixed(1) + "px," + gy.toFixed(1) + "px,0)";
  const lod = view.s >= LOD_SCALE ? 1 : 0;
  if(lod !== applyView._lod){
    applyView._lod = lod;
    nodesLayer.style.setProperty("--lod", lod);
  }
  if(typeof updateCrumbsThrottled === "function") updateCrumbsThrottled();
}

/* =====================================================================
   6. 帧循环：弹簧 + 惯性 + 连线重绘
   ===================================================================== */
let rafId = 0, lastT = 0, vel = { x:0, y:0 }, inertiaOn = false;

function needsFrame(){
  if(inertiaOn) return true;
  if(view.springing) return true;
  for(const n of NODES){
    if(!n.visible || !n.el) continue;
    if(n.alpha < 0.999 || n.scaleIn < 0.999) return true;
    if(n.fx || n.fy || n.fvx || n.fvy) return true;
  }
  return false;
}

function frame(t){
  rafId = 0;
  if(!lastT) lastT = t;
  let dt = (t - lastT) / 1000;
  lastT = t;
  dt = Math.min(dt, 1/30);           // 掉帧时不让弹簧积分爆炸

  /* --- 节点动效：FLIP 弹簧归零 + 入场淡入/缩放 --- */
  let moving = false;
  for(const n of NODES){
    if(!n.visible || !n.el) continue;
    let anim = false;
    if(n.fx || n.fy || n.fvx || n.fvy){
      const ax = -SPRING_K * n.fx - SPRING_C * n.fvx;
      const ay = -SPRING_K * n.fy - SPRING_C * n.fvy;
      n.fvx += ax * dt; n.fvy += ay * dt;
      n.fx  += n.fvx * dt; n.fy  += n.fvy * dt;
      if(Math.abs(n.fx) < 0.3 && Math.abs(n.fy) < 0.3 &&
         Math.abs(n.fvx) < 2 && Math.abs(n.fvy) < 2){
        n.fx = n.fy = n.fvx = n.fvy = 0;
      }else{
        anim = true;
      }
    }
    const fadeIn = n.alpha < 1, growIn = n.scaleIn < 1;
    if(fadeIn) n.alpha = Math.min(1, n.alpha + dt * (1000 / TWEEN_BASE));
    if(growIn) n.scaleIn = Math.min(1, n.scaleIn + dt * (1000 / 220));
    if(anim || fadeIn || growIn){
      const sc = 0.92 + 0.08 * n.scaleIn;
      n.el.style.transform =
        "translate3d(" + n.fx.toFixed(2) + "px," + n.fy.toFixed(2) + "px,0) scale(" + sc.toFixed(3) + ")";
      n.el.style.opacity = n.alpha.toFixed(3);
      n.x = n.tx + n.fx; n.y = n.ty + n.fy;
      n._anim = true;
      moving = true;
    }else if(n._anim){
      n.el.style.transform = "";
      n.el.style.opacity = "";
      n.x = n.tx; n.y = n.ty;
      n._anim = false;
    }
  }

  /* --- 视图弹簧（滚轮/按钮缩放） --- */
  if(view.springing){
    const k = 300, c = 26;
    view._vx = (view._vx || 0) + (-k * (view.s - view.ts) - c * view._vx) * dt;
    view.s += view._vx * dt;
    if(Math.abs(view.s - view.ts) < 0.0008 && Math.abs(view._vx) < 0.004){
      view.s = view.ts; view._vx = 0; view.springing = false;
    }
    applyView();
    moving = true;
  }

  /* --- 惯性衰减（0.92/帧，对齐 Compose Decay） --- */
  if(inertiaOn){
    view.px += vel.x * dt; view.py += vel.y * dt;
    const decay = Math.pow(0.92, dt * 60);
    vel.x *= decay; vel.y *= decay;
    applyView();
    if(Math.hypot(vel.x, vel.y) < 18) inertiaOn = false;
    moving = true;
  }

  if(moving) drawEdges();

  if(needsFrame()) rafId = requestAnimationFrame(frame);
  else { lastT = 0; if(moving) drawEdges(); }
}

function kick(){
  if(!rafId){ lastT = 0; rafId = requestAnimationFrame(frame); }
}

/* =====================================================================
   7. 连线：bezierPath 复刻
      dx = max(|ex-sx|, 60) * 0.5 ; cubicTo(sx+dx, sy, ex-dx, ey)
   ===================================================================== */
function anchorOut(n){
  return VERTICAL
    ? { x:n.x + cardW(n)/2, y:n.y + n.h }        /* 纵向：父出点在下边中点 */
    : { x:n.x + cardW(n),   y:n.y + n.h/2 };     /* 横向：父出点在右边中点 */
}
function anchorIn(n){
  return VERTICAL
    ? { x:n.x + cardW(n)/2, y:n.y }              /* 纵向：子入点在上边中点 */
    : { x:n.x,              y:n.y + n.h/2 };
}
function cardW(n){ return n.paraOpen ? W_PARA : n.w; }

/* 自适应卡宽的唯一实现：先量 max-content 自然宽，再收敛到 [MIN_CARD_W, 列上限]。
   createCard 与 resize 共用，避免两处逻辑分叉。 */
/* 文本像素宽度估算：CJK 按 1em，拉丁/数字按 0.55em。
   为什么不用 offsetWidth：那需要「加 measuring 类 → 强制同步重排 → 读回 → 去类」，
   3,618 张卡逐个同步重排会让首屏明显卡顿；而且量宽时机稍有不慎
   （元素未挂载 / display:none）就恒得 0，代码只能回落列宽上限，
   于是所有卡又变回满列宽 —— 这正是"卡片浪费面积"反复出现的根因。
   纯文本度量无重排、无时序依赖，结果确定。 */
function textPx(str, fs){
  let w = 0;
  for(let i = 0; i < str.length; i++){
    const c = str.charCodeAt(i);
    /* CJK 统一表意文字 / 全角标点 / 假名 / 谚文：1em */
    if((c >= 0x2E80 && c <= 0x9FFF) || (c >= 0xAC00 && c <= 0xD7AF) ||
       (c >= 0xF900 && c <= 0xFAFF) || (c >= 0xFF00 && c <= 0xFF60) ||
       (c >= 0x3000 && c <= 0x303F)) w += fs;
    else if(c === 32) w += fs * 0.28;
    else w += fs * 0.55;
  }
  return w;
}

function measureCardW(n){
  const el = n.el;
  if(!el || n.paraOpen) return n.w;
  const capW = COL_W[Math.min(n.depth, COL_W.length - 1)];

  /* 展开态：只有知识点卡有详情行，需要横向空间，才用列宽上限。
     章节/小节卡展开只是露出子节点，自身内容不变宽 ——
     对它们强制列宽会白扔 80~105px（实测第一章空 105px、第二章空 79px）。 */
  if(n.open && n.kind === "kp"){
    n.w = capW;
    el.style.width = capW + "px";
    return capW;
  }

  const fs = n.kind === "root" ? 15 : n.kind === "chapter" ? 13
           : n.kind === "section" ? 12.5 : 13;
  let w = textPx(n.label || "", fs);

  /* 装饰宽度：padding 左右 + gap + 按钮 + 徽标 */
  /* 装饰宽度只算「常驻占位」的元素。
     win/doc 两个按钮已改为 hover 时绝对定位浮现，不占流内宽度，
     因此这里不再计入 —— 与 CSS 保持同一口径，否则又会白留 36px。 */
  /* 必须把 border 算进去：.card 是 box-sizing:border-box 且有 1px 边框，
     内容可用宽 = 宽 - 2*padding - 2*border。
     .card      padding:3px 7px  → 7*2 + 1*2 = 16
     .card.kp   padding:2px 5px  → 5*2 + 1*2 = 12（边框透明但仍然占宽）
     旧值 14 / 10 漏掉了这 2px，导致卡片内容宽比文字窄 1~2px，
     几乎每张单行卡都被迫折成两行：实测卡高 24px → 39px，
     整棵树被凭空拉高一倍，再被 fitView 压缩，字就更小。
     这是"卡片浪费面积 + 树过高对不齐"的隐藏放大项。 */
  const pad = n.kind === "kp" ? 12 : 16;
  let chrome = pad;
  if(n.children.length || n.hasPara || (n.kind === "kp" && n.kp &&
     ((n.kp.p && n.kp.p.length) || n.kp.y)))   chrome += 2 + 16;   /* 展开箭头 */

  const natural = Math.ceil(w + chrome) + 1;
  /* 上限仍是列宽：标题过长时按两行折行，不无限拉宽 */
  const out = Math.max(MIN_CARD_W, Math.min(capW, natural));
  n.w = out;
  n.measured = true;
  el.style.width = out + "px";
  return out;
}

let edgePool = [];
/* 连线按父节点层级分色：根→章 用次级色，章→节 用三级色，其余用描边色 */
function edgeStyle(parent){
  if(parent.kind === "root")    return { c:"var(--secondary)", w:1.6,  o:0.72 };
  if(parent.kind === "chapter") return { c:"var(--tertiary)",  w:1.25, o:0.55 };
  return { c:"var(--outline)", w:0.9, o:0.34 };
}
function drawEdges(){
  let i = 0;
  for(const n of NODES){
    if(!n.visible || !n.open) continue;
    const p = anchorOut(n);
    for(const c of kidsOf(n)){
      if(!c.visible) continue;
      const e = anchorIn(c);
      let d;
      if(VERTICAL){
        /* 纵向：控制点沿 y 轴拉伸，形成 TreeChat 式圆润竖向下垂 */
        const dy = Math.max(Math.abs(e.y - p.y), 40) * 0.5;
        d = "M" + p.x.toFixed(1) + " " + p.y.toFixed(1) +
            "C" + p.x.toFixed(1) + " " + (p.y + dy).toFixed(1) + "," +
                  e.x.toFixed(1) + " " + (e.y - dy).toFixed(1) + "," +
                  e.x.toFixed(1) + " " + e.y.toFixed(1);
      }else{
        /* 控制点偏移必须跟随真实水平间隙，不能设保底值。
           旧代码 Math.max(|dx|, 60) * 0.5 在间隙只有 8px 时把控制点推到 30px，
           两个控制点都落到卡片内部，曲线向外鼓出 —— 就是肉眼看到的"扭曲"。
           改为取实际间隙的一半，曲线始终落在父子之间的走廊里。 */
        const dx = Math.max(3, Math.abs(e.x - p.x) * 0.5);
        d = "M" + p.x.toFixed(1) + " " + p.y.toFixed(1) +
            "C" + (p.x + dx).toFixed(1) + " " + p.y.toFixed(1) + "," +
                  (e.x - dx).toFixed(1) + " " + e.y.toFixed(1) + "," +
                   e.x.toFixed(1) + " " + e.y.toFixed(1);
      }
      let path = edgePool[i];
      if(!path){
        path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        edgeLayer.appendChild(path);
        edgePool.push(path);
      }
      path.setAttribute("d", d);
      const st = edgeStyle(n);
      const hot = (c.weight === "high");
      path.setAttribute("stroke", hot ? "var(--gold)" : st.c);
      path.setAttribute("stroke-width", String(hot ? st.w + 0.35 : st.w));
      path.setAttribute("opacity", String(hot ? Math.min(0.9, st.o + 0.25) : st.o));
      path.style.display = "";
      i++;
    }
  }
  for(let k = i; k < edgePool.length; k++) edgePool[k].style.display = "none";
}

/* =====================================================================
   8. 展开 / 收起
   ===================================================================== */
function setOpen(n, open){
  n.open = open;
  if(n.el) n.el.classList.toggle("open", open);
  /* 展开/收起改变内容宽度，重新量一次（仅状态变化时，非每帧） */
  if(n.el && n.kind === "kp") measureCardW(n);
  /* 新出现的子节点从父节点位置弹出去（Compose 入场感） */
  if(open){
    kidsOf(n).forEach(c => {
      if(!c.el) createCard(c);
      c.alpha = 0; c.scaleIn = 0;      /* 入场：淡入 + 从 0.92 生长 */
      c.visible = true;
    });
  }
}

/* FLIP：布局由浏览器算，动效靠"反向位移 + 弹簧归零"实现。
   relayout 前记录每张卡的世界坐标，重排后算出位移差，交给 frame() 弹回 0。
   这样既有原来的弹簧手感，又不会和 flex 布局打架。 */
function captureRects(){
  const wr = world.getBoundingClientRect();
  const s  = view.s || 1;
  const m = new Map();
  for(const n of NODES){
    if(n.visible && n.el && n.el.isConnected){
      const r = n.el.getBoundingClientRect();
      m.set(n, { x:(r.left - wr.left) / s, y:(r.top - wr.top) / s });
    }
  }
  return m;
}

function relayout(animate){
  const before = (animate === false) ? null : captureRects();
  computeLayout();
  if(before){
    for(const n of NODES){
      if(!n.visible || !n.el) continue;
      const old = before.get(n);
      if(old){
        n.fx = old.x - n.tx;
        n.fy = old.y - n.ty;
      }else{
        /* 新出现的卡片：从父卡当前位置弹出来（Compose 入场感） */
        const p = n.parent;
        if(p && p.visible){
          n.fx = (p.tx + p.fx) - n.tx;
          n.fy = (p.ty + p.fy) - n.ty;
        }else{ n.fx = 0; n.fy = 0; }
        n.fvx = 0; n.fvy = 0;
        n.alpha = 0; n.scaleIn = 0;
      }
    }
  }
  for(const n of NODES){
    if(!n.visible || !n.el) continue;
    n.x = n.tx + (n.fx || 0);
    n.y = n.ty + (n.fy || 0);
  }
  drawEdges();
  updateBadge();
  kick();
}

function updateBadge(){
  const bt = document.getElementById("buildTag");
  if(!bt) return;
  let mx = 0, pairs = 0;
  for(const n of NODES){
    if(!n.visible || !n.open) continue;
    const kids = kidsOf(n).filter(c => c.visible);
    if(!kids.length) continue;
    const last = kids[kids.length - 1];
    const d = (ALIGN_MODE === "center")
      ? Math.abs((n.ty + n.h / 2) - (kids[0].ty + (last.ty + last.h)) / 2)
      : Math.abs(kids[0].ty - n.ty);
    pairs++;
    if(d > mx) mx = d;
  }
  bt.textContent = BUILD_ID + " · " + (ALIGN_MODE === "center" ? "居中" : "顶部")
                 + " · Δ" + (Math.round(mx * 10) / 10) + " (" + pairs + ")";
}

function toggleNode(n){
  /* 分页哨兵：再放一页知识点出来 */
  if(n.kind === "more"){
    const p = n.parent;
    if(!p) return;
    p.shown = (p.shown == null ? KP_CHUNK : p.shown) + KP_CHUNK;
    relayout();
    return;
  }
  /* 知识点：展开/收起详情行。默认收起，避免要点铺满画布 */
  if(n.kind === "kp"){
    setOpen(n, !n.open);
    relayout();
    return;
  }
  if(n.kind === "section" && n.hasPara){
    /* 有正文的节：先展开子节点，再允许正文 */
    if(n.children.length){ setOpen(n, !n.open); relayout(); return; }
  }
  if(n.children.length){
    setOpen(n, !n.open);
    relayout();
  }
}

/* 正文分页渲染：先 80 段，底部按钮按需追加，避免 6390 段一次性进 DOM */
function paraHtml(list, from, to){
  let html = "";
  for(let i = from; i < to; i++){
    const p = list[i];
    html += '<p><span class="pid">p' + p.i + '</span>' + esc(p.t) + '</p>';
  }
  return html;
}

function renderParaPage(n){
  if(!n.paraEl || !n.paraAll) return;
  const total = n.paraAll.length;
  const to = Math.min(total, n.paraShown);
  n.paraBody.innerHTML = paraHtml(n.paraAll, 0, to);
  if(to < total){
    const left = total - to;
    n.paraBody.insertAdjacentHTML("beforeend",
      '<button class="para-more" type="button">继续加载 ' +
      Math.min(PARA_CHUNK, left) + ' 段 · 余 ' + left + '</button>');
    n.paraBody.querySelector(".para-more").addEventListener("click", ev => {
      ev.stopPropagation();
      n.paraShown = Math.min(total, n.paraShown + PARA_CHUNK);
      renderParaPage(n);
      n.h = Math.max(22, n.el.offsetHeight);
      relayout();
    });
  }
}

async function togglePara(n){
  if(!n.paraLoaded){
    n.paraLoaded = true;
    n.el.classList.add("loading");
    try{
      const r = await fetch("data/para/" + n.id + ".json");
      n.paraAll = await r.json();
      n.el.insertAdjacentHTML("beforeend", '<div class="para"><div class="para-body"></div></div>');
      n.paraEl   = n.el.querySelector(".para");
      n.paraBody = n.paraEl.querySelector(".para-body");
      n.paraShown = Math.min(PARA_CHUNK, n.paraAll.length);
      renderParaPage(n);
    }catch(e){
      n.el.insertAdjacentHTML("beforeend",
        '<div class="para" style="color:var(--outline)">正文分片加载失败（需通过 http 打开）</div>');
      n.paraEl = n.el.querySelector(".para");
    }
    n.el.classList.remove("loading");
  }
  n.paraOpen = !n.paraOpen;
  n.el.classList.toggle("para-open", n.paraOpen);
  if(n.paraEl) n.paraEl.style.display = n.paraOpen ? "" : "none";
  n.el.style.width = (n.paraOpen ? W_PARA : n.w) + "px";
  n.h = Math.max(22, n.el.offsetHeight);
  relayout();
}

/* =====================================================================
   9. 手势：拖拽 / 惯性 / 双指缩放 / 滚轮缩放
   ===================================================================== */
let ptrs = new Map();
let dragging = false, lastPt = null, downPt = null, moved = false;
let pinchStart = 0, pinchScale = 1;

stage.addEventListener("pointerdown", e => {
  /* 卡片上同样要能拖动画布、双指缩放。
     只排除正文阅读区（那里要能选中文字），其余一律放行；
     点击与拖拽靠下面 moved>4px 阈值区分，所以不会误伤卡片点击。 */
  if(e.target.closest(".para")) return;
  ptrs.set(e.pointerId, { x:e.clientX, y:e.clientY });
  /* 不做 setPointerCapture：它会把 pointerup 重定向到 stage，
     导致卡片及其按钮拿不到原生 click（展开/收起/正文按钮全失效）。
     改为把 move/up 挂到 window 上，指针移出卡片也不断流。 */
  if(ptrs.size === 1){
    dragging = true; moved = false;
    stage.classList.add("dragging");
    inertiaOn = false;
    lastPt = { x:e.clientX, y:e.clientY };
    downPt = { x:e.clientX, y:e.clientY };
    vel.x = vel.y = 0;
  }else if(ptrs.size === 2){
    const a = [...ptrs.values()];
    pinchStart = Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y);
    pinchScale = view.s;
  }
});

window.addEventListener("pointermove", e => {
  if(!ptrs.has(e.pointerId)) return;
  ptrs.set(e.pointerId, { x:e.clientX, y:e.clientY });

  if(ptrs.size === 1 && dragging){
    const dx = e.clientX - lastPt.x;
    const dy = e.clientY - lastPt.y;
    if(Math.abs(e.clientX - downPt.x) + Math.abs(e.clientY - downPt.y) > 4) moved = true;
    view.px += dx; view.py += dy;
    /* 速度采样，松手后接惯性 */
    vel.x = vel.x * 0.65 + (dx / 0.016) * 0.35;
    vel.y = vel.y * 0.65 + (dy / 0.016) * 0.35;
    lastPt = { x:e.clientX, y:e.clientY };
    applyView();
  }else if(ptrs.size === 2){
    const a = [...ptrs.values()];
    const d = Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y);
    if(pinchStart > 0){
      const ns = Math.max(SCALE_MIN, Math.min(SCALE_MAX, pinchScale * (d / pinchStart)));
      const cx = (a[0].x + a[1].x) / 2, cy = (a[0].y + a[1].y) / 2;
      zoomAt(ns, cx, cy);
    }
  }
});

function endPtr(e){
  ptrs.delete(e.pointerId);
  if(ptrs.size === 0){
    if(dragging){
      dragging = false;
      stage.classList.remove("dragging");
      if(moved && Math.hypot(vel.x, vel.y) > 120){
        inertiaOn = true; kick();
      }else{
        vel.x = vel.y = 0;
      }
    }
    pinchStart = 0;
  }else if(ptrs.size === 1){
    const a = [...ptrs.values()];
    lastPt = { x:a[0].x, y:a[0].y };
  }
}
window.addEventListener("pointerup", endPtr);
window.addEventListener("pointercancel", endPtr);

/* 以某点为锚缩放 */
function zoomAt(ns, cx, cy){
  const k = ns / view.s;
  view.px = cx - (cx - view.px) * k;
  view.py = cy - (cy - view.py) * k;
  view.s  = ns;
  applyView();
}

/* 滚轮 / 触控板 */
stage.addEventListener("wheel", e => {
  /* 正文阅读区内的滚轮要留给文字自己滚动，
     否则一滚就缩放，长段落永远读不到下半部分。 */
  if(e.target.closest(".para")) return;
  e.preventDefault();
  const factor = Math.exp(-e.deltaY * 0.0016);
  const ns = Math.max(SCALE_MIN, Math.min(SCALE_MAX, view.s * factor));
  zoomAt(ns, e.clientX, e.clientY);
}, { passive:false });

/* 点击卡片 */
nodesLayer.addEventListener("click", e => {
  /* 拖拽/缩放结束后浏览器仍会补发一次 click。
     不拦截的话，拖完画布松手就会误触展开/收起。 */
  if(moved){ moved = false; return; }
  const card = e.target.closest(".card");
  if(!card) return;
  const n = NODES.find(x => x.id === card.dataset.id);
  if(!n) return;
  const act = e.target.closest("[data-act]");
  if(act && act.dataset.act === "win"){ openSectionWindow(n); return; }
  if(act && act.dataset.act === "para"){ togglePara(n); return; }
  toggleNode(n);
});

/* =====================================================================
   10. 自适应视图（computeFitScale 复刻：padding 90 / clamp 0.35~1.3）
   ===================================================================== */
function fitView(animate){
  const vis = NODES.filter(n => n.visible);
  if(!vis.length) return;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for(const n of vis){
    minX = Math.min(minX, n.tx);
    minY = Math.min(minY, n.ty);
    maxX = Math.max(maxX, n.tx + cardW(n));
    maxY = Math.max(maxY, n.ty + n.h);
  }
  const cw = Math.max(1, maxX - minX);
  const chh = Math.max(1, maxY - minY);
  const vw = stage.clientWidth, vh = stage.clientHeight;
  const topSafe = document.getElementById("topbar").offsetHeight + 24;
  const availW = vw - FIT_PAD * 2;
  const availH = vh - FIT_PAD - topSafe;

  /* 纵向布局只按宽度取景。
     纵向内容动辄 2000px 高，若同时按高度拟合会算出 0.245，
     被 FIT_MIN=0.35 截断后既没真正放下、字又变小 —— 两头不讨好。
     纵向本来就是靠纵向滚动阅读的，所以顶部对齐、保持可读字号。 */
  if(VERTICAL){
    const nsv = Math.max(FIT_MIN, Math.min(FIT_MAX, availW / cw));
    const npxv = Math.min((vw - cw * nsv) / 2, FIT_PAD) - minX * nsv;
    const npyv = topSafe - minY * nsv;
    if(animate){
      animateViewTo(npxv, npyv, nsv);
    }else{
      view.px = view.tpx = npxv; view.py = view.tpy = npyv;
      view.s = view.ts = nsv;
      applyView();
    }
    return;
  }

  /* 横向：宽度必须拟合，高度只在"字号仍可读"时才拟合。
     24 个并列小节纵向堆叠可达 1800px，若强行按高度塞进 900px 视口，
     缩放会掉到 0.456（13px 字变 5.9px）—— 图是"看全"了，但根本读不了。
     所以设一个可读下限 READABLE_MIN：高度拟合跌破它时放弃高度拟合，
     顶部对齐，纵向靠拖拽平移查看。 */
  /* 取景策略：可读优先，其次控制纵向溢出。
     旧策略在"填满宽度"(FILL_MAX=2.4) 与"塞进高度"之间二选一，两头都不可用：
       1548×1032 实测填满宽度 → scale 2.4，根卡字 36px，
         一屏只剩 3 章，其余全在屏幕外 —— 用户说的"完全用不了"；
       纯按高度拟合 → scale 0.72（约 9px 字）—— 用户说的"有的字看不清楚"。
     改为三步：
       1) 先按宽度拟合，上限 FIT_MAX（1.3，约 17px 字）；
       2) 若纵向溢出超过 MAX_VSCREENS 屏，压到刚好那么多屏；
       3) 压缩后不低于 READABLE_SCALE（1.0，约 13px 字）。
     纵向溢出交给拖拽平移 —— 这是可平移画布，本来就不需要一屏看全。 */
  const byW = availW / cw;
  const MAX_VSCREENS = 1.6;
  const READABLE_SCALE = 1.0;
  let ns = Math.min(byW, FIT_MAX);
  const capH = (availH * MAX_VSCREENS) / chh;
  if(ns > capH) ns = Math.max(capH, Math.min(byW, READABLE_SCALE));
  ns = Math.max(FIT_MIN, ns);
  const overflows = chh * ns > availH;

  const npx = (vw - cw * ns) / 2 - minX * ns;
  /* 高度没拟合时不能对齐"包围盒顶边"。
     横向布局里整棵树是围绕根节点垂直居中的，根节点位于树的中段；
     若把包围盒顶边贴到顶栏下沿，根节点会被推到视口下方（实测 y=1036 > 900）。
     正确做法是把根节点本身对齐到视口中上部，其余部分上下拖拽查看。 */
  /* 高度没拟合 / 放大后溢出：都不能对齐包围盒顶边。
     横向布局整棵树围绕根节点垂直居中，根节点位于树中段，
     对齐顶边会把根节点推到视口下方（实测 y=1036 > 900）。
     改为把根节点本身锚定到顶栏下沿。 */
  /* 溢出时的纵向锚点：
     居中对齐下内容会延伸到根卡【上方】，若把根卡贴到顶栏，上半截会被裁掉。
     改为取两者较高者（npy 越小内容越靠上）：
       A) 包围盒顶端对齐 → 内容从头可见；
       B) 根卡落在视口上 1/3 → 保证根卡一定出现在屏幕里（全展开时内容极高，
          只对齐顶端会把根卡推到屏幕下方）。 */
  const npyA = topSafe - minY * ns;
  const npyRoot = topSafe + availH * 0.33 - (ROOT.ty + ROOT.h / 2) * ns;
  const npy = overflows
    ? Math.min(npyA, npyRoot)
    : (topSafe + (availH - chh * ns) / 2 - minY * ns);

  if(animate){
    animateViewTo(npx, npy, ns);
  }else{
    view.px = view.tpx = npx; view.py = view.tpy = npy;
    view.s = view.ts = ns;
    applyView();
  }
}

function animateViewTo(px, py, s){
  const sx = view.px, sy = view.py, ss = view.s;
  const t0 = performance.now(), dur = 460;
  function step(t){
    let k = Math.min(1, (t - t0) / dur);
    /* M3 emphasized decelerate */
    k = 1 - Math.pow(1 - k, 3);
    view.px = sx + (px - sx) * k;
    view.py = sy + (py - sy) * k;
    view.s  = ss + (s  - ss) * k;
    applyView();
    if(k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* =====================================================================
   11. 顶栏与工具
   ===================================================================== */
const booksBar = document.getElementById("books");
const tbTitle  = document.getElementById("tbTitle");

function renderBooks(){
  booksBar.innerHTML = DATA.map((b, i) =>
    '<button class="chip' + (i === bookIdx ? " on" : "") + '" data-i="' + i + '">' +
    esc(b.t) + '</button>').join("");
}

booksBar.addEventListener("click", e => {
  const b = e.target.closest(".chip");
  if(!b) return;
  bookIdx = +b.dataset.i;
  renderBooks();
  loadBook();
});

/* 首屏自动填充：按屏幕大小决定展开多少章节。
   固定"展开前 2 章"会让 1440 屏上只有 26 张卡片，
   画布大片空白 —— 这才是"浪费可显示面积"的主因，
   而不是卡片内部太胖（实测内部空白仅 0.2%~0.6%）。

   策略：BFS 逐层展开章节；每展开一个就重排并试算取景缩放，
   一旦缩放跌破 READABLE_MIN 就回退并停止。小屏少展、大屏多展。 */
/* 屏幕被卡片覆盖的比例：Σ卡片面积 × 缩放² / 视口面积。
   这是"有没有浪费显示面积"最直接的度量 —— 展开子节点会增加卡片面积，
   但同时可能撑大包围盒、压低缩放，两者相抵未必更满，必须实测比较。 */
/* 屏幕真实覆盖率：只统计「当前真正落在视口内」的卡片面积。
   旧实现是「全部可见卡面积 × s² / 视口面积」，把已经放大到屏幕外、
   用户根本看不到的卡片也算了进去。实测 1440 屏包围盒 795×856，
   按 1.6 倍填满宽度后高 1370px，而视口只有 812px ——
   近 40% 卡片落在折叠线以下，旧公式却报 39.4% 的占用率，
   指标虚高，autoFill 一直在优化一个用户看不见的数字。
   新实现按矩形求交，只算屏幕上真的被卡片占住的地方。 */
function usageScore(){
  const vw = stage.clientWidth || W, vh = stage.clientHeight || H;
  if(vw <= 0 || vh <= 0) return 0;
  const s = view.s, px = view.px, py = view.py;
  if(!(s > 0)) return 0;
  let hit = 0;
  for(const n of NODES){
    if(!n.visible) continue;
    const x0 = n.tx * s + px, y0 = n.ty * s + py;
    const x1 = Math.min(x0 + cardW(n) * s, vw), y1 = Math.min(y0 + n.h * s, vh);
    const ax = Math.max(x0, 0), ay = Math.max(y0, 0);
    if(x1 > ax && y1 > ay) hit += (x1 - ax) * (y1 - ay);
  }
  return hit / (vw * vh);
}

function autoFill(targetCards){
  /* 目标卡片数必须跟着视口面积走。
     实测固定 64 张时：1440 屏占用 39.4%，1920 屏只有 25.4% ——
     同样 64 张卡摊在 1.6 倍面积上，自然显得空。
     以 1440×900（1.296M px²）= 64 张为基准等比放大。 */
  const vw = stage.clientWidth  || 1440;
  const vh = stage.clientHeight || 900;
  const TARGET = targetCards ||
    Math.max(48, Math.min(220, Math.round(64 * (vw * vh) / 1296000)));
  const queue = [ROOT];
  let guard = 0;
  while(queue.length && guard++ < 400){
    if(NODES.filter(n => n.visible).length >= TARGET) break;
    const n = queue.shift();
    if(!n.children.length || n.depth >= 3) continue;
    if(n.open) { n.children.forEach(c => { if(c.children.length) queue.push(c); }); continue; }

    const before = usageScore();
    setOpen(n, true);
    refreshVisible();
    computeLayout();
    fitView(false);
    /* 判据：展开后"屏幕被卡片覆盖的比例"是否真的上升。
       试过改成「只看字号是否可读」，实测是负优化：
       1440 屏从 64 张卡 / 占用 39.4% 变成 65 张卡 / 占用 29.9% ——
       多展的那一层把包围盒撑高，fitView 缩放从 1.577 掉到 1.363，
       缩放是平方项，掉一点就吃掉全部收益。所以仍用占用率判据。 */
    const after = usageScore();
    if(view.s < FONT_FLOOR || after <= before * 1.02){
      setOpen(n, false);
      refreshVisible();
      computeLayout();
      fitView(false);
      continue;
    }
    n.children.forEach(c => { if(c.children.length) queue.push(c); });
  }
  refreshVisible();
  computeLayout();
}

function loadBook(){
  const book = DATA[bookIdx];
  tbTitle.textContent = book.t;
  nodesLayer.innerHTML = "";
  edgePool.forEach(p => p.remove());
  edgePool = [];
  computeMetrics();
  buildTree(book);
  /* 首屏内容量交给 autoFill 按屏幕决定（原来固定展 2 章，大屏太空） */
  relayout();
  autoFill(64);
  relayout();
  requestAnimationFrame(() => {
    fitView(false);
    kick();
  });
}

const btnAlign = document.getElementById("btnAlign");
function syncAlignBtn(){ if(btnAlign) btnAlign.textContent = "对齐:" + (ALIGN_MODE === "center" ? "居中" : "顶部"); }
syncAlignBtn();
if(btnAlign) btnAlign.addEventListener("click", () => {
  ALIGN_MODE = (ALIGN_MODE === "center") ? "top" : "center";
  try{ localStorage.setItem("alignMode", ALIGN_MODE); }catch(_){}
  syncAlignBtn();
  relayout();
});

/* ---------- 手账主题模式（亮色米纸 / 暗色皮革） ---------- */
let THEME_MODE = "light";
try{ THEME_MODE = localStorage.getItem("theme") || "light"; }catch(_){}
const btnTheme = document.getElementById("btnTheme");
const themeIco = document.getElementById("themeIco");
const SUN_PATH = '<path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 000-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"/>';
const MOON_PATH = '<path d="M12.3 2a10 10 0 00-1.9 19.8 10 10 0 0011.6-11.6A10 10 0 0012.3 2zm-1.8 17.8A8 8 0 0110 4.1a8.2 8.2 0 001.3 4.2 8 8 0 008.6 4.1 8 8 0 01-9.4 7.4z"/>';

function applyTheme(m){
  THEME_MODE = m;
  if(m === "dark") document.documentElement.setAttribute("data-theme", "dark");
  else document.documentElement.removeAttribute("data-theme");
  if(themeIco) themeIco.innerHTML = (m === "dark") ? SUN_PATH : MOON_PATH;
  if(btnTheme) btnTheme.title = (m === "dark") ? "切换为米白象牙手账" : "切换为深黛皮革手账";
  try{ localStorage.setItem("theme", m); }catch(_){}
  drawEdges();
}
applyTheme(THEME_MODE);

if(btnTheme) btnTheme.addEventListener("click", () => {
  applyTheme(THEME_MODE === "dark" ? "light" : "dark");
});

document.getElementById("btnFit").addEventListener("click", () => fitView(true));
document.getElementById("btnIn").addEventListener("click", () => {
  const cx = stage.clientWidth / 2, cy = stage.clientHeight / 2;
  animateZoom(Math.min(SCALE_MAX, view.s * 1.25), cx, cy);
});
document.getElementById("btnOut").addEventListener("click", () => {
  const cx = stage.clientWidth / 2, cy = stage.clientHeight / 2;
  animateZoom(Math.max(SCALE_MIN, view.s / 1.25), cx, cy);
});

function animateZoom(ns, cx, cy){
  const s0 = view.s, p0x = view.px, p0y = view.py;
  const p1x = cx - (cx - p0x) * (ns / s0);
  const p1y = cy - (cy - p0y) * (ns / s0);
  animateViewTo(p1x, p1y, ns);
}

document.getElementById("btnCollapseAll").addEventListener("click", () => {
  ROOT.children.forEach(c => setOpen(c, false));
  relayout();
  setTimeout(() => fitView(true), 60);
});

document.getElementById("btnToggleBar").addEventListener("click", () => {
  document.getElementById("topbar").classList.toggle("hide");
});

/* 首屏提示自动淡出 */
setTimeout(() => document.getElementById("hint").classList.add("gone"), 4200);

let _rsT = 0;
window.addEventListener("resize", () => {
  applyView(); layoutDock();
  clearTimeout(_rsT);
  _rsT = setTimeout(() => {
    computeMetrics();
    /* 不能把 n.w 重置成列宽 —— 那会把自适应量宽的结果冲掉，
       窗口一变所有卡片退回"宽卡少字"。必须重新测量。 */
    /* 只重测可见节点：隐藏节点的 offsetWidth 恒为 0，
       重测只会让它们退回列宽上限，展开后又得再算一次。 */
    for(const n of NODES){
      if(n.el && n.visible){
        if(n.paraOpen) n.el.style.width = W_PARA + "px";
        else measureCardW(n);
      }
    }
    relayout();
    /* 方向切换后重新取景，否则会停在旧方向的空白处 */
    fitView(false);
  }, 180);
});

/* =====================================================================
   12. 悬浮小窗 / 画布伪全屏 / 真全屏
       逐条复刻 FloatingWindowManager.kt + FloatingWindowCard.kt
   ===================================================================== */
const CARD_MIN_W  = 186;    // CARD_MIN_WIDTH
const CARD_MIN_H  = 76;     // CARD_MIN_HEIGHT
const MIN_WIN_W   = 260;    // MIN_WINDOW_WIDTH_DP
const MIN_WIN_H   = 280;    // MIN_WINDOW_HEIGHT_DP
const MIN_VISIBLE = 56;     // MIN_VISIBLE_DP
const TITLE_H     = 46;     // 标题栏高度
const SNAP_DWELL  = 1000;   // snapDwellToken → delay(1s)
const SNAP_EDGE   = 14;     // 边缘判定带宽

/* 尺寸 / 位移弹簧：DampingRatioNoBouncy + StiffnessMedium(1500f) */
const WIN_K = 1500, WIN_C = 2 * Math.sqrt(1500);
/* 透明度弹簧：dampingRatio .48f / stiffness 420f */
const ALPHA_K = 420, ALPHA_C = 2 * 0.48 * Math.sqrt(420);

const WINS = [];
let winZ = 40, winSeq = 0, winRaf = 0, winLastT = 0;
let dragWin = null, dragMode = null, dragStart = null, dragOrig = null;
let snapTarget = null, snapTimer = 0;

const WICON = {
  full  : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 14H5v5h5v-2H7zm-2-4h2V7h3V5H5zm12 7h-3v2h5v-5h-2zM14 5v2h3v3h2V5z"/></svg>',
  unfull: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 16h3v3h2v-5H5zm3-8H5v2h5V5H8zm6 11h2v-3h3v-2h-5zm2-11V5h-2v5h5V8z"/></svg>',
  canvas: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17 4h3c1.1 0 2 .9 2 2v3h-2V6h-3zM4 6h3V4H4c-1.1 0-2 .9-2 2v3h2zm0 12v-3H2v3c0 1.1.9 2 2 2h3v-2zm16 0h-3v2h3c1.1 0 2-.9 2-2v-3h-2z"/></svg>',
  uncanvas:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 5H7v3h2zm8 3h-2V5h2zM9 19H7v-3h2zm8-3h-2v3h2zM4 4h4v2H6v2H4zm16 4h-2V6h-2V4h4zM4 20v-4h2v2h2v2zm16 0h-4v-2h2v-2h2z"/></svg>',
  close : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.4L17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>'
};

/* 停靠坞矢量图标（无 emoji） */
const DOCK_ICON = {
  drag :'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11 5h2v2h-2zm0 6h2v2h-2zm0 6h2v2h-2zM5 5h2v2H5zm0 6h2v2H5zm0 6h2v2H5zm12-12h2v2h-2zm0 6h2v2h-2zm0 6h2v2h-2z"/></svg>',
  pin  :'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14.5 2.5l7 7-2.1 2.1-1.4-1.4-4.2 4.2.7 3.5-1.4 1.4-4.2-4.2L3.5 21 3 20.5l5.9-5.4-4.2-4.2 1.4-1.4 3.5.7 4.2-4.2-1.4-1.4z"/></svg>',
  close:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.4L17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>'
};

function bringToFront(w){
  w.el.style.zIndex = String(++winZ);
}

/* 进入特殊形态前记下原尺寸，供"退出即还原" */
function savePre(w){
  if(!w.inSpecial){
    w.preX = w.tx; w.preY = w.ty; w.preW = w.tw; w.preH = w.th;
  }
  w.inSpecial = true;
}
function restorePre(w){
  w.inSpecial = false; w.isSnapped = false;
  w.tx = w.preX; w.ty = w.preY; w.tw = w.preW; w.th = w.preH;
  w.x = w.preX; w.y = w.preY;
}

/* 7 种吸附位（SnapTarget 枚举），半屏不小于最小宽度 */
function snapRect(t){
  const W = innerWidth, H = innerHeight;
  const hw = Math.max(W * 0.5, MIN_WIN_W);
  const hh = Math.max(H * 0.5, MIN_WIN_H);
  switch(t){
    case "LEFT_HALF"   : return { x:0,       y:0,       w:hw, h:H  };
    case "RIGHT_HALF"  : return { x:W - hw,  y:0,       w:hw, h:H  };
    case "TOP_LEFT"    : return { x:0,       y:0,       w:hw, h:hh };
    case "TOP_RIGHT"   : return { x:W - hw,  y:0,       w:hw, h:hh };
    case "BOTTOM_LEFT" : return { x:0,       y:H - hh,  w:hw, h:hh };
    case "BOTTOM_RIGHT": return { x:W - hw,  y:H - hh,  w:hw, h:hh };
  }
  return null;
}

function snapZone(px, py){
  const W = innerWidth, H = innerHeight, E = SNAP_EDGE;
  const top = py < E, bot = py > H - E, lef = px < E, rig = px > W - E;
  if(top && lef) return "TOP_LEFT";
  if(top && rig) return "TOP_RIGHT";
  if(bot && lef) return "BOTTOM_LEFT";
  if(bot && rig) return "BOTTOM_RIGHT";
  if(top) return "TOP_FULLSCREEN";
  if(lef) return "LEFT_HALF";
  if(rig) return "RIGHT_HALF";
  return null;
}

function clearSnap(){
  clearTimeout(snapTimer); snapTimer = 0; snapTarget = null;
  const g = document.getElementById("snapGhost");
  if(g) g.classList.remove("on");
}

function evalSnap(px, py, w){
  const t = snapZone(px, py);
  if(t === snapTarget) return;
  snapTarget = t;
  clearTimeout(snapTimer);
  const g = document.getElementById("snapGhost");
  if(!t){ g.classList.remove("on"); return; }

  if(t === "TOP_FULLSCREEN"){
    /* 贴顶 = 最大化：源码直接进真全屏，不画影子 */
    g.classList.remove("on");
    snapTimer = setTimeout(() => {
      if(snapTarget === "TOP_FULLSCREEN") applySnap(w, "TOP_FULLSCREEN");
    }, SNAP_DWELL);
    return;
  }
  const r = snapRect(t);
  g.style.left = r.x + "px"; g.style.top = r.y + "px";
  g.style.width = r.w + "px"; g.style.height = r.h + "px";
  g.classList.add("on");
  snapTimer = setTimeout(() => {
    if(snapTarget === t) applySnap(w, t);
  }, SNAP_DWELL);
}

function applySnap(w, t){
  clearSnap();
  if(t === "TOP_FULLSCREEN"){ setFull(w, true); return; }
  savePre(w);
  const r = snapRect(t);
  if(!r) return;
  w.tx = r.x; w.ty = r.y; w.tw = r.w; w.th = r.h;
  w.x = r.x; w.y = r.y;
  w.isSnapped = true;
  applyWin(w); kickWin();
}

/* ---------- 真全屏：覆盖全屏（含顶栏），radius 0 / 无阴影 ---------- */
/* ---------- 真全屏：浏览器 Fullscreen API ---------- */
function fsElement(){
  return document.fullscreenElement || document.webkitFullscreenElement || null;
}

function fsRequest(el){
  const fn = el.requestFullscreen || el.webkitRequestFullscreen;
  if(!fn) return false;
  try{
    const r = fn.call(el, { navigationUI: "hide" });
    if(r && r.catch) r.catch(() => {});   // 用户拒绝 / 非用户手势，静默降级
    return true;
  }catch(e){ return false; }
}

function fsExit(){
  const fn = document.exitFullscreen || document.webkitExitFullscreen;
  if(!fn) return;
  try{
    const r = fn.call(document);
    if(r && r.catch) r.catch(() => {});
  }catch(e){}
}

function setFull(w, on){
  if(on === w.isFullScreen) return;
  if(on){
    if(w.isCollapsed) setCollapsed(w, false);
    savePre(w);
    w.isCanvasFullScreen = false;
    w.el.classList.remove("canvas-full");
    w.isFullScreen = true;
    w.el.classList.add("full");
    w.tx = 0; w.ty = 0; w.tw = innerWidth; w.th = innerHeight;
    /* 交给浏览器：ESC / 系统返回手势都能退出，和 Compose 里的观感一致 */
    if(fsElement() !== w.el) fsRequest(w.el);
  }else{
    w.isFullScreen = false;
    w.el.classList.remove("full");
    restorePre(w);
    if(fsElement()) fsExit();
  }
  syncTitle(w);
  applyWin(w); kickWin();
}

/* ESC / 系统手势退出全屏后，把窗口状态收回来，避免"UI 显示已全屏但实际没有" */
function syncFullscreenState(){
  const cur = fsElement();

  /* ① 已在全屏、但浏览器已经退出 → 回退到全屏前的尺寸 */
  for(const w of WINS){
    if(w.isFullScreen && cur !== w.el){
      w.isFullScreen = false;
      w.el.classList.remove("full");
      restorePre(w);
      syncTitle(w);
      applyWin(w);
    }
  }

  /* ② 浏览器已进入全屏 → 同步窗口状态与目标尺寸 */
  if(cur && cur.classList && cur.classList.contains("win")){
    const w = WINS.find(x => x.el === cur);
    if(w){
      if(!w.isFullScreen){
        savePre(w);
        w.isCanvasFullScreen = false;
        w.el.classList.remove("canvas-full");
        w.isFullScreen = true;
        w.el.classList.add("full");
        syncTitle(w);
      }
      w.tw = innerWidth; w.th = innerHeight;
      w.tx = 0; w.ty = 0;
      applyWin(w);
    }
  }
  kickWin();
}

document.addEventListener("fullscreenchange", syncFullscreenState);
document.addEventListener("webkitfullscreenchange", syncFullscreenState);

/* 退出全屏时尺寸会变，重算一次目标矩形 */
window.addEventListener("resize", () => {
  const cur = fsElement();
  if(!cur) return;
  const w = WINS.find(x => x.el === cur);
  if(w){ w.tw = innerWidth; w.th = innerHeight; w.tx = 0; w.ty = 0; applyWin(w); kickWin(); }
});

/* ---------- 画布伪全屏：撑满画布视口（顶栏下沿 → 底部） ---------- */
function setCanvasFull(w, on){
  if(on === w.isCanvasFullScreen) return;
  if(on){
    if(w.isCollapsed) setCollapsed(w, false);
    savePre(w);
    w.isFullScreen = false;
    w.el.classList.remove("full");
    w.isCanvasFullScreen = true;
    w.el.classList.add("canvas-full");
    const top = document.getElementById("topbar").offsetHeight;
    w.tx = 0; w.ty = top; w.tw = innerWidth; w.th = Math.max(160, innerHeight - top);
  }else{
    w.isCanvasFullScreen = false;
    w.el.classList.remove("canvas-full");
    restorePre(w);
  }
  syncTitle(w);
  applyWin(w); kickWin();
}

function syncTitle(w){
  /* 圆点只切状态，不改 innerHTML（否则会把圆点本身抹掉） */
  const bf = w.titleEl.querySelector('[data-wact="full"]');
  const bc = w.titleEl.querySelector('[data-wact="canvas"]');
  const bm = w.titleEl.querySelector('[data-wact="collapse"]');
  if(bf){ bf.classList.toggle("on", !!w.isFullScreen);
          bf.title = w.isFullScreen ? "退出全屏" : "全屏"; }
  if(bc){ bc.classList.toggle("on", !!w.isCanvasFullScreen);
          bc.title = w.isCanvasFullScreen ? "退出画布全屏" : "画布全屏"; }
  if(bm){ bm.classList.toggle("on", !!w.isCollapsed);
          bm.title = w.isCollapsed ? "还原窗口" : "最小化到侧边"; }
}

/* ---------- 最小化：收成屏幕两侧的大头针标签（复刻 TreeChat WindowDockBar） ---------- */
const DOCK_PAD = 56;      /* 上下各留 56px，避免顶到顶栏 / 压住底栏 */
let dockDrag = null;

function dockSideOf(w){
  return (w.tx + w.tw / 2) < innerWidth / 2 ? "left" : "right";
}

function setCollapsed(w, on){
  if(!!on === !!w.isCollapsed) return;
  if(on){
    if(w.isFullScreen) setFull(w, false);
    if(w.isCanvasFullScreen) setCanvasFull(w, false);
    w.isCollapsed = true;
    w.preDock = { x:w.tx, y:w.ty, w:w.tw, h:w.th };
    w.dockSide = dockSideOf(w);
    /* 纵向比例 0..1，换算成像素后落在 DOCK_PAD .. H-DOCK_PAD 之间 */
    w.dockFrac = Math.min(0.92, Math.max(0.08, w.ty / Math.max(1, innerHeight)));
    w.el.style.display = "none";
    addDockPin(w);
  }else{
    w.isCollapsed = false;
    w.el.style.display = "";
    if(w.preDock){
      w.tx = w.preDock.x; w.ty = w.preDock.y;
      w.tw = w.preDock.w; w.th = w.preDock.h;
    }
    removeDockPin(w);
  }
  syncTitle(w); kickWin();
}

function addDockPin(w){
  if(w.pinEl) return;
  const el = document.createElement("div");
  el.className = "dockpin " + w.dockSide;
  el.innerHTML =
    DOCK_ICON.drag + DOCK_ICON.pin +
    '<span class="dp-t">' + esc(w.title) + '</span>' +
    '<button class="dp-x" title="关闭">' + DOCK_ICON.close + '</button>';
  document.getElementById("dock").appendChild(el);
  w.pinEl = el;

  /* 顺序与源码一致：先挂拖拽，再挂点击。
     反过来会让拖动一开始就被 click 吃掉，表现成"能点开但拖不动"。 */
  el.addEventListener("pointerdown", e => {
    if(e.target.closest(".dp-x")) return;
    dockDrag = { w:w, startY:e.clientY, frac:w.dockFrac, moved:false };
    try{ el.setPointerCapture(e.pointerId); }catch(err){}
    e.preventDefault();
    e.stopPropagation();
  });
  el.addEventListener("pointermove", e => {
    if(!dockDrag || dockDrag.w !== w) return;
    const dy = e.clientY - dockDrag.startY;
    if(!dockDrag.moved && Math.abs(dy) > 3){
      dockDrag.moved = true;
      el.classList.add("dragging");
    }
    if(!dockDrag.moved) return;
    /* 只认纵向位移：标签永远贴边，横向没有意义 */
    const avail = Math.max(1, innerHeight - DOCK_PAD * 2);
    w.dockFrac = Math.min(1, Math.max(0, dockDrag.frac + dy / avail));
    layoutDock();
  });
  const endDrag = e => {
    if(!dockDrag || dockDrag.w !== w) return;
    const moved = dockDrag.moved;
    dockDrag = null;
    el.classList.remove("dragging");
    if(!moved) setCollapsed(w, false);   /* 没拖动 = 点击还原 */
  };
  el.addEventListener("pointerup", endDrag);
  el.addEventListener("pointercancel", endDrag);

  el.querySelector(".dp-x").addEventListener("click", e => {
    e.stopPropagation();
    closeWindow(w);
  });

  layoutDock();
}

function removeDockPin(w){
  if(w.pinEl && w.pinEl.parentNode) w.pinEl.parentNode.removeChild(w.pinEl);
  w.pinEl = null;
}

function layoutDock(){
  const avail = Math.max(1, innerHeight - DOCK_PAD * 2);
  for(const w of WINS){
    if(!w.pinEl) continue;
    w.pinEl.style.top = (DOCK_PAD + avail * w.dockFrac).toFixed(1) + "px";
    w.pinEl.classList.toggle("left",  w.dockSide === "left");
    w.pinEl.classList.toggle("right", w.dockSide === "right");
  }
}

/* ---------- 写入样式（唯一合成层思路：transform 不触发重排） ---------- */
function applyWin(w){
  const sc = 0.85 + 0.15 * w.alpha;   // scaleIn(initialScale = 0.85f)
  w.el.style.transform =
    "translate3d(" + w.x.toFixed(1) + "px," + w.y.toFixed(1) + "px,0) scale(" + sc.toFixed(4) + ")";
  w.el.style.opacity = w.alpha.toFixed(3);
  const ws = w.w.toFixed(1) + "px", hs = w.h.toFixed(1) + "px";
  if(w.el.style.width  !== ws) w.el.style.width  = ws;
  if(w.el.style.height !== hs) w.el.style.height = hs;
}

function winNeedsFrame(){
  for(const w of WINS){
    if(Math.abs(w.w - w.tw) > 0.4 || Math.abs(w.h - w.th) > 0.4) return true;
    if(Math.abs(w.x - w.tx) > 0.4 || Math.abs(w.y - w.ty) > 0.4) return true;
    if(Math.abs(w.alpha - w.ta) > 0.004) return true;
  }
  return false;
}

function winFrame(t){
  winRaf = 0;
  if(!winLastT) winLastT = t;
  let dt = (t - winLastT) / 1000; winLastT = t;
  dt = Math.min(dt, 1/30);

  for(const w of WINS){
    /* 尺寸 */
    w.vw += (-WIN_K * (w.w - w.tw) - WIN_C * w.vw) * dt;
    w.vh += (-WIN_K * (w.h - w.th) - WIN_C * w.vh) * dt;
    w.w  += w.vw * dt; w.h += w.vh * dt;
    /* 位移 */
    w.vx += (-WIN_K * (w.x - w.tx) - WIN_C * w.vx) * dt;
    w.vy += (-WIN_K * (w.y - w.ty) - WIN_C * w.vy) * dt;
    w.x  += w.vx * dt; w.y += w.vy * dt;
    /* 透明度 */
    w.va += (-ALPHA_K * (w.alpha - w.ta) - ALPHA_C * w.va) * dt;
    w.alpha += w.va * dt;
    if(w.alpha < 0) w.alpha = 0;
    if(w.alpha > 1) w.alpha = 1;
    applyWin(w);
  }
  if(winNeedsFrame()) winRaf = requestAnimationFrame(winFrame);
  else winLastT = 0;
}

function kickWin(){
  if(!winRaf){ winLastT = 0; winRaf = requestAnimationFrame(winFrame); }
}

/* ---------- 创建窗口 ---------- */
function createWindow(title){
  const W = innerWidth, H = innerHeight;
  const top = document.getElementById("topbar").offsetHeight;
  const cascade = (WINS.length % 5) * 22;

  const ww = Math.min(404, W - 28);
  const wh = Math.min(540, H - top - 72);
  let wx = Math.max(14, (W - ww) / 2 + cascade);
  let wy = Math.max(top + 14, (H - wh) / 2 + cascade);
  wx = Math.min(wx, W - ww - 14);
  wy = Math.min(wy, H - wh - 14);

  const el = document.createElement("div");
  el.className = "win";
  el.innerHTML =
    '<div class="win-title">' +
      '<div class="win-dots">' +
        '<button class="dot dot-close"  data-wact="close"    title="关闭"></button>' +
        '<button class="dot dot-min"    data-wact="collapse" title="收起"></button>' +
        '<button class="dot dot-canvas" data-wact="canvas"   title="画布全屏"></button>' +
        '<button class="dot dot-full"   data-wact="full"     title="全屏"></button>' +
      '</div>' +
      '<span class="t">' + esc(title) + '</span>' +
    '</div>' +
    '<div class="win-body"></div>' +
    '<div class="rz rz-r" data-rmode="r"></div>' +
    '<div class="rz rz-b" data-rmode="b"></div>' +
    '<div class="rz rz-c" data-rmode="c"></div>';
  document.body.appendChild(el);

  const w = {
    id: "w" + (++winSeq), title: title, el: el,
    titleEl: el.querySelector(".win-title"),
    bodyEl : el.querySelector(".win-body"),
    x: wx, y: wy, w: ww, h: wh,
    tx: wx, ty: wy, tw: ww, th: wh,
    vx: 0, vy: 0, vw: 0, vh: 0,
    alpha: 0, ta: 1, va: 0,
    isFullScreen: false, isCanvasFullScreen: false,
    isSnapped: false, inSpecial: false,
    preX: wx, preY: wy, preW: ww, preH: wh
  };
  WINS.push(w);
  el.style.zIndex = String(++winZ);
  applyWin(w);
  kickWin();

  /* --- 标题栏：拖动 / 双击全屏 / 按钮 --- */
  w.titleEl.addEventListener("pointerdown", e => {
    if(e.target.closest("[data-wact]")) return;
    if(w.isFullScreen || w.isCanvasFullScreen) return;  // moveWindow 守卫
    beginDrag(w, "title", e);
  });
  w.titleEl.addEventListener("dblclick", e => {
    if(e.target.closest("[data-wact]")) return;
    setFull(w, !w.isFullScreen);
  });
  w.titleEl.addEventListener("click", e => {
    const b = e.target.closest("[data-wact]");
    if(!b) return;
    const a = b.dataset.wact;
    if(a === "close"){ closeWindow(w); return; }
    if(a === "collapse"){ setCollapsed(w, !w.isCollapsed); return; }
    if(a === "full"){ setFull(w, !w.isFullScreen); return; }
    if(a === "canvas"){ setCanvasFull(w, !w.isCanvasFullScreen); return; }
  });

  /* --- 边缘缩放 --- */
  el.querySelectorAll(".rz").forEach(h => {
    h.addEventListener("pointerdown", e => {
      if(w.isFullScreen || w.isCanvasFullScreen) return;
      beginDrag(w, h.dataset.rmode, e);
    });
  });

  el.addEventListener("pointerdown", () => bringToFront(w));
  return w;
}

function beginDrag(w, mode, e){
  dragWin = w; dragMode = mode;
  dragStart = { x: e.clientX, y: e.clientY };
  dragOrig  = { x: w.tx, y: w.ty, w: w.tw, h: w.th };
  w.vx = w.vy = w.vw = w.vh = 0;
  bringToFront(w);
  e.preventDefault();
  e.stopPropagation();
}

window.addEventListener("pointermove", e => {
  if(!dragWin) return;
  const dx = e.clientX - dragStart.x;
  const dy = e.clientY - dragStart.y;

  if(dragMode === "title"){
    /* 非全屏下 offsetSpec = snap，直接落位（Compose snap<Float>） */
    const W = innerWidth, H = innerHeight;
    let nx = dragOrig.x + dx;
    let ny = dragOrig.y + dy;
    nx = Math.max(-dragWin.tw + MIN_VISIBLE, Math.min(W - MIN_VISIBLE, nx));
    ny = Math.max(0, Math.min(H - MIN_VISIBLE, ny));
    dragWin.tx = dragWin.x = nx;
    dragWin.ty = dragWin.y = ny;
    evalSnap(e.clientX, e.clientY, dragWin);
    applyWin(dragWin);
  }else if(dragMode === "r"){
    dragWin.tw = Math.max(MIN_WIN_W, dragOrig.w + dx);
    kickWin();
  }else if(dragMode === "b"){
    dragWin.th = Math.max(MIN_WIN_H, dragOrig.h + dy);
    kickWin();
  }else if(dragMode === "c"){
    dragWin.tw = Math.max(MIN_WIN_W, dragOrig.w + dx);
    dragWin.th = Math.max(MIN_WIN_H, dragOrig.h + dy);
    kickWin();
  }
});

function endWinDrag(){
  if(!dragWin) return;
  if(dragMode === "title") clearSnap();
  dragWin = null; dragMode = null;
}
window.addEventListener("pointerup", endWinDrag);
window.addEventListener("pointercancel", endWinDrag);

/* ---------- 关闭（scaleOut 0.62 + fadeOut 150ms） ---------- */
function closeWindow(w){
  const i = WINS.indexOf(w);
  if(i < 0) return;
  removeDockPin(w);
  WINS.splice(i, 1);
  w.ta = 0;
  setTimeout(() => { if(w.el && w.el.parentNode) w.el.parentNode.removeChild(w.el); }, 160);
  kickWin();
}

/* ---------- 填充内容：考点速记 + 教材原文 ---------- */
async function openSectionWindow(n){
  const exist = WINS.find(w => w.nodeId === n.id);
  if(exist){ bringToFront(exist); return; }

  const w = createWindow(n.label);
  w.nodeId = n.id;

  let html = "";
  const kps = n.children.filter(c => c.kp).map(c => c.kp);
  if(kps.length){
    html += "<h4>考点速记</h4>";
    html += kps.map(kp => {
      const hot = kp.w === "high" ? " hot" : "";
      let tag = "";
      if(kp.e && kp.e.length) tag = '<span class="ky">' + esc(kp.e.join(" · ")) + '</span>';
      else if(kp.y) tag = '<span class="ky">' + esc(kp.y) + '</span>';
      const pts = (kp.p || []).map(p => '<div class="kp-pt"><span>' + esc(p) + '</span></div>').join("");
      return '<div class="kpitem' + hot + '"><div class="kt">' + esc(kp.t) + tag + '</div>' + pts + '</div>';
    }).join("");
  }else{
    html += '<div class="loading">本节未抽取到知识点</div>';
  }
  html += "<h4>教材原文</h4><div class=\"para\"><div class=\"loading\">载入中…</div></div>";
  w.bodyEl.innerHTML = html;

  try{
    const r = await fetch("data/para/" + n.id + ".json");
    const paras = await r.json();
    let ph = "";
    for(const p of paras){
      ph += '<p><span class="pid">p' + p.i + '</span>' + esc(p.t) + "</p>";
    }
    w.bodyEl.querySelector(".para").innerHTML = ph || '<div class="loading">本节无正文分片</div>';
  }catch(err){
    w.bodyEl.querySelector(".para").innerHTML =
      '<div class="loading">正文分片加载失败（需通过 http 打开）</div>';
  }
}

/* 窗口随视口变化重新贴合全屏形态 */
window.addEventListener("resize", () => {
  for(const w of WINS){
    if(w.isFullScreen){
      w.tx = 0; w.ty = 0; w.tw = innerWidth; w.th = innerHeight;
    }else if(w.isCanvasFullScreen){
      const top = document.getElementById("topbar").offsetHeight;
      w.tx = 0; w.ty = top; w.tw = innerWidth; w.th = Math.max(160, innerHeight - top);
    }
    w.x = w.tx; w.y = w.ty;
  }
  kickWin();
});

/* =====================================================================
   13. 启动
   ===================================================================== */
renderBooks();
loadBook();

/* =====================================================================
   14. PWA：注册 Service Worker、离线包进度、断网提示
   ===================================================================== */
const PWA_ICON = {
  down: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a9 9 0 100 18 9 9 0 000-18zm0 2a7 7 0 110 14 7 7 0 010-14zm-1 2v5H8l4 4 4-4h-3V7h-2z"/></svg>',
  done: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm-1.2 14.2l-4-4 1.4-1.4 2.6 2.6 5.6-5.6 1.4 1.4-7 7z"/></svg>',
  off:  '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.3 2L2 3.3l2.6 2.6A10 10 0 0012 22a10 10 0 007.3-3.2L21 20l1.3-1.3L3.3 2zM12 20a8 8 0 01-5.4-2.1l1.5-1.5A6 6 0 0012 18a6 6 0 003.9-1.4l1.5 1.5A8 8 0 0112 20zM12 2a10 10 0 016.2 2.1l-1.5 1.5A8 8 0 0012 4a8 8 0 00-3.4.7L7.1 3.2A10 10 0 0112 2z"/></svg>'
};

const chip = document.getElementById("pwaChip");
const chipIco = document.getElementById("pwaIco");
const chipTxt = document.getElementById("pwaTxt");
let chipTimer = 0;

function showChip(kind, icon, text, autoHide){
  if(!chip) return;
  chip.hidden = false;
  chip.classList.remove("ready", "offline");
  if(kind) chip.classList.add(kind);
  chipIco.innerHTML = icon;
  chipTxt.textContent = text;
  requestAnimationFrame(() => chip.classList.add("on"));
  clearTimeout(chipTimer);
  if(autoHide){
    chipTimer = setTimeout(() => {
      chip.classList.remove("on");
      setTimeout(() => { chip.hidden = true; }, 320);
    }, autoHide);
  }
}
function hideChip(){
  if(!chip) return;
  clearTimeout(chipTimer);
  chip.classList.remove("on");
  setTimeout(() => { chip.hidden = true; }, 320);
}

/* 断网 / 恢复：即时反馈，说明已缓存内容仍可看 */
window.addEventListener("offline", () => {
  showChip("offline", PWA_ICON.off, "已断网 · 已缓存的内容仍可正常阅读");
});
window.addEventListener("online", () => {
  showChip("ready", PWA_ICON.done, "网络已恢复", 2400);
});

if("serviceWorker" in navigator && location.protocol !== "file:"){
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").then(reg => {
      /* 监听离线包打包进度 */
      navigator.serviceWorker.addEventListener("message", ev => {
        const d = ev.data || {};
        if(d.type === "pack"){
          showChip("", PWA_ICON.down,
            "正在缓存离线正文 " + d.done + " / " + d.total);
        }else if(d.type === "pack-done"){
          if(d.fail > 0){
            showChip("offline", PWA_ICON.off,
              "离线包部分完成 · " + d.cached + " 节已缓存", 4200);
          }else{
            showChip("ready", PWA_ICON.done,
              "离线包已就绪 · " + d.cached + " 节全文可离线阅读", 4200);
          }
        }
      });

      /* 主动催一次补全（SW 激活时也会自己跑） */
      const ping = () => {
        if(reg.active) reg.active.postMessage({ type: "pack" });
      };
      if(reg.active) ping();
      else if(reg.installing || reg.waiting){
        const sw = reg.installing || reg.waiting;
        sw.addEventListener("statechange", () => {
          if(sw.state === "activated") ping();
        });
      }
    }).catch(() => { /* file:// 或权限受限时静默降级 */ });
  });
}

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

/* ---------- 面包屑 ---------- */
var crumbsEl = document.getElementById("crumbs");
var _crumbT = 0;

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
</script>
<script>
/* 构建自更新：每 10 秒比对 build.txt，发现新构建自动刷新。
   本地/线上都可能被 Service Worker 或 HTTP 缓存挡住，手动刷新不一定生效；
   这段保证"打开一次之后永远是最新的"。构建标记同时显示在顶栏，便于核对。 */
(function(){
  var B = "__BUILD__";
  var tag = document.getElementById("buildTag");
  if(tag) tag.textContent = B;
  if(location.protocol !== "http:" && location.protocol !== "https:") return;
  setInterval(function(){
    fetch("build.txt?_=" + Date.now(), { cache: "no-store" })
      .then(function(r){ return r.ok ? r.text() : ""; })
      .then(function(t){ if(t && t.trim() !== B) location.reload(); })
      .catch(function(){});
  }, 10000);
})();
</script>
</body>
</html>
"""


def build():
    books = load_data()
    n_para, n_paras = export_paragraphs()

    kp_total = sum(len(s["k"]) for b in books for c in b["c"] for s in c["s"])
    sec_total = sum(len(c["s"]) for b in books for c in b["c"])
    ch_total = sum(len(b["c"]) for b in books)

    payload = json.dumps(books, ensure_ascii=False, separators=(",", ":"))
    import datetime
    build_id = datetime.datetime.now().strftime("%m%d-%H%M%S")
    html = HTML.replace("__DATA__", payload).replace("__BUILD__", build_id)

    os.makedirs(WEB, exist_ok=True)

    # 本机 Android 共享目录：存在才写，换机器/换系统不会报错
    SHARED = "/sdcard/cccodroid/kaoyan_mindmap"
    has_shared = os.path.isdir("/sdcard/cccodroid")

    targets = [
        os.path.join(WEB, "index.html"),
        os.path.join(BASE, "index.html"),
    ]
    if has_shared:
        targets.append(os.path.join(SHARED, "index.html"))

    for t in targets:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with open(t, "w", encoding="utf-8") as f:
            f.write(html)

    # 构建标记文件：页面轮询它来发现新构建
    with open(os.path.join(WEB, "build.txt"), "w", encoding="utf-8") as f:
        f.write(build_id)
    if has_shared:
        with open(os.path.join(SHARED, "build.txt"), "w", encoding="utf-8") as f:
            f.write(build_id)

    # 正文分片同步一份到共享目录（仅本机 Android）
    if has_shared:
        shared = os.path.join(SHARED, "data", "para")
        if os.path.isdir(shared):
            shutil.rmtree(shared)
        os.makedirs(shared, exist_ok=True)
        src = os.path.join(WEB, "data", "para")
        for fn in os.listdir(src):
            shutil.copy2(os.path.join(src, fn), os.path.join(shared, fn))

    # PWA：manifest / sw.js / 图标 / 分片清单
    # 版本号取 index.html 内容哈希，重建即换缓存桶，旧包自动清理
    import hashlib
    import pwa_build
    ver = hashlib.md5(html.encode("utf-8")).hexdigest()[:10]
    _, n_shards = pwa_build.write_all(WEB, ver, os.path.join(WEB, "data", "para"))

    print("✅ 数据装配完成")
    print("   书 %d 本 / 章 %d / 节 %d / 知识点 %d" % (len(books), ch_total, sec_total, kp_total))
    print("   正文分片 %d 个 / %d 段" % (n_para, n_paras))
    print("   内联骨架 %.1f KB" % (len(payload.encode("utf-8")) / 1024))
    print("   HTML 总体 %.1f KB" % (len(html.encode("utf-8")) / 1024))
    for t in targets:
        print("   →", t)


if __name__ == "__main__":
    build()
