#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2 前置 — 生成 Gemini 请求载荷（纯代码，无 LLM 调用）
把 skeleton.json 的每个 section 切成 <=60k 字的请求，写入 out/requests/。
本脚本不联网、不调用任何模型，只负责「把活儿分好、把提示词拼好」。

用法:
  python3 stage2_prepare.py              # 生成请求 + manifest
  python3 stage2_prepare.py --curl 3     # 额外输出前 3 条 curl 命令示例
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
REQ = os.path.join(OUT, "requests")
MAX_CHARS = 60000          # SPEC §2 Stage2 分片上限

def load_skeleton():
    p = os.path.join(OUT, "skeleton.json")
    if not os.path.exists(p):
        print("❌ 缺少 skeleton.json，先跑 stage1_split.py"); sys.exit(1)
    return json.load(open(p, encoding="utf-8"))

def load_paras(doc_id):
    p = os.path.join(OUT, "paragraphs", f"{doc_id}.jsonl")
    d = {}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            d[o["para_id"]] = o["text"]
    return d

def slice_text(paras, rng):
    """按 para_range 取原文，每段前置 [pNNN] 便于回溯"""
    return "\n".join(f'[p{i}] {paras[i]}' for i in range(rng[0], rng[1] + 1) if i in paras)

def split_by_size(text, limit):
    """按段落边界切分，保证不切断段落"""
    if len(text) <= limit:
        return [text]
    blocks, cur = [], []
    size = 0
    for line in text.split("\n"):
        if size + len(line) > limit and cur:
            blocks.append("\n".join(cur)); cur, size = [], 0
        cur.append(line); size += len(line) + 1
    if cur:
        blocks.append("\n".join(cur))
    return blocks

def main():
    sk = load_skeleton()
    prompt_tpl = open(os.path.join(BASE, "prompts", "gemini_extract.md"), encoding="utf-8").read()
    schema = json.load(open(os.path.join(BASE, "schema", "kp.schema.json"), encoding="utf-8"))
    os.makedirs(REQ, exist_ok=True)

    cache, manifest, n_req, skipped = {}, [], 0, 0
    for b in sk["books"]:
        doc = b["doc"]
        if doc not in cache:
            cache[doc] = load_paras(doc)
        paras = cache[doc]
        for ch in b["chapters"]:
            for sec in ch["sections"]:
                sid = sec["section_id"]
                text = slice_text(paras, sec["para_range"])
                if len(text) < 80:            # 空节跳过
                    skipped += 1
                    continue
                for part, chunk in enumerate(split_by_size(text, MAX_CHARS), 1):
                    body = (
                        f"{prompt_tpl}\n\n---\n\n"
                        f"<section_id>{sid}</section_id>\n"
                        f"<title>{sec['title']}</title>\n"
                        f"<part>{part}</part>\n"
                        f"<text>\n{chunk}\n</text>\n"
                    )
                    name = f"{sid}" + (f"_p{part}" if part > 1 else "")
                    payload = {
                        "task": "extract_kp",
                        "section_id": sid,
                        "chapter": ch["title"],
                        "book": b["title"],
                        "para_range": sec["para_range"],
                        "chars": len(chunk),
                        "response_schema": schema,
                        "system": "你是结构化抽取器。只输出符合 schema 的 JSON，禁止改写原文。",
                        "input": body,
                    }
                    json.dump(payload, open(os.path.join(REQ, f"{name}.json"), "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
                    manifest.append({"request": f"{name}.json", "section_id": sid,
                                     "book": b["title"], "chapter": ch["title"],
                                     "chars": len(chunk), "para_range": sec["para_range"]})
                    n_req += 1

    json.dump({"total": n_req, "max_chars": MAX_CHARS, "requests": manifest},
              open(os.path.join(OUT, "requests_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    tot = sum(m["chars"] for m in manifest)
    big = [m for m in manifest if m["chars"] > MAX_CHARS]
    print(f"✅ 生成请求 {n_req} 个 -> out/requests/  (跳过空节 {skipped})")
    print(f"   覆盖原文 {tot} 字 | 最大单请求 {max((m['chars'] for m in manifest), default=0)} 字")
    print(f"   超限请求: {len(big)} 个 {'✅' if not big else '⚠️'}")
    print(f"   manifest: out/requests_manifest.json")
    if "--curl" in sys.argv:
        n = int(sys.argv[sys.argv.index("--curl") + 1]) if len(sys.argv) > sys.argv.index("--curl") + 1 else 1
        sample = manifest[0]["request"] if manifest else None
        if sample:
            print(f"\n--- 示例: 把 out/requests/{sample} 的 input 发给模型 ---")
            print("curl -s https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent \\")
            print('  -H "x-goog-api-key: $GEMINI_API_KEY" -H "Content-Type: application/json" \\')
            print(f'  -d @<(python3 -c "import json;d=json.load(open(\'out/requests/{sample}\'));'
                  'print(json.dumps({\\"contents\\":[{\\"parts\\":[{\\"text\\":d[\\"input\\"]}]}],'
                  '\\"generationConfig\\":{\\"responseMimeType\\":\\"application/json\\",'
                  '\\"responseSchema\\":d[\\"response_schema\\"]}}))")')
            print(f"\n返回 JSON 存为 out/kp_raw/{sample.replace('.json','')}.json 后跑 stage3_validate.py")

if __name__ == "__main__":
    main()
