#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2 本地高质量知识点抽取与原文逐字锚定引擎
- 忠实提取 10 本教材各章节的核心概念、定义、分类、理论与真题考点
- 防幻觉铁律：quote 必须是原文段落截取的逐字子串（Verbatim Substring）
- 输出格式严格遵循 schema/kp.schema.json
- 产出写入 out/kp_raw/<section_id>.json
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
RAW = os.path.join(OUT, "kp_raw")
PWA = os.path.normpath(os.path.join(BASE, "..", "kaoyan_pwa", "data"))

VALID_TYPES = ["名词解释", "简答题", "论述题", "填空题", "判断题", "选择题", "分析题", "其他"]

def norm_ws(s):
    return re.sub(r'\s+', '', s or '')

def clean_watermark(t):
    t = re.sub(r'获取更多资料\s*汉硕[^\n]*?cn\)?', '', t, flags=re.I)
    t = re.sub(r'汉硕网免费题库', '', t)
    return t.strip()

def split_sentences(text):
    """将文本切分为句子，保留标点"""
    sents = re.split(r'([。！？；;\n]+)', text)
    res = []
    for i in range(0, len(sents) - 1, 2):
        s = (sents[i] + sents[i+1]).strip()
        if len(s) >= 8:
            res.append(s)
    if len(sents) % 2 == 1 and len(sents[-1].strip()) >= 8:
        res.append(sents[-1].strip())
    return res

def load_all_paras():
    """预加载全部教材段落"""
    print("⏳ 正在预加载教材段落数据...")
    paras_by_doc = {}
    pdir = os.path.join(OUT, "paragraphs")
    for fname in os.listdir(pdir):
        if fname.endswith(".jsonl"):
            doc_id = fname[:-6]
            paras = {}
            for line in open(os.path.join(pdir, fname), encoding="utf-8"):
                d = json.loads(line)
                paras[d["para_id"]] = d["text"]
            paras_by_doc[doc_id] = paras
    print(f"✅ 已加载 {len(paras_by_doc)} 本文档段落")
    return paras_by_doc

def load_exam_questions():
    """加载题库中的全部考点"""
    print("⏳ 正在加载历年真题与考点库...")
    qpath = os.path.join(PWA, "all_subjects_data.json")
    if not os.path.exists(qpath):
        print("⚠️ 未找到 all_subjects_data.json，仅使用教材段落挖掘")
        return []
    try:
        data = json.load(open(qpath, encoding="utf-8"))
        all_qs = []
        for sub, qs in data.get("questions", {}).items():
            for q in qs:
                stem = q.get("stem", "").strip()
                if not stem or len(stem) < 2 or len(stem) > 30:
                    continue
                qtype = q.get("type", "名词解释")
                if qtype not in VALID_TYPES:
                    qtype = "名词解释"
                pts = q.get("answer_points") or [q.get("answer", "")]
                pts = [p.strip() for p in pts if p.strip()]
                if not pts:
                    pts = [stem]
                all_qs.append({
                    "stem": stem,
                    "type": qtype,
                    "points": pts[:6],
                    "answer": q.get("answer", ""),
                    "freq": q.get("frequency", ""),
                    "years": q.get("exam_years", []),
                    "sub": sub
                })
        print(f"✅ 已加载 {len(all_qs)} 道真题考点")
        return all_qs
    except Exception as e:
        print(f"⚠️ 读取题库失败: {e}")
        return []

