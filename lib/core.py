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
import subprocess
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
SITE_URL = os.environ.get("SITE_URL", "https://save.phatloctech.vn").rstrip("/")
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
    h, w = video.get("height"), video.get("width")
    q = f"{h}p" if h else ""
    formats = [{"label": f"Video {q} không logo".replace("  ", " "), "url": play_nowm, "ext": "mp4",
                "kind": "av", "height": h, "width": w, "filesize": None}]
    if play_nowm != play:
        formats.append({"label": f"Video {q} có logo".replace("  ", " "), "url": play, "ext": "mp4",
                        "kind": "av", "height": h, "width": w, "filesize": None})
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

    av, vonly, aonly = [], [], []
    for f in info.get("formats") or []:
        furl, proto = f.get("url"), f.get("protocol") or ""
        if not furl or not proto.startswith("http"):
            continue
        vc, ac = f.get("vcodec"), f.get("acodec")
        # yt-dlp: "none" = KHÔNG có; None = không rõ (bản HD/SD Facebook có tiếng thuộc loại này)
        has_v = vc != "none" and not (vc is None and f.get("video_ext") == "none")
        has_a = ac != "none" and not (ac is None and f.get("audio_ext") == "none")
        h, ext = f.get("height"), f.get("ext") or "mp4"
        item = {"url": furl, "ext": ext, "height": h, "width": f.get("width"), "q": f.get("quality") or 0,
                "filesize": f.get("filesize") or f.get("filesize_approx"), "fid": f.get("format_id") or ""}
        if has_v and has_a:
            name = f"Video {h}p" if h else f"Video {item['fid'].upper()}".strip()
            av.append({**item, "kind": "av", "label": name})
        elif has_v:
            vonly.append({**item, "kind": "video"})
        elif has_a:
            abr = f.get("abr")
            aonly.append({**item, "kind": "audio", "abr": abr or 0,
                          "label": f"Âm thanh {ext.upper()}" + (f" {int(abr)}k" if abr else "")})

    def dedupe(lst, key):
        seen, res = set(), []
        for x in lst:
            k = key(x)
            if k not in seen:
                seen.add(k)
                res.append(x)
        return res

    av.sort(key=lambda x: (-(x["height"] or 0), -x["q"], -(x["filesize"] or 0)))
    av = dedupe(av, lambda x: x["label"])[:4]
    # âm thanh tốt nhất, ưu tiên m4a (ghép vào mp4 được)
    aonly.sort(key=lambda x: (x["ext"] != "m4a", -x["abr"], -(x["filesize"] or 0)))
    best_audio = aonly[0] if aonly else None

    # Bản GHÉP hình + tiếng (máy chủ ghép, gửi qua Telegram): chỉ cho độ phân giải cao hơn bản có sẵn tiếng
    merged = []
    if best_audio:
        top_av = max([x["height"] or 0 for x in av] or [0])
        vonly.sort(key=lambda x: (x["ext"] != "mp4", -(x["height"] or 0), -(x["filesize"] or 0)))
        for v in dedupe(vonly, lambda x: x["height"]):
            if (v["height"] or 0) > top_av and v["ext"] == "mp4" and best_audio["ext"] == "m4a":
                size = (v["filesize"] + best_audio["filesize"]) if v["filesize"] and best_audio["filesize"] else None
                merged.append({"kind": "merge", "label": f"Video {v['height']}p", "ext": "mp4",
                               "height": v["height"], "width": v.get("width"), "url": "", "video_url": v["url"],
                               "audio_url": best_audio["url"], "filesize": size,
                               "v_size": v["filesize"], "a_size": best_audio["filesize"]})
        # đã có bản sẵn tiếng: chỉ thêm 1 bản ghép cao nhất; chưa có: tối đa 3 bản
        merged = merged[:1] if av else merged[:3]

    formats = av + merged + ([best_audio] if best_audio else [])
    for f in formats:
        for k in ("q", "fid", "abr"):
            f.pop(k, None)
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
    jobs = []  # (format, khoá dung lượng, url)
    for f in formats:
        if f.get("filesize"):
            continue
        if f["kind"] == "merge":
            if not f.get("v_size"):
                jobs.append((f, "v_size", f["video_url"]))
            if not f.get("a_size"):
                jobs.append((f, "a_size", f["audio_url"]))
        else:
            jobs.append((f, "filesize", f["url"]))
    if jobs:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for (f, key, _), n in zip(jobs, ex.map(lambda j: probe_size(j[2], platform), jobs)):
                f[key] = n
    for f in formats:
        if f["kind"] == "merge" and not f.get("filesize") and f.get("v_size") and f.get("a_size"):
            f["filesize"] = f["v_size"] + f["a_size"]
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


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def merge_av(video_path, audio_path):
    """Ghép hình + tiếng, không mã hoá lại (rất nhanh)."""
    out = video_path.rsplit(".", 1)[0] + "_merged.mp4"
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", video_path, "-i", audio_path,
           "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, timeout=40)
    if r.returncode != 0 or not os.path.exists(out):
        raise ValueError("Ghép hình và tiếng thất bại, vui lòng chọn chất lượng khác.")
    if os.path.getsize(out) > TG_LIMIT:
        os.remove(out)
        raise ValueError("Video sau khi ghép lớn hơn 50MB, vui lòng chọn chất lượng thấp hơn.")
    return out


def send_to_chat(chat_id, info, fmt, platform):
    title = info.get("title") or "Video"
    paths = []
    try:
        if fmt["kind"] == "merge":
            v = download_tmp(fmt["video_url"], platform, "mp4"); paths.append(v)
            a = download_tmp(fmt["audio_url"], platform, "m4a"); paths.append(a)
            path = merge_av(v, a); paths.append(path)
        else:
            path = download_tmp(fmt["url"], platform, fmt["ext"]); paths.append(path)
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
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass


def pick_format(formats, label=None):
    """Chọn theo nhãn người dùng chọn, hoặc bản CÓ TIẾNG tốt nhất ≤50MB (sẵn tiếng trước, rồi bản ghép)."""
    if label:
        for f in formats:
            if f["label"] == label:
                return f
    for kind in ("av", "merge"):
        c = [f for f in formats if f["kind"] == kind and f.get("filesize") and f["filesize"] <= TG_LIMIT]
        if c:
            return c[0]
    c = [f for f in formats if f["kind"] == "av"]
    return c[-1] if c else None
