# Ke hoach du an LingoGlass AR

## 1. Tom tat san pham

LingoGlass AR la kinh hien thi phu de va ban dich theo thoi gian gan thuc cho du lich, hoc tap va giao tiep da ngon ngu. Trong giai doan dau, san pham khong co gang xu ly tat ca tren kinh. Kien truc MVP se la:

- Kinh: hien thi phu de, dieu khien co ban, ket noi khong day.
- Dien thoai: gateway thu am, chup hinh OCR, dieu phoi ket noi.
- Cloud AI: STT, dich, OCR nang, dong bo va phan tich chat luong.

Muc tieu cua MVP la chung minh ba dieu: phu de doc duoc tren kinh, do tre du thap de hoi thoai tu nhien, va pin/nhiet/trong luong phu hop de deo hang ngay.

### Boi canh thuc thi

Day la du an solo, co AI agents dong hanh trong nghien cuu, lap ke hoach, viet tai lieu, ho tro code va test. Vi vay ke hoach phai uu tien prototype nho, automation va pham vi hep.

| Nguyen tac | Cach ap dung |
| --- | --- |
| Solo-first | Moi milestone phai lam duoc boi 1 nguoi trong 1-3 tuan |
| AI-assisted | Dung AI agents de viet spec, sinh test cases, review code, tong hop log |
| Hardware-light | Uu tien dev kit/module co san, tranh custom hardware qua som |
| Evidence-driven | Khong mo rong tinh nang neu chua co log latency/display/power |
| Scope control | Moi giai doan chi co mot cau hoi ky thuat chinh can tra loi |

## 2. Dinh vi san pham

**Dinh vi de xuat:** Kinh phu de thoi gian thuc cho du lich va giao tiep da ngon ngu.

### Khach hang muc tieu

| Nhom khach hang | Van de chinh | Gia tri LingoGlass AR mang lai |
| --- | --- | --- |
| Khach du lich quoc te | Khong doc duoc bien bao, menu, huong dan | Dich OCR va phu de ngan gon ngay trong tam nhin |
| Du hoc sinh/lao dong nuoc ngoai | Kho khan khi giao tiep hang ngay | Phu de hoi thoai, giam phu thuoc vao dien thoai |
| Nhan vien dich vu/ban le | Can phan hoi nhanh voi khach nuoc ngoai | Hien thi cau goi y va ban dich trong luc noi chuyen |
| Doanh nhan di cong tac | Hop/nghe noi da ngon ngu | Phu de song ngu va ghi chu sau cuoc hop |

### Loi the can dat

- Nhanh hon viec cam dien thoai de dich.
- Tu nhien hon thiet bi dich cam tay.
- Nhe va it gay chu y hon kinh AR giai tri.
- Co the dung duoc ngoai troi va trong khong gian cong cong.

## 3. Pham vi MVP

MVP khong nen la mot "he sinh thai AI AR" day du. MVP nen tap trung vao mot luong gia tri cot loi.

### Spike ky thuat bat buoc trong tuan dau

Truoc khi lap roadmap dai, du an phai tra loi mot cau hoi ky thuat toi thieu:

**Phone -> BLE -> ESP32-S3 -> display: text co hien thi on dinh khong?**

| Spike | Muc tieu | Tieu chi pass | Neu fail |
| --- | --- | --- | --- |
| Display connectivity spike | Gui chuoi subtitle ngan tu dien thoai den ESP32-S3 va hien thi tren display that hoac dev display tuong duong | 20 lan gui lien tiep, text dung, khong treo, latency app-to-display <200 ms | Xem lai display module, giao thuc ket noi hoac bo controller |
| BLE packet spike | Gui subtitle 20-100 ky tu qua BLE voi fragmentation | Mat goi <1%, subtitle hien thi dung thu tu | Doi protocol, tang MTU, can nhac Wi-Fi |
| Render stability spike | Cap nhat 1-2 dong subtitle lien tuc trong 5 phut | Khong nhay layout, khong vo font, khong leak memory | Don gian hoa layout/render engine |

### Chuc nang trong MVP

