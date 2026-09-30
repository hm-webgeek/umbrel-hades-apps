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
        rows = "".join(
            f"<section><h2>{d['name']}</h2><p>{pretty(d['used'])} / {pretty(d['size'])}</p>"
            f"<p>{pretty(d['avail'])} left</p></section>"
            for d in ds
        ) or "<p>No external disks mounted.</p>"
        self.send_html(
            "<!doctype html><meta charset=utf-8><title>External disks</title>"
            "<style>body{font-family:system-ui;background:#111;color:#eee;padding:32px}"
            "h1{font-size:22px}section{margin:0 0 28px}p{opacity:.85}</style>"
            f"<h1>External disks</h1>{rows}"
        )


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
