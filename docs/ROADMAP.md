# Lộ Trình Phát Triển & Định Hướng Mở Rộng (Roadmap)
## DanceCoverUni Automation Project

Tài liệu này vạch ra các giai đoạn phát triển của hệ thống tự động hóa kênh Dance Cover Universe, phân định rõ ràng giữa những tính năng cốt lõi đang vận hành ngay và các ý tưởng mở rộng nâng cao cho tương lai.

---

## 1. Giai Đoạn 1: Vận Hành Tự Động Hoàn Toàn 100% (Hiện Tại - Ưu Tiên Cao Nhất)

Mục tiêu giai đoạn này là đảm bảo cỗ máy tự động hoạt động ổn định hàng ngày, không cần bất kỳ sự can thiệp thủ công nào từ người dùng.

### A. Chu kỳ phát hành 3/3 liên hoàn (Autonomous 3/3 Publishing Loop)
- **Mỗi ngày sản xuất 6 video hợp lệ**:
  - **3 video xuất bản hôm nay**: Giãn cách theo khung giờ vàng tiếp cận khán giả (ví dụ: ngay lập tức, +4 giờ, +8 giờ).
  - **3 video lên lịch sẵn cho ngày mai**: Đặt lịch phát hành tự động (ví dụ: +24 giờ, +28 giờ, +32 giờ).
- **Vòng lặp kế tiếp**: Khi pipeline chạy chu kỳ ngày tiếp theo, các video của ngày mai đã sẵn sàng phát sóng, và hệ thống tiếp tục cào chuẩn bị cho ngày tiếp theo.
- **Không yêu cầu tương tác thủ công**: Không cần nút duyệt/từ chối trên Telegram Bot. Hệ thống AI Vision tự động thẩm định và phân loại chất lượng dựa trên các tiêu chí khắt khe đã cấu hình.

### B. Tập trung nguồn cào & Chủ đề cốt lõi
- **Nguồn cào chủ lực**: **Douyin** (nguồn chính) và **TikTok** (nguồn bổ trợ khi Douyin thiếu ứng viên).
- **Trọng tâm nội dung**: Vũ đạo, dance cover, choreography của vũ công Châu Á (K-pop, C-pop, Douyin Viral Dance, Street Dance, Hip-hop).
- **Quản lý chủ đề cấu trúc qua `config/topics.json`**:
  - Tách bạch rõ từ khóa tiếng Trung cho Douyin và hashtag cho TikTok.
  - Phân bổ trọng số ưu tiên cho từng thể loại nhảy.
  - Tích hợp từ khóa loại trừ (`negative_keywords`) để lọc bỏ rác (podcast, meme, hướng dẫn nói suông không nhảy).

### C. Quản trị Quota & Cảnh báo an toàn
- Giám sát lượng token Jina API tiêu thụ và token còn lại.
- Tự động phát cảnh báo nổi bật trên Telegram khi token Jina API chỉ còn **<= 1.000.000 tokens** để quản trị viên kịp thời thay thế API Key.

---

## 2. Giai Đoạn 2: Xử Lý Video Nâng Cao & Tối Ưu Trải Nghiệm (Tương Lai)

*(Theo định hướng dự án, các tính năng dưới đây được ghi nhận để phát triển sau khi giai đoạn 1 đã vận hành ổn định trơn tru)*

### A. Xử lý video thông minh (Video Processing & Cleanup)
- **Lọc Watermark Douyin / TikTok**:
  - Tự động nhận diện vùng logo/watermark động ở 4 góc video và làm mờ (blur) hoặc crop nhẹ tỷ lệ 9:16 để đảm bảo tính thẩm mỹ cao nhất trên YouTube Shorts.
- **Cắt bỏ phần thừa (Intro/Outro Trimming)**:
  - Tự động cắt bỏ 2-3 giây đầu hoặc đuôi video nếu người biểu diễn chỉ đứng bấm máy hoặc có màn hình đen kết thúc của app.

### B. Tự động hóa Phụ đề & Âm nhạc (AI Subtitles & Audio Enhancement)
- Nhận diện nhịp điệu (beat) hoặc lời bài hát để chèn hiệu ứng chữ (dynamic animated captions) bắt mắt theo phong cách Shorts/Reels thịnh hành.
- Chuẩn hóa âm lượng (Audio Normalization) bằng `ffmpeg` để tránh hiện tượng video quá to hoặc quá nhỏ khi phát liên tiếp.

### C. Tự động đồng bộ bản vá Upstream `yt-dlp`
- Xây dựng một GitHub Actions workflow định kỳ (chạy hàng tuần hoặc khi có lỗi tải Douyin):
  - Kiểm tra xem upstream `yt-dlp/yt-dlp` đã merge PR #17826 vào bản phát hành chính thức hay chưa.
  - Tự động chuyển đổi giữa nhánh PR của tác giả sang bản release stable khi đã được merge chính thức.
