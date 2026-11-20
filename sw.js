// PLT Save – service worker tối giản (cần để cài ứng dụng & nhận link từ nút Chia sẻ)
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {}); // không lưu cache, luôn lấy bản mới nhất
