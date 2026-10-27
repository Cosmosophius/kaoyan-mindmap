#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1.5 — 用 Gemini 补全章节树
用途: 正则识别不全的书（如 culture 6/18 章），交给 Gemini 读目录段还原。
产出: out/toc_override.json —— stage1_split.py 会自动优先读取。

子命令:
  prepare   生成 out/toc_requests/<doc>.json（不联网）
  run       调用 Gemini 并写 toc_override.json
  status    对比识别数与原书章数

用法:
  python3 pipeline/stage1_toc_run.py prepare
  export GEMINI_API_KEY=xxx
  python3 pipeline/stage1_toc_run.py run
  python3 pipeline/stage1_toc_run.py status
"""
import json, os, re, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
TREQ = os.path.join(OUT, "toc_requests")
OVERRIDE = os.path.join(OUT, "toc_override.json")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 原书应有章数（人工核定，用于判定是否需要补全）
EXPECT = {
    "culture": 18, "xdhy_up": 4, "xdhy_down": 2, "yinlun": 10,
    "rumen": 10, "zhenti_10_23": 1, "ziliao": 1,
    "zhenti_24": 1, "zhenti_25": 1, "zhenti_2026": 1,
}

TOC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["book", "chapters", "missing", "confidence"],
    "properties": {
        "book": {"type": "string"},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["no", "title", "sections"],
                "properties": {
                    "no": {"type": "integer", "minimum": 1},
                    "title": {"type": "string", "minLength": 2},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["no", "title"],
                            "properties": {
                                "no": {"type": "integer", "minimum": 1},
                                "title": {"type": "string", "minLength": 2},
                            },
                        },
                    },
                },
            },
        },
        "missing": {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

def load_skeleton():
    p = os.path.join(OUT, "skeleton.json")
    if not os.path.exists(p):
        print("❌ 缺少 skeleton.json，先跑 stage1_split.py"); sys.exit(1)
    return json.load(open(p, encoding="utf-8"))

def is_toc_line(t):
    """目录行特征: 含省略号引导符 或 '标题 / 页码'"""
    if not re.search(r'第[一二三四五六七八九十百零〇两\d]+[章节]', t):
        return False
    if len(t) > 400:
        return False
    return bool(re.search(r'[…⋯]{2,}', t) or re.search(r'/\s*\d{1,3}', t)
                or re.search(r'[（(]\s*\d{1,3}\s*[)）]\s*$', t))

def toc_paragraphs(doc_id, max_gap=3, limit=80):
    """只取【连续】的目录区块。
    实测: 正文里的页眉也形如 '第十五章第十五章精美器物'，散落全文，
          若全量扫描会把正文当目录喂给模型。故限定为首个目录段起的连续块。
    """
    p = os.path.join(OUT, "paragraphs", f"{doc_id}.jsonl")
    if not os.path.exists(p):
        return []
    rows = []
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        rows.append((d["para_id"], d["text"]))

    # 找第一处目录行
    first = None
    for i, (pid, t) in enumerate(rows):
        if is_toc_line(t):
            first = i
            break
    if first is None:
        return []

    picked, gap = [], 0
    for pid, t in rows[first:]:
        if is_toc_line(t):
            picked.append(f"[p{pid}] {t}")
            gap = 0
            if len(picked) >= limit:
                break
        else:
            gap += 1
            if gap > max_gap:          # 连续多段非目录 -> 目录区结束
                break
    return picked

def cmd_status():
    sk = load_skeleton()
    print(f"{'文档':<16}{'识别':>6}{'应有':>6}  状态")
    print("-" * 46)
    need = []
    for b in sk["books"]:
        doc = b["doc"]
        got = len(b["chapters"])
        exp = EXPECT.get(doc, 0)
        if exp <= 1:
            mark = "—"
        elif got >= exp:
            mark = "✅"
        else:
            mark = f"⚠️ 缺 {exp-got} 章"
            need.append(doc)
        print(f"{doc:<16}{got:>6}{exp:>6}  {mark}")
    print()
    if need:
        print(f"需补全: {', '.join(need)}")
        print("下一步: python3 pipeline/stage1_toc_run.py prepare")
    else:
        print("章节树全部达标 ✅")

def cmd_prepare():
    sk = load_skeleton()
    os.makedirs(TREQ, exist_ok=True)
    tpl = open(os.path.join(BASE, "prompts", "gemini_toc.md"), encoding="utf-8").read()
    n = 0
    for b in sk["books"]:
        doc = b["doc"]
        exp = EXPECT.get(doc, 0)
        if exp <= 1 or len(b["chapters"]) >= exp:
            continue
        paras = toc_paragraphs(doc)
        if not paras:
            print(f"⚠️ {doc}: 找不到目录段，跳过")
            continue
        body = (f"{tpl}\n\n---\n\n<book>{b['title']}</book>\n"
                f"<text>\n" + "\n".join(paras) + "\n</text>\n")
        payload = {
            "task": "restore_toc", "doc": doc, "book": b["title"],
            "expected_chapters": exp, "identified": len(b["chapters"]),
            "response_schema": TOC_SCHEMA,
            "system": "你是目录结构还原器。只输出符合 schema 的 JSON，禁止编造章节。",
            "input": body,
        }
        json.dump(payload, open(os.path.join(TREQ, f"{doc}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"✅ {doc}: 目录段 {len(paras)} 行 -> out/toc_requests/{doc}.json")
        n += 1
    print(f"\n共生成 {n} 个目录请求")

def call_gemini(model, key, payload, timeout=180):
    url = API.format(model=model)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"x-goog-api-key": key,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    parts = (data["candidates"][0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return json.loads(text.strip())

def cmd_run(model="gemini-2.5-flash", sleep=2.0):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("❌ 未设置 GEMINI_API_KEY"); sys.exit(1)
    if not os.path.isdir(TREQ):
        print("❌ 先跑 prepare"); sys.exit(1)
    files = sorted(f for f in os.listdir(TREQ) if f.endswith(".json"))
    if not files:
        print("没有待处理的目录请求"); return
    ov = {}
    if os.path.exists(OVERRIDE):
        ov = json.load(open(OVERRIDE, encoding="utf-8"))
    for f in files:
        d = json.load(open(os.path.join(TREQ, f), encoding="utf-8"))
        payload = {"contents": [{"parts": [{"text": d["input"]}]}],
                   "generationConfig": {"responseMimeType": "application/json",
                                        "responseSchema": d["response_schema"],
                                        "temperature": 0.1}}
        try:
            res = call_gemini(model, key, payload)
            chs = res.get("chapters") or []
            ov[d["doc"]] = [{"no": c["no"], "title": c["title"],
                             "sections": c.get("sections") or []} for c in chs]
            miss = res.get("missing") or []
            print(f"✅ {d['doc']}: 还原 {len(chs)} 章"
                  + (f" | 目录缺失章号 {miss}" if miss else "")
                  + f" | 置信 {res.get('confidence')}")
        except Exception as e:
            print(f"❌ {d['doc']}: {type(e).__name__}: {e}")
        time.sleep(sleep)
    json.dump(ov, open(OVERRIDE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n✅ 已写 {OVERRIDE}")
    print("下一步: python3 pipeline/stage1_split.py && python3 pipeline/stage2_prepare.py")

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        cmd_status()
    elif cmd == "prepare":
        cmd_prepare()
    elif cmd == "run":
        cmd_run()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
