"""
GET /api/dl?d=...&s=...  -> máy chủ ghép hình + tiếng và TRUYỀN THẲNG file MP4 về trình duyệt (streaming).
Link được /api/info ký sẵn (HMAC), hết hạn sau 2 giờ, chỉ nhận máy chủ video của Facebook/YouTube/Douyin.
"""
import os
import subprocess
import sys
import unicodedata
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import core, web  # noqa: E402

CHUNK = 256 * 1024


def error_page(h, code, msg):
    body = (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<div style='font-family:sans-serif;max-width:480px;margin:60px auto;padding:20px;text-align:center'>"
            f"<h3>⚠️ {msg}</h3><p><a href='/'>← Quay lại trang tải video</a></p></div>").encode()
    h.send_response(code)
    h.send_header("Content-Type", "text/html; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = web.query(self)
        p = core.read_dl(q.get("d"), q.get("s"))
        if not p:
            return error_page(self, 403, "Link tải đã hết hạn. Vui lòng dán lại link video và bấm Tải video.")

        proc = subprocess.Popen(core.stream_merge_cmd(p["v"], p["a"], p.get("p", "")),
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            first = proc.stdout.read(CHUNK)
            if not first:
                proc.kill()
                return error_page(self, 502, "Không ghép được video (link gốc có thể đã hết hạn). Vui lòng thử lại.")
            name = p.get("n") or "video.mp4"
            ascii_name = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
            ascii_name = ascii_name.encode("ascii", "ignore").decode().replace('"', "") or "video.mp4"
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(name)}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(first)
            while True:
                chunk = proc.stdout.read(CHUNK)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # người dùng huỷ tải
        finally:
            if proc.poll() is None:
                proc.kill()
