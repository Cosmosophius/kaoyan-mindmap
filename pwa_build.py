#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWA 资产生成：manifest / service worker / 图标 / 分片清单。

为什么要单独一个模块：
  build_treechat_web.py 每次重建都会覆写 index.html，
  若把 manifest、sw.js 手写在 web/ 里，重建不会丢，
  但图标是二进制、sw 需要按内容哈希打版本号，
  放在构建流程里才能保证「重建一次 = 离线包版本跟着变」。

离线策略（三层）：
  1. 安装期预缓存 shell —— index.html 已内联全部骨架（2.3 MB），
     所以只要装好，即使完全断网也能打开、能展开、能看知识点。
  2. 激活后后台补全正文分片 —— 151 个 data/para/*.json 共 6.2 MB，
     并发 4 拉取写入 data 缓存，不阻塞首屏。
  3. 导航请求 stale-while-revalidate —— 先用缓存秒开，后台静默更新。
"""

import io
import json
import os
import struct
import zlib

# ---------------------------------------------------------------- 配色
BG      = (0x0D, 0x13, 0x10)   # surface，与 theme-color 一致
PRIMARY = (0x7F, 0xD9, 0x8A)   # primary tone80（种子 0xFF28C840）
DIM     = (0x4A, 0x6B, 0x52)   # 连线，低对比
ACCENT  = (0xC8, 0xB0, 0x6A)   # tertiary，真题强调


# ---------------------------------------------------------------- 极简 PNG 编码
def _png(width, height, rgba):
    """rgba: bytes，长度 = w*h*4，逐行 filter=0 后 zlib 压缩"""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- 形状光栅化
def _circle(buf, W, H, cx, cy, r, color, alpha=1.0):
    x0, x1 = max(0, int(cx - r - 1)), min(W, int(cx + r + 2))
    y0, y1 = max(0, int(cy - r - 1)), min(H, int(cy + r + 2))
    r2 = r * r
    for y in range(y0, y1):
        dy = y + 0.5 - cy
        for x in range(x0, x1):
            dx = x + 0.5 - cx
            if dx * dx + dy * dy <= r2:
                i = (y * W + x) * 4
                if alpha >= 1.0:
                    buf[i] = color[0]; buf[i + 1] = color[1]
                    buf[i + 2] = color[2]; buf[i + 3] = 255
                else:
                    buf[i]     = int(buf[i]     * (1 - alpha) + color[0] * alpha)
                    buf[i + 1] = int(buf[i + 1] * (1 - alpha) + color[1] * alpha)
                    buf[i + 2] = int(buf[i + 2] * (1 - alpha) + color[2] * alpha)
                    buf[i + 3] = 255


def _capsule(buf, W, H, x0, y0, x1, y1, w, color, alpha=1.0):
    """粗线段：到线段的距离 <= w/2 即填充"""
    hw = w / 2.0
    bx0 = max(0, int(min(x0, x1) - hw - 1)); bx1 = min(W, int(max(x0, x1) + hw + 2))
    by0 = max(0, int(min(y0, y1) - hw - 1)); by1 = min(H, int(max(y0, y1) + hw + 2))
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            px, py = x + 0.5 - x0, y + 0.5 - y0
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * vx + py * vy) / L2))
            dx, dy = px - vx * t, py - vy * t
            if dx * dx + dy * dy <= hw * hw:
                i = (y * W + x) * 4
                if alpha >= 1.0:
                    buf[i] = color[0]; buf[i + 1] = color[1]
                    buf[i + 2] = color[2]; buf[i + 3] = 255
                else:
                    buf[i]     = int(buf[i]     * (1 - alpha) + color[0] * alpha)
                    buf[i + 1] = int(buf[i + 1] * (1 - alpha) + color[1] * alpha)
                    buf[i + 2] = int(buf[i + 2] * (1 - alpha) + color[2] * alpha)
                    buf[i + 3] = 255


def make_icon(size, maskable=False):
    """
    画一棵极简思维导图：左侧根节点，向右分三条枝，末端各一个节点。
    采用 3 倍超采样再降采样，边缘干净，不依赖任何外部字体或图片。
    """
    SS = 3
    W = size * SS
    H = size * SS
    buf = bytearray(W * H * 4)

    # 背景：maskable 必须满幅铺底（留出安全区被裁掉也不露白）
    _circle(buf, W, H, W / 2, H / 2, W * 1.2, BG)

    # 版面：根节点在左 1/4 处垂直居中
    rx, ry = W * 0.26, H * 0.50
    r_root = W * 0.085
    # 三条枝的终点
    tips = [(W * 0.72, H * 0.26), (W * 0.74, H * 0.50), (W * 0.72, H * 0.74)]
    r_tip = W * 0.055

    # 连线先画，节点后画，避免线压在节点上
    for i, (tx, ty) in enumerate(tips):
        mx = (rx + tx) / 2
        _capsule(buf, W, H, rx, ry, mx, ry, W * 0.030, DIM)
        _capsule(buf, W, H, mx, ry, tx, ty, W * 0.030, DIM)

    # 根节点：主色
    _circle(buf, W, H, rx, ry, r_root, PRIMARY)
    # 中间节点挖个洞，做出「空心」的层次感
    _circle(buf, W, H, rx, ry, r_root * 0.44, BG)

    # 末梢节点：中间那个用强调色，呼应真题高亮
    for i, (tx, ty) in enumerate(tips):
        _circle(buf, W, H, tx, ty, r_tip, ACCENT if i == 1 else PRIMARY)

    # 降采样
    out = bytearray(size * size * 4)
    n = SS * SS
    for y in range(size):
        for x in range(size):
            r = g = b = a = 0
            for sy in range(SS):
                base = ((y * SS + sy) * W + x * SS) * 4
                for sx in range(SS):
                    i = base + sx * 4
                    r += buf[i]; g += buf[i + 1]; b += buf[i + 2]; a += buf[i + 3]
            o = (y * size + x) * 4
            out[o] = r // n; out[o + 1] = g // n
            out[o + 2] = b // n; out[o + 3] = a // n

    # 非 maskable 版本切圆角（Android 自适应图标会自己裁，普通图标需要圆角）
    if not maskable:
        rad = size * 0.22
        for y in range(size):
            for x in range(size):
                cx = min(max(x + 0.5, rad), size - rad)
                cy = min(max(y + 0.5, rad), size - rad)
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                if dx * dx + dy * dy > rad * rad:
                    o = (y * size + x) * 4
                    out[o + 3] = 0

    return _png(size, size, bytes(out))


# ---------------------------------------------------------------- manifest
MANIFEST = {
    "name": "汉硕考研 · 全书思维导图",
    "short_name": "考研导图",
    "description": "10 本教材 / 58 章 / 151 节 / 3618 条考点，可离线使用的交互式思维导图。",
    "lang": "zh-CN",
    "dir": "ltr",
    "start_url": "./index.html",
    "scope": "./",
    "id": "./",
    "display": "standalone",
    "display_override": ["window-controls-overlay", "standalone", "minimal-ui"],
    "orientation": "any",
    "background_color": "#0d1310",
    "theme_color": "#0d1310",
    "categories": ["education", "productivity"],
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}


# ---------------------------------------------------------------- service worker
SW_JS = r"""/* 汉硕考研思维导图 · Service Worker
   版本号由构建时按 index.html 内容哈希注入，重建即换缓存桶，旧包自动清掉。 */
