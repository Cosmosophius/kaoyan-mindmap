/* 汉硕考研思维导图 · Service Worker
   版本号由构建时按 index.html 内容哈希注入，重建即换缓存桶，旧包自动清掉。 */
const VER   = "ba982b4b43";
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

  /* 1) 导航：缓存优先，后台静默更新（离线也能开） */
  if(req.mode === "navigate"){
    e.respondWith((async () => {
      const c = await caches.open(SHELL);
      const hit = await c.match("./index.html");
      const net = fetch(req).then(res => {
        if(res && res.ok) c.put("./index.html", res.clone());
        return res;
      }).catch(() => null);
      if(hit) return hit;
      const fresh = await net;
      return fresh || new Response(
        "<h1>离线且未缓存</h1><p>请联网打开一次以完成离线包安装。</p>",
        { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
      );
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
