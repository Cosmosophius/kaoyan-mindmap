#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 0 — docx 提取（纯代码，无 LLM）
输入: /sdcard/Documents/RAG/*.docx
输出: out/paragraphs/<doc_id>.jsonl
para_id 一经生成不可变，后续所有回溯依赖它。
"""
import json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

SRC = "/sdcard/Documents/RAG"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "paragraphs")

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"}

# 文件名 -> doc_id（固定映射，勿改）
DOC_MAP = {
    "中国文化要略": "culture",
    "对外汉语教学入门": "rumen",
    "对外汉语教育学引论": "yinlun",
    "南师大汉硕10-23真题带答案": "zhenti_10_23",
    "现代汉语通论上册": "xdhy_up",
    "现代汉语通论下册": "xdhy_down",
    "夸克扫描王": "ziliao",
    "24南京师范大学": "zhenti_24",
    "2026年南京师范大学": "zhenti_2026",
    "25南京师范大学": "zhenti_25",
}

def doc_id_of(fname):
    for k, v in DOC_MAP.items():
        if fname.startswith(k):
            return v
    return re.sub(r'[^a-z0-9]+', '_', fname.lower())[:20]

def clean_text(s):
    s = s.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def heading_level(p):
    """从 pStyle / outlineLvl 判断标题层级"""
    ppr = p.find("w:pPr", NS)
    if ppr is None:
        return 0
    ps = ppr.find("w:pStyle", NS)
    if ps is not None:
        v = ps.get("{%s}val" % NS["w"]) or ""
        m = re.search(r'(?:Heading|heading|标题)\s*(\d)', v)
        if m:
            return int(m.group(1))
    ol = ppr.find("w:outlineLvl", NS)
    if ol is not None:
        try:
            return int(ol.get("{%s}val" % NS["w"])) + 1
        except (TypeError, ValueError):
            pass
    return 0

def own_text(p, parent):
    """只取属于本段落的 w:t，跳过嵌套在子段落里的，避免文本框导致重复计数"""
    parts = []
    for t in p.iter("{%s}t" % NS["w"]):
        a = parent.get(t)
        owner = p
        skip = False
        while a is not None:
            # mc:AlternateContent 的 Fallback 与 Choice 文本相同，只保留一份
            if a.tag == "{%s}Fallback" % NS["mc"]:
                skip = True
                break
            if a.tag == "{%s}p" % NS["w"]:
                owner = a
                break
            a = parent.get(a)
        if not skip and owner is p:
            parts.append(t.text or "")
    return "".join(parts)

def parse_docx(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)
    parent = {c: p for p in body.iter() for c in p}
    paras = []
    for p in body.iter("{%s}p" % NS["w"]):
        text = clean_text(own_text(p, parent))
        if not text:
            continue
        paras.append({"text": text, "level": heading_level(p)})
    return paras

def merge_broken_lines(paras):
    """行尾无标点且下一行非标题 -> 合并（修复 docx 断行）"""
    END = "。！？；：”」』）】…"
    HEAD = re.compile(rf'^第[一二三四五六七八九十百零〇两\d]+[章节]')
    out = []
    for cur in paras:
        if (out and cur["level"] == 0 and out[-1]["level"] == 0
                and out[-1]["text"] and out[-1]["text"][-1] not in END
                and not re.match(r'^[（(]?\d+[）).、]', cur["text"])
                and len(out[-1]["text"]) < 60
                and not HEAD.match(out[-1]["text"])):
            out[-1]["text"] += cur["text"]
        else:
            out.append(dict(cur))
    return out

def drop_repeated_headers(paras, min_repeat=5):
    """出现 >= min_repeat 次的短行视为页眉页脚"""
    from collections import Counter
    cnt = Counter(p["text"] for p in paras if len(p["text"]) < 30)
    bad = {t for t, c in cnt.items() if c >= min_repeat}
    return [p for p in paras if p["text"] not in bad]

def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".docx"))
    if not files:
        print(f"❌ {SRC} 下没有 docx"); sys.exit(1)
    summary = []
    for f in files:
        did = doc_id_of(f)
        try:
            paras = parse_docx(os.path.join(SRC, f))
        except Exception as e:
            print(f"❌ {f}: {e}"); continue
        paras = drop_repeated_headers(merge_broken_lines(paras))
        path = os.path.join(OUT, f"{did}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for i, p in enumerate(paras, 1):
                fh.write(json.dumps({
                    "doc": did, "para_id": i,
                    "style": f"Heading{p['level']}" if p["level"] else "Body",
                    "text": p["text"]
                }, ensure_ascii=False) + "\n")
        chars = sum(len(p["text"]) for p in paras)
        summary.append((did, f, len(paras), chars))
        print(f"✅ {did:14} {len(paras):>6} 段 {chars:>8} 字  <- {f[:40]}")

    total = sum(s[3] for s in summary)
    print(f"\n合计 {len(summary)} 个文件 / {sum(s[2] for s in summary)} 段 / {total} 字")
    # 与 SPEC §1 实测值比对（2,158,463 字，容差 3%）
    ref = 2158463
    dev = abs(total - ref) / ref * 100
    print(f"对照 SPEC 基准 {ref} 字：偏差 {dev:.1f}%  {'✅ 通过' if dev < 3 else '⚠️ 超 3%'}")

if __name__ == "__main__":
    main()
