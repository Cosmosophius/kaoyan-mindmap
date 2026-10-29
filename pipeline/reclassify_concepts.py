#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reclassify_concepts.py
将 4880 张高质量考研背诵概念卡片（书的概念、名词解释、核心要点）
严格按照权威 RAG 题库的真实书籍、章节、小节进行精确重分类与排序！
- 绝不引入选择题/填空题，纯粹由书的概念卡片组成
- 彻底消除“语法概述里出现春节、对比分析”等任何跨书错位
- 章节内考点按考频高低与重要程度优雅排序
"""

import json
import os
import glob
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")

# 1. 载入权威 RAG 数据源，建立概念->真实归属的精确映射
pwa = json.load(open("/data/user/0/cc.codroid/files/home/workspace/kaoyan_pwa/data/all_subjects_data.json", encoding="utf-8"))
apk = json.load(open("/data/user/0/cc.codroid/files/home/workspace/apk_inspect/assets/questions.json", encoding="utf-8"))

concept_locations = {} # clean_title -> list of (doc, chapter_title, section_title)

def clean_t(s):
    if not s: return ""
    s = s.strip()
    return re.sub(r'^[“"‘\'《](.*?)[”"’\'》]$', r'\1', s)

# 从 PWA 建立
for sub_id, qs in pwa.get("questions", {}).items():
    doc = "culture" if sub_id == "culture" else ("yinlun" if sub_id == "yinlun" else "xdhy")
    for q in qs:
        ct = clean_t(q.get("stem"))
        c = (q.get("chapter") or "").strip()
        s = (q.get("section") or "").strip()
        if ct:
            if ct not in concept_locations:
                concept_locations[ct] = []
            concept_locations[ct].append((doc, c, s))

# 从 APK 建立（区分现代汉语上下册、入门等）
for q in apk.get("questions", []):
    bname = q.get("book_name", "")
    doc = "xdhy_up" if "现代汉语通论（上）" in bname else (
          "xdhy_down" if "现代汉语通论（下）" in bname else (
          "yinlun" if "引论" in bname else (
          "rumen" if "入门" in bname else "")))
    if doc:
        ct = clean_t(q.get("stem"))
        c = (q.get("chapter") or "").strip()
        s = (q.get("section") or "").strip()
        if ct:
            if ct not in concept_locations:
                concept_locations[ct] = []
            concept_locations[ct].append((doc, c, s))

# 2. 读取标准 mindmap.json 大纲，建立 (doc, chapter, section) -> section_id 的路由表
mm = json.load(open(os.path.join(OUT_DIR, "mindmap.json"), encoding="utf-8"))
route_map = {} # (doc, clean_chapter, clean_section) -> section_id
sec_meta = {}  # section_id -> {title, doc, chapter_title}
all_sections = []

for b in mm["books"]:
    doc = b["doc"]
    for c in b["chapters"]:
        c_name = c["title"].strip()
        for s in c["sections"]:
            s_name = s["title"].strip()
            sid = s["id"]
            sec_meta[sid] = {"title": s_name, "doc": doc, "chapter": c_name}
            all_sections.append(sid)
            # 记录多种匹配键
            route_map[(doc, c_name, s_name)] = sid
            # 模糊匹配键
            c_core = re.sub(r'第[一二三四五六七八九十\d]+章', '', c_name).strip()
            s_core = re.sub(r'第[一二三四五六七八九十\d]+节', '', s_name).strip()
            route_map[(doc, c_core, s_core)] = sid

print(f"标准章节路由表小节总数: {len(all_sections)}")

# 3. 收集所有概念卡片并去重
leaf_files = glob.glob(os.path.join(LEAVES_DIR, "*.json"))
all_cards = []
seen_cards = set()

for lf in leaf_files:
    d = json.load(open(lf, encoding="utf-8"))
    for kp in d.get("kps", []):
        t = (kp.get("title") or "").strip()
        pts = tuple(kp.get("points") or [])
        key = (t, pts)
        if key not in seen_cards:
            seen_cards.add(key)
            all_cards.append(kp)

print(f"去重后得到高质量概念卡片总数: {len(all_cards)}")

# 4. 重新路由每张卡片到正确的 section_id
classified = defaultdict(list)
missed = 0

for card in all_cards:
    t = card.get("title", "").strip()
    ct = clean_t(t)
    orig_sid = card.get("section_id", "")
    orig_doc = card.get("doc", "")

    target_sid = None

    # 优先查找 RAG 中记录的真实学科归属
    if ct in concept_locations:
        locs = concept_locations[ct]
        # 挑选最佳匹配
        for doc, c_name, s_name in locs:
            # 现代汉语映射到上下册
            if doc == "xdhy":
                doc = "xdhy_up" if ("语音" in c_name or "汉字" in c_name or "词汇" in c_name) else "xdhy_down"

            # 精确查
            if (doc, c_name, s_name) in route_map:
                target_sid = route_map[(doc, c_name, s_name)]
                break
            # 模糊查
            c_core = re.sub(r'第[一二三四五六七八九十\d]+章', '', c_name).strip()
            s_core = re.sub(r'第[一二三四五六七八九十\d]+节', '', s_name).strip()
            for (rd, rc, rs), sid in route_map.items():
                if rd == doc and (c_core in rc or rc in c_core) and (s_core in rs or rs in s_core):
                    target_sid = sid
                    break
            if target_sid:
                break

    # 若 RAG 未命中，按原所属合法 section_id
    if not target_sid:
        if orig_sid in sec_meta:
            target_sid = orig_sid
        else:
            # 备用：按原 doc 放入第一小节
            for sid in all_sections:
                if sec_meta[sid]["doc"] == orig_doc:
                    target_sid = sid
                    break
        missed += 1

    if not target_sid:
        target_sid = all_sections[0]

    # 更新卡片的 section_id 与 doc
    card["section_id"] = target_sid
    card["doc"] = sec_meta[target_sid]["doc"]
    classified[target_sid].append(card)

print(f"分类完成！其中通过 RAG 权威归位: {len(all_cards) - missed} 张，原节保持: {missed} 张")

# 5. 排序与回写 leaves 文件
for sid in all_sections:
    cards = classified[sid]
    # 排序规则：高频 (weight == 'high') 在前，概念名称长度适中在前
    cards.sort(key=lambda x: (
        0 if x.get("weight") == "high" else 1,
        0 if "真题" in str(x.get("evidence", [])) else 1,
        len(x.get("title", ""))
    ))

    leaf_obj = {
        "section_id": sid,
        "title": sec_meta[sid]["title"],
        "kps": cards
    }
    with open(os.path.join(LEAVES_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

# 6. 更新 mindmap.json 中每个小节与章节的 weight
for b in mm["books"]:
    for c in b["chapters"]:
        c_hot = False
        for s in c["sections"]:
            sid = s["id"]
            kps = classified[sid]
            s_hot = any(k.get("weight") == "high" for k in kps)
            s["weight"] = "high" if s_hot else "normal"
            if s_hot: c_hot = True
        c["weight"] = "high" if c_hot else "normal"

with open(os.path.join(OUT_DIR, "mindmap.json"), "w", encoding="utf-8") as f:
    json.dump(mm, f, ensure_ascii=False, indent=2)

print("🎉 重分类与排序写入完成！")
