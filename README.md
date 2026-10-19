# 💃 Dance Cover Universe (dancecoveruni)

Hệ thống tự động hóa tìm kiếm video Douyin/TikTok (9:16 Shorts) theo chủ đề Dance Cover, kiểm duyệt chất lượng bằng Gemini Vision, tải lên kênh **YouTube Shorts** và sao lưu qua **Telegram Bot**, vận hành tự động theo lịch cron hàng ngày trên **GitHub Actions**.

---

## 🚀 Luồng Hoạt Động (Pipeline Flow)

1. **Khởi tạo Từ khóa**:
   - Tự động kiểm tra tin nhắn gần nhất từ Telegram Bot (nếu bạn gửi từ khóa qua lệnh `/kw <tên bài hát/vũ đạo>`).
   - Nếu không có, **Gemini Flash** tự động sinh 6-8 từ khóa tiếng Trung thịnh hành dựa trên danh mục trong `config/channel_config.json`.
2. **Tìm kiếm & Cào URL**:
   - Sử dụng **Jina Search** (`s.jina.ai`) & **Firecrawl API** truy vấn Google Dorking: `site:douyin.com/video/ "<keyword>"`.
   - Trích xuất URL video và lọc trùng với `data/history.json`.
3. **Tải Video & Kiểm Duyệt Chất Lượng**:
   - Dùng **`yt-dlp`** tải video MP4 dọc (9:16).
   - Dùng **`ffmpeg`** bóc tách các frame mẫu gửi cho **Gemini Vision** kiểm định 4 tiêu chuẩn (đúng biểu diễn vũ đạo, không ảnh tĩnh/nói chuyện, không có watermark che người, nội dung an toàn). Có cơ chế sleep chống lỗi rate limit RPM.
4. **Phân Phối & Quản Lý Quota (Tối đa 6 video/ngày = 9,600 units)**:
   - **3 video đầu tiên**: Đăng công khai (**Public**) ngay trong ngày theo các mốc thời gian cách nhau.
   - **3 video tiếp theo**: Đặt lịch hẹn giờ (**Scheduled**) tự động publish vào ngày mai.
   - Gửi video MP4 và thông tin đăng tải về **Telegram Bot** để lưu trữ dự phòng.
5. **Cập nhật Lịch sử**:
   - Lưu các video đã đăng vào `data/history.json` và GitHub Actions bot tự động commit lại repo.

---

## 🛠️ Hướng Dẫn Khởi Tạo Git & Đẩy Lên GitHub

Mở terminal tại thư mục này (`dancecoveruni`) và chạy các lệnh:

```bash
# 1. Khởi tạo Git repository
git init

# 2. Thêm toàn bộ file dự án
git add .

# 3. Tạo commit đầu tiên
git commit -m "feat: initial dancecoveruni automated pipeline"

# 4. Đổi tên nhánh chính thành main
git branch -M main

# 5. Kết nối với remote repository trên GitHub của bạn
git remote add origin https://github.com/<USERNAME>/<REPO_NAME>.git

# 6. Đẩy code lên GitHub
git push -u origin main
```

---

## 🔐 Cấu Hình GitHub Actions Secrets

Sau khi đẩy repo lên GitHub, bạn vào:
**Settings > Secrets and variables > Actions > New repository secret** và thêm 7 biến sau:

| Secret Name | Mô tả | Nguồn lấy |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Key AI Studio để sinh từ khóa & kiểm duyệt video | [Google AI Studio](https://aistudio.google.com/) (Free tier RPD cao) |
| `JINA_API_KEY` | Key tìm kiếm Google Dorking qua Jina Search | [Jina AI](https://jina.ai/) (hoặc để trống nếu dùng rate limit mặc định) |
| `FIRECRAWL_API_KEY` | Key tìm kiếm phụ trợ Firecrawl (tùy chọn) | [Firecrawl](https://www.firecrawl.dev/) |
| `TELEGRAM_BOT_TOKEN`| Token của Bot gửi thông báo & sao lưu video | Tạo qua `@BotFather` trên Telegram |
| `TELEGRAM_CHAT_ID`  | Chat ID của nhóm/kênh nhận video | Lấy qua bot `@userinfobot` hoặc `@getmyid_bot` |
| `YOUTUBE_CLIENT_ID` | OAuth 2.0 Client ID | Google Cloud Console (YouTube Data API v3) |
| `YOUTUBE_CLIENT_SECRET` | OAuth 2.0 Client Secret | Google Cloud Console |
| `YOUTUBE_REFRESH_TOKEN` | Refresh Token để tự động gia hạn quyền upload | Lấy một lần qua OAuth Playground hoặc script OAuth local |

---

## ⚙️ Tùy Chỉnh Kênh (`config/channel_config.json`)

Bạn có thể chỉnh sửa file `config/channel_config.json` trực tiếp trên GitHub:
- `title_template`: Mẫu tiêu đề YouTube Shorts (hỗ trợ `{detected_dance}`, `{author_name}`).
- `description_template`: Mẫu mô tả kèm credit tác giả Douyin/TikTok.
- `tags`: Danh sách hashtag mặc định.
- `seed_categories`: Danh mục vũ đạo ưu tiên tìm kiếm.
- `schedule`: Cấu hình số lượng video và giãn cách giờ đăng.

---

## 📲 Gửi Từ Khóa Thủ Công Qua Telegram

Trong ngày nếu bạn muốn kênh đăng một bài hát/vũ đạo Douyin cụ thể, chỉ cần gửi tin nhắn cho Telegram Bot của bạn với cú pháp:
```
/kw Tên bài hát hoặc điệu nhảy tiếng Trung
```
Pipeline khi chạy vào khung giờ cron sẽ ưu tiên tìm kiếm theo từ khóa này trước tiên!
