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
<style>
/* ============================================================
   M3 配色：种子色 0xFF28C840（TreeChat ThemePalette.DEFAULT_GREEN）
   用 OKLCH 复现 HCT Tonal Spot 映射，深色主题下
   primary=tone80 / primaryContainer=tone30 / surface=tone6 这一套配对
   ============================================================ */
:root{
  --h:145;
  --primary:            oklch(80% 0.19 var(--h));
  --on-primary:         oklch(20% 0.06 var(--h));
  --primary-container:  oklch(30% 0.09 var(--h));
  --on-primary-cont:    oklch(90% 0.07 var(--h));

  --secondary:          oklch(80% 0.07 var(--h));
  --on-secondary:       oklch(20% 0.03 var(--h));
  --secondary-container:oklch(30% 0.04 var(--h));
  --on-secondary-cont:  oklch(90% 0.03 var(--h));

  --tertiary:           oklch(82% 0.10 205);
  --tertiary-container: oklch(30% 0.06 205);
  --on-tertiary-cont:   oklch(92% 0.05 205);

  --gold:               oklch(86% 0.14 85);
  --gold-container:     oklch(32% 0.07 85);

  --surface:            oklch(7% 0.012 var(--h));
  --sc-lowest:          oklch(5% 0.010 var(--h));
  --sc-low:             oklch(10% 0.012 var(--h));
  --sc:                 oklch(13% 0.014 var(--h));
  --sc-high:            oklch(17% 0.016 var(--h));
  --sc-highest:         oklch(22% 0.018 var(--h));

  --on-surface:         oklch(92% 0.010 var(--h));
  --on-surface-var:     oklch(80% 0.020 var(--h));
  --outline:            oklch(58% 0.020 var(--h));
  --outline-var:        oklch(32% 0.016 var(--h));

  /* Shape.kt：4/8/12/16/28 */
  --r-xs:4px; --r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:28px;

  /* Compose MotionScheme 对应曲线 */
  --ease-standard: cubic-bezier(0.2,0,0,1);
  --ease-emphasized: cubic-bezier(0.05,0.7,0.1,1);
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

/* 点阵背景：36px 网格 / 1.2r / alpha .22，跟随平移但不参与缩放重绘 */
#grid{
  position:absolute;inset:-72px;
  background-image:radial-gradient(circle, color-mix(in oklch, var(--outline) 22%, transparent) 1.2px, transparent 1.2px);
  background-size:36px 36px;
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
#nodes{position:absolute;left:0;top:0;}

/* ---------- 卡片 ---------- */
.card{
  position:absolute;left:0;top:0;
  box-sizing:border-box;          /* 让 COL_W 是含 padding 的实际宽度 */
  border-radius:var(--r-md);
  background:var(--sc-high);
  border:1px solid var(--outline-var);
  padding:11px 13px;
  box-shadow:0 1px 2px rgba(0,0,0,.30), 0 4px 12px rgba(0,0,0,.26);
  will-change:transform,opacity;
  contain:layout style;
  transform-origin:0 50%;         /* 树向右生长：从左侧顶点长出 */
  transition:background .18s var(--ease-standard),
             border-color .18s var(--ease-standard),
             box-shadow .22s var(--ease-standard);
}
/* 悬停抬升（仅精确指针，触屏不触发，避免误触残留） */
@media (hover:hover) and (pointer:fine){
  .card:hover{
    box-shadow:0 2px 4px rgba(0,0,0,.34), 0 10px 26px rgba(0,0,0,.40);
    border-color:color-mix(in oklch,var(--outline) 55%, var(--outline-var));
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
  padding:9px 12px;
}
.card.more .label{
  color:var(--primary);font-size:12px;font-weight:600;
  -webkit-line-clamp:1;text-align:center;letter-spacing:.02em;
}
.card.more:hover{background:color-mix(in oklch,var(--primary) 9%, transparent);}
.card.root{
  border-radius:14px;
  background:var(--primary-container);
  border:1.5px solid var(--primary);
  box-shadow:0 6px 18px rgba(0,0,0,.44);
  padding:14px 16px;
}
.card.chapter{
  background:var(--secondary-container);
  border-color:var(--secondary);
}
.card.section{background:var(--sc-high);}
.card.kp{background:var(--sc);}
.card.kp.hot{
  background:var(--gold-container);
  border-color:var(--gold);
}

.row{display:flex;align-items:center;gap:8px;}
.label{
  flex:1;min-width:0;
  overflow:hidden;
  /* 两行截断：中文标题不再被压成一行省略号 */
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  white-space:normal;
  word-break:break-word;
  line-height:1.38;
  font-weight:500;letter-spacing:.01em;
}
.card.root .label{font-size:17px;font-weight:700;color:var(--on-primary-cont);letter-spacing:.02em;}
.card.chapter .label{font-size:14px;font-weight:700;color:var(--on-secondary-cont);}
.card.section .label{font-size:13.5px;font-weight:600;}
.card.kp .label{font-size:13px;font-weight:500;}

.badge{
  flex:none;font-size:9.5px;line-height:1;padding:3px 6px;border-radius:var(--r-xs);
  background:var(--tertiary-container);color:var(--on-tertiary-cont);
  letter-spacing:.02em;font-weight:600;
}
.badge.gold{background:var(--gold-container);color:var(--gold);}

/* 纯矢量图标按钮（无 emoji） */
.ibtn{
  flex:none;width:24px;height:24px;border:0;border-radius:50%;
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
.detail{
  margin-top:6px;font-size:11.5px;line-height:1.62;color:var(--on-surface-var);
  opacity:var(--lod,1);
  transition:opacity .18s var(--ease-standard);
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

/* ---------- 顶栏 ---------- */
#topbar{
  position:fixed;left:0;right:0;top:0;z-index:20;
  padding:calc(env(safe-area-inset-top) + 10px) 12px 10px;
  background:color-mix(in oklch,var(--sc-low) 92%,transparent);
  border-bottom:1px solid var(--outline-var);
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
  flex:none;border:1px solid var(--outline-var);border-radius:var(--r-sm);
  background:transparent;color:var(--on-surface-var);
  padding:7px 12px;font-size:12.5px;font-weight:500;white-space:nowrap;cursor:pointer;
  transition:background .2s var(--ease-standard),color .2s var(--ease-standard),border-color .2s var(--ease-standard);
}
.chip.on{
  background:var(--secondary-container);color:var(--on-secondary-cont);
  border-color:var(--secondary);font-weight:700;
}

/* ---------- 右下工具列 ---------- */
#tools{
  position:fixed;right:12px;bottom:calc(env(safe-area-inset-bottom) + 16px);z-index:20;
  display:flex;flex-direction:column;gap:10px;
}
.fab{
  width:44px;height:44px;border:0;border-radius:var(--r-lg);
  background:var(--sc-high);color:var(--on-surface);
  display:grid;place-items:center;cursor:pointer;
  box-shadow:0 3px 10px rgba(0,0,0,.42);
  transition:background .18s var(--ease-standard),transform .18s var(--ease-emphasized);
}
.fab:active{transform:scale(.92);}
.fab svg{width:20px;height:20px;display:block;}
.fab.primary{background:var(--primary);color:var(--on-primary);}

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
    <button class="ibtn" id="btnCollapseAll" title="全部收起">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 8l-6 6 1.4 1.4L12 10.8l4.6 4.6L18 14z"/></svg>
    </button>
    <button class="ibtn" id="btnToggleBar" title="收起顶栏">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7.4 15.4L12 10.8l4.6 4.6L18 14l-6-6-6 6z"/></svg>
    </button>
  </div>
  <div id="books"></div>
</div>

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
let   FIT_PAD    = 90;

/* 布局常量（DictMindMap.computeMindMapLayout） */
/* ---- 响应式度量：按视口实时计算，小屏不再溢出 ---- */
const COL_W_BASE = [268, 300, 320, 348];  // 桌面基准列宽
const W_PARA_BASE = 520;

/* 小屏纵向缩进布局（TreeChat 窄屏模式）：横排四列在 360px 上必然缩到 0.4 倍，
   文字不可读，因此窄屏改为自上而下缩进，只沿纵向滚动 */
let VERTICAL   = false;   // 是否纵向布局
let INDENT_V   = 34;      // 每层缩进
let PAD_V      = 16;      // 左右安全边距
let GAP_Y_V    = 12;      // 纵向卡片间距
let COL_W_V    = [];      // 纵向各层卡片宽度
const KP_CHUNK   = 20;                 // 每节首屏挂载的知识点数
const PARA_CHUNK = 80;                 // 正文首屏渲染的段落数

let COL_W  = COL_W_BASE.slice();
let GAP_X  = 92;
let GAP_Y  = 20;
let W_PARA = W_PARA_BASE;
let IS_COMPACT = false;

function computeMetrics(){
  const W = innerWidth, H = innerHeight;
  const tiny    = W < 420;
  const compact = W < 720 || H < 620;
  IS_COMPACT = compact;

  /* 列宽按屏宽收缩，但守住可读下限（再窄中文标题就没法两行了） */
  const k = tiny ? 0.60 : compact ? 0.76 : 1;
  const floor = tiny ? 188 : compact ? 210 : 0;
  /* 先算出"横向布局"的列宽，作为方向判据的唯一依据。
     注意不能直接读 COL_W —— 纵向模式下 COL_W 已被改写，
     重复调用会自我污染，得出"越来越窄"的错误结论。 */
  const COL_W_H = COL_W_BASE.map(w => Math.max(floor, Math.round(w * k)));

  GAP_X = tiny ? 40 : compact ? 56 : 92;
  GAP_Y = compact ? 16 : 20;
  W_PARA = Math.min(W_PARA_BASE, Math.max(280, W - 48));
  FIT_PAD = compact ? 28 : 90;

  /* 方向判据：横排放进屏宽后，缩放比还够不够读？
     只看"放不放得下"会把 1440 桌面也判成纵向（四列共 1512px）。
     真正该问的是 fitView 缩放后字号是否还可读，阈值 0.72。 */
  const hNeed   = COL_W_H.reduce((a, b) => a + b, 0) + GAP_X * 3;
  const fitNeed = (W * 0.92) / hNeed;
  VERTICAL = fitNeed < 0.72;

  if(VERTICAL){
    INDENT_V = tiny ? 18 : 24;
    PAD_V    = tiny ? 12 : 16;
    GAP_Y_V  = tiny ? 10 : 12;
    /* 每层可用宽度 = 屏宽 - 两侧边距 - 该层缩进；守住可读下限 200 */
    COL_W_V = COL_W_BASE.map((_, d) =>
      Math.max(200, Math.min(440, W - PAD_V * 2 - d * INDENT_V)));
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
    w:COL_W[0], h:44,
    x:0, y:0, vx:0, vy:0, tx:0, ty:0,
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
function computeLayout(){
  let cursor = 0;
  const seen = [];          /* 本次真正参与布局的节点（可见分支） */

  /* ① 第一遍：定 depth + 纵向位置。
     必须先跑这一遍 —— 否则新展开的子节点 depth 还是初值 0，
     下面按列统计最大宽度时会把它们全算进第 0 列，列宽推算直接失效。 */
  function walkY(n, depth){
    n.depth = depth;
    seen.push(n);
    const kids = kidsOf(n);
    if(VERTICAL){
      /* 纵向：前序 —— 父占自己的槽位，子节点依次排在下方 */
      n.ty = cursor;
      cursor += n.h + GAP_Y_V;
      kids.forEach(k => walkY(k, depth + 1));
      return;
    }
    if(kids.length === 0){
      n.ty = cursor;
      cursor += n.h + GAP_Y;
    }else{
      kids.forEach(k => walkY(k, depth + 1));
      n.ty = (kids[0].ty + kids[kids.length-1].ty) / 2;
    }
  }
  walkY(ROOT, 0);

  /* ② 每列实际宽度 = 该列所有可见节点的最大宽度。
     某张卡片展开正文（320 → 520）时，右侧整列会被真正推开，
     而不是压在展开的正文上面。 */
  const DW = COL_W.slice();
  for(const n of seen){
    const d = n.depth;
    if(d < 0 || d >= DW.length) continue;
    const cw = cardW(n);
    if(cw > DW[d]) DW[d] = cw;
  }

  const COLX = [];
  if(VERTICAL){
    /* 纵向：横向坐标只由层深决定，与列宽无关 */
    for(let d=0; d<COL_W_V.length; d++){
      COLX[d] = PAD_V + d * INDENT_V;
    }
  }else{
    for(let d=0; d<DW.length; d++){
      COLX[d] = d===0 ? 60 : COLX[d-1] + DW[d-1] + GAP_X;
    }
  }

  /* ③ 第三遍：落横向坐标 */
  for(const n of seen){
    n.tx = COLX[Math.min(n.depth, DW.length - 1)];
  }

  /* 横向布局垂直居中；纵向布局从顶部起排，避免首屏把根节点顶出视野 */
  if(!VERTICAL){
    const shift = cursor / 2 - ROOT.h / 2;
    for(const n of seen){ n.ty -= shift; }
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
  el.style.width = (n.paraOpen ? W_PARA : n.w) + "px";

  const hasKids = n.children.length > 0;
  const chev = (hasKids || n.hasPara)
    ? '<button class="ibtn chev" data-act="toggle">' + SVG.chev + '</button>' : '';

  let badge = "";
  if(n.kind === "chapter" && n.children.length)
    badge = '<span class="badge">' + n.children.length + '节</span>';
  if(n.kind === "section" && n.kpCount)
    badge = '<span class="badge">' + n.kpCount + '点</span>';
  if(n.kind === "kp" && n.weight === "high")
    badge = '<span class="badge gold">真题</span>';

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
        ? '<button class="ibtn" data-act="win" title="在窗口中打开">' + SVG.win + '</button>' +
          '<button class="ibtn" data-act="para" title="画布内展开正文">' + SVG.doc + '</button>'
        : '') +
      chev +
    '</div>' + detail;

  nodesLayer.appendChild(el);
  n.el = el;

  /* 一次性量高，之后布局不再触发重排 */
  n.h = Math.max(40, el.offsetHeight);
  return el;
}

/* =====================================================================
   5. 视图变换（唯一合成层，只改 transform）
   ===================================================================== */
const view = { px:0, py:0, s:1, tpx:0, tpy:0, ts:1, springing:false };

function applyView(){
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
}

/* =====================================================================
   6. 帧循环：弹簧 + 惯性 + 连线重绘
   ===================================================================== */
let rafId = 0, lastT = 0, vel = { x:0, y:0 }, inertiaOn = false;

function needsFrame(){
  if(inertiaOn) return true;
  if(view.springing) return true;
  for(const n of NODES){
    if(!n.visible) continue;
    if(Math.abs(n.x - n.tx) > 0.25 || Math.abs(n.vx) > 0.6) return true;
    if(Math.abs(n.y - n.ty) > 0.25 || Math.abs(n.vy) > 0.6) return true;
    if(n.alpha < 0.999) return true;
    if(n.scaleIn < 0.999) return true;
  }
  return false;
}

function frame(t){
  rafId = 0;
  if(!lastT) lastT = t;
  let dt = (t - lastT) / 1000;
  lastT = t;
  dt = Math.min(dt, 1/30);           // 掉帧时不让弹簧积分爆炸

  /* --- 节点弹簧 --- */
  let moving = false;
  for(const n of NODES){
    if(!n.visible) continue;
    const ax = -SPRING_K * (n.x - n.tx) - SPRING_C * n.vx;
    const ay = -SPRING_K * (n.y - n.ty) - SPRING_C * n.vy;
    n.vx += ax * dt; n.vy += ay * dt;
    n.x  += n.vx * dt; n.y  += n.vy * dt;
    if(n.alpha < 1) n.alpha = Math.min(1, n.alpha + dt * (1000 / TWEEN_BASE));
    if(n.scaleIn < 1) n.scaleIn = Math.min(1, n.scaleIn + dt * (1000 / 220));
    const sc = 0.92 + 0.08 * n.scaleIn;
    n.el.style.transform =
      "translate3d(" + n.x.toFixed(1) + "px," + n.y.toFixed(1) + "px,0) scale(" + sc.toFixed(3) + ")";
    if(n.alpha < 0.999) n.el.style.opacity = n.alpha.toFixed(3);
    if(Math.abs(n.x - n.tx) > 0.25 || Math.abs(n.y - n.ty) > 0.25) moving = true;
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

let edgePool = [];
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
        const dx = Math.max(Math.abs(e.x - p.x), 60) * 0.5;
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
      const hot = (c.weight === "high");
      path.setAttribute("stroke", hot ? "var(--gold)" : "var(--outline)");
      path.setAttribute("stroke-width", hot ? "1.6" : "1.1");
      path.setAttribute("opacity", hot ? "0.72" : "0.42");
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
  /* 新出现的子节点从父节点位置弹出去（Compose 入场感） */
  if(open){
    kidsOf(n).forEach(c => {
      if(!c.el) createCard(c);
      c.x = n.x; c.y = n.y; c.vx = 0; c.vy = 0;
      c.alpha = 0; c.scaleIn = 0;      /* 入场：淡入 + 从 0.92 生长 */
      c.visible = true;
    });
  }
}

function relayout(){
  refreshVisible();
  computeLayout();
  for(const n of NODES){
    if(n.visible && !n.el) createCard(n);
  }
  /* 隐藏的节点从 DOM 上摘掉 transform 成本（保留元素复用） */
  for(const n of NODES){
    if(n.el) n.el.style.display = n.visible ? "" : "none";
  }
  /* 批量测量真实卡片高度：纵向布局按 h 堆叠，h 不准就会重叠。
     连续只读不写 → 只触发一次同步布局，无逐节点重排。 */
  for(const n of NODES){
    if(n.visible && n.el){
      const hh = n.el.offsetHeight;
      if(hh > 0 && hh !== n.h) n.h = hh;
    }
  }
  /* 高度变了要重算 ty（上面已按旧 h 排过一遍） */
  if(VERTICAL){
    let c2 = 0;
    (function walkY2(n){
      n.ty = c2;
      c2 += n.h + GAP_Y_V;
      kidsOf(n).forEach(walkY2);
    })(ROOT);
  }
  /* 根节点首次落位 */
  if(ROOT && ROOT.alpha === 0){ ROOT.x = ROOT.tx; ROOT.y = ROOT.ty; ROOT.alpha = 1; }
  drawEdges();
  kick();
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
      n.h = Math.max(40, n.el.offsetHeight);
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
  n.h = Math.max(40, n.el.offsetHeight);
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
    const npxv = (vw - cw * nsv) / 2 - minX * nsv;
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
  const READABLE_MIN = 0.72;
  const byW = availW / cw;
  const byH = availH / chh;
  const heightBound = byH < READABLE_MIN && byH < byW;
  let ns = Math.min(heightBound ? byW : Math.min(byW, byH), FIT_MAX);
  ns = Math.max(FIT_MIN, ns);

  const npx = (vw - cw * ns) / 2 - minX * ns;
  /* 高度没拟合时不能对齐"包围盒顶边"。
     横向布局里整棵树是围绕根节点垂直居中的，根节点位于树的中段；
     若把包围盒顶边贴到顶栏下沿，根节点会被推到视口下方（实测 y=1036 > 900）。
     正确做法是把根节点本身对齐到视口中上部，其余部分上下拖拽查看。 */
  const npy = heightBound
    ? ((topSafe + availH * 0.42) - (ROOT.ty + ROOT.h / 2) * ns)
    : (topSafe + (availH - chh * ns) / 2 - minY * ns);        /* 真正放下了才居中 */

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

function loadBook(){
  const book = DATA[bookIdx];
  tbTitle.textContent = book.t;
  nodesLayer.innerHTML = "";
  edgePool.forEach(p => p.remove());
  edgePool = [];
  computeMetrics();
  buildTree(book);
  /* 默认展开根 + 前两个章节，首屏有内容但不至于铺满 */
  ROOT.children.slice(0, 2).forEach(c => setOpen(c, true));
  relayout();
  requestAnimationFrame(() => {
    fitView(false);
    kick();
  });
}

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
    for(const n of NODES){
      n.w = COL_W[Math.min(n.depth, COL_W.length - 1)];
      if(n.el) n.el.style.width = cardW(n) + "px";
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
    html = HTML.replace("__DATA__", payload)

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
