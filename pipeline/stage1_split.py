#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 — 章节树切分（纯代码，无 LLM）
实测难点: 这批 docx 无 Heading 样式, 且存在 3 类噪声
  (a) 目录行: 含 '…'/'⋯' 或 '标题 / 页码'
  (b) 页眉混入正文: '10第一章 语音' 前缀/后缀
  (c) 正文标题: '第一章 语 音'（字间可能有空格）
策略: 先去目录 -> 去页眉 -> 按正文标题建树
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARA_DIR = os.path.join(BASE, "out", "paragraphs")
OUT = os.path.join(BASE, "out", "skeleton.json")

BOOK_TITLE = {
    "culture": "中国文化要略（第四版）", "rumen": "对外汉语教学入门（第3版）",
    "yinlun": "对外汉语教育学引论", "zhenti_10_23": "南师大汉硕10-23真题带答案",
    "xdhy_up": "现代汉语通论（上册）", "xdhy_down": "现代汉语通论（下册）",
    "ziliao": "汉硕考研资料汇总", "zhenti_24": "24南师大354+445真题和答案",
    "zhenti_2026": "2026南师大334+445真题", "zhenti_25": "25南师大354+445真题",
}
CN = "一二三四五六七八九十百零〇两"
RE_CH  = re.compile(rf'^第[{CN}\d]+章\s*([^\s。，、]{{1,20}})')
RE_SEC = re.compile(rf'^第[{CN}\d]+节\s*([^\s。，、]{{1,20}})')
RE_L3  = re.compile(rf'^[{CN}]+、')
RE_L4  = re.compile(rf'^[（(][{CN}\d]+[）)]')