| Chuc nang | Mo ta | Tieu chi chap nhan |
| --- | --- | --- |
| Phu de hoi thoai | Thu am tu dien thoai hoac micro tren kinh, STT va dich sang ngon ngu dich | Do tre end-to-end muc tieu 1.5-2.5 giay |
| Dich van ban qua camera | Chup hinh bang dien thoai, OCR, dich, hien thi ket qua rut gon len kinh | Ket qua doc duoc trong 3 giay cho menu/bien bao |
| Hien thi subtitle tren kinh | Gui text tu app len kinh qua BLE hoac Wi-Fi | Text on dinh, khong nhay layout, doc duoc ngoai troi sang vua |
| Mobile gateway | Quan ly thiet bi, ngon ngu, lich su ban dich, ket noi cloud | App co mot luong demo hoan chinh |
| Logging ky thuat | Ghi do tre, loi API, muc pin, nhiet do | Co dashboard/log de danh gia prototype |

### Chuc nang chua lam trong MVP

- AI agent du lich tu dong dat ban/dat ve.
- Speaker ID trong moi truong dong nguoi.
- Dich offline hoan toan tren kinh.
- Kubernetes/microservices phuc tap.
- Thuong mai hoa hang loat hoac crowdfunding khi chua co prototype that.

## 4. Kien truc ky thuat de xuat

```text
Micro/Mobile Camera
        |
        v
Mobile App Gateway
        |
        +--> Local pre-processing: VAD, compression, frame crop
        |
        v
Cloud AI API
        |
        +--> STT
        +--> Translation
        +--> OCR
        |
        v
Mobile App
        |
        v
LingoGlass Display Controller
        |
        v
Micro-OLED / Waveguide display
```

### Vai tro tung thanh phan

| Thanh phan | Vai tro dung | Khong nen gan vai tro |
| --- | --- | --- |
| ESP32-S3 | Dieu khien display, BLE/Wi-Fi, input, power state, wake-word nhe | STT/OCR/dich thoi gian thuc |
| Dien thoai | Gateway, thu am/chup hinh, xu ly nhe, UI cau hinh | Chi la remote phu |
| Cloud AI | STT/dich/OCR nang, quality routing, logging | He thong microservices phuc tap ngay tu dau |
| Kinh AR | Hien thi phu de ngan gon, trang thai, canh bao | Thay the hoan toan smartphone |

### Quyet dinh MVP can lock som

| Quyet dinh | De xuat cho MVP | Ly do |
| --- | --- | --- |
| Nguon audio | Dung microphone dien thoai trong MVP | Giam rui ro codec/I2S/power/beamforming tren kinh |
| Camera OCR | Dung camera dien thoai trong MVP | Tranh tang pin, nhiet va privacy risk tren kinh |
| Ket noi subtitle | BLE truoc, Wi-Fi chi de debug/fallback | Payload subtitle nho, tiet kiem pin |
| Display module | Chon module co tai lieu interface ro va co the mua ngay | Khong the viet firmware neu chua biet interface |
| Privacy indicator | LED vat ly + indicator tren app/OLED | LED vat ly de nguoi xung quanh nhan biet |

## 5. Tech stack giai doan dau

| Lop | Lua chon de xuat | Ly do |
| --- | --- | --- |
| Firmware | ESP-IDF tren ESP32-S3 | On dinh, ho tro BLE/Wi-Fi, power management |
| Mobile app | Flutter hoac React Native | Lam nhanh app iOS/Android, de demo |
| Backend MVP | Node.js/FastAPI + WebSocket | Don gian, du cho prototype realtime |
| STT | Faster-Whisper cloud hoac API realtime | De thu nghiem do tre/chat luong |
| Translation | OpenAI/DeepL/Google Translate tuy ngon ngu | Co the A/B test chat luong va chi phi |
| OCR | Google Vision API hoac ML Kit cho mobile | Nhanh de prototype, co huong on-device |
| Observability | Log JSON + dashboard don gian | Do latency va loi truoc khi scale |

## 6. Latency budget

| Buoc | Muc tieu MVP | Ghi chu |
| --- | ---: | --- |
| Thu am/VAD | 100-300 ms | Can cat doan am thanh thong minh, tranh doi cau qua dai |
| Upload audio | 100-300 ms | Phu thuoc mang; can nen audio |
| STT | 500-1,000 ms | Yeu cau streaming neu muon hoi thoai tu nhien |
| Dich | 200-600 ms | Cau ngan, context ngan, cache system prompt |
| Gui text ve app/kinh | 50-200 ms | BLE co the du neu payload ngan |
| Render tren display | <100 ms | Text layout phai on dinh |
| **Tong muc tieu** | **1.5-2.5 giay** | Neu vuot 3 giay, trai nghiem hoi thoai giam manh |

## 7. Power budget so bo

Day la muc uoc tinh de thiet ke prototype, can do lai bang phan cung that.

