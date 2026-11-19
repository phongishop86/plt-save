"""
Lõi xử lý chung - PLT Tải Video v1.1.0
- Lấy link tải (Facebook, YouTube qua yt-dlp; Douyin tự xử lý)
- Đo dung lượng từng chất lượng
- Tải file tạm và gửi qua bot Telegram
- Mã kết nối Telegram (ký HMAC, không cần cơ sở dữ liệu)
"""
import base64
import hashlib
import hmac
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor

import requests
import yt_dlp

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

TG_LIMIT = 50 * 1024 * 1024          # bot Telegram gửi tối đa 50MB
TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_BOT_USERNAME = os.environ.get("TG_BOT_USERNAME", "PLT_TaiVideo_bot")
LINK_SECRET = os.environ.get("LINK_SECRET", "doi-chuoi-bi-mat-nay")
SITE_URL = os.environ.get("SITE_URL", "https://v-save.phatloctech.vn").rstrip("/")
SHOP_URL = os.environ.get("SHOP_URL", "https://phatloctech.vn")

PROMO = (f"📥 Tải bởi PLT Tải Video – {SITE_URL.replace('https://', '')}\n"
         f"🛒 Linh phụ kiện máy tính, dịch vụ tin học: {SHOP_URL.replace('https://', '')}")


def detect_platform(url: str) -> str:
    u = url.lower()
    if "douyin.com" in u or "iesdouyin.com" in u:
        return "douyin"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "facebook.com" in u or "fb.watch" in u or "fb.com" in u:
        return "facebook"
    return "other"


def ua_for(platform):
    return MOBILE_UA if platform == "douyin" else DESKTOP_UA


# ---------------- DOUYIN ----------------
def _http_get(url, ua=MOBILE_UA):
    r = requests.get(url, headers={"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9"},
                     timeout=15, allow_redirects=True)
    return r.url, r.text


def douyin_info(url: str):
    final_url, _ = _http_get(url)
    m = (re.search(r"/video/(\d+)", final_url) or re.search(r"modal_id=(\d+)", final_url)
         or re.search(r"/video/(\d+)", url) or re.search(r"modal_id=(\d+)", url))
    if not m:
        raise ValueError("Không tìm thấy mã video Douyin trong link.")
    vid = m.group(1)
    _, html = _http_get(f"https://www.iesdouyin.com/share/video/{vid}/")
    m = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        raise ValueError("Douyin đổi cấu trúc trang hoặc video bị ẩn.")
    data = json.loads(m.group(1))
    item = None
    for val in data.get("loaderData", {}).values():
        if isinstance(val, dict) and val.get("videoInfoRes"):
            lst = val["videoInfoRes"].get("item_list") or []
            if lst:
                item = lst[0]
                break
    if not item:
        raise ValueError("Video Douyin không tồn tại hoặc đã bị xóa.")
    video = item.get("video", {})
    play = (video.get("play_addr", {}).get("url_list") or [None])[0]
    if not play:
        raise ValueError("Không lấy được link phát của video Douyin.")
    play_nowm = play.replace("playwm", "play")
    h = video.get("height")
    formats = [{"label": f"Không logo {h or ''}p".replace(" p", ""), "url": play_nowm, "ext": "mp4",
                "kind": "av", "height": h, "filesize": None}]
    if play_nowm != play:
        formats.append({"label": "Có logo", "url": play, "ext": "mp4",
                        "kind": "av", "height": h, "filesize": None})
    music = (item.get("music", {}).get("play_url", {}).get("url_list") or [None])[0]
    if music:
        formats.append({"label": "Nhạc nền MP3", "url": music, "ext": "mp3",
                        "kind": "audio", "height": None, "filesize": None})
    return {"title": item.get("desc") or f"douyin_{vid}",
            "thumbnail": (video.get("cover", {}).get("url_list") or [None])[0],
            "duration": round((video.get("duration") or 0) / 1000) or None,
            "formats": formats}


