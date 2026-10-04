#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import posixpath

ROOT = "/mnt/external"
PREFERRED = "IRONWOLF-01"
PORT = 3000


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


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storage</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
    color: #fff;
    background:
      radial-gradient(1200px 800px at 20% 10%, #1b3a5c 0%, transparent 55%),
      radial-gradient(900px 700px at 90% 80%, #3a1848 0%, transparent 50%),
      #0b0d12;
  }
  .backdrop {
    min-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    background: rgba(0,0,0,.45);
  }
  .glass {
    background-color: #ffffff08;
    border: .1px solid #ffffff0a;
    box-shadow: 0 4px 8px #0000001a, inset 0 1px #ffffff14, inset 0 .5px #ffffff07, inset 0 -1px #0000001f;
    backdrop-filter: blur(8px) saturate(1.7) brightness(1.3);
    -webkit-backdrop-filter: blur(8px) saturate(1.7) brightness(1.3);
    background-image: linear-gradient(#ffffff0d,#ffffff0d);
  }
  .panel {
    width: min(420px, 100%);
    border-radius: 24px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .head h1 {
    margin: 0;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -.04em;
    opacity: .9;
  }
  .close {
    width: 28px;
    height: 28px;
    border: 0;
    border-radius: 999px;
    background: #ffffff24;
    color: #fff;
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    display: grid;
    place-items: center;
    padding: 0;
  }
  .close:hover { background: #ffffff3d; }
  .tabs { display: flex; flex-wrap: wrap; gap: 8px; }
  .tab {
    border: 0;
    background: #ffffff14;
    color: #ffffff99;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: -.02em;
    cursor: pointer;
  }
  .tab[aria-selected="true"] { background: #ffffff2e; color: #fff; }
  .card { display: flex; flex-direction: column; gap: 8px; padding-bottom: 8px; }
  .label { font-size: 13px; font-weight: 500; letter-spacing: -.02em; color: #ffffff66; }
  .value-row { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
  .value { font-size: 20px; font-weight: 600; letter-spacing: -.03em; line-height: 1; }
  .sub { font-size: 13px; font-weight: 600; color: #ffffff73; }
  .left { font-size: 12px; letter-spacing: -.02em; color: #ffffff40; }
  .bar {
    position: relative;
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
    width: 0;
  }
  .list {
    border-radius: 24px;
    overflow: hidden;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    border: 0;
    background: transparent;
    color: inherit;
    padding: 12px;
    border-bottom: 1px solid #ffffff0f;
    cursor: pointer;
    text-align: left;
    font: inherit;
  }
  .row:last-child { border-bottom: 0; }
  .row[aria-current="true"] { background: #ffffff0a; }
  .icon {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: #ffffff1f;
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }
  .icon svg { display: block; }
  .row-name {
    min-width: 0;
    flex: 1;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -.04em;
    opacity: .9;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mini {
    height: 4px;
    width: 96px;
    flex-shrink: 0;
    overflow: hidden;
    border-radius: 999px;
    background: #ffffff1a;
  }
  .mini > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: #ffffff59;
  }
  .row-used {
    flex-shrink: 0;
    min-width: 76px;
    text-align: right;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -.03em;
    color: #ffffff73;
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
  }
  .empty { margin: 0; font-size: 13px; color: #ffffff80; }
</style>
<body>
  <div class="backdrop">
    <section class="glass panel" role="dialog" aria-labelledby="title">
      <div class="head">
        <h1 id="title">Storage</h1>
        <button class="close" type="button" aria-label="Close" onclick="window.close()">×</button>
      </div>
      <div id="body"></div>
    </section>
  </div>
<script>
const DISKS = __DISKS__;
const PREFERRED = __PREFERRED__;

function fill(el, p) {
  el.style.width = Math.max(0, Math.min(100, p * 100)) + "%";
}

function icon() {
  return `<span class="icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="10" rx="2" fill="white"/><rect x="4" y="5.5" width="8" height="2" rx="1" fill="#ffffff55"/><circle cx="11" cy="10" r="1.1" fill="#0b0d12"/></svg></span>`;
}

function render(name) {
  const root = document.getElementById("body");
  if (!DISKS.length) {
    root.innerHTML = `<p class="empty">No external disks mounted.</p>`;
    return;
  }
  const selected = DISKS.find(d => d.name === name) || DISKS.find(d => d.name === PREFERRED) || DISKS[0];
  const tabs = DISKS.map(d =>
    `<button class="tab" type="button" aria-selected="${d.name === selected.name}" data-name="${d.name}">${d.name}</button>`
  ).join("");
  const rows = DISKS.map(d =>
    `<button class="row" type="button" aria-current="${d.name === selected.name}" data-name="${d.name}">
      ${icon()}
      <span class="row-name">${d.name}</span>
      <span class="mini"><span style="width:${Math.max(0, Math.min(100, d.progress * 100))}%"></span></span>
      <span class="row-used">${d.used}</span>
    </button>`
  ).join("");
  root.innerHTML = `
    <div class="tabs">${tabs}</div>
    <div class="card">
      <div class="label">${selected.name}</div>
      <div class="value-row"><span class="value">${selected.used}</span><span class="sub">/ ${selected.size}</span></div>
      <div class="left">${selected.avail} left</div>
      <div class="bar"><span id="mainbar"></span></div>
    </div>
    <div class="glass list">${rows}</div>`;
  fill(document.getElementById("mainbar"), selected.progress);
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

const start = new URLSearchParams(location.search).get("disk");
render(start);
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

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, code=200):
        body = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = posixpath.normpath(self.path.split("?", 1)[0])
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
