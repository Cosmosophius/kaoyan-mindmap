#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pure_concept_mindmap.py
严格只提取书本的核心概念（名词解释、概念定义、分类体系、理论要点）
杜绝任何选择题、判断题、填空题或冗长大题！
严格按照本地 RAG 权威学科章节（Book -> Chapter -> Section）进行物理分发与排序！
"""

import json
import os
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")
os.makedirs(LEAVES_DIR, exist_ok=True)

# 1. 载入权威 RAG 数据源
pwa_data = json.load(open("/data/user/0/cc.codroid/files/home/workspace/kaoyan_pwa/data/all_subjects_data.json", encoding="utf-8"))
apk_data = json.load(open("/data/user/0/cc.codroid/files/home/workspace/apk_inspect/assets/questions.json", encoding="utf-8"))

def clean_concept_title(t):
    if not t: return ""
    t = t.strip()
    t = re.sub(r'^(【名词解释】|名词解释：|名词解释)', '', t).strip()
    t = re.sub(r'^[“"‘\'《](.*?)[”"’\'》]$', r'\1', t).strip()
    return t

def is_concept_question(q):
    t = q.get("type", "")
    stem = clean_concept_title(q.get("stem", ""))
    if not stem: return False
    # 彻底过滤问答题、判断题、选择题、案例分析题
    if re.search(r'(判断|下列|请分析|请指出|指出|分析|病例|【案例】|用划线|试比较|简述|如何|为什么|从.*角度|运用|结合|试述|在.*中|对于|根据|什么|解释|阅读课|初级阶段|中高级|教学法|教学有哪些|教学的原则|教学原则|教学方法|教学应注意|练习|次序|主张|？|\?|（|）|\(|\)|_____|____)', stem):
        return False
    if len(stem) > 20:
        return False
    # 必须有背诵要点
    pts = q.get("answer_points") or []
    ans = q.get("answer") or ""
    if not pts and not ans:
        return False
    return True

def format_evidence(q):
    ev = []
    years = q.get("exam_years") or []
    if isinstance(years, list):
        for y in years: ev.append(f"{y} 真题")
    elif isinstance(years, str) and years:
        ev.append(f"{years} 真题")
    src = q.get("source") or ""
    if "真题" in src:
        m = re.search(r'(20\d\d)', src)
        if m and f"{m.group(1)} 真题" not in ev:
            ev.append(f"{m.group(1)} 真题")
    if not ev:
        if q.get("frequency") == "高频": ev.append("教材高频")
        else: ev.append("核心概念")
    return ev

def make_concept_card(q, sid, doc):
    stem = clean_concept_title(q.get("stem", ""))
    pts = q.get("answer_points") or []
    if isinstance(pts, str): pts = [pts]
    ans = q.get("answer") or ""
    if not pts and ans:
        pts = [s.strip() for s in re.split(r'[。；;\n]', ans) if len(s.strip()) >= 4][:5]

    quote = q.get("source_quote") or ""
    if not quote and ans:
        quote = ans[:160]

    is_hot = (q.get("frequency") == "高频") or (q.get("importance_score", 0) >= 40) or bool(q.get("exam_years"))

    return {
        "section_id": sid,
        "doc": doc,
        "title": stem,
        "type": "名词解释",
        "points": pts,
        "quote": quote,
        "weight": "high" if is_hot else "normal",
        "evidence": format_evidence(q)
    }

# 2. 读取标准大纲
mm = json.load(open(os.path.join(OUT_DIR, "mindmap.json"), encoding="utf-8"))

# 3. 收集概念题
raw_concepts = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

# 从 PWA 收集
for sub_id, qs in pwa_data.get("questions", {}).items():
    for q in qs:
        if not is_concept_question(q): continue
        c_name = (q.get("chapter") or "").strip()
        s_name = (q.get("section") or "").strip()
        if sub_id == "culture":
            raw_concepts["culture"][c_name][s_name].append(q)
        elif sub_id == "yinlun":
            raw_concepts["yinlun"][c_name][s_name].append(q)
        elif sub_id == "xdhy":
            # 区分现汉上下册
            if any(k in c_name for k in ["语音", "汉字", "词汇"]):
                raw_concepts["xdhy_up"][c_name][s_name].append(q)
            else:
                raw_concepts["xdhy_down"][c_name][s_name].append(q)

# 从 APK 补充入门以及上下册
for q in apk_data.get("questions", []):
    if not is_concept_question(q): continue
    bname = q.get("book_name", "")
    c_name = (q.get("chapter") or "").strip()
    s_name = (q.get("section") or "").strip()
    if "入门" in bname:
        raw_concepts["rumen"][c_name][s_name].append(q)
    elif "现代汉语通论（上）" in bname:
        raw_concepts["xdhy_up"][c_name][s_name].append(q)
    elif "现代汉语通论（下）" in bname:
        raw_concepts["xdhy_down"][c_name][s_name].append(q)

# 4. 精准匹配到每个小节并写入
total_cards = 0
for b in mm["books"]:
    doc = b["doc"]
    book_pool = raw_concepts.get(doc, {})
    for c in b["chapters"]:
        c_title = c["title"].strip()
        c_core = re.sub(r'第[一二三四五六七八九十\d]+章', '', c_title).strip()
        # 寻找匹配的章池
        matched_cpool = {}
        for rc_name, s_map in book_pool.items():
            rc_core = re.sub(r'第[一二三四五六七八九十\d]+章', '', rc_name).strip()
            if rc_core and (rc_core in c_core or c_core in rc_core):
                matched_cpool.update(s_map)

        c_has_hot = False
        for s in c["sections"]:
            sid = s["id"]
            s_title = s["title"].strip()
            s_core = re.sub(r'第[一二三四五六七八九十\d]+节', '', s_title).strip()

            # 寻找该节对应的概念
            kps_raw = []
            for rs_name, q_list in matched_cpool.items():
                rs_core = re.sub(r'第[一二三四五六七八九十\d]+节', '', rs_name).strip()
                if rs_core and (rs_core in s_core or s_core in rs_core):
                    kps_raw.extend(q_list)

            # 去重
            seen_titles = set()
            cards = []
            for q in kps_raw:
                card = make_concept_card(q, sid, doc)
                if card["title"] not in seen_titles:
                    seen_titles.add(card["title"])
                    cards.append(card)

            # 排序：高频在前，有真题在前，标题短小精悍在前
            cards.sort(key=lambda x: (
                0 if x.get("weight") == "high" else 1,
                0 if "真题" in str(x.get("evidence", [])) else 1,
                len(x["title"])
            ))

            leaf_obj = {
                "section_id": sid,
                "title": s_title,
                "kps": cards
            }
            with open(os.path.join(LEAVES_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
                json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

            s_hot = any(k.get("weight") == "high" for k in cards)
            s["weight"] = "high" if s_hot else "normal"
            if s_hot: c_has_hot = True
            total_cards += len(cards)

        c["weight"] = "high" if c_has_hot else "normal"

with open(os.path.join(OUT_DIR, "mindmap.json"), "w", encoding="utf-8") as f:
    json.dump(mm, f, ensure_ascii=False, indent=2)

print(f"🎉 纯概念卡片重构完成！全书共生成 {total_cards} 张极品背诵概念卡片！")