# ---------------- FACEBOOK / YOUTUBE ----------------
def ytdlp_info(url: str):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            "socket_timeout": 15, "http_headers": {"User-Agent": DESKTOP_UA}, "cachedir": False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)

    out = []
    for f in info.get("formats") or []:
        furl, proto = f.get("url"), f.get("protocol") or ""
        if not furl or not proto.startswith("http"):
            continue
        v = f.get("vcodec") not in (None, "none")
        a = f.get("acodec") not in (None, "none")
        kind = "av" if (v and a) else ("video" if v else ("audio" if a else None))
        if not kind:
            continue
        h, ext = f.get("height"), f.get("ext") or "mp4"
        if kind == "audio":
            abr = f.get("abr")
            label = f"Âm thanh {ext.upper()}" + (f" {int(abr)}k" if abr else "")
        else:
            q = f"{h}p" if h else (f.get("format_note") or f.get("format_id") or "").upper()
            label = q + ("" if kind == "av" else " (không tiếng)")
        out.append({"label": label, "url": furl, "ext": ext, "kind": kind, "height": h,
                    "filesize": f.get("filesize") or f.get("filesize_approx")})

    order = {"av": 0, "video": 1, "audio": 2}
    out.sort(key=lambda x: (order[x["kind"]], -(x["height"] or 0), -(x["filesize"] or 0)))
    seen, formats = set(), []
    for f in out:
        key = (f["kind"], f["height"], f["ext"]) if f["kind"] != "audio" else ("audio",)
        if key in seen:
            continue
        seen.add(key)
        formats.append(f)
    formats = formats[:8]
    if not formats and info.get("url"):
        formats = [{"label": "Video", "url": info["url"], "ext": info.get("ext", "mp4"),
                    "kind": "av", "height": info.get("height"), "filesize": None}]
    return {"title": info.get("title"), "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"), "formats": formats}


# ---------------- ĐO DUNG LƯỢNG ----------------
def probe_size(url, platform):
    hdr = {"User-Agent": ua_for(platform)}
    try:
        r = requests.head(url, headers=hdr, timeout=6, allow_redirects=True)
        n = int(r.headers.get("Content-Length") or 0)
        if r.ok and n > 1024:
            return n
    except Exception:
        pass
    try:
        r = requests.get(url, headers={**hdr, "Range": "bytes=0-0"}, timeout=6, stream=True, allow_redirects=True)
        cr = r.headers.get("Content-Range", "")
        r.close()
        m = re.search(r"/(\d+)$", cr)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def fill_sizes(formats, platform):
    need = [f for f in formats if not f.get("filesize")]
    if not need:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f, n in zip(need, ex.map(lambda f: probe_size(f["url"], platform), need)):
            f["filesize"] = n
    for f in formats:
        f["filesize"] = int(f["filesize"]) if f.get("filesize") else None


# ---------------- XỬ LÝ CHÍNH ----------------
def extract_link(text: str):
    text = (text or "").strip()
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None


def get_info(raw: str, with_size=True):
    """Trả (mã http, dữ liệu)."""
    url = extract_link(raw)
    if not url:
        return 400, {"ok": False, "error": "Vui lòng dán link video hợp lệ."}
    platform = detect_platform(url)
    if platform == "other":
        return 400, {"ok": False, "error": "Hiện hỗ trợ Facebook, Douyin, YouTube."}
    try:
        data = douyin_info(url) if platform == "douyin" else ytdlp_info(url)
        if not data["formats"]:
            return 422, {"ok": False, "error": "Không tìm thấy định dạng tải được."}
        if with_size:
            fill_sizes(data["formats"], platform)
        for f in data["formats"]:
            f["tg_ok"] = bool(f.get("filesize")) and f["filesize"] <= TG_LIMIT
        return 200, {"ok": True, "platform": platform, "link": url, "tg_limit": TG_LIMIT, **data}
    except Exception as e:  # noqa
        return 422, {"ok": False, "platform": platform, "error": friendly_error(e)}