const VER   = "__VER__";
const SHELL = "shell-" + VER;
const DATA  = "data-" + VER;

const SHELL_URLS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/maskable-512.png",
  "./icons/apple-touch-icon-180.png"
];

/* ---------- 安装：预缓存 shell ---------- */
self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    /* 逐个 add，单个失败不拖垮整包（比如某个图标 404） */
    await Promise.all(SHELL_URLS.map(u =>
      c.add(new Request(u, { cache: "reload" })).catch(() => {})
    ));
    await self.skipWaiting();
  })());
});

/* ---------- 激活：清旧桶 + 后台补全正文分片 ---------- */
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))
    );
    await self.clients.claim();
    packAll();               /* 不 await：首屏不等这 6.2 MB */
  })());
});

async function notify(msg){
  const cs = await self.clients.matchAll({ includeUncontrolled: true });
  cs.forEach(c => { try{ c.postMessage(msg); }catch(_){} });
}

/* 并发受限地拉全 151 个正文分片 */
async function packAll(){
  try{
    const r = await fetch("./data/para/_list.json", { cache: "no-store" });
    if(!r.ok) return;
    const ids = await r.json();
    const c = await caches.open(DATA);

    let done = 0, skip = 0, fail = 0;
    const queue = ids.slice();
    const CONC = 4;

    async function worker(){
      while(queue.length){
        const id = queue.shift();
        const url = "./data/para/" + id + ".json";
        const hit = await c.match(url);
        if(hit){ skip++; done++; continue; }
        try{
          const res = await fetch(url, { cache: "no-store" });
          if(res.ok) await c.put(url, res.clone());
          else fail++;
        }catch(_){ fail++; }
        done++;
        if(done % 20 === 0 || done === ids.length){
          notify({ type: "pack", done, total: ids.length, fail });
        }
      }
    }
    await Promise.all(Array.from({ length: CONC }, worker));
    notify({ type: "pack-done", total: ids.length, cached: done - fail, fail });
  }catch(_){}
}

