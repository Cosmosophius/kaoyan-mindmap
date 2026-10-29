#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_xdhy_down_complete.py
彻底解决现代汉语下册卡片空缺、点击无内容的问题：
从 questions.json 中将《现代汉语通论（下）》全部 415 道高质量考研考点
精准、完整、饱满地注入到下册第四章（语法12节）与第五章（语用8节）共20个小节中！
"""

import json
import os
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")

# 1. 载入 questions.json
apk_path = "/data/user/0/cc.codroid/files/home/workspace/apk_inspect/assets/questions.json"
apk_data = json.load(open(apk_path, encoding="utf-8"))

down_qs = [q for q in apk_data["questions"] if q.get("book_name") == "现代汉语通论（下）"]
print(f"载入现汉下册考点总数: {len(down_qs)}")

def clean_t(s):
    if not s: return ""
    s = s.strip()
    s = re.sub(r'^(【名词解释】|名词解释：|名词解释)', '', s).strip()
    return re.sub(r'^[“"‘\'《](.*?)[”"’\'》]$', r'\1', s).strip()

def format_ev(q):
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
        else: ev.append("核心考点")
    return ev

# 2. 映射章节小节字典
sec_map = {
    # 第四章 语法
    ("第四章 语法", "第一节 现代汉语语法概述"): "xdhy_down-c01-s01",
    ("第四章 语法", "第二节 词类和功能分析法"): "xdhy_down-c01-s02",
    ("第四章 语法", "第三节 虚词的作用及其辨析"): "xdhy_down-c01-s03",
    ("第四章 语法", "第四节 短语与层次分析法"): "xdhy_down-c01-s04",
    ("第四章 语法", "第五节 句型系统"): "xdhy_down-c01-s05",
    ("第四章 语法", "第六节 句式系统"): "xdhy_down-c01-s06",
    ("第四章 语法", "第七节 句类系统"): "xdhy_down-c01-s07",
    ("第四章 语法", "第八节 句法结构中的语义分析"): "xdhy_down-c01-s08",
    ("第四章 语法", "第九节 歧义结构与框式结构"): "xdhy_down-c01-s09",
    ("第四章 语法", "第十节 认知解释与动态变化"): "xdhy_down-c01-s10",
    ("第四章 语法", "第十一节 复句类型"): "xdhy_down-c01-s11",
    ("第四章 语法", "第十二节 多重复句与紧缩复句"): "xdhy_down-c01-s12",

    # 第五章 语用
    ("第五章 语用", "第一节 现代汉语语用概述"): "xdhy_down-c02-s01",
    ("第五章 语用", "第二节 话语意义"): "xdhy_down-c02-s02",
    ("第五章 语用", "第三节 言语行为与会话原则"): "xdhy_down-c02-s03",
    ("第五章 语用", "第四节 话语结构"): "xdhy_down-c02-s04",
    ("第五章 语用", "第五节 语言要素的修辞"): "xdhy_down-c02-s05",
    ("第五章 语用", "第六节 语用效果与辞格"): "xdhy_down-c02-s06",
    ("第五章 语用", "第七节 语体的分类与功能"): "xdhy_down-c02-s07",
    ("第五章 语用", "第八节 病句的类型与修改"): "xdhy_down-c02-s08",
}

# 3. 分组并格式化卡片
grouped = defaultdict(list)
for q in down_qs:
    c = (q.get("chapter") or "").strip()
    s = (q.get("section") or "").strip()
    sid = sec_map.get((c, s))
    if not sid:
        # 模糊匹配
        for (mc, ms), target_sid in sec_map.items():
            if c in mc and s in ms:
                sid = target_sid; break

    if sid:
        t = clean_t(q.get("stem", ""))
        pts = q.get("answer_points") or []
        if isinstance(pts, str): pts = [pts]
        ans = q.get("answer") or ""
        if not pts and ans:
            pts = [st.strip() for st in re.split(r'[。；;\n]', ans) if len(st.strip()) >= 4][:5]

        quote = q.get("source_quote") or (ans[:160] if ans else "")
        is_hot = (q.get("frequency") == "高频") or (q.get("importance_score", 0) >= 40) or bool(q.get("exam_years"))

        card = {
            "section_id": sid,
            "doc": "xdhy_down",
            "title": t,
            "type": q.get("type") or "名词解释",
            "points": pts,
            "quote": quote,
            "weight": "high" if is_hot else "normal",
            "evidence": format_ev(q)
        }
        grouped[sid].append(card)

# 4. 写入每一个小节的 leaves 文件
sec_titles = {v: k[1] for k, v in sec_map.items()}

written_cards = 0
for sid, title in sec_titles.items():
    cards = grouped[sid]
    # 去重
    seen_t = set()
    unique_cards = []
    for c in cards:
        if c["title"] not in seen_t:
            seen_t.add(c["title"])
            unique_cards.append(c)

    unique_cards.sort(key=lambda x: (
        0 if x.get("weight") == "high" else 1,
        0 if "真题" in str(x.get("evidence", [])) else 1,
        len(x["title"])
    ))

    leaf_obj = {
        "section_id": sid,
        "title": title,
        "kps": unique_cards
    }
    with open(os.path.join(LEAVES_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

    written_cards += len(unique_cards)
    print(f"  写入 {sid} ({title}): {len(unique_cards)} 张卡片")

print(f"\n🎉 现汉下册 20 个小节已全部饱满注入！总计注入 {written_cards} 张极品考点卡片！")
