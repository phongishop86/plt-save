# PLT Tải Video – Web v1.4.0 (build 20261124-0750)

Tính năng: chọn chất lượng có hiện dung lượng → chọn nơi lưu: **Tải về máy** hoặc **Gửi qua Telegram** (bot, ≤50MB).
Góc **Extension** chỉ hiện trên máy tính, file nằm ở `download/plt-taivideo-ext.zip`.

## 1. Tạo bot Telegram (5 phút, miễn phí)
1. Mở Telegram, tìm **@BotFather** → gõ `/newbot`.
2. Đặt tên: `PLT Tải Video`, username ví dụ: `PLT_TaiVideo_bot` (phải kết thúc bằng `bot`).
3. BotFather gửi **token** dạng `123456:ABC...` → lưu lại, **không chia sẻ cho ai**.
4. (Tuỳ chọn) `/setuserpic` để gắn logo PLT, `/setdescription` để ghi giới thiệu.

## 2. Sửa thông tin công ty
Mở `index.html`, tìm khối `CONFIG`: hotline, Zalo, địa chỉ, email.

## 3. Đưa lên GitHub + Vercel
1. Tạo repo `plt-taivideo` trên GitHub → upload toàn bộ file (giữ nguyên thư mục `api`, `lib`, `download`).
2. Vercel → **Add New → Project** → chọn repo → Framework: **Other**.
3. Trước khi bấm Deploy, mở **Environment Variables**, thêm:

| Tên | Giá trị |
|---|---|
| `TG_BOT_TOKEN` | token từ BotFather |
| `TG_BOT_USERNAME` | username bot, không có @ (vd `PLT_TaiVideo_bot`) |
| `LINK_SECRET` | chuỗi ngẫu nhiên dài, tự gõ ~30 ký tự |
| `TG_WEBHOOK_SECRET` | chuỗi ngẫu nhiên khác, chỉ dùng chữ, số, gạch dưới |
| `SITE_URL` | `https://save.phatloctech.vn` |
| `SHOP_URL` | `https://phatloctech.vn` |

4. Bấm **Deploy**.

> Lưu ý: đổi `LINK_SECRET` sau này thì mọi người phải kết nối Telegram lại.

## 4. Nối bot với web (làm 1 lần)
Mở trình duyệt, dán link sau (thay chỗ <...>), nhấn Enter:

```
https://api.telegram.org/bot<TG_BOT_TOKEN>/setWebhook?url=https://save.phatloctech.vn/api/tgbot&secret_token=<TG_WEBHOOK_SECRET>&allowed_updates=["message"]
```
Thấy `"ok":true` là xong. Mở bot, gõ `/start` để thử.

## 5. Gắn tên miền `save.phatloctech.vn`
Vercel → Settings → Domains → thêm `save.phatloctech.vn`. Vào trang quản lý DNS ở **Nhân Hòa** thêm bản ghi **CNAME**: tên `save`, giá trị đúng như Vercel hiện (thường là `cname.vercel-dns.com`).

## Cách người dùng gửi Telegram
1. Chọn chất lượng → bấm **Gửi qua Telegram**.
2. Lần đầu: mở bot → Start → bot gửi **mã kết nối** → copy, dán vào web → web tự gửi video.
3. Lần sau: bấm là gửi luôn.
4. Hoặc dán thẳng link video vào chat với bot.

## Bảo trì
- Lỗi lấy video hàng loạt: Vercel → Deployments → **Redeploy** để cập nhật yt-dlp mới nhất.
- Cập nhật extension: thay file `download/plt-taivideo-ext.zip`.

## Cấu trúc
- `index.html` – giao diện
- `api/info.py` – lấy danh sách chất lượng + đo dung lượng
- `api/tg.py` – web yêu cầu gửi video vào Telegram
- `api/tgbot.py` – webhook của bot (Start, nhận link)
- `lib/core.py` – lõi xử lý chung
- `download/` – extension cho máy tính

## Tải nhanh bằng nút Chia sẻ (v1.4.0)
- **Android**: mở web bằng Chrome → bấm **Cài ứng dụng PLT Save** (hoặc ⋮ → Thêm vào màn hình chính). Sau đó trên Facebook bấm **Chia sẻ → PLT Save**, web tự mở và lấy video.
- **iPhone**: tạo Phím tắt (hướng dẫn ngay trên web, mục "Tải nhanh bằng nút Chia sẻ"), mở link `https://save.phatloctech.vn/?url=<link đã mã hoá>`.
- Web tự đọc tham số `url`, `text`, `title` trên đường dẫn, lấy link video và bấm tải tự động.
- File liên quan: `manifest.webmanifest`, `sw.js`.
