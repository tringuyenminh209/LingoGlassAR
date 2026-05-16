# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LingoGlass AR là kính hiển thị phụ đề và bản dịch thời gian gần thực cho du lịch và giao tiếp đa ngôn ngữ. Đây là dự án **solo founder + AI agents**, hiện ở giai đoạn lập kế hoạch và chuẩn bị prototype.

Kiến trúc MVP: điện thoại làm gateway (thu âm, OCR, kết nối cloud) → Cloud AI (STT/dịch/OCR) → ESP32-S3 controller → Micro-OLED/waveguide display.

## Tài liệu hiện có

| File | Nội dung |
|---|---|
| `LingoGlass_AR_Project_Plan.md` | Tổng quan sản phẩm, MVP scope, tech stack, BOM, roadmap, go/no-go criteria |
| `LingoGlass_AR_Strategic_Analysis.md` | Phân tích thị trường, đối thủ, điểm nghẽn kỹ thuật, risk register, KPI pilot |
| `LingoGlass_AR_Development_Plan.md` | V-model phát triển, spike spec, FR/NFR, thiết kế chi tiết firmware/BLE/backend |

## Quyết định kỹ thuật đã được lock

- **Audio MVP**: microphone điện thoại (không phải mic trên kính)
- **Camera OCR**: camera điện thoại (không phải camera trên kính)
- **Kết nối subtitle**: BLE trước, Wi-Fi chỉ là fallback/debug
- **Controller**: ESP32-S3 (ESP-IDF)
- **Backend MVP**: FastAPI hoặc Node.js + WebSocket (không Kubernetes)
- **Privacy indicator**: LED vật lý bắt buộc trong MVP, không chỉ dùng icon trên OLED

## BLE Subtitle Protocol

Binary packet format đã được define:

```
version(1) | message_type(1) | sequence_id(2) | fragment_index(1) |
fragment_count(1) | payload_length(1) | payload(N) | crc8(1)
```

Quy tắc render: chỉ render khi nhận đủ fragment của sequence hiện tại. Sequence mới hơn hủy subtitle cũ chưa hoàn tất. Test trên MTU 20/185/247 bytes.

## Roadmap Solo (ưu tiên dùng)

| Sprint | Thời lượng | Output bắt buộc |
|---|---:|---|
| S0 | 1 tuần | Spike: Phone → BLE → ESP32-S3 → display, pass/fail với log latency |
| S1 | 2 tuần | App gửi subtitle, diagnostics cơ bản |
| S2 | 2-3 tuần | STT + translation benchmark với audio điện thoại |
| S3 | 2 tuần | OCR qua phone camera, hiển thị kết quả trên display |
| S4 | 2-4 tuần | Readability test với AR dev kit hoặc wearable mock |
| S5 | 2-4 tuần | 5-10 người test, report p50/p95, cost |

Mỗi sprint phải làm được bởi 1 người trong thời gian đó. Nếu không, phải cắt scope.

## Ứng viên phần cứng

| Lựa chọn | Dùng để làm gì |
|---|---|
| Waveshare OLED (SSD1306, SPI/I2C) | Spike rẻ nhất cho BLE → ESP32 → text render |
| Brilliant Monocle | AR dev kit (cần xác minh availability trước khi mua) |
| Vuzix Blade/Z100 | Backup software-first nếu custom hardware quá chậm |

**Lưu ý**: Kiểm tra availability và giá thực tế trước khi mua bất kỳ module nào.

## Plan B Spike

| Lỗi | Hướng xử lý |
|---|---|
| BLE latency > 200ms | Tăng MTU, binary packet, giảm subtitle length, fallback Wi-Fi local |
| Fragment lỗi | ACK/NAK, retry theo sequence_id, chỉ render khi đủ fragment |
| ESP32-S3 render không ổn | Đơn giản hóa font/render, thử ESP32-P4/STM32/RP2040 |
| Display không có datasheet | Loại module đó, chỉ dùng module có sample code |
| Waveguide không đọc được | Thử module khác, giảm target ngoài trời, pilot software-first trên Vuzix/Monocle |

## Go/No-Go Criteria

| Hạng mục | Go | No-go |
|---|---|---|
| Latency hội thoại | 1.5-2.5s với câu ngắn | Thường xuyên > 3.5s |
| Hiển thị ngoài trời | Đọc được trong ánh sáng ban ngày vừa | Phải nhìn lâu mới đọc được |
| Pin | 2-4h active, 8h mixed use | Dưới 1h active |
| Nhiệt | Đeo liên tục không nóng khó chịu | Nóng ở vùng thái dương/sống mũi |

## Latency Budget

| Bước | Mục tiêu |
|---|---:|
| VAD/cắt đoạn âm thanh | 100-300ms |
| Upload audio | 100-300ms |
| STT streaming | 500-1,000ms |
| Dịch | 200-600ms |
| Gửi về kính (BLE) | 50-200ms |
| Render display | <100ms |
| **Tổng** | **1.5-2.5s** |

Log p50/p90/p95 — không chỉ đo demo tốt nhất.

## Cloud Cost Pilot (50 users)

Ước tính $100-550 USD/tháng (75-450 AI + 25-100 infra). Đặt hard cap usage và log chi phí theo session trong pilot.
