"""
Webhook bot Telegram: POST /api/tgbot  (Telegram gọi vào)
- /start      -> gửi nút "Kết nối với web" (kèm mã kết nối)
- Dán link    -> bot tự tải bản có tiếng tốt nhất ≤50MB và gửi lại
"""
import html
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import core, web  # noqa: E402

WEBHOOK_SECRET = os.environ.get("TG_WEBHOOK_SECRET", "")


def reply(chat_id, text, buttons=None, html=False):
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if html:
        data["parse_mode"] = "HTML"
    if buttons:
        data["reply_markup"] = {"inline_keyboard": buttons}
    core.tg("sendMessage", json=data)


def on_update(upd):
    msg = upd.get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return
    chat_id, text = chat["id"], (msg.get("text") or "").strip()
    name = (msg.get("from") or {}).get("first_name") or "bạn"

    if text.startswith("/start") or text.startswith("/help"):
        token = core.make_token(chat_id)
        link = f"{core.SITE_URL}/?tg={token}&n={urllib.parse.quote(name)}"
        reply(chat_id,
              f"Chào {html.escape(name)} 👋\nĐây là bot <b>PLT Tải Video</b> của Phát Lộc Tech.\n\n"
              "🔑 <b>Mã kết nối của bạn</b> (chạm để copy, rồi dán vào ô trên web):\n"
              f"<code>{token}</code>\n\n"
              "• Hoặc bấm nút <b>Kết nối với web</b> bên dưới.\n"
              "• Hoặc dán thẳng link Facebook / Douyin / YouTube vào đây, bot gửi video cho bạn.\n\n"
              "Giới hạn: video tối đa 50MB.",
              [[{"text": "🔗 Kết nối với web", "url": link}],
               [{"text": "🛒 Linh kiện máy tính – Phát Lộc Tech", "url": core.SHOP_URL}]], html=True)
        return

    url = core.extract_link(text)
    if not url:
        reply(chat_id, "Bạn dán link video Facebook, Douyin hoặc YouTube vào đây nhé.")
        return

    core.tg("sendChatAction", json={"chat_id": chat_id, "action": "upload_video"})
    code, info = core.get_info(url)
    if not info.get("ok"):
        reply(chat_id, "⚠️ " + info["error"])
        return
    fmt = core.pick_format(info["formats"])
    if not fmt or (fmt.get("filesize") or 0) > core.TG_LIMIT:
        reply(chat_id, "Video lớn hơn 50MB nên bot không gửi được. Bạn tải trên web nhé:",
              [[{"text": "🌐 Mở web tải video", "url": core.SITE_URL}]])
        return
    try:
        core.send_to_chat(chat_id, info, fmt, info["platform"])
    except Exception as e:  # noqa
        reply(chat_id, "⚠️ " + (str(e) if isinstance(e, ValueError) else "Gửi video thất bại, bạn thử lại sau nhé."))


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if WEBHOOK_SECRET and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            return web.send_json(self, 403, {"ok": False})
        try:
            on_update(web.read_json(self))
        except Exception:
            pass  # luôn trả 200 để Telegram không gửi lặp lại
        web.send_json(self, 200, {"ok": True})

    def do_GET(self):
        web.send_json(self, 200, {"ok": True, "bot": core.TG_BOT_USERNAME})