def extract_section_kps(sec, doc_id, paras, exam_qs):
    sid = sec["section_id"]
    p_start, p_end = sec["para_range"]
    sec_title = sec["title"]

    # 收集本节有效段落
    sec_paras = []
    for pid in range(p_start, p_end + 1):
        if pid in paras:
            raw = paras[pid]
            cleaned = clean_watermark(raw)
            if len(cleaned) >= 10:
                sec_paras.append((pid, raw, cleaned))

    if not sec_paras:
        return []

    # 构造全节拼接文本（用于验证子串）
    full_seg = norm_ws("".join(paras.get(i, "") for i in range(p_start, p_end + 1)))

    kps = []
    seen_titles = set()

    # 1. 优先匹配历年真题考点
    for eq in exam_qs:
        stem = eq["stem"]
        clean_stem = re.sub(r'[^一-鿿0-9A-Za-z]', '', stem)
        if len(clean_stem) < 2 or clean_stem in seen_titles:
            continue

        # 在本节段落中寻找包含 stem 的段落
        matched_pid, matched_quote = None, None
        for pid, raw, cleaned in sec_paras:
            if clean_stem in re.sub(r'[^一-鿿0-9A-Za-z]', '', cleaned):
                # 从 raw 段落中直接切出包含 stem 的原句子，确保为 raw 的真实子串
                sents = split_sentences(cleaned)
                for s in sents:
                    if clean_stem in re.sub(r'[^一-鿿0-9A-Za-z]', '', s):
                        # 必须在 raw 原文中能原样找到
                        if s in raw and len(s) >= 12 and len(s) <= 300:
                            matched_pid = pid
                            matched_quote = s
                            break
                if not matched_quote and len(cleaned) >= 15:
                    # 如果单句没切准，直接从 raw 中截取 15~150 字
                    idx = raw.find(stem)
                    if idx != -1:
                        q_start = max(0, idx - 10)
                        q_end = min(len(raw), idx + len(stem) + 90)
                        sub = raw[q_start:q_end].strip()
                        if len(sub) >= 15:
                            matched_pid = pid
                            matched_quote = sub
                            break
                if matched_quote:
                    break

        if matched_pid and matched_quote and norm_ws(matched_quote) in full_seg:
            pts = eq["points"]
            # 格式清洗 points
            valid_pts = []
            for p in pts:
                p_clean = re.sub(r'\s+', ' ', p).strip()[:180]
                if len(p_clean) >= 2:
                    valid_pts.append(p_clean)
            if not valid_pts:
                valid_pts = [matched_quote[:150]]

            kps.append({
                "title": stem[:30],
                "type": eq["type"],
                "points": valid_pts[:6],
                "quote": matched_quote[:350],
                "para_id": matched_pid,
                "confidence": 0.95
            })
            seen_titles.add(clean_stem)

    # 2. 深度挖掘教材本节核心概念（补充未在题库或未命中的知识点）
    if len(kps) < 8:
        for pid, raw, cleaned in sec_paras:
            if len(kps) >= 25:
                break
            # 寻找定义、特征、核心条目模式
            patterns = [
                r'([“"《]([^\s"”》]{2,20})[”"》])(?:是指|是|指|包括|分为|定义为)',
                r'([一二三四五六七八九十\d]+[、.．])\s*([^\s。，；：]{2,20})[：:—\-]',
                r'^(?:所谓|关于)?([^\s。，；：]{2,15})(?:是指|就是|包含|由.*组成)',
            ]
            for pat in patterns:
                m = re.search(pat, cleaned)
                if m:
                    cand_title = m.group(len(m.groups())).strip()
                    cand_title = re.sub(r'[^一-鿿0-9A-Za-z]', '', cand_title)
                    if not (2 <= len(cand_title) <= 25) or cand_title in seen_titles:
                        continue
                    if cand_title in ["第一", "第二", "第三", "例如", "总之", "因此", "此外"]:
                        continue

                    # 截取该段中包含该定义的完整原句作为 quote
                    sents = split_sentences(cleaned)
                    target_quote = None
                    for s in sents:
                        if cand_title in s and s in raw and 15 <= len(s) <= 350:
                            target_quote = s
                            break
                    if not target_quote:
                        idx = raw.find(cand_title)
                        if idx != -1:
                            sub = raw[max(0, idx - 10):min(len(raw), idx + 120)].strip()
                            if len(sub) >= 15:
                                target_quote = sub

                    if target_quote and norm_ws(target_quote) in full_seg:
                        # 自动推导题型
                        if any(w in target_quote for w in ["是指", "定义", "概念", "称为"]):
                            ktype = "名词解释"
                        elif any(w in target_quote for w in ["特点", "特征", "原则", "区别"]):
                            ktype = "简答题"
                        elif any(w in target_quote for w in ["分为", "包括", "主要有"]):
                            ktype = "分析题"
                        else:
                            ktype = "简答题"

                        kps.append({
                            "title": cand_title,
                            "type": ktype,
                            "points": [target_quote[:180]],
                            "quote": target_quote,
                            "para_id": pid,
                            "confidence": 0.88
                        })
                        seen_titles.add(cand_title)
                        break

    # 3. 兜底保护：若本节依然没有任何知识点，以小节核心段落提取首要考点
    if not kps and sec_paras:
        # 取本节前 3 段中最长且实质的一段
        cand = sorted(sec_paras[:5], key=lambda x: len(x[2]), reverse=True)[0]
        pid, raw, cleaned = cand
        clean_title = re.sub(r'^(第[一二三四五六七八九十\d]+[章节讲篇编]|导论|导言|附录|[一二三四五六七八九十\d]+[、.．])\s*', '', sec_title)
        clean_title = re.sub(r'\s+', '', clean_title)[:25] or "核心考点"

        # 从 raw 中提取开头 40~150 字
        q_len = min(150, max(25, len(raw) // 2))
        q = raw[:q_len].strip()
        while len(q) >= 10 and norm_ws(q) not in full_seg:
            q = q[:-5]

        if len(q) >= 10:
            kps.append({
                "title": clean_title,
                "type": "简答题",
                "points": [q[:180]],
                "quote": q,
                "para_id": pid,
                "confidence": 0.80
            })

    return kps

def main():
    sk = json.load(open(os.path.join(OUT, "skeleton.json"), encoding="utf-8"))
    paras_by_doc = load_all_paras()
    exam_qs = load_exam_questions()

    total_secs = sum(len(c["sections"]) for b in sk["books"] for c in b["chapters"])
    print(f"\n🚀 开始处理 {total_secs} 个小节知识点提取与段落锚定...")

    os.makedirs(RAW, exist_ok=True)
    count = 0
    total_kps = 0

    for b in sk["books"]:
        doc_id = b["doc"]
        paras = paras_by_doc.get(doc_id, {})
        for ch in b["chapters"]:
            for sec in ch["sections"]:
                sid = sec["section_id"]
                kps = extract_section_kps(sec, doc_id, paras, exam_qs)

                payload = {
                    "section_id": sid,
                    "kps": kps
                }

                out_path = os.path.join(RAW, f"{sid}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                count += 1
                total_kps += len(kps)
                if count % 20 == 0 or count == total_secs:
                    print(f"进度: {count:3d}/{total_secs} 小节已生成 | 累计知识点: {total_kps} 条")

    print(f"\n✅ 全部完成！共生成 {total_secs} 个小节文件，提取知识点 {total_kps} 条")

if __name__ == "__main__":
    main()
