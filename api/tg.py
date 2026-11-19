"""
POST /api/tg  {"link": "<link video gốc>", "label": "<nhãn chất lượng>", "token": "<mã kết nối>"}
Máy chủ lấy lại link (tránh link hết hạn), tải file ≤50MB rồi gửi vào Telegram của người dùng.
GET  /api/tg  -> trả tên bot để web tạo nút kết nối.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import core, web  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        web.send_json(self, 200, {"bot": core.TG_BOT_USERNAME, "ready": bool(core.TG_TOKEN)})

    def do_POST(self):
        body = web.read_json(self)
        chat_id = core.read_token(body.get("token", ""))
        if not chat_id:
            return web.send_json(self, 401, {"ok": False, "need_connect": True,
                                             "error": "Chưa kết nối Telegram hoặc mã kết nối không hợp lệ."})
        code, info = core.get_info(body.get("link", ""), with_size=False)
        if not info.get("ok"):
            return web.send_json(self, code, info)
        fmt = core.pick_format(info["formats"], body.get("label"))
        if not fmt:
            return web.send_json(self, 422, {"ok": False, "error": "Không tìm thấy chất lượng đã chọn."})
        try:
            core.send_to_chat(chat_id, info, fmt, info["platform"])
            return web.send_json(self, 200, {"ok": True})
        except Exception as e:  # noqa
            msg = str(e)
            if "chat not found" in msg.lower() or "blocked" in msg.lower():
                return web.send_json(self, 401, {"ok": False, "need_connect": True,
                                                 "error": "Bot chưa được mở hoặc đã bị chặn. Vui lòng kết nối lại."})
            return web.send_json(self, 422, {"ok": False, "error": msg if isinstance(e, ValueError) else
                                             "Gửi Telegram thất bại, vui lòng thử lại hoặc chọn chất lượng thấp hơn."})
