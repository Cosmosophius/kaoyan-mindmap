#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2 批量执行器 — 直接调用 Gemini API
Gemini 不会写这个，所以备好。你只需要设 GEMINI_API_KEY 然后运行。

特性:
  - 断点续跑（已存在的 kp_raw 自动跳过）
  - 失败重试 3 次，指数退避
  - 限速（默认 1 秒/请求，避免 429）
  - 温度 0.1 + 强制 JSON + responseSchema 约束
  - 结果写入 out/kp_raw/<section_id>.json

用法:
  export GEMINI_API_KEY=xxx
  python3 pipeline/stage2_run.py                  # 跑全部
  python3 pipeline/stage2_run.py --limit 3        # 先试 3 个
  python3 pipeline/stage2_run.py --model gemini-2.5-flash --sleep 2
  python3 pipeline/stage2_run.py --dry-run        # 只检查不调用
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")
REQ = os.path.join(OUT, "requests")
RAW = os.path.join(OUT, "kp_raw")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def call_gemini(model, key, payload, timeout=180):
    url = API.format(model=model)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError(f"无 candidates: {json.dumps(data)[:300]}")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("返回空文本")
    if text.startswith("```"):                 # 容错: 剥掉 markdown 围栏
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    return json.loads(text)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and not args.dry_run:
        print("❌ 未设置 GEMINI_API_KEY")
        print("   export GEMINI_API_KEY=你的key")
        sys.exit(1)
    if not os.path.isdir(REQ):
        print("❌ 缺少 out/requests，先跑 stage2_prepare.py"); sys.exit(1)
    os.makedirs(RAW, exist_ok=True)

    files = sorted(f for f in os.listdir(REQ) if f.endswith(".json"))
    todo = [f for f in files if not os.path.exists(os.path.join(RAW, f))]
    print(f"请求总数 {len(files)} | 已完成 {len(files)-len(todo)} | 待跑 {len(todo)}")
    if args.limit:
        todo = todo[:args.limit]
        print(f"本次只跑 {len(todo)} 个（--limit）")

    if args.dry_run:
        print("dry-run：仅检查请求文件完整性")
        bad = 0
        for f in todo:
            d = json.load(open(os.path.join(REQ, f), encoding="utf-8"))
            if not d.get("input") or not d.get("response_schema"):
                print(f"  ⚠️ {f} 缺 input/schema"); bad += 1
        print(f"检查完成，异常 {bad} 个" if bad else "全部正常 ✅")
        return

    ok = fail = 0
    for i, f in enumerate(todo, 1):
        d = json.load(open(os.path.join(REQ, f), encoding="utf-8"))
        payload = {
            "contents": [{"parts": [{"text": d["input"]}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": d["response_schema"],
                "temperature": 0.1,
            },
        }
        done = False
        for attempt in range(1, args.retries + 1):
            try:
                res = call_gemini(args.model, key, payload)
                if "kps" not in res:
                    raise RuntimeError("返回缺 kps 字段")
                res["section_id"] = d["section_id"]      # 以请求为准
                json.dump(res, open(os.path.join(RAW, f), "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                ok += 1; done = True
                print(f"[{i}/{len(todo)}] ✅ {f[:-5]} ({len(res.get('kps') or [])} 条)")
                break
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "ignore")[:200]
                print(f"[{i}/{len(todo)}] ⚠️ {f[:-5]} HTTP {e.code} (第{attempt}次) {msg}")
                if e.code in (400, 403, 404):
                    print("   -> 不可重试错误，跳过"); break
            except Exception as e:
                print(f"[{i}/{len(todo)}] ⚠️ {f[:-5]} {type(e).__name__}: {e} (第{attempt}次)")
            if attempt < args.retries:
                time.sleep(2 ** attempt)
        if not done:
            fail += 1
            print(f"   ❌ {f[:-5]} 未成功")
        time.sleep(args.sleep)

    print(f"\n完成: 成功 {ok} / 失败 {fail}")
    if ok:
        print("下一步: python3 pipeline/stage3_validate.py")

if __name__ == "__main__":
    main()