| Thanh phan | Cong suat uoc tinh | Ghi chu |
| --- | ---: | --- |
| ESP32-S3 BLE/Wi-Fi | 80-250 mW | Phu thuoc che do ket noi |
| Micro-OLED + driver | 300-900 mW | Phu thuoc do sang va noi dung |
| Microphone array | 20-100 mW | Tuy so micro va codec |
| Camera/OCR capture | 300-1,000 mW | Neu camera dat tren kinh se tang pin/nhiet dang ke |
| Bone conduction audio | 100-500 mW | Chi bat khi can phat am |
| Misc sensors/power loss | 50-150 mW | Regulator, IMU, LED, hao hut |

Ket luan: muc pin 8-12 gio chi kha thi neu display va Wi-Fi khong hoat dong lien tuc. MVP nen dat muc tieu thuc te hon: 2-4 gio su dung lien tuc hoac 8 gio standby/mixed use.

## 8. BOM uoc tinh cho prototype

| Hang muc | Gia prototype uoc tinh | Ghi chu |
| --- | ---: | --- |
| ESP32-S3 module/dev board | 5-15 USD | Ban san xuat co the re hon |
| Micro-OLED/waveguide module | 150-400+ USD | Rui ro chi phi lon nhat |
| Battery + charging | 10-30 USD | Can tinh an toan va nhiet |
| Microphone/codec | 5-30 USD | Tuy chat luong beamforming |
| Khung/co khi | 30-150 USD | Prototype thu cong rat dat |
| PCB/driver/custom cable | 30-200 USD | Phu thuoc display interface |
| Cloud/API cho demo | 50-500 USD/thang | Phu thuoc so nguoi test |

Muc tieu gia ban 499-699 USD chi nen duoc xac nhan sau khi co BOM san xuat 1,000 units va bao gia module quang hoc thuc te.

## 8.1 Checklist chon display module

Display module la rui ro lon nhat, nen phai chon bang checklist thay vi chi dua vao do phan giai.

| Tieu chi | Cau hoi can tra loi |
| --- | --- |
| Interface | SPI, RGB parallel, LVDS, MIPI hay driver board rieng? ESP32-S3 co dieu khien duoc truc tiep khong? |
| Tai lieu | Co datasheet, timing diagram, init sequence, SDK hoac sample code khong? |
| Do sang | Text co doc duoc ngoai troi sang vua khong? |
| Eyebox | Vung nhin co du rong khi nguoi dung di chuyen/leo kinh khong? |
| Font/text | Co render duoc 1-2 dong text ro o kich thuoc subtitle khong? |
| Power | Display + driver tieu thu bao nhieu mW o do sang thuc dung? |
| Mechanical | Gan duoc vao khung prototype khong, co can can chinh quang hoc phuc tap khong? |
| Availability | Mua duoc 2-5 module trong 2-4 tuan khong? Co bao gia 100/1,000 units khong? |
| Cost | Gia module co lam hong muc tieu BOM khong? |

Quyet dinh chon module phai co truoc khi thiet ke firmware chi tiet.

### Ung vien display/dev kit cho spike

| Lua chon | Vai tro phu hop | Diem manh | Gioi han |
| --- | --- | --- | --- |
| Waveshare 0.49 inch OLED | Spike BLE -> ESP32 -> OLED gia re | Re, co tai lieu SPI/I2C va sample code | Khong phai AR/waveguide, chi test text pipeline |
| Brilliant Monocle | Spike AR dev kit that | Co display 640x400, Bluetooth, camera, microphone | Phu thuoc availability/gia, khong phai custom hardware cua rieng du an |
| Vuzix Blade/Blade 2 SDK | Backup software-first | Co nen tang smart glasses va developer resources | It kiem soat hardware, phu hop pilot app hon la tu thiet ke kinh |

Khuyen nghi solo: bat dau bang Waveshare/SSD1306 hoac display dev module tuong duong de pass pipeline BLE/render trong tuan 1. Sau do moi quyet dinh co dung Brilliant Monocle/Vuzix cho demo AR that hay tiep tuc custom hardware.

## 8.2 BLE subtitle protocol so bo

BLE GATT payload mac dinh co the rat nho, vi vay subtitle khong nen gui nhu chuoi tuy tien.

### Message format de xuat

