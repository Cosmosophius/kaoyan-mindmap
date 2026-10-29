#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore_clean_3618.py
1. 完整载入 Git 892ffbb 版本中的全部 3618 张原版高质量考研背诵卡片，一张不漏！
2. 彻底清除新造的任何生硬段落拼凑卡片，不留任何杂质。
3. 仅对少数错配卡片进行学科与章节纠偏：
   - 语法概述中误塞的 春节 -> 文化要略节日；对比分析/态度 -> 引论习得；义项/同音词 -> 现汉词汇；的字结构 -> 现汉短语
   - 文化要略第一节中误塞的 态度 -> 引论心理；丝绸之路 -> 中外交流；四大发明 -> 科技成就
   - 其余卡片严格保留在原本所属章节
4. 输出严格保证：卡片总数不多不少，正好 3618 张！
"""

import json
import subprocess
import os
import re
from collections import defaultdict

BASE_DIR = "/data/user/0/cc.codroid/files/home/workspace/kaoyan_mindmap"
OUT_DIR = os.path.join(BASE_DIR, "out")
LEAVES_DIR = os.path.join(OUT_DIR, "leaves")
os.makedirs(LEAVES_DIR, exist_ok=True)

# 1. 载入规范标准大纲 mindmap.json
# 读取当前 mindmap.json (包含完整章节结构)
mm = json.load(open(os.path.join(OUT_DIR, "mindmap.json"), encoding="utf-8"))

# 建立快速查找表: (doc, c_core, s_core) -> sid
sec_table = {}
all_valid_sids = set()
doc_first_sec = {}

for b in mm["books"]:
    doc = b["doc"]
    for c in b["chapters"]:
        c_title = c["title"].strip()
        c_core = re.sub(r'第[一二三四五六七八九十\d]+章', '', c_title).strip()
        for s in c["sections"]:
            sid = s["id"]
            all_valid_sids.add(sid)
            s_title = s["title"].strip()
            s_core = re.sub(r'第[一二三四五六七八九十\d]+节', '', s_title).strip()
            sec_table[(doc, c_title, s_title)] = sid
            sec_table[(doc, c_core, s_core)] = sid
            if doc not in doc_first_sec:
                doc_first_sec[doc] = sid

# 2. 从 Git 892ffbb 完整提取全部 3618 张原版卡片
print("⏳ 从 Git 892ffbb 提取原始卡片...")
res = subprocess.run(["git", "ls-tree", "-r", "892ffbb", "out/leaves/"], stdout=subprocess.PIPE, text=True, cwd=BASE_DIR)
files = [line.split()[-1] for line in res.stdout.strip().splitlines() if line.endswith(".json")]

all_cards = []
for f in files:
    content = subprocess.run(["git", "show", f"892ffbb:{f}"], stdout=subprocess.PIPE, text=True, cwd=BASE_DIR).stdout
    d = json.loads(content)
    orig_sid = d.get("section_id") or f.split("/")[-1][:-5]
    for kp in d.get("kps", []):
        card = dict(kp)
        card["orig_sid"] = orig_sid
        all_cards.append(card)

print(f"✅ 成功提取原版卡片总数: {len(all_cards)} (目标: 3618)")
assert len(all_cards) == 3618, f"提取卡片数 {len(all_cards)} != 3618"

# 3. 精准纠偏路由逻辑 (只针对错配卡片)
def find_correct_sid(card):
    t = card.get("title", "").strip()
    orig_sid = card.get("orig_sid", "")
    orig_doc = card.get("doc") or orig_sid.split("-")[0]

    # 针对 xdhy_down-c01-s01 (原语法概述) 中错塞的卡片纠偏
    if orig_sid == "xdhy_down-c01-s01":
        if t in ["春节"]:
            return sec_table.get(("culture", "风俗习惯", "岁时节日")) or "culture-c16-s01"
        if t in ["对比分析"]:
            return sec_table.get(("yinlun", "第二语言习得研究", "第二语言习得过程研究")) or "yinlun-c06-s01"
        if t in ["态度", "语言能力"]:
            return sec_table.get(("yinlun", "第二语言习得研究", "学习者的个体因素")) or "yinlun-c06-s02"
        if t in ["普遍语法"]:
            return sec_table.get(("yinlun", "语言习得理论", "第二语言习得理论和假说")) or "yinlun-c05-s03"
        if t in ["语音", "音节"]:
            return sec_table.get(("xdhy_up", "语音", "现代汉语语音概述")) or "xdhy_up-c01-s01"
        if t in ["汉字"]:
            return sec_table.get(("xdhy_up", "汉字", "现代汉字概述")) or "xdhy_up-c02-s01"
        if t in ["语素", "构词法"]:
            return sec_table.get(("xdhy_up", "词汇", "构词法与造词法")) or "xdhy_up-c03-s02"
        if t in ["义项"]:
            return sec_table.get(("xdhy_up", "词汇", "词义构成")) or "xdhy_up-c03-s03"
        if t in ["同音词", "同形词"]:
            return sec_table.get(("xdhy_up", "词汇", "词汇的分类系统")) or "xdhy_up-c03-s05"
        if t in ["成语"]:
            return sec_table.get(("xdhy_up", "词汇", "词汇的熟语系统")) or "xdhy_up-c03-s07"
        if t in ["词汇"]:
            return sec_table.get(("xdhy_up", "词汇", "现代汉语词汇概述")) or "xdhy_up-c03-s01"
        if t in ["短语", "“的”字结构"]:
            return sec_table.get(("xdhy_down", "语法", "短语与层次分析法")) or "xdhy_down-c01-s04"
        if t in ["介词", "助词", "语气词"]:
            return sec_table.get(("xdhy_down", "语法", "虚词的作用及其辨析")) or "xdhy_down-c01-s03"
        if t in ["词类", "代词", "方位词", "区别词", "状态形容词", "能愿动词"]:
            return sec_table.get(("xdhy_down", "语法", "词类和功能分析法")) or "xdhy_down-c01-s02"
        # 其余留在语法概述: 语法、语法功能、描写语法、传统语法、功能、语言和言语
        return "xdhy_down-c01-s01"

    # 针对 culture-c01-s01 中错塞的卡片纠偏
    if orig_sid == "culture-c01-s01":
        if t in ["态度"]:
            return sec_table.get(("yinlun", "第二语言习得研究", "学习者的个体因素")) or "yinlun-c06-s02"
        if t in ["丝绸之路"]:
            return sec_table.get(("culture", "中外文化交流", "陆上与海上丝路")) or "culture-c17-s01"
        if t in ["四大发明"]:
            return sec_table.get(("culture", "科技成就", "造纸术与印刷术")) or "culture-c11-s01"
        return "culture-c01-s01"

    # 其他卡片：如果原始 sid 存在于当前标准大纲中，直接归入！
    if orig_sid in all_valid_sids:
        return orig_sid

    # 容错：按原 doc 放入该 doc 的第一节
    if orig_doc in doc_first_sec:
        return doc_first_sec[orig_doc]

    return list(all_valid_sids)[0]

# 4. 执行分类与归位
classified = defaultdict(list)
moved_count = 0

for card in all_cards:
    target_sid = find_correct_sid(card)
    if target_sid != card.get("orig_sid"):
        moved_count += 1
    card["section_id"] = target_sid
    card["doc"] = target_sid.split("-")[0]
    classified[target_sid].append(card)

print(f"✅ 分类归位完毕！成功对 {moved_count} 张错配卡片完成精准纠偏！")

# 5. 排序并写回 leaves 文件
written_cards = 0
for b in mm["books"]:
    doc = b["doc"]
    for c in b["chapters"]:
        c_has_hot = False
        for s in c["sections"]:
            sid = s["id"]
            kps = classified.get(sid, [])
            # 排序：高频在前，有真题在前，标题长度适中在前
            kps.sort(key=lambda x: (
                0 if x.get("weight") == "high" else 1,
                0 if "真题" in str(x.get("evidence", [])) else 1,
                len(x.get("title", ""))
            ))
            leaf_obj = {
                "section_id": sid,
                "title": s["title"],
                "kps": kps
            }
            with open(os.path.join(LEAVES_DIR, f"{sid}.json"), "w", encoding="utf-8") as f:
                json.dump(leaf_obj, f, ensure_ascii=False, indent=2)

            s_hot = any(k.get("weight") == "high" for k in kps)
            s["weight"] = "high" if s_hot else "normal"
            if s_hot: c_has_hot = True
            written_cards += len(kps)

        c["weight"] = "high" if c_has_hot else "normal"

# 6. 回写 mindmap.json
with open(os.path.join(OUT_DIR, "mindmap.json"), "w", encoding="utf-8") as f:
    json.dump(mm, f, ensure_ascii=False, indent=2)

print(f"\n🎉 写入完成！总计写入卡片数: {written_cards} 张 (与原版 3618 完全一致！)")
assert written_cards == 3618, f"最终写入卡片数 {written_cards} 不等于 3618！"
