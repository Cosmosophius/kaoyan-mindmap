#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_from_rag.py
严格根据本地权威 RAG 题库（all_subjects_data.json + questions.json）
重建思维导图结构树 mindmap.json 与知识点叶子 leaves/*.json
彻底根治跨书盲目字符匹配导致的“语法概述里出现春节、对比分析”等严重错乱问题！
"""

import json
import os
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")
os.makedirs(LEAVES_DIR, exist_ok=True)

# 1. 载入 RAG 数据库
pwa_path = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_pwa/data/all_subjects_data.json"
apk_path = "/data/user/0/cc.codroid/files/home/workspace/apk_inspect/assets/questions.json"

pwa_data = json.load(open(pwa_path, encoding="utf-8"))
apk_data = json.load(open(apk_path, encoding="utf-8"))

def clean_title(t):
    return (t or "").strip()

def format_evidence(q):
    ev = []
    years = q.get("exam_years") or []
    if isinstance(years, list):
        for y in years:
            ev.append(f"{y} 真题")
    elif isinstance(years, str) and years:
        ev.append(f"{years} 真题")
    src = q.get("source") or ""
    if "真题" in src:
        m = re.search(r'(20\d\d)', src)
        if m and f"{m.group(1)} 真题" not in ev:
            ev.append(f"{m.group(1)} 真题")
    if not ev:
        if q.get("frequency") == "高频":
            ev.append("教材高频")
        else:
            ev.append("核心考点")
    return ev

def convert_kp(q):
    pts = q.get("answer_points") or []
    if isinstance(pts, str):
        pts = [pts]
    ans = q.get("answer") or ""
    if not pts and ans:
        # 分句作为 points
        pts = [s.strip() for s in re.split(r'[。；;\n]', ans) if len(s.strip()) >= 4][:5]

    quote = q.get("source_quote") or ""
    if not quote and ans:
        quote = ans[:160]

    is_hot = (q.get("frequency") == "高频") or (q.get("importance_score", 0) >= 40) or bool(q.get("exam_years"))

    return {
        "title": clean_title(q.get("stem")),
        "type": q.get("type") or "名词解释",
        "points": pts,
        "quote": quote,
        "weight": "high" if is_hot else "normal",
        "evidence": format_evidence(q)
    }

# 2. 建立章节与小节题库索引
# PWA 题目
pwa_questions = pwa_data.get("questions", {})

# APK 题目（补充入门和真题等）
apk_questions = apk_data.get("questions", [])

# 构建书籍列表
books = []

# ========== 1. 中国文化要略（第四版） ==========
print("构建: 中国文化要略（第四版）...")
culture_sub = next(s for s in pwa_data["subjects"] if s["id"] == "culture")
culture_qs = pwa_questions.get("culture", [])
# 按章与小节分组
cult_grouped = defaultdict(lambda: defaultdict(list))
for q in culture_qs:
    c_name = clean_title(q.get("chapter"))
    s_name = clean_title(q.get("section"))
    cult_grouped[c_name][s_name].append(convert_kp(q))

cult_chapters = []
for c_idx, c_info in enumerate(culture_sub["chapters"], start=1):
    c_title = clean_title(c_info["chapter"])
    c_id = f"culture-c{c_idx:02d}"
    secs = []

    # 按照定义的 sections 顺序
    sec_names = list(c_info["sections"].keys())
    # 检查是否有未在定义中但在题目中出现的小节
    for s_name in cult_grouped[c_title].keys():
        if s_name not in sec_names:
            sec_names.append(s_name)

    for s_idx, s_title in enumerate(sec_names, start=1):
        s_id = f"{c_id}-s{s_idx:02d}"
        kps = cult_grouped[c_title].get(s_title, [])
        # 写 leaf
        leaf_obj = {
            "section_id": s_id,
            "title": s_title,
            "kps": kps
        }
        with open(os.path.join(LEAVES_DIR, f"{s_id}.json"), "w", encoding="utf-8") as f:
            json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

        has_hot = any(k["weight"] == "high" for k in kps)
        secs.append({
            "id": s_id,
            "title": s_title,
            "weight": "high" if has_hot else "normal"
        })

    has_hot_chap = any(s["weight"] == "high" for s in secs)
    cult_chapters.append({
        "id": c_id,
        "title": c_title,
        "weight": "high" if has_hot_chap else "normal",
        "sections": secs
    })

books.append({
    "doc": "culture",
    "title": "中国文化要略（第四版）",
    "chapters": cult_chapters
})

# ========== 2. 对外汉语教育学引论 ==========
print("构建: 对外汉语教育学引论...")
yinlun_sub = next(s for s in pwa_data["subjects"] if s["id"] == "yinlun")
yinlun_qs = pwa_questions.get("yinlun", [])
yinlun_grouped = defaultdict(lambda: defaultdict(list))
for q in yinlun_qs:
    c_name = clean_title(q.get("chapter"))
    s_name = clean_title(q.get("section"))
    yinlun_grouped[c_name][s_name].append(convert_kp(q))

yinlun_chapters = []
for c_idx, c_info in enumerate(yinlun_sub["chapters"], start=1):
    c_title = clean_title(c_info["chapter"])
    c_id = f"yinlun-c{c_idx:02d}"
    secs = []
    sec_names = list(c_info["sections"].keys())
    for s_name in yinlun_grouped[c_title].keys():
        if s_name not in sec_names:
            sec_names.append(s_name)

    for s_idx, s_title in enumerate(sec_names, start=1):
        s_id = f"{c_id}-s{s_idx:02d}"
        kps = yinlun_grouped[c_title].get(s_title, [])
        leaf_obj = {
            "section_id": s_id,
            "title": s_title,
            "kps": kps
        }
        with open(os.path.join(LEAVES_DIR, f"{s_id}.json"), "w", encoding="utf-8") as f:
            json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

        has_hot = any(k["weight"] == "high" for k in kps)
        secs.append({
            "id": s_id,
            "title": s_title,
            "weight": "high" if has_hot else "normal"
        })

    has_hot_chap = any(s["weight"] == "high" for s in secs)
    yinlun_chapters.append({
        "id": c_id,
        "title": c_title,
        "weight": "high" if has_hot_chap else "normal",
        "sections": secs
    })

books.append({
    "doc": "yinlun",
    "title": "对外汉语教育学引论",
    "chapters": yinlun_chapters
})

# ========== 3. 现代汉语通论（上册与下册） ==========
print("构建: 现代汉语通论（上册与下册）...")
xdhy_sub = next(s for s in pwa_data["subjects"] if s["id"] == "xdhy")
xdhy_qs = pwa_questions.get("xdhy", [])
xdhy_grouped = defaultdict(lambda: defaultdict(list))
for q in xdhy_qs:
    c_name = clean_title(q.get("chapter"))
    s_name = clean_title(q.get("section"))
    xdhy_grouped[c_name][s_name].append(convert_kp(q))

# 上册包含: 第一章语音、第二章汉字、第三章词汇
up_chapters_def = xdhy_sub["chapters"][:3]
# 下册包含: 第四章语法、第五章语用
down_chapters_def = xdhy_sub["chapters"][3:]

# 上册
xdhy_up_chaps = []
for c_idx, c_info in enumerate(up_chapters_def, start=1):
    c_title = clean_title(c_info["chapter"])
    c_id = f"xdhy_up-c{c_idx:02d}"
    secs = []
    sec_names = list(c_info["sections"].keys())
    for s_name in xdhy_grouped[c_title].keys():
        if s_name not in sec_names:
            sec_names.append(s_name)
    for s_idx, s_title in enumerate(sec_names, start=1):
        s_id = f"{c_id}-s{s_idx:02d}"
        kps = xdhy_grouped[c_title].get(s_title, [])
        leaf_obj = {"section_id": s_id, "title": s_title, "kps": kps}
        with open(os.path.join(LEAVES_DIR, f"{s_id}.json"), "w", encoding="utf-8") as f:
            json.dump(leaf_obj, f, ensure_ascii=False, indent=2)
        has_hot = any(k["weight"] == "high" for k in kps)
        secs.append({"id": s_id, "title": s_title, "weight": "high" if has_hot else "normal"})
    has_hot_chap = any(s["weight"] == "high" for s in secs)
    xdhy_up_chaps.append({"id": c_id, "title": c_title, "weight": "high" if has_hot_chap else "normal", "sections": secs})

books.append({
    "doc": "xdhy_up",
    "title": "现代汉语通论（上册）",
    "chapters": xdhy_up_chaps
})

# 下册
xdhy_down_chaps = []
for c_idx, c_info in enumerate(down_chapters_def, start=1):
    c_title = clean_title(c_info["chapter"])
    c_id = f"xdhy_down-c{c_idx:02d}"
    secs = []
    sec_names = list(c_info["sections"].keys())
    for s_name in xdhy_grouped[c_title].keys():
        if s_name not in sec_names:
            sec_names.append(s_name)
    for s_idx, s_title in enumerate(sec_names, start=1):
        s_id = f"{c_id}-s{s_idx:02d}"
        kps = xdhy_grouped[c_title].get(s_title, [])
        leaf_obj = {"section_id": s_id, "title": s_title, "kps": kps}
        with open(os.path.join(LEAVES_DIR, f"{s_id}.json"), "w", encoding="utf-8") as f:
            json.dump(leaf_obj, f, ensure_ascii=False, indent=2)
        has_hot = any(k["weight"] == "high" for k in kps)
        secs.append({"id": s_id, "title": s_title, "weight": "high" if has_hot else "normal"})
    has_hot_chap = any(s["weight"] == "high" for s in secs)
    xdhy_down_chaps.append({"id": c_id, "title": c_title, "weight": "high" if has_hot_chap else "normal", "sections": secs})

books.append({
    "doc": "xdhy_down",
    "title": "现代汉语通论（下册）",
    "chapters": xdhy_down_chaps
})

# ========== 4. 对外汉语教学入门（第3版） ==========
print("构建: 对外汉语教学入门（第3版）...")
rumen_qs = [q for q in apk_questions if q.get("book_name") == "对外汉语教学入门"]
rumen_grouped = defaultdict(lambda: defaultdict(list))
for q in rumen_qs:
    c_name = clean_title(q.get("chapter"))
    s_name = clean_title(q.get("section"))
    rumen_grouped[c_name][s_name].append(convert_kp(q))

# 章节按数字排序
CN_NUM = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10,
          '十一':11, '十二':12, '十三':13, '十四':14, '十五':15, '十六':16, '十七':17, '十八':18, '十九':19, '二十':20}

def get_chap_num(c_name):
    m = re.match(r'^第([一二三四五六七八九十]+)章', c_name)
    return CN_NUM.get(m.group(1), 99) if m else 99

def get_sec_num(s_name):
    m = re.match(r'^第([一二三四五六七八九十]+)节', s_name)
    return CN_NUM.get(m.group(1), 99) if m else 99

sorted_rumen_chaps = sorted(rumen_grouped.keys(), key=get_chap_num)
rumen_chapters = []
for c_idx, c_title in enumerate(sorted_rumen_chaps, start=1):
    c_id = f"rumen-c{c_idx:02d}"
    secs = []
    sorted_secs = sorted(rumen_grouped[c_title].keys(), key=get_sec_num)
    for s_idx, s_title in enumerate(sorted_secs, start=1):
        s_id = f"{c_id}-s{s_idx:02d}"
        kps = rumen_grouped[c_title][s_title]
        leaf_obj = {"section_id": s_id, "title": s_title, "kps": kps}
        with open(os.path.join(LEAVES_DIR, f"{s_id}.json"), "w", encoding="utf-8") as f:
            json.dump(leaf_obj, f, ensure_ascii=False, indent=2)
        has_hot = any(k["weight"] == "high" for k in kps)
        secs.append({"id": s_id, "title": s_title, "weight": "high" if has_hot else "normal"})
    has_hot_chap = any(s["weight"] == "high" for s in secs)
    rumen_chapters.append({"id": c_id, "title": c_title, "weight": "high" if has_hot_chap else "normal", "sections": secs})

books.append({
    "doc": "rumen",
    "title": "对外汉语教学入门（第3版）",
    "chapters": rumen_chapters
})

# ========== 5. 历年真题与汇总资料 ==========
# 从原 mindmap.json 保留原有的真题结构与叶子
old_mm = json.load(open(os.path.join(OUT_DIR, "mindmap.json"), encoding="utf-8"))
for old_b in old_mm["books"]:
    if old_b["doc"] in ["zhenti_10_23", "zhenti_2026", "zhenti_24", "zhenti_25", "ziliao"]:
        print(f"保留真题/资料: {old_b['title']} (doc: {old_b['doc']})...")
        books.append(old_b)

# 写入新的 mindmap.json
new_mm = {"books": books}
with open(os.path.join(OUT_DIR, "mindmap.json"), "w", encoding="utf-8") as f:
    json.dump(new_mm, f, ensure_ascii=False, indent=2)

print("\n🎉 重构完成！全书总架构：")
for b in books:
    total_secs = sum(len(c["sections"]) for c in b["chapters"])
    print(f"- {b['title']} (doc: {b['doc']}): {len(b['chapters'])} 章, {total_secs} 节")
