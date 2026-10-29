#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fine_grained_distribute.py
1. 彻底过滤掉判断题、选择题、冗长案例分析题，只保留考生要背诵的书本核心概念（名词解释、概念定义、分类体系、理论要点）
2. 将卡片严格按最小粒度的小节标题与概念内涵进行精准分配：
   - 把字句/被字句/存现句 -> 句式系统
   - 复句/并列复句/转折复句 -> 复句类型
   - 多重复句/紧缩复句 -> 多重复句
   - 歧义 -> 歧义结构
   - 短语/的字结构 -> 短语与层次分析法
   - 词类/虚词 -> 词类与虚词
   - 春节/中秋/端午 -> 风俗习惯·岁时节日
   - 对比分析/中介语 -> 第二语言习得研究
   - 态度/动机 -> 学习者个体心理因素
3. 小节内按概念重要性与考频排序
"""

import json
import os
import glob
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")

# 1. 概念有效性清洗函数（严格过滤选择题、判断题、案例大题）
def is_valid_concept(title, points):
    t = title.strip()
    # 过滤选择题/判断题/案例题/问答题大题
    if re.search(r'^(判断|下列|请分析|请指出|指出|分析|病例|【案例】|用划线|试比较|简述.*[？?]|.*产生歧义的原因是|.*属于.*（\s*）)', t):
        return False
    if "（　）" in t or "（　　）" in t or "______" in t:
        return False
    if len(t) > 30 and not t.startswith("【名词解释】"):
        return False
    # 必须有干货 points
    if not points or len(points) == 0:
        return False
    return True

def clean_concept_title(t):
    t = t.strip()
    t = re.sub(r'^(【名词解释】|名词解释：|名词解释)', '', t).strip()
    t = re.sub(r'^[“"‘\'《](.*?)[”"’\'》]$', r'\1', t).strip()
    return t

# 2. 读取标准大纲
mm = json.load(open(os.path.join(OUT_DIR, "mindmap.json"), encoding="utf-8"))
all_sids = {}
doc_sec_map = defaultdict(list)

for b in mm["books"]:
    doc = b["doc"]
    for c in b["chapters"]:
        c_title = c["title"].strip()
        for s in c["sections"]:
            s_title = s["title"].strip()
            sid = s["id"]
            meta = {"sid": sid, "doc": doc, "chap": c_title, "sec": s_title}
            all_sids[sid] = meta
            doc_sec_map[doc].append(meta)

# 3. 收集所有原始概念卡片
all_cards = []
seen = set()

for lf in glob.glob(os.path.join(LEAVES_DIR, "*.json")):
    d = json.load(open(lf, encoding="utf-8"))
    for kp in d.get("kps", []):
        t = (kp.get("title") or "").strip()
        pts = kp.get("points") or []
        if not is_valid_concept(t, pts):
            continue
        ct = clean_concept_title(t)
        key = (ct, tuple(pts[:2]))
        if key not in seen:
            seen.add(key)
            kp["title"] = ct
            kp["type"] = "名词解释"
            all_cards.append(kp)

print(f"清洗并提炼出的纯书本概念背诵卡片总数: {len(all_cards)}")

# 4. 最小粒度小节精准分发规则
def match_best_section(card):
    t = card["title"]
    pts_str = " ".join(card.get("points", []))
    full_text = t + " " + pts_str

    # --- 文化要略细分 ---
    if any(k in t for k in ["春节", "除夕", "元宵", "端午", "中秋", "重阳", "清明", "七夕", "腊八", "冬至", "寒食", "节日"]):
        for s in doc_sec_map["culture"]:
            if "岁时节日" in s["sec"] or "风俗" in s["chap"]: return s["sid"]
    if any(k in t for k in ["婚", "丧", "礼仪", "冠礼", "笄礼"]):
        for s in doc_sec_map["culture"]:
            if "人生礼仪" in s["sec"] or "风俗" in s["chap"]: return s["sid"]
    if any(k in t for k in ["饮食", "茶", "酒", "生肖"]):
        for s in doc_sec_map["culture"]:
            if "生肖" in s["sec"] or "风俗" in s["chap"]: return s["sid"]
    if any(k in t for k in ["诗经", "楚辞", "赋", "乐府", "唐诗", "宋词", "元曲", "明清小说", "红楼梦", "三国", "水浒", "西游"]):
        for s in doc_sec_map["culture"]:
            if "古典文学" in s["chap"] or "文学" in s["sec"]: return s["sid"]
    if any(k in t for k in ["京剧", "昆曲", "书法", "国画", "音乐", "舞蹈"]):
        for s in doc_sec_map["culture"]:
            if "艺术" in s["chap"] or "艺术" in s["sec"]: return s["sid"]
    if any(k in t for k in ["儒家", "孔子", "孟子", "道家", "老子", "庄子", "法家", "墨家", "理学", "心学"]):
        for s in doc_sec_map["culture"]:
            if "学术思想" in s["chap"]: return s["sid"]
    if any(k in t for k in ["科举", "殿试", "会试", "乡试", "童生", "秀才", "举人", "进士", "状元"]):
        for s in doc_sec_map["culture"]:
            if "科举" in s["chap"]: return s["sid"]
    if any(k in t for k in ["佛教", "道教", "基督教", "伊斯兰教", "宗族", "祖先"]):
        for s in doc_sec_map["culture"]:
            if "宗教" in s["chap"]: return s["sid"]

    # --- 现代汉语语法细分 (xdhy_down) ---
    if any(k in t for k in ["把字句", "被字句", "存现句", "连动句", "兼语句", "句式"]):
        for s in doc_sec_map["xdhy_down"]:
            if "句式" in s["sec"]: return s["sid"]
    if any(k in t for k in ["多重复句", "紧缩复句"]):
        for s in doc_sec_map["xdhy_down"]:
            if "多重复句" in s["sec"]: return s["sid"]
    if any(k in t for k in ["并列复句", "递进复句", "转折复句", "因果复句", "条件复句", "让步复句", "假设复句", "复句", "单重复句"]):
        for s in doc_sec_map["xdhy_down"]:
            if "复句类型" in s["sec"] or "复句" in s["sec"]: return s["sid"]
    if any(k in t for k in ["歧义", "框式结构"]):
        for s in doc_sec_map["xdhy_down"]:
            if "歧义" in s["sec"]: return s["sid"]
    if any(k in t for k in ["短语", "的字结构", "所字结构", "介词短语", "层次分析"]):
        for s in doc_sec_map["xdhy_down"]:
            if "短语" in s["sec"]: return s["sid"]
    if any(k in t for k in ["单句", "主谓句", "非主谓句", "句型"]):
        for s in doc_sec_map["xdhy_down"]:
            if "句型" in s["sec"]: return s["sid"]
    if any(k in t for k in ["陈述句", "疑问句", "祈使句", "感叹句", "句类"]):
        for s in doc_sec_map["xdhy_down"]:
            if "句类" in s["sec"]: return s["sid"]
    if any(k in t for k in ["实词", "虚词", "副词", "介词", "连词", "助词", "叹词", "拟声词", "词类", "名词", "动词", "形容词", "区别词", "代词", "数词", "量词"]):
        for s in doc_sec_map["xdhy_down"]:
            if "虚词" in t and "虚词" in s["sec"]: return s["sid"]
            if "词类" in s["sec"]: return s["sid"]
    if any(k in t for k in ["语法", "传统语法", "描写语法", "形式语法", "生成语法"]):
        for s in doc_sec_map["xdhy_down"]:
            if "语法概述" in s["sec"]: return s["sid"]

    # --- 现代汉语词汇细分 (xdhy_up) ---
    if any(k in t for k in ["义项", "义素", "义位", "词义"]):
        for s in doc_sec_map["xdhy_up"]:
            if "词义构成" in s["sec"] or "词义" in s["sec"]: return s["sid"]
    if any(k in t for k in ["同音词", "同形词", "单义词", "多义词", "同义词", "反义词"]):
        for s in doc_sec_map["xdhy_up"]:
            if "分类系统" in s["sec"] or "词汇" in s["chap"]: return s["sid"]
    if any(k in t for k in ["成语", "惯用语", "歇后语", "谚语"]):
        for s in doc_sec_map["xdhy_up"]:
            if "熟语" in s["sec"]: return s["sid"]
    if any(k in t for k in ["单纯词", "合成词", "词根", "词缀", "重叠", "构词"]):
        for s in doc_sec_map["xdhy_up"]:
            if "构词法" in s["sec"]: return s["sid"]

    # --- 引论与入门细分 ---
    if any(k in t for k in ["对比分析", "偏误分析", "中介语", "习得过程"]):
        for s in doc_sec_map["yinlun"]:
            if "习得研究" in s["chap"] or "习得过程" in s["sec"]: return s["sid"]
    if any(k in t for k in ["态度", "动机", "焦虑", "认知方式", "个体因素", "学习策略"]):
        for s in doc_sec_map["yinlun"]:
            if "心理学基础" in s["chap"] or "个体" in s["sec"] or "心理" in s["sec"]: return s["sid"]
    if any(k in t for k in ["语法翻译法", "直接法", "听说法", "视听说", "交际法", "任务型", "暗示法", "默教法", "全身反应法"]):
        for s in doc_sec_map["yinlun"]:
            if "教学法主要流派" in s["chap"]: return s["sid"]
    if any(k in t for k in ["测试", "信度", "效度", "区分度", "难度", "水平测试", "成绩测试"]):
        for s in doc_sec_map["yinlun"]:
            if "教学理论与应用" in s["chap"]: return s["sid"]

    # 兜底：保留在其原始章节或对应书籍第一节
    orig_sid = card.get("section_id")
    if orig_sid in all_sids:
        return orig_sid
    orig_doc = card.get("doc", "culture")
    if orig_doc in doc_sec_map and doc_sec_map[orig_doc]:
        return doc_sec_map[orig_doc][0]["sid"]
    return list(all_sids.keys())[0]

# 5. 执行分发
distributed = defaultdict(list)
for card in all_cards:
    target_sid = match_best_section(card)
    card["section_id"] = target_sid
    card["doc"] = all_sids[target_sid]["doc"]
    distributed[target_sid].append(card)

# 6. 回写每一个 leaves 文件
for sid, meta in all_sids.items():
    cards = distributed[sid]
    # 优雅排序：高频在前，概念名称短小精悍在前
    cards.sort(key=lambda x: (
        0 if x.get("weight") == "high" else 1,
        0 if "真题" in str(x.get("evidence", [])) else 1,
        len(x.get("title", ""))
    ))
    leaf_obj = {
        "section_id": sid,
        "title": meta["sec"],
        "kps": cards
    }
    with open(os.path.join(LEAVES_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

# 7. 更新 mindmap.json
for b in mm["books"]:
    for c in b["chapters"]:
        c_hot = False
        for s in c["sections"]:
            sid = s["id"]
            kps = distributed[sid]
            s_hot = any(k.get("weight") == "high" for k in kps)
            s["weight"] = "high" if s_hot else "normal"
            if s_hot: c_hot = True
        c["weight"] = "high" if c_hot else "normal"

with open(os.path.join(OUT_DIR, "mindmap.json"), "w", encoding="utf-8") as f:
    json.dump(mm, f, ensure_ascii=False, indent=2)

print("🎉 最小粒度概念精准归类分发回写完毕！")
