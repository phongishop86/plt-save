# PLT Tải Video – Web v1.1.0 (build 20261119-1105)

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
| `SITE_URL` | `https://v-save.phatloctech.vn` |
| `SHOP_URL` | `https://phatloctech.vn` |

4. Bấm **Deploy**.

> Lưu ý: đổi `LINK_SECRET` sau này thì mọi người phải kết nối Telegram lại.

## 4. Nối bot với web (làm 1 lần)
Mở trình duyệt, dán link sau (thay chỗ <...>), nhấn Enter:

```
https://api.telegram.org/bot<TG_BOT_TOKEN>/setWebhook?url=https://v-save.phatloctech.vn/api/tgbot&secret_token=<TG_WEBHOOK_SECRET>&allowed_updates=["message"]
```
Thấy `"ok":true` là xong. Mở bot, gõ `/start` để thử.

## 5. Gắn tên miền `v-save.phatloctech.vn`
Vercel → Settings → Domains → thêm `v-save.phatloctech.vn`. Ở nơi quản lý tên miền thêm bản ghi **CNAME**: tên `v-save`, giá trị `cname.vercel-dns.com`.

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