```text
Header:
  version: 1 byte
  message_type: 1 byte
  sequence_id: 2 bytes
  fragment_index: 1 byte
  fragment_count: 1 byte
  payload_length: 1 byte

Payload:
  UTF-8 text fragment hoac compressed text

Checksum:
  crc8: 1 byte
```

### Nguyen tac

- Subtitle toi da MVP: 100 ky tu.
- App phai chia fragment neu payload vuot MTU.
- Firmware chi render khi nhan du fragment dung sequence.
- Subtitle moi co sequence_id moi; subtitle cu bi huy neu co message moi hon.
- Can test MTU 20 bytes, 185 bytes va 247 bytes de biet latency thuc te.

## 8.3 Privacy indicator design

| Thanh phan | Thiet ke MVP |
| --- | --- |
| LED vat ly | LED nho o mat truoc/canh gong kinh, bat khi audio/camera dang duoc dung |
| App indicator | Banner/trang thai "listening" hoac "camera active" trong app |
| OLED indicator | Icon nho trong goc display de nguoi dung biet dang nghe/chup |
| Privacy mode | Tat history mac dinh, cho phep xoa session |
| Push-to-talk | Nen co trong prototype de tranh ghi am lien tuc |

LED vat ly nen duoc xem la yeu cau MVP, khong phai tinh nang trang tri, vi no anh huong den niem tin nguoi dung va compliance sau nay.

## 8.4 Plan B neu spike fail

| Loi spike | Dau hieu | Plan B |
| --- | --- | --- |
| BLE latency cao | App-to-display >200 ms voi text ngan | Tang MTU, toi uu packet binary, giam subtitle length, fallback Wi-Fi local |
| BLE fragmentation loi | Text dai mat fragment/sai thu tu | Bat ACK/NAK don gian, retry theo sequence_id, gioi han 2 dong text |
| ESP32-S3 render cham/treo | Cap nhat subtitle lien tuc bi freeze | Don gian hoa font/render, dung display driver co buffer, thu ESP32-P4/STM32/RP2040 |
| OLED dev display qua nho | Khong danh gia duoc readability | Van dung de test pipeline, chuyen readability sang AR dev kit/phone mock |
| Micro-OLED/waveguide khong doc duoc | Text mo, eyebox hep, sang ngoai troi kem | Thu module khac, giam target ngoai troi, dung Vuzix/Monocle cho pilot software |
| Display module khong co datasheet | Khong viet duoc driver on dinh | Loai khoi MVP, chi chon module co SDK/sample code |
| Privacy LED kho tich hop | Khung prototype chua co vi tri | Dung LED tren dev board cho spike, sau do chot vi tri tren gong kinh |

Plan B khong duoc mo rong scope. Muc tieu van la chung minh subtitle pipeline nho nhat co the.

## 8.5 Cloud cost model cho pilot

Gia API thay doi theo thoi gian, nen bang nay chi la template tinh chi phi. Can cap nhat bang gia thuc te truoc moi pilot.

### Cong thuc

```text
monthly_cost =
  users
  * sessions_per_user_per_day
  * utterances_per_session
  * 30
  * cost_per_utterance
```

### Uoc tinh pilot 50 nguoi

| Kich ban | Gia tri |
| --- | ---: |
| Users | 50 |
| Sessions/user/day | 1 |
| Utterances/session | 10 |
| Utterances/month | 15,000 |
| Cost/utterance muc thap | 0.005 USD |
| Cost/utterance muc cao | 0.03 USD |
| Cloud AI/month | 75-450 USD |
| Logging/storage/bandwidth buffer | 25-100 USD |
| Tong uoc tinh | 100-550 USD/thang |

De tranh surprise:

- Dat usage cap cho pilot.
- Log cost theo user/session.
- Cache prompts va routing model re hon cho cau ngan.
- Tach chi phi STT, translation, OCR.
- Dung batch/offline cho tom tat sau session, khong dung realtime model dat tien.

## 9. Mo hinh kinh doanh

| Nguon doanh thu | Mo ta | Dieu kien de kha thi |
| --- | --- | --- |
| Ban thiet bi | Kinh + sac + app co ban | BOM, yield va bao hanh duoc kiem soat |
| Goi Premium | STT/dich chat luong cao, do tre thap, lich su/tom tat | Co usage data de tinh gross margin |
| B2B/Enterprise | Ban cho khach san, san bay, truong hoc, cong ty dao tao | Can privacy, admin console, SLA |
| API/SDK | Cho doi tac tich hop hien thi subtitle | Chi nen lam sau khi san pham cot loi on dinh |

