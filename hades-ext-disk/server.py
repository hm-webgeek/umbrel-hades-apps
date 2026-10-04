#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import posixpath
import re

ROOT = "/mnt/external"
PREFERRED = "IRONWOLF-01"
PORT = 3000
WALLPAPER_DIR = "/mnt/wallpapers"
UMBREL_YAML = "/mnt/umbrel.yaml"


def pretty(n):
    n = float(n)
    for unit in ("B", "kB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1000:
            if unit == "B":
                return f"{int(n)} B"
            text = f"{n:.1f}".rstrip("0").rstrip(".")
            return f"{text} {unit}"
        n /= 1000.0
    return f"{n:.1f} PB"


def disks():
    out = []
    if not os.path.isdir(ROOT):
        return out
    try:
        names = sorted(os.listdir(ROOT))
    except OSError:
        return out
    for name in names:
        if name.startswith("."):
            continue
        path = os.path.join(ROOT, name)
        if not os.path.isdir(path):
            continue
        try:
            st = os.statvfs(path)
        except OSError:
            continue
        size = st.f_frsize * st.f_blocks
        avail = st.f_frsize * st.f_bavail
        if size <= 0:
            continue
        out.append({"name": name, "size": size, "used": size - avail, "avail": avail})
    return out


def pick(ds, name=None):
    if name:
        for d in ds:
            if d["name"] == name:
                return d
        return None
    for d in ds:
        if d["name"] == PREFERRED:
            return d
    return ds[0] if ds else None


def widget(d):
    size, used, avail = d["size"], d["used"], d["avail"]
    progress = min(1.0, max(0.0, used / size)) if size else 0.0
    return {
        "type": "text-with-progress",
        "link": "",
        "refresh": "30s",
        "title": d["name"],
        "text": pretty(used),
        "subtext": f"/ {pretty(size)}",
        "progressLabel": f"{pretty(avail)} left",
        "progress": f"{progress:.2f}",
    }


def view_disks(ds):
    out = []
    for d in ds:
        size, used, avail = d["size"], d["used"], d["avail"]
        progress = min(1.0, max(0.0, used / size)) if size else 0.0
        out.append(
            {
                "name": d["name"],
                "used": pretty(used),
                "size": pretty(size),
                "avail": pretty(avail),
                "progress": round(progress, 4),
            }
        )
    return out


def wallpaper_id():
    try:
        with open(UMBREL_YAML, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "17"
    m = re.search(r"^\s*wallpaper:\s*['\"]?([^'\"\n#]+)", text, re.M)
    if not m:
        return "17"
    wid = m.group(1).strip()
    if not wid or "/" in wid or ".." in wid or "\\" in wid:
        return "17"
    return wid


def wallpaper_path():
    wid = wallpaper_id()
    candidates = [
        os.path.join(WALLPAPER_DIR, f"{wid}.jpg"),
        os.path.join(WALLPAPER_DIR, f"{wid}.png"),
        os.path.join(WALLPAPER_DIR, f"{wid}.webp"),
        os.path.join(WALLPAPER_DIR, "generated-avif", f"{wid}.avif"),
        os.path.join(WALLPAPER_DIR, "17.jpg"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storage</title>
<style>
  :root {
    color-scheme: dark;
    --wp: none;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
    color: #ffffffe6;
    letter-spacing: -.03em;
    background: #0b0d12;
    overflow: hidden;
    user-select: none;
  }
  .wallpaper {
    position: fixed;
    inset: 0;
    background-image: var(--wp);
    background-size: cover;
    background-position: 50%;
    transform: scale(1.2);
    filter: blur(40px) saturate(1.5) brightness(.7);
  }
  .stage {
    position: relative;
    z-index: 1;
    min-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2vh 16px;
  }
  .window {
    width: min(1120px, 92vw);
    height: min(860px, 90vh);
    border-radius: 40px;
    background: rgb(0 0 0 / .7);
    border: .5px solid rgb(255 255 255 / .08);
    box-shadow:
      0 10px 64px rgb(0 0 0 / .8),
      1px 0 rgb(255 255 255 / .075) inset,
      -1px 0 rgb(255 255 255 / .075) inset,
      0 1px rgb(255 255 255 / .25) inset,
      0 .5px rgb(255 255 255 / .125) inset;
    display: flex;
    flex-direction: column;
    padding: 28px 28px 24px;
    min-height: 0;
  }
  @media (max-width: 1023px) {
    .window { border-radius: 24px; width: 94vw; height: 92vh; padding: 20px; }
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-shrink: 0;
  }
  .head h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -.04em;
  }
  .close {
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: 999px;
    background: #ffffff24;
    color: #fff;
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
    display: grid;
    place-items: center;
    padding: 0;
  }
  .close:hover { background: #ffffff3d; }
  .tiles {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .tile {
    appearance: none;
    border: 0;
    text-align: left;
    color: inherit;
    font: inherit;
    cursor: pointer;
    border-radius: 24px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 96px;
    overflow: hidden;
    background-color: #ffffff08;
    border: .1px solid #ffffff0a;
    box-shadow: 0 4px 8px #0000001a, inset 0 1px #ffffff14, inset 0 .5px #ffffff07, inset 0 -1px #0000001f;
    backdrop-filter: blur(8px) saturate(1.7) brightness(1.3);
    -webkit-backdrop-filter: blur(8px) saturate(1.7) brightness(1.3);
    background-image: linear-gradient(#ffffff0d, #ffffff0d);
  }
  .tile[aria-selected="true"] {
    flex: 1;
    min-height: 220px;
    outline: 1px solid rgb(var(--brand, 83 142 245) / .4);
    outline-offset: -1px;
  }
  .name { font-size: 13px; font-weight: 500; color: #ffffff66; }
  .value-row { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
  .value { font-size: 24px; font-weight: 600; letter-spacing: -.03em; line-height: 1; }
  .tile:not([aria-selected="true"]) .value { font-size: 20px; }
  .sub { font-size: 13px; font-weight: 600; color: #ffffff73; }
  .left { font-size: 12px; letter-spacing: -.02em; color: #ffffff40; }
  .bar {
    margin-top: auto;
    height: 8px;
    overflow: hidden;
    border-radius: 999px;
    background: #ffffff1a;
  }
  .bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: #ffffff59;
  }
  .empty { margin: 0; font-size: 13px; color: #ffffff80; }
</style>
<body>
  <div class="wallpaper" id="wallpaper"></div>
  <div class="stage">
    <section class="window" role="dialog" aria-labelledby="title">
      <div class="head">
        <h1 id="title">Storage</h1>
        <button class="close" type="button" aria-label="Close" onclick="window.close()">×</button>
      </div>
      <div class="tiles" id="body"></div>
    </section>
  </div>
<script>
const DISKS = __DISKS__;
const PREFERRED = __PREFERRED__;

function setWallpaper(id) {
  document.documentElement.style.setProperty("--wp", `url("/wallpaper?v=${encodeURIComponent(id)}")`);
}

async function refreshWallpaper() {
  try {
    const r = await fetch("/meta", { cache: "no-store" });
    const d = await r.json();
    if (d.wallpaper && d.wallpaper !== refreshWallpaper.last) {
      refreshWallpaper.last = d.wallpaper;
      setWallpaper(d.wallpaper);
    }
  } catch (e) {}
}

function render(name) {
  const root = document.getElementById("body");
  if (!DISKS.length) {
    root.innerHTML = `<p class="empty">No external disks mounted.</p>`;
    return;
  }
  const selected = DISKS.find(d => d.name === name) || DISKS.find(d => d.name === PREFERRED) || DISKS[0];
  root.innerHTML = DISKS.map(d => {
    const on = d.name === selected.name;
    const pct = Math.max(0, Math.min(100, d.progress * 100));
    return `<button class="tile" type="button" aria-selected="${on}" data-name="${d.name}">
      <div class="name">${d.name}</div>
      <div class="value-row"><span class="value">${d.used}</span><span class="sub">/ ${d.size}</span></div>
      <div class="left">${d.avail} left</div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    </button>`;
  }).join("");
  root.querySelectorAll("[data-name]").forEach(btn => {
    btn.addEventListener("click", () => {
      const next = btn.getAttribute("data-name");
      const url = new URL(location.href);
      url.searchParams.set("disk", next);
      history.replaceState(null, "", url);
      render(next);
    });
  });
}

refreshWallpaper();
setInterval(refreshWallpaper, 8000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshWallpaper();
});
render(new URLSearchParams(location.search).get("disk"));
</script>
</body>
</html>
"""


def page(ds):
    html = PAGE.replace("__DISKS__", json.dumps(view_disks(ds)))
    html = html.replace("__PREFERRED__", json.dumps(PREFERRED))
    return html


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def send_bytes(self, body, content_type, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, code=200, extra=None):
        self.send_bytes(json.dumps(obj).encode(), "application/json", code, extra)

    def send_html(self, html, code=200):
        self.send_bytes(html.encode(), "text/html; charset=utf-8", code)

    def do_GET(self):
        path = posixpath.normpath(self.path.split("?", 1)[0])
        if path == "/meta":
            return self.send_json(
                {"wallpaper": wallpaper_id()},
                extra={"Cache-Control": "no-store"},
            )
        if path == "/wallpaper":
            wp = wallpaper_path()
            if not wp:
                return self.send_json({"error": "no wallpaper"}, 404)
            ext = os.path.splitext(wp)[1].lower()
            types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".avif": "image/avif"}
            try:
                with open(wp, "rb") as f:
                    body = f.read()
            except OSError:
                return self.send_json({"error": "no wallpaper"}, 404)
            return self.send_bytes(
                body,
                types.get(ext, "image/jpeg"),
                extra={"Cache-Control": "no-store"},
            )
        ds = disks()
        if path == "/widgets/storage":
            d = pick(ds)
            if not d:
                return self.send_json({"error": "no external disk"}, 404)
            return self.send_json(widget(d))
        if path.startswith("/widgets/"):
            d = pick(ds, path[len("/widgets/") :])
            if not d:
                return self.send_json({"error": "not found"}, 404)
            return self.send_json(widget(d))
        self.send_html(page(ds))


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