CN_DIGIT = {"零":0,"〇":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
CN_UNIT  = {"十":10,"百":100}

def cn2int(t):
    """中文数字/阿拉伯数字 -> int"""
    if not t: return None
    if t.isdigit(): return int(t)
    total, cur = 0, 0
    for ch in t:
        if ch in CN_DIGIT:
            cur = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            u = CN_UNIT[ch]
            total += (cur if cur else 1) * u
            cur = 0
        else:
            return None
    return total + cur

def seq_num(text, kind):
    """取 '第X章/第X节' 的 X 数值"""
    m = re.match(rf'^第([{CN}\d]+){kind}', text)
    return cn2int(m.group(1)) if m else None

def is_toc(text):
    if text.count("…") >= 3 or text.count("⋯") >= 3: return True
    if re.search(r'[.·]{5,}', text): return True
    if re.match(rf'^第[{CN}\d]+[章节]', text) and re.search(r'/\s*\d+\s*$', text): return True
    if re.match(rf'^第[{CN}\d]+[章节]', text) and re.search(r'[（(]\d+[）)]\s*$', text): return True
    return False

RUN_HEAD = re.compile(
    rf'\d{{1,3}}\s*第[{CN}\d]+章\s*(?:导\s*论|语\s*音|汉\s*字|词\s*汇|语\s*法|语\s*用)')

def strip_running_header(text):
    """去掉混入正文的页眉，如 '10第一章 语音在不同的区域...'"""
    if len(text) < 25:
        return text
    m = RUN_HEAD.match(text)
    if m and len(text) - m.end() > 8:
        text = text[m.end():]
    m2 = re.search(rf'\d{{1,3}}\s*第[{CN}\d]+章\s*[一-鿿]{{1,6}}$', text)
    if m2 and m2.start() > 10:
        text = text[:m2.start()]
    return text.strip()

def normalize_title(t):
    """标题归一化: 去所有空白、去尾标点、统一括号，用于去重与展示"""
    t = re.sub(r'\s+', '', t)
    t = t.replace("（", "(").replace("）", ")")
    t = re.sub(r'[。．.、，,；;：:]+$', '', t)
    return t

def heading_title(text):
    """返回 (level, title) 或 (0, None)。标题允许字间有空格，需整体取出。"""
    if len(text) > 30 or is_toc(text):
        return 0, None
    for lv, rx in ((1, RE_CH), (2, RE_SEC)):
        m = rx.match(text)
        if m:
            # 取整行作为标题，去掉页码残留后归一化
            t = re.sub(r'/\s*\d+\s*$', '', text)
            t = re.sub(r'[(（]\s*\d+\s*[)）]\s*$', '', t)
            t = re.sub(r'(?<=[\u4e00-\u9fff])\s*\d{1,3}\s*$', '', t)  # 尾部页码
            t = normalize_title(t)
            if len(t) > 40:
                return 0, None
            return lv, t
    if RE_L3.match(text) and len(text) < 26:
        return 3, normalize_title(text)
    if RE_L4.match(text) and len(text) < 26:
        return 4, normalize_title(text)
    return 0, None


RE_HEAD_ONLY = re.compile(rf'^第[{CN}\d]+[章节]$')

def join_split_headings(paras):
    """修复被拆成两段的标题: '第一章' + '简论' -> '第一章简论'"""
    out = []
    i = 0
    while i < len(paras):
        cur = dict(paras[i])
        # 先去内部空白再判断，兼容 "第三章" / "第 三 章" / "第三章 "
        if (RE_HEAD_ONLY.match(re.sub(r'\s+', '', cur["text"]))
                and i + 1 < len(paras)):
            nxt = paras[i + 1]["text"].strip()
            if (0 < len(nxt) <= 20
                    and not re.match(rf'^第[{CN}\d]+[章节]', nxt)
                    and not is_toc(nxt)):
                cur["text"] = re.sub(r'\s+', '', cur["text"]) + nxt
                out.append(cur)
                i += 2
                continue
        out.append(cur)
        i += 1
    return out


def parse_toc(paras):
    """从目录行解析权威章节表（行首锚定版，实测最稳）。
    目录特征: '第X章 标题 / 页码'。
    注意: 合并成一段的目录(p30 那种)无法可靠拆分，故交给 toc_override.json 人工修正。
    """
    entries, seen = [], set()
    for p in paras:
        t = p["text"]
        if not re.search(r'[/…⋯·.\s]\s*\d{1,3}\s*$', t):
            continue
        if len(t) > 60:
            continue
        for lv, kind in ((1, "章"), (2, "节")):
            m = re.match(rf'^第([{CN}\d]+){kind}', t)
            if not m:
                continue
            no = cn2int(m.group(1))
            if no is None or (lv, no) in seen:
                break
            title = re.sub(r'[/…⋯·.\s]*\d{1,3}\s*$', '', t)
            title = normalize_title(title)
            if 3 <= len(title) <= 45:
                seen.add((lv, no))
                entries.append((lv, no, title))
            break
    return entries

def load_override(doc_id):
    """人工修正文件: out/toc_override.json
    格式: {"culture": [{"no":1,"title":"第一章 简论","sections":[{"no":1,"title":"第一节 ..."}]}]}
    """
    path = os.path.join(BASE, "out", "toc_override.json")
    if not os.path.exists(path):
        return None
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    return data.get(doc_id)

def clean_para_text(t):
    """去除水印与空白干扰"""
    t = re.sub(r"获取更多资料\s*汉硕[^\n]*?cn\)?", "", t, flags=re.I)
    t = re.sub(r"\s+", "", t)
    return t

def locate_in_body(paras, title, start_idx):
    """在正文中定位章节标题所在段落，返回段落索引或 None"""
    full = re.sub(r"\s+", "", title)
    core = re.sub(r"^(第[一二三四五六七八九十\d]+[章节讲篇编]|导论|导言|附录|[一二三四五六七八九十\d]+[、.．])\s*", "", title)
    core = re.sub(r"\s+", "", core)

    # 1. 完整匹配
    for i in range(start_idx, len(paras)):
        raw = clean_para_text(paras[i]["text"])
        if not raw:
            continue
        if full in raw:
            return i

    # 2. 核心词匹配
    if len(core) >= 2:
        for i in range(start_idx, len(paras)):
            raw = clean_para_text(paras[i]["text"])
            if not raw:
                continue
            if core in raw[:80] or (len(raw) < 120 and core in raw):
                return i

    # 3. 容错匹配: 去掉非字标点
    k2 = re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", core if len(core) >= 3 else full)
    if len(k2) >= 3:
        for i in range(start_idx, len(paras)):
            raw = clean_para_text(paras[i]["text"])
            body = re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", raw)
            if k2 in body[:60] or (len(body) < 100 and k2 in body):
                return i
    return None

def find_toc_end_index(paras, max_scan=120):
    """检测前置目录的结束段落索引，避免定位章节时误命中目录"""
    last_toc = -1
    for i in range(min(len(paras), max_scan)):
        t = paras[i]["text"]
        if is_toc(t) or re.search(r"[…⋯]{2,}", t) or re.search(r"/\s*\d{1,4}", t):
            last_toc = i
    return last_toc + 1 if last_toc >= 0 else 0

def build_doc(doc_id, paras):
    """优先: 目录驱动（权威两阶段定位）; 兜底: 正文启发式"""
    ov = load_override(doc_id)
    if ov:
        # 阶段 1: 全局仅定位【章】，严格单调递增，杜绝小节将全局 cursor 带偏
        chapters_raw, cursor = [], find_toc_end_index(paras)
        for ch in ov:
            idx = locate_in_body(paras, ch["title"], cursor)
            if idx is None:
                continue
            chapters_raw.append({
                "no": ch["no"],
                "title": normalize_title(ch["title"]),
                "idx": idx,
                "para_id": paras[idx]["para_id"],
                "raw_sections": ch.get("sections", [])
            })
            cursor = idx + 1

        if chapters_raw:
            # 计算每章在 paras 列表中的起止索引 [start_idx, end_idx]
            final_chapters = []
            for i, ch_info in enumerate(chapters_raw):
                ch_start_idx = ch_info["idx"]
                ch_end_idx = (chapters_raw[i+1]["idx"] - 1) if (i + 1 < len(chapters_raw)) else (len(paras) - 1)
                ch_end_pid = paras[ch_end_idx]["para_id"]
                
                node = {
                    "chapter_id": f"{doc_id}-c{ch_info["no"]:02d}",
                    "title": ch_info["title"],
                    "para_range": [ch_info["para_id"], ch_end_pid],
                    "sections": []
                }
                
                # 阶段 2: 仅在当前章的 [ch_start_idx, ch_end_idx] 局部区间内定位节
                sec_cursor = ch_start_idx
                for sec in ch_info["raw_sections"]:
                    sidx = locate_in_body(paras[:ch_end_idx + 1], sec["title"], sec_cursor)
                    if sidx is None or sidx > ch_end_idx:
                        continue
                    node["sections"].append({
                        "section_id": f"{node["chapter_id"]}-s{len(node["sections"])+1:02d}",
                        "title": normalize_title(sec["title"]),
                        "para_range": [paras[sidx]["para_id"], paras[sidx]["para_id"]]
                    })
                    sec_cursor = sidx + 1
                
                # 回填小节终点
                secs = node["sections"]
                for j, sec in enumerate(secs):
                    e = (secs[j+1]["para_range"][0] - 1) if (j + 1 < len(secs)) else node["para_range"][1]
                    sec["para_range"][1] = max(sec["para_range"][0], e)
                
                if not secs:
                    node["sections"].append({
                        "section_id": f"{node["chapter_id"]}-s01",
                        "title": node["title"][:60],
                        "para_range": list(node["para_range"])
                    })
                final_chapters.append(node)
            return final_chapters

    toc = parse_toc(paras)
    if toc:
        chapters, cur_ch = [], None
        cursor = 0
        for lv, no, title in toc:
            idx = locate_in_body(paras, title, cursor)
            if idx is None:
                continue
            pid = paras[idx]["para_id"]
            if lv == 1:
                cur_ch = {"chapter_id": f"{doc_id}-c{no:02d}", "title": title,
                          "para_range": [pid, pid], "sections": []}
                chapters.append(cur_ch)
                cursor = idx + 1
            elif cur_ch is not None:
                cur_ch["sections"].append({
                    "section_id": f'{cur_ch["chapter_id"]}-s{len(cur_ch["sections"])+1:02d}',
                    "title": title, "para_range": [pid, pid]})
                cursor = idx + 1
        # 用下一章起点回填本章终点
        for i, ch in enumerate(chapters):
            end = (chapters[i+1]["para_range"][0] - 1) if i + 1 < len(chapters) else paras[-1]["para_id"]
            ch["para_range"][1] = max(ch["para_range"][0], end)
            secs = ch["sections"]
            for j, sec in enumerate(secs):
                s_end = (secs[j+1]["para_range"][0] - 1) if j + 1 < len(secs) else ch["para_range"][1]
                sec["para_range"][1] = max(sec["para_range"][0], s_end)
            if not secs:
                ch["sections"].append({"section_id": f'{ch["chapter_id"]}-s01',
                                       "title": ch["title"][:60], "para_range": list(ch["para_range"])})
        if chapters:
            return chapters
    return build_doc_heuristic(doc_id, paras)

def build_doc_heuristic(doc_id, paras):

    chapters, cur_ch, cur_sec = [], None, None
    seen_ch, seen_sec = set(), set()
    last_ch_no, last_sec_no = 0, 0
    for p in paras:
        pid, text = p["para_id"], p["text"]
        if is_toc(text):                      # 目录整行丢弃
            continue
        text = strip_running_header(text)
        lv, title = heading_title(text)
        if lv == 1:
            no = seq_num(text, "章")
            # 章号必须严格递增，滤掉页眉重复与误判
            if no is None or no <= last_ch_no:
                continue
            last_ch_no, last_sec_no = no, 0
            seen_sec = set()
            cur_ch = {"chapter_id": f"{doc_id}-c{len(chapters)+1:02d}", "title": title,
                      "para_range": [pid, pid], "sections": []}
            chapters.append(cur_ch); cur_sec = None
        elif lv == 2 and cur_ch is not None:
            no = seq_num(text, "节")
            if no is None or no <= last_sec_no:
                continue
            last_sec_no = no
            cur_sec = {"section_id": f'{cur_ch["chapter_id"]}-s{len(cur_ch["sections"])+1:02d}',
                       "title": title, "para_range": [pid, pid]}
            cur_ch["sections"].append(cur_sec)
        else:
            if cur_sec is not None:   cur_sec["para_range"][1] = pid
            elif cur_ch is not None:  cur_ch["para_range"][1] = pid
    if not chapters and paras:
        # 真题/资料类无章节结构，整本作为单章
        chapters = [{"chapter_id": f"{doc_id}-c01", "title": "全文",
                     "para_range": [paras[0]["para_id"], paras[-1]["para_id"]], "sections": []}]
    for ch in chapters:
        if not ch["sections"]:
            ch["sections"].append({"section_id": f'{ch["chapter_id"]}-s01',
                                   "title": ch["title"][:60], "para_range": list(ch["para_range"])})
    return chapters

def main():
    files = sorted(f for f in os.listdir(PARA_DIR) if f.endswith(".jsonl"))
    if not files:
        print("❌ 无段落文件，先跑 stage0"); sys.exit(1)
    books = []
    for f in files:
        doc_id = f[:-6]
        paras = [json.loads(l) for l in open(os.path.join(PARA_DIR, f), encoding="utf-8")]
        paras = join_split_headings(paras)
        chapters = build_doc(doc_id, paras)
        n_sec = sum(len(c["sections"]) for c in chapters)
        books.append({"doc": doc_id, "title": BOOK_TITLE.get(doc_id, doc_id), "chapters": chapters})
        heads = " | ".join(c["title"][:14] for c in chapters[:4])
        print(f"{doc_id:14} {len(chapters):>3} 章 {n_sec:>4} 节  {heads}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"version": 1, "books": books}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    tot_ch = sum(len(b["chapters"]) for b in books)
    tot_sec = sum(len(c["sections"]) for b in books for c in b["chapters"])
    print(f"\n✅ skeleton.json: {len(books)} 本 / {tot_ch} 章 / {tot_sec} 节 / {os.path.getsize(OUT)/1024:.0f} KB")

if __name__ == "__main__":
    main()