/* ---------- 拦截 ---------- */
self.addEventListener("fetch", e => {
  const req = e.request;
  if(req.method !== "GET") return;

  let url;
  try{ url = new URL(req.url); }catch(_){ return; }
  if(url.origin !== self.location.origin) return;

  /* 1) 导航：网络优先，失败回落缓存。
     曾经是"缓存优先 + 后台更新"：只要缓存里有 index.html 就先返回旧页面。
     本地开发服务器停掉后，后台更新永远失败，页面就永久停在旧版本 ——
     用户改了代码却怎么刷都是旧的（实测卡在 PACK_COLS_MAX=2 的旧布局）。
     改为网络优先：在线永远拿到最新构建；断网时回落到缓存，离线可用性不变。 */
  if(req.mode === "navigate"){
    e.respondWith((async () => {
      const c = await caches.open(SHELL);
      try {
        const res = await fetch(req, { cache: "no-store" });
        if(res && res.ok) c.put("./index.html", res.clone());
        return res;
      } catch (_) {
        const hit = await c.match("./index.html");
        return hit || new Response(
          "<h1>离线且未缓存</h1><p>请联网打开一次以完成离线包安装。</p>",
          { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
        );
      }
    })());
    return;
  }

  /* 2) 正文分片：缓存优先，命中即秒开 */
  if(url.pathname.indexOf("/data/para/") >= 0){
    e.respondWith((async () => {
      const c = await caches.open(DATA);
      const hit = await c.match(req);
      if(hit) return hit;
      try{
        const res = await fetch(req);
        if(res.ok) c.put(req, res.clone());
        return res;
      }catch(_){
        return new Response("[]", {
          status: 200, headers: { "Content-Type": "application/json" }
        });
      }
    })());
    return;
  }

  /* build.txt：只走网络、绝不缓存 —— 页面靠它判断是否有新构建 */
  if(url.pathname.endsWith("/build.txt")){
    e.respondWith(fetch(req, { cache: "no-store" }).catch(
      () => new Response("", { status: 504 })
    ));
    return;
  }

  /* 3) 其他静态资源：缓存优先 */
  e.respondWith((async () => {
    const c = await caches.open(SHELL);
    const hit = await c.match(req);
    if(hit) return hit;
    try{
      const res = await fetch(req);
      if(res.ok && res.type === "basic") c.put(req, res.clone());
      return res;
    }catch(_){
      return new Response("", { status: 504 });
    }
  })());
});

/* ---------- 手动触发 / 查询 ---------- */
self.addEventListener("message", e => {
  const d = e.data || {};
  if(d.type === "pack") packAll();
  if(d.type === "ping" && e.source) e.source.postMessage({ type: "pong", ver: VER });
});
"""


def write_all(web_dir, ver, para_dir):
    """生成 manifest / sw.js / 图标 / 分片清单，返回写出的文件列表"""
    os.makedirs(web_dir, exist_ok=True)
    icons = os.path.join(web_dir, "icons")
    os.makedirs(icons, exist_ok=True)
    written = []

    # manifest
    p = os.path.join(web_dir, "manifest.webmanifest")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)
    written.append(p)

    # sw.js
    p = os.path.join(web_dir, "sw.js")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(SW_JS.replace("__VER__", ver))
    written.append(p)

    # 图标
    specs = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("maskable-512.png", 512, True),
        ("apple-touch-icon-180.png", 180, False),
    ]
    for name, size, mask in specs:
        p = os.path.join(icons, name)
        with open(p, "wb") as f:
            f.write(make_icon(size, mask))
        written.append(p)

    # 分片清单：给 SW 后台补全离线包用
    ids = []
    if os.path.isdir(para_dir):
        ids = sorted(fn[:-5] for fn in os.listdir(para_dir)
                     if fn.endswith(".json") and not fn.startswith("_"))
    p = os.path.join(para_dir, "_list.json")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, separators=(",", ":"))
    written.append(p)

    return written, len(ids)


if __name__ == "__main__":
    import hashlib
    base = os.path.dirname(os.path.abspath(__file__))
    web = os.path.join(base, "web")
    idx = os.path.join(web, "index.html")
    ver = hashlib.md5(open(idx, "rb").read()).hexdigest()[:10]
    files, n = write_all(web, ver, os.path.join(web, "data", "para"))
    print("ver =", ver, "| 分片", n)
    for f in files:
        print("  ", f, os.path.getsize(f), "B")
