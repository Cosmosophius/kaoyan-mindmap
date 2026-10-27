#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 4 — 真题权重注入（纯代码，无 LLM）
输入: out/kp_clean.jsonl, kaoyan_pwa/data/{exam_papers,all_subjects_data}.json
输出: out/mindmap.json (骨架, 首屏加载) + out/leaves/<section_id>.json (按需加载)

权重三档（SPEC §2 Stage4）:
  high   = 真题命中 >=1 次
  mid    = 教材标高频但真题未命中
  normal = 其余
"""
import json, os, re, sys, unicodedata
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
PWA = os.path.normpath(os.path.join(BASE, "..", "kaoyan_pwa", "data"))

def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r'\s+', '', s).lower()

def strip_punct(s):
    return re.sub(r'[^一-鿿0-9a-z]', '', norm(s))

def bigrams(s):
    s = strip_punct(s)
    return {s[i:i+2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())

def load_json(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default

def collect_exam_index():
    """从真题与考点库收集: 标题 -> 证据列表"""
    idx = defaultdict(list)

    # 1) 结构化考点库: 自带 frequency / exam_years / importance_score
    a = load_json(os.path.join(PWA, "all_subjects_data.json"), {})
    for sub, qs in (a.get("questions") or {}).items():
        for q in qs:
            t = q.get("stem") or ""
            if not t:
                continue
            yrs = q.get("exam_years") or []
            freq = q.get("frequency") or ""
            if yrs:
                for y in yrs:
                    idx[strip_punct(t)].append(f"{y} 真题")
            elif freq == "高频":
                idx[strip_punct(t)].append("教材高频")
    # 2) 真题卷: 题干文本
    e = load_json(os.path.join(PWA, "exam_papers.json"), {})
    for p in (e.get("papers") or []):
        year, code = p.get("year", ""), p.get("code", "")
        for sec in p.get("sections") or []:
            for q in sec.get("questions") or []:
                txt = q.get("text") or ""
                if len(txt) < 4:
                    continue
                idx[strip_punct(txt)].append(f"{year} {code} {sec.get('name','')[:8]}")
    return idx

def match_weight(title, idx, bg_index):
    """三级匹配: 精确 -> 去标点 -> bigram 覆盖率 >=0.8"""
    k = strip_punct(title)
    if not k:
        return "normal", []
    if k in idx:
        return "high", idx[k][:4]
    bg = bigrams(title)
    if not bg:
        return "normal", []
    best, best_cov = None, 0.0
    for cand_bg, ev in bg_index:
        if not cand_bg:
            continue
        cov = len(bg & cand_bg) / len(bg)
        if cov > best_cov:
            best_cov, best = cov, ev
    if best_cov >= 0.8 and best:
        return "high", best[:4]
    return "normal", []

def build_bigram_index(idx):
    out = []
    for k, ev in idx.items():
        bg = {k[i:i+2] for i in range(len(k) - 1)} if len(k) > 1 else {k}
        out.append((bg, ev))
    return out

def main():
    clean_p = os.path.join(OUT, "kp_clean.jsonl")
    if not os.path.exists(clean_p):
        print("⚠️ 缺少 kp_clean.jsonl，先跑 Stage 3（需 Stage 2 产出）")
        print("   本脚本语法自检通过 ✅")
        return

    sk = load_json(os.path.join(OUT, "skeleton.json"))
    if not sk:
        print("❌ 缺少 skeleton.json"); sys.exit(1)

    kps = [json.loads(l) for l in open(clean_p, encoding="utf-8")]
    print(f"读入知识点 {len(kps)} 条")
    idx = collect_exam_index()
    bg_index = build_bigram_index(idx)
    print(f"真题/高频索引 {len(idx)} 条")

    by_sec = defaultdict(list)
    for kp in kps:
        w, ev = match_weight(kp["title"], idx, bg_index)
        # 教材高频但真题未命中 -> mid
        if w == "normal" and "高频" in str(kp.get("freq", "")):
            w = "mid"
        kp["weight"] = w
        kp["evidence"] = ev
        by_sec[kp["section_id"]].append(kp)

    leaves_dir = os.path.join(OUT, "leaves")
    os.makedirs(leaves_dir, exist_ok=True)
    sec_weight = {}
    for sid, items in by_sec.items():
        ws = [k["weight"] for k in items]
        sec_weight[sid] = "high" if "high" in ws else ("mid" if "mid" in ws else "normal")
        items.sort(key=lambda x: ({"high":0,"mid":1,"normal":2}[x["weight"]], x["title"]))
        json.dump({"section_id": sid, "kps": items},
                  open(os.path.join(leaves_dir, f"{sid}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)

    # 骨架（不含 leaves 正文，控制体积）
    books_out = []
    for b in sk["books"]:
        chs = []
        for ch in b["chapters"]:
            secs, wsum = [], []
            for sec in ch["sections"]:
                sid = sec["section_id"]
                n = len(by_sec.get(sid, []))
                w = sec_weight.get(sid, "normal")
                wsum.append(w)
                secs.append({"id": sid, "title": sec["title"], "kp_count": n, "weight": w})
            cw = "high" if "high" in wsum else ("mid" if "mid" in wsum else "normal")
            chs.append({"id": ch["chapter_id"], "title": ch["title"],
                        "weight": cw, "sections": secs})
        books_out.append({"doc": b["doc"], "title": b["title"], "chapters": chs})

    mm = {"version": 1, "books": books_out}
    mp = os.path.join(OUT, "mindmap.json")
    json.dump(mm, open(mp, "w", encoding="utf-8"), ensure_ascii=False)
    size = os.path.getsize(mp) / 1024
    cnt = {"high": 0, "mid": 0, "normal": 0}
    for k in kps:
        cnt[k["weight"]] += 1
    print(f"\n✅ mindmap.json {size:.0f} KB (首屏) | leaves {len(by_sec)} 个")
    print(f"   权重分布: 高频 {cnt['high']} / 中频 {cnt['mid']} / 普通 {cnt['normal']}")
    print(f"   验收线: 首屏 <800KB -> {'通过' if size < 800 else '超标'}")

if __name__ == "__main__":
    main()