## 10. Quyen rieng tu va tuan thu

San pham co camera, micro va xu ly ngon ngu nen can thiet ke privacy tu dau.

| Van de | Huong xu ly de xuat |
| --- | --- |
| Ghi am nguoi xung quanh | Co den/trang thai ro rang khi dang nghe/ghi |
| Luu audio/video | Mac dinh khong luu audio/video tho; chi luu text khi nguoi dung bat |
| Xu ly cloud | Cong bo nha cung cap AI va khu vuc xu ly du lieu |
| Du lieu nhay cam | Co che do xoa lich su, export, tat logging |
| Crowdfunding | Demo bang prototype that, noi ro tinh nang nao da/chua hoat dong |

## 11. Roadmap 12 thang

| Giai doan | Thoi luong | Ket qua can co |
| --- | --- | --- |
| 0. Spike ky thuat toi thieu | 1 tuan | Phone -> BLE -> ESP32-S3 -> display text pass/fail |
| 1. Lam sach tai lieu va spec | 2 tuan | Product brief, technical spec, risk register |
| 2. Prototype hien thi | 4-6 tuan | Text tu app hien thi on dinh tren display |
| 3. Prototype hoi thoai | 6-8 tuan | STT + dich + subtitle voi log latency |
| 4. Prototype OCR | 4-6 tuan | Chup menu/bien bao va hien thi ban dich rut gon |
| 5. Wearable prototype | 8-12 tuan | Khung deo duoc, pin, nhiet, test ngoai troi |
| 6. Pilot nho | 6-8 tuan | 20-50 nguoi test, bao cao loi va usage |
| 7. Quyet dinh crowdfunding | 2-4 tuan | Chi launch neu prototype that dat nguong latency/pin/display |

### Roadmap solo-first rut gon

Neu chi co mot nguoi lam chinh, dung roadmap sau thay cho ke hoach day du:

| Sprint | Thoi luong | Cau hoi can tra loi |
| --- | ---: | --- |
| S0 | 1 tuan | BLE -> ESP32 -> display co chay on dinh khong? |
| S1 | 2 tuan | App co gui subtitle va hien thi diagnostics duoc khong? |
| S2 | 2-3 tuan | STT + translation co dat latency p50 <=2s voi audio dien thoai khong? |
| S3 | 2 tuan | OCR qua camera dien thoai co hien thi ban dich <=3s khong? |
| S4 | 2-4 tuan | Co demo AR/dev kit hoac mock wearable de test readability khong? |
| S5 | 2-4 tuan | 5-10 nguoi test co thay gia tri that khong? |

Muc tieu solo 3 thang: co demo full loop va so lieu ban dau, khong can san pham deo hoan chinh.

## 14. Nguon tham khao phan cung can xac minh

| Hang muc | Nguon |
| --- | --- |
| Waveshare 0.49 inch OLED | https://www.waveshare.net/wiki/0.49inch_OLED_Module |
| Brilliant Monocle hardware | https://docs.brilliant.xyz/monocle/hardware/ |
| Vuzix developer resources | https://support.vuzix.com/docs/developer-resources |
| Vuzix Blade downloads | https://support.vuzix.com/docs/blade-downloads |

Truoc khi mua bat ky module/dev kit nao, can kiem tra lai gia, availability, shipping, license SDK va kha nang lap trinh tu khu vuc hien tai.

## 12. Tieu chi go/no-go

| Hang muc | Go | No-go |
| --- | --- | --- |
| Latency hoi thoai | 1.5-2.5 giay voi cau ngan | Thuong xuyen tren 3.5 giay |
| Hien thi ngoai troi | Doc duoc trong anh sang ban ngay vua | Text kho doc, phai nhin lau |
| Pin | 2-4 gio active hoac 8 gio mixed use | Duoi 1 gio active |
| Nhiet | Deo duoc lien tuc, khong nong kho chiu | Nong o vung thai duong/song mui |
| BOM | Co duong toi gia ban hop ly | Module quang hoc lam gia ban vuot tran |
| Privacy | Co co che thong bao/xoa du lieu | Khong ro dang ghi/luu gi |

## 13. Viec can lam tiep theo

1. Chon mot module display/waveguide co the mua ngay cho prototype.
2. Lam app gateway don gian gui text len kinh/dev board.
3. Do latency pipeline STT -> dich -> display bang cau hoi thoai ngan.
4. Lap BOM va power budget bang so do thuc te.
5. Tao video demo that, khong dung render gay hieu nham.