def friendly_error(e: Exception) -> str:
    low = str(e).lower()
    if "sign in to confirm" in low or "not a bot" in low:
        return "YouTube đang chặn máy chủ tạm thời. Vui lòng thử lại sau ít phút."
    if "private" in low or "login" in low or "log in" in low or "cookies" in low:
        return "Video riêng tư hoặc cần đăng nhập. Chỉ tải được video công khai."
    if "unsupported url" in low:
        return "Link không hợp lệ hoặc chưa hỗ trợ."
    if "timed out" in low or "timeout" in low:
        return "Nền tảng phản hồi chậm, vui lòng thử lại."
    if isinstance(e, ValueError):
        return str(e)
    return "Không lấy được video. Kiểm tra link có công khai không rồi thử lại."


# ---------------- MÃ KẾT NỐI TELEGRAM ----------------
def make_token(chat_id: int) -> str:
    cid = str(chat_id)
    sig = hmac.new(LINK_SECRET.encode(), cid.encode(), hashlib.sha256).hexdigest()[:20]
    return base64.urlsafe_b64encode(cid.encode()).decode().rstrip("=") + "." + sig


def read_token(token: str):
    try:
        b, sig = token.split(".", 1)
        cid = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        good = hmac.new(LINK_SECRET.encode(), cid.encode(), hashlib.sha256).hexdigest()[:20]
        return int(cid) if hmac.compare_digest(good, sig) else None
    except Exception:
        return None


# ---------------- TELEGRAM ----------------
def tg(method, **kw):
    if not TG_TOKEN:
        raise RuntimeError("Chưa cấu hình TG_BOT_TOKEN trên Vercel.")
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", timeout=55, **kw)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(j.get("description", "Telegram báo lỗi"))
    return j["result"]


def download_tmp(url, platform, ext):
    """Tải file về /tmp, dừng nếu quá 50MB. Trả đường dẫn."""
    fd, path = tempfile.mkstemp(suffix="." + ext, dir="/tmp")
    total = 0
    with requests.get(url, headers={"User-Agent": ua_for(platform)}, stream=True, timeout=20) as r, \
            os.fdopen(fd, "wb") as f:
        r.raise_for_status()
        for chunk in r.iter_content(1024 * 256):
            total += len(chunk)
            if total > TG_LIMIT:
                f.close()
                os.remove(path)
                raise ValueError("Video lớn hơn 50MB, bot Telegram không gửi được. Vui lòng chọn chất lượng thấp hơn hoặc tải về máy.")
            f.write(chunk)
    return path


def safe_name(s):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", s or "video")
    return re.sub(r"\s+", " ", s).strip()[:60] or "video"


def send_to_chat(chat_id, info, fmt, platform):
    title = info.get("title") or "Video"
    path = download_tmp(fmt["url"], platform, fmt["ext"])
    try:
        caption = f"🎬 {title[:300]}\n🎞 {fmt['label']}\n\n{PROMO}"
        fname = f"{safe_name(title)}_{safe_name(fmt['label'])}.{fmt['ext']}"
        with open(path, "rb") as fh:
            if fmt["kind"] == "audio":
                tg("sendAudio", data={"chat_id": chat_id, "caption": caption, "title": title[:60]},
                   files={"audio": (fname, fh)})
            elif fmt["ext"] == "mp4":
                tg("sendVideo", data={"chat_id": chat_id, "caption": caption, "supports_streaming": "true"},
                   files={"video": (fname, fh)})
            else:
                tg("sendDocument", data={"chat_id": chat_id, "caption": caption},
                   files={"document": (fname, fh)})
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def pick_format(formats, label=None):
    """Chọn theo nhãn người dùng chọn, hoặc bản có tiếng tốt nhất ≤50MB."""
    if label:
        for f in formats:
            if f["label"] == label:
                return f
    cands = [f for f in formats if f["kind"] == "av" and (f.get("filesize") or 0) <= TG_LIMIT]
    cands = [f for f in cands if f.get("filesize")] or cands
    return cands[0] if cands else None
