"""GET /api/info?url=...  |  POST /api/info {"url": "..."}  -> danh sách chất lượng + dung lượng"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import core, web  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        web.send_json(self, *core.get_info(web.query(self).get("url", "")))

    def do_POST(self):
        web.send_json(self, *core.get_info(web.read_json(self).get("url", "")))
