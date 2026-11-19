"""Tiện ích nhỏ cho các hàm Vercel: đọc body, trả JSON."""
import json
import urllib.parse


def read_json(h):
    try:
        n = int(h.headers.get("Content-Length") or 0)
        return json.loads(h.rfile.read(n) or b"{}")
    except Exception:
        return {}


def query(h):
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query).items()}


def send_json(h, code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    h.wfile.write(body)
