#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3 — 校验 + 防幻觉（纯代码，无 LLM）
输入: out/skeleton.json, out/paragraphs/<doc>.jsonl, out/kp_raw/<section_id>.json
输出: out/kp_clean.jsonl, out/rejected.jsonl, out/stage3_report.txt

核心: Gemini 输出的 quote 必须是原文逐字子串，否则判定为幻觉并拒绝。
不依赖 jsonschema，内置轻量校验。
"""
import json, os, re, sys, unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
TYPES = {"名词解释","简答题","论述题","填空题","判断题","选择题","分析题","其他"}

def norm_ws(s):
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r'\s+', '', s)

def load_skeleton():
    p = os.path.join(OUT, "skeleton.json")
    if not os.path.exists(p):
        print("❌ 缺少 skeleton.json，先跑 stage1"); sys.exit(1)
    return json.load(open(p, encoding="utf-8"))

def load_paras(doc_id):
    p = os.path.join(OUT, "paragraphs", f"{doc_id}.jsonl")
    d = {}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            d[o["para_id"]] = o["text"]
    return d

def check_kp(kp, para_range, paras):
    """返回 (ok, reason)。逐条执行 SPEC §3 的校验。"""
    if not isinstance(kp, dict):
        return False, "非对象"
    for f in ("title", "type", "points", "quote", "para_id", "confidence"):
        if f not in kp:
            return False, f"缺字段 {f}"
    if not (2 <= len(str(kp["title"])) <= 30):
        return False, "title 长度越界"
    if kp["type"] not in TYPES:
        return False, f"type 非法: {kp['type']}"
    pts = kp["points"]
    if not isinstance(pts, list) or not (1 <= len(pts) <= 8):
        return False, "points 数量越界"
    pid = kp["para_id"]
    if not isinstance(pid, int) or not (para_range[0] <= pid <= para_range[1]):
        return False, f"para_id {pid} 不在本节范围 {para_range}"
    # 防幻觉: quote 必须是本节原文子串
    seg = norm_ws("".join(paras.get(i, "") for i in range(para_range[0], para_range[1] + 1)))
    q = norm_ws(kp["quote"])
    if len(q) < 5:
        return False, "quote 过短"
    if q not in seg:
        return False, "quote 非原文子串（疑似改写/幻觉）"
    return True, ""

def main():
    sk = load_skeleton()
    raw_dir = os.path.join(OUT, "kp_raw")
    if not os.path.isdir(raw_dir):
        print(f"⚠️ 尚无 {raw_dir}，Stage 2 (Gemini) 未运行。")
        print("   本脚本将在 kp_raw 存在后执行校验。语法自检通过 ✅")
        return
    files = sorted(f for f in os.listdir(raw_dir) if f.endswith(".json"))
    if not files:
        print("⚠️ kp_raw 为空，等待 Stage 2 产出。"); return

    # section 索引
    sec_idx, doc_of = {}, {}
    for b in sk["books"]:
        for ch in b["chapters"]:
            for sec in ch["sections"]:
                sec_idx[sec["section_id"]] = tuple(sec["para_range"])
                doc_of[sec["section_id"]] = b["doc"]

    para_cache, clean, rejected, stats = {}, [], [], []
    for f in files:
        sid = f[:-5]
        if sid not in sec_idx:
            rejected.append({"section_id": sid, "reason": "section_id 不在 skeleton"})
            continue
        doc = doc_of[sid]
        if doc not in para_cache:
            para_cache[doc] = load_paras(doc)
        paras = para_cache[doc]
        rng = sec_idx[sid]
        try:
            data = json.load(open(os.path.join(raw_dir, f), encoding="utf-8"))
        except Exception as e:
            rejected.append({"section_id": sid, "reason": f"JSON 解析失败: {e}"})
            continue
        kps = data.get("kps") or []
        seen, ok_n, rej_n = set(), 0, 0
        used_paras = set()
        for kp in kps:
            ok, reason = check_kp(kp, rng, paras)
            if ok:
                key = norm_ws(kp["title"])
                if key in seen:
                    rej_n += 1
                    rejected.append({"section_id": sid, "title": kp["title"], "reason": "重复"})
                    continue
                seen.add(key)
                used_paras.add(kp["para_id"])
                clean.append({"section_id": sid, "doc": doc, **kp})
                ok_n += 1
            else:
                rej_n += 1
                rejected.append({"section_id": sid,
                                 "title": kp.get("title", "?"), "reason": reason})
        total_paras = rng[1] - rng[0] + 1
        cov = len(used_paras) / total_paras if total_paras else 0
        stats.append((sid, ok_n, rej_n, cov))

    with open(os.path.join(OUT, "kp_clean.jsonl"), "w", encoding="utf-8") as fh:
        for kp in clean:
            fh.write(json.dumps(kp, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT, "rejected.jsonl"), "w", encoding="utf-8") as fh:
        for r in rejected:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    tot_ok = sum(s[1] for s in stats); tot_rej = sum(s[2] for s in stats)
    rate = tot_rej / max(tot_ok + tot_rej, 1)
    lines = [f"通过 {tot_ok} / 拒绝 {tot_rej} / 拒绝率 {rate:.1%}"]
    low = [s for s in stats if s[3] < 0.4]
    lines.append(f"覆盖率 <40% 的节: {len(low)} 个（可能漏抽，需复查）")
    for sid, ok, rj, cov in low[:20]:
        lines.append(f"  {sid}: 覆盖 {cov:.0%}")
    report = "\n".join(lines)
    open(os.path.join(OUT, "stage3_report.txt"), "w", encoding="utf-8").write(report)
    print(report)
    print(f"\n✅ 验收线: 拒绝率 <15% -> 当前 {rate:.1%} {'通过' if rate < 0.15 else '未通过'}")

if __name__ == "__main__":
    main()
