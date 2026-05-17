# Ke hoach phat trien LingoGlass AR

Tai lieu nay chuyen 6 buoc phat trien trong so do thanh ke hoach thuc thi cho du an LingoGlass AR:

1. Yeu cau phan tich
2. Dinh nghia yeu cau
3. Thiet ke co ban
4. Thiet ke chi tiet
5. Coding
6. Test

Muc tieu la dua du an tu y tuong sang prototype co the demo that, do duoc latency, pin, do doc va tinh kha thi ky thuat.

## Cach thuc thi cho solo founder + AI agents

Du an nay duoc gia dinh la mot nguoi lam chinh, co AI agents ho tro. Vi vay quy trinh phai nho gon hon mot team hardware day du.

| Viec | Nguoi lam chinh | AI agents ho tro |
| --- | --- | --- |
| Chon use case va quyet dinh scope | Founder | Tong hop rui ro, tao checklist, review tradeoff |
| Firmware/display spike | Founder | Sinh protocol spec, test cases, debug checklist |
| Mobile app prototype | Founder | Tao screen flow, code skeleton, test data |
| Backend/AI pipeline | Founder | Viet API spec, benchmark script, phan tich log |
| Test/pilot | Founder | Tao test matrix, tong hop feedback, tao report |
| Tai lieu/pitch | Founder | Bien tap, rut gon, tao bang/roadmap |

Nguyen tac: neu mot milestone can hon 1-3 tuan solo work thi phai cat scope hoac dung dev kit co san.

## Spike ky thuat truoc V-model

Truoc khi vao day du 6 giai doan, du an can mot spike rat nho trong tuan dau:

**Phone -> BLE -> ESP32-S3 -> display: subtitle co hien thi on dinh khong?**

### Pham vi spike

| Hang muc | Noi dung |
| --- | --- |
| Input | Dien thoai hoac script mobile gui subtitle 20-100 ky tu |
| Transport | BLE GATT voi MTU mac dinh va MTU mo rong neu co |
| Controller | ESP32-S3 nhan message, ghep fragment, kiem tra sequence |
| Output | Hien thi 1-2 dong text tren micro-OLED/display dev tuong duong |
| Logging | Do latency app-to-display va loi packet |

### Tieu chi pass/fail

| Tieu chi | Pass |
| --- | --- |
| Do on dinh | 20 subtitle lien tiep hien thi dung |
| Latency | App-to-display <200 ms voi subtitle ngan |
| Fragmentation | Subtitle 100 ky tu hien thi dung thu tu |
| Render | Khong vo layout, khong nhay kich thuoc text |
| Recovery | Mat ket noi va ket noi lai khong treo firmware |

Neu spike fail, phai dung de xem lai display module, BLE protocol hoac controller truoc khi lam cac module AI/backend lon hon.

### Lua chon display cho spike

| Lua chon | Muc dich | Ghi chu |
| --- | --- | --- |
| Waveshare 0.49 inch OLED hoac OLED SPI/I2C tuong duong | Test BLE -> ESP32 -> text render re nhat | Khong dai dien cho AR optics |
| Brilliant Monocle | Test wearable AR nhanh | Co san display/Bluetooth/camera/mic, phu thuoc availability |
| Vuzix Blade/Blade 2/Z100 | Pilot software tren smart glasses | Backup neu custom hardware qua cham |

Quyet dinh thuc te: dung display dev module re de pass spike tuan 1, sau do moi mua/dev kit AR neu pipeline hoat dong.

### Plan B neu spike fail

| Loi | Plan B |
| --- | --- |
| BLE latency qua cao | Tang MTU, binary packet, giam subtitle length, fallback Wi-Fi local |
| Fragmentation loi | ACK type=0x03 voi status code (0x01 OK / 0x03 error), retry theo sequence_id, render chi khi du fragment |
| ESP32-S3 render khong on dinh | Don gian hoa font, dung display buffer, thu ESP32-P4/STM32/RP2040 |
| Display module khong co driver | Loai module, chon module co sample code/datasheet |
| Text khong doc duoc tren AR/dev kit | Thu module khac, giam target ngoai troi, pilot software-first tren Vuzix/Monocle |

## Mo hinh phat trien chu V

LingoGlass AR nen dung mo hinh chu V cho giai doan prototype va pilot. Diem quan trong cua mo hinh nay la moi giai doan phat trien o ben trai phai co mot giai doan test tuong ung o ben phai.

```text
Yeu cau phan tich        <----------------------> Van hanh test / Acceptance test
    Dinh nghia yeu cau   <-------------------> System test
        Thiet ke co ban  <---------------> Integration test
            Thiet ke chi tiet <-------> Unit test
                    Coding
```

### Quan he giua phat trien va test

| Giai doan phat trien | Test tuong ung | Muc dich |
| --- | --- | --- |
| Yeu cau phan tich | Van hanh test / Acceptance test | Kiem tra san pham co giai quyet dung van de nguoi dung khong |
| Dinh nghia yeu cau | System test | Kiem tra toan bo he thong co dat yeu cau FR/NFR khong |
| Thiet ke co ban | Integration test | Kiem tra app, backend, AI service va kinh ket noi dung khong |
| Thiet ke chi tiet | Unit test | Kiem tra tung module/API/protocol/display function |
| Coding | Debug va build verification | Xac nhan code chay duoc truoc khi dua vao cac cap test cao hon |

### Nguyen tac ap dung

- Viet tieu chi test ngay khi viet yeu cau, khong doi den cuoi du an.
- Moi yeu cau quan trong phai truy vet duoc den test case.
- Bug phat hien o cap test nao phai quay ve dung cap thiet ke/yeu cau tuong ung de sua.
- Voi phan cung deo nhu LingoGlass AR, van hanh test phai co nguoi dung that va moi truong that, khong chi test trong lab.

## 1. Yeu cau phan tich

### Muc tieu

Hieu dung van de can giai quyet, nguoi dung muc tieu, moi truong su dung va cac gioi han ky thuat chinh.

### Viec can lam

| Hang muc | Noi dung |
| --- | --- |
| Phan tich nguoi dung | Khach du lich, du hoc sinh, lao dong nuoc ngoai, nhan vien dich vu |
| Phan tich van de | Can dich nhanh ma khong phai cam dien thoai lien tuc |
| Phan tich moi truong | Ngoai troi, nha ga, san bay, nha hang, lop hoc, hoi thao |
| Phan tich doi thu | App dich, thiet bi dich cam tay, Ray-Ban Meta, Xreal |
| Phan tich rui ro | Display, latency, pin, nhiet, privacy, BOM |

### Dau ra

- Danh sach persona nguoi dung.
- Danh sach use case uu tien.
- Bang problem-solution fit.
- Danh sach rui ro ban dau.
- Tieu chi thanh cong cua prototype.
- Acceptance test outline cho pilot.
- Quyet dinh MVP ve audio: microphone dien thoai hay microphone tren kinh.
- Quyet dinh MVP ve camera OCR: camera dien thoai hay camera tren kinh.

### Tieu chi hoan thanh

- Chon duoc 2-3 use case chinh cho MVP.
- Xac dinh ro cai gi lam trong MVP va cai gi chua lam.
- Co KPI do duoc: latency, thoi luong pin, do doc, ty le loi ket noi.
- Co cach kiem tra voi nguoi dung that sau nay.
- Lock audio MVP, khuyen nghi dung microphone dien thoai de giam rui ro hardware.

## 2. Dinh nghia yeu cau

### Muc tieu

Chuyen nhu cau nguoi dung thanh yeu cau san pham va yeu cau ky thuat co the kiem thu.

### Yeu cau chuc nang

| ID | Yeu cau | Uu tien | Tieu chi chap nhan |
| --- | --- | --- | --- |
| FR-01 | Hien thi phu de dich tren kinh | Cao | Text tu app hien thi tren kinh trong <200 ms sau khi nhan |
| FR-02 | Dich hoi thoai ngan | Cao | End-to-end latency muc tieu 1.5-2.5 giay |
| FR-03 | Dich OCR tu anh chup | Cao | Menu/bien bao duoc OCR va hien thi ket qua trong <=3 giay |
| FR-04 | Chon ngon ngu nguon/dich tren app | Cao | Nguoi dung doi ngon ngu khong can restart |
| FR-05 | Luu lich su ban dich tuy chon | Trung binh | Mac dinh tat, nguoi dung co the bat/tat |
| FR-06 | Trang thai ket noi va pin | Trung binh | App hien thi connection, battery, error state |

### Yeu cau phi chuc nang

| ID | Yeu cau | Muc tieu |
| --- | --- | --- |
| NFR-01 | Latency hoi thoai | p50 <=2.0s, p95 <=3.5s |
| NFR-02 | Pin | >=2h active, >=6h mixed use prototype |
| NFR-03 | Do doc | >=80% nguoi test doc duoc ngoai troi sang vua |
| NFR-04 | Nhiet | Khong gay kho chiu khi deo 30-60 phut |
| NFR-05 | Privacy | Khong luu audio/video tho mac dinh |
| NFR-06 | On dinh ket noi | Loi ket noi <=2 lan trong 30 phut test |

### Dau ra

- Product Requirements Document.
- Software Requirements Specification.
- Hardware Requirements Specification.
- Test acceptance criteria.
- System test plan.

### Tieu chi hoan thanh

- Moi yeu cau quan trong co ID, muc uu tien va cach test.
- Khong con yeu cau mo ho nhu "AI thong minh" hoac "dich khong cham" ma khong co chi so.
- Moi FR/NFR co it nhat mot system test case tuong ung.

## 3. Thiet ke co ban

### Muc tieu

Xac dinh kien truc tong the va cach cac thanh phan giao tiep voi nhau.

### Kien truc tong the

```text
User speech / phone camera
        |
        v
Mobile App Gateway
        |
        v
Realtime Backend API
        |
        +--> STT service
        +--> Translation service
        +--> OCR service
        |
        v
Mobile App Gateway
        |
        v
Glasses Controller
        |
        v
Micro-OLED / Waveguide Display
```

### Module chinh

| Module | Trach nhiem |
| --- | --- |
| Firmware | Ket noi BLE/Wi-Fi, nhan text, render display, quan ly power |
| Mobile App | Cau hinh ngon ngu, thu am/chup anh, gui request, gui subtitle len kinh |
| Backend | WebSocket session, route STT/dich/OCR, logging latency |
| AI Services | STT, translation, OCR |
| Observability | Log latency, error, battery, connection event |

### Quyet dinh thiet ke co ban

- MVP dung dien thoai lam gateway.
- Kinh khong xu ly STT/OCR/dich nang.
- Backend MVP khong can Kubernetes.
- Uu tien WebSocket cho luong hoi thoai.
- BLE duoc uu tien cho payload text ngan; Wi-Fi chi dung khi can throughput cao.

### Dau ra

- Architecture diagram.
- Danh sach module.
- Data flow.
- API boundary.
- Deployment model MVP.
- Integration test plan.

### Tieu chi hoan thanh

- Moi thanh phan co vai tro ro.
- Biet du lieu nao di qua mobile, backend va kinh.
- Biet diem nao can logging de do latency.
- Biet can test tich hop cap nao: app-backend, backend-AI, app-glasses, full loop.

## 4. Thiet ke chi tiet

### Muc tieu

Chuyen thiet ke co ban thanh dac ta du de code va test.

### Firmware detail

| Hang muc | Thiet ke |
| --- | --- |
| Connection | BLE GATT service cho subtitle/status, tuy chon Wi-Fi cho debug |
| Message format | Binary packet co version, message_type, sequence_id, fragment_index, fragment_count, payload_length, crc8 |
| Display layout | 1-2 dong text, font co kich thuoc co dinh, khong nhay layout |
| Power state | Active, dim, sleep, reconnect |
| Error state | Lost connection, low battery, display error |

### Display module detail

| Hang muc | Can co truoc coding |
| --- | --- |
| Interface | SPI/RGB/LVDS/MIPI/driver board rieng |
| Datasheet | Timing, init sequence, electrical limits |
| Sample | SDK, Arduino/ESP-IDF sample, hoac reference driver |
| Power | Muc tieu mW o do sang dung duoc |
| Mechanical | Kich thuoc, vi tri gan, can chinh quang hoc |
| Availability | Module mau mua duoc va co duong toi san xuat nho |

### Mobile detail

| Hang muc | Thiet ke |
| --- | --- |
| Screens | Pairing, language settings, conversation, OCR, history, diagnostics |
| Audio | VAD, chunking, upload streaming |
| OCR | Capture, crop, compress, send to OCR |
| Device control | Connect/disconnect, send subtitle, get battery/status |
| Privacy | Toggle history, delete data, recording indicator |

### BLE subtitle protocol detail

| Truong | Kich thuoc | Mo ta |
| --- | ---: | --- |
| version | 1 byte | Version protocol |
| message_type | 1 byte | Subtitle, status, ack, error |
| sequence_id | 2 bytes | Tang dan cho moi subtitle |
| fragment_index | 1 byte | Vi tri fragment |
| fragment_count | 1 byte | Tong so fragment |
| payload_length | 1 byte | So byte payload |
| payload | N bytes | UTF-8 text fragment |
| crc8 | 1 byte | Kiem tra loi don gian |

Quy tac render: firmware chi render khi da nhan du fragment cua sequence hien tai. Neu sequence moi hon den, subtitle cu chua hoan tat bi huy.

### Privacy indicator detail

| Indicator | Thiet ke MVP |
| --- | --- |
| LED vat ly | Bat khi microphone/camera dang hoat dong |
| App indicator | Hien thi listening/camera active |
| OLED indicator | Icon nho cho nguoi deo kinh |
| Push-to-talk | Co che do bat/tat nghe chu dong |

### Backend detail

| Endpoint | Chuc nang |
| --- | --- |
| `WS /session` | Hoi thoai realtime |
| `POST /ocr` | OCR va dich anh |
| `POST /translate` | Dich text ngan |
| `POST /logs` | Gui log latency/error |
| `GET /health` | Kiem tra backend |

### Data model so bo

| Bang/doi tuong | Truong chinh |
| --- | --- |
| UserSettings | source_language, target_language, privacy_mode |
| DeviceSession | device_id, app_id, connected_at, battery_level |
| TranslationEvent | input_type, latency_ms, source_text, translated_text, error_code |
| DiagnosticLog | timestamp, component, event_name, metadata |

### Dau ra

- Firmware protocol spec.
- API spec.
- Mobile screen flow.
- Database/log schema.
- Test cases chi tiet.
- Unit test plan.

### Tieu chi hoan thanh

- Developer co the code ma khong can doan y.
- Moi API co input/output/error ro.
- Moi flow co test case tuong ung.
- Moi module quan trong co unit test hoac test procedure cu the.

## 5. Coding

### Muc tieu

Xay prototype theo tung milestone nho, moi milestone co demo va log do duoc.

### Thu tu coding khuyen nghi

| Milestone | Noi dung | Ket qua |
| --- | --- | --- |
| M1 | Firmware nhan text va hien thi | App/debug tool gui text len display |
| M2 | Mobile pairing va send subtitle | Dien thoai ket noi kinh va gui subtitle |
| M3 | Backend WebSocket session | App gui audio/text, backend tra ve ban dich |
| M4 | Conversation loop | Noi cau ngan, thay phu de tren kinh |
| M5 | OCR loop | Chup menu/bien bao, hien thi ban dich |
| M6 | Diagnostics | Log latency, pin, connection, error |
| M7 | Wearable prototype | Gan vao khung deo va test 30-60 phut |

### Nguyen tac coding

- Moi milestone phai co demo chay duoc.
- Khong toi uu som khi chua co so do.
- Logging la tinh nang bat buoc, khong phai viec phu.
- Tach ro code demo va code san pham.
- Mac dinh khong luu audio/video tho.

### Dau ra

- Firmware prototype.
- Mobile app prototype.
- Backend MVP.
- AI integration.
- Diagnostic logs.
- Demo video thuc te.

### Tieu chi hoan thanh

- Co the chay full loop: speech/OCR -> AI -> app -> display.
- Co log latency end-to-end.
- Co the demo khong can thao tac thu cong qua console.

## 6. Test

### Muc tieu

Kiem tra prototype trong dieu kien gan voi thuc te, khong chi trong moi truong lab.

### Thu tu test theo chu V

| Cap test | Dua tren tai lieu nao | Vi du test cho LingoGlass AR |
| --- | --- | --- |
| Unit test | Thiet ke chi tiet | Parser subtitle, BLE packet, API response, text layout |
| Integration test | Thiet ke co ban | App ket noi kinh, app goi backend, backend goi STT/dich/OCR |
| System test | Dinh nghia yeu cau | Full flow speech -> translation -> display dat latency p95 |
| Van hanh/acceptance test | Yeu cau phan tich | Nguoi dung di nha ga/nha hang va dung kinh de dich that |

### Test matrix

| Nhom test | Noi dung | Tieu chi |
| --- | --- | --- |
| Unit test | API, parser, display message, settings | Chuc nang co ban khong loi |
| BLE protocol test | MTU 23/185/247 (BLE min la 23, ATT payload 20), fragmentation, sequence, reconnect | Subtitle 100 ky tu dung thu tu, khong treo |
| Integration test | App-backend, app-glasses, backend-AI | Full flow hoat dong on dinh |
| Latency test | Hoi thoai cau ngan, cau dai, mang yeu | p50/p95 dat muc tieu |
| Display test | Trong nha, ngoai troi, nen phuc tap | >=80% nguoi test doc duoc |
| Battery test | Active, mixed use, standby | Dat muc tieu pin prototype |
| Thermal test | Deo 30-60 phut | Khong nong kho chiu |
| Audio test | Quan ca phe, nha ga, duong pho | STT chap nhan duoc |
| Privacy test | LED vat ly, app/OLED indicator, history toggle, delete data | Khong luu du lieu trai y nguoi dung |

### Pilot test

| Giai doan | So nguoi | Muc tieu |
| --- | ---: | --- |
| Internal alpha | 3-5 | Tim loi nghiem trong, do latency co ban |
| Closed beta | 10-20 | Kiem tra use case du lich/OCR/hoi thoai |
| Pilot | 20-50 | Do retention, muc hai long, loi ket noi, pin |

### Dau ra

- Test report.
- Latency report p50/p90/p95.
- Battery/thermal report.
- Display readability report.
- Bug list uu tien.
- Go/no-go recommendation.
- Requirement traceability matrix.

### Tieu chi hoan thanh

- Co so lieu that thay vi cam nhan.
- Co danh sach loi uu tien theo tac dong.
- Co quyet dinh ro: tiep tuc, thu hep, hay doi huong.
- Moi yeu cau uu tien cao deu co ket qua pass/fail.

## Requirement traceability matrix mau

| Requirement ID | Noi dung | Test cap | Test case | Ket qua mong doi |
| --- | --- | --- | --- | --- |
| FR-01 | Hien thi phu de dich tren kinh | Integration/System | App gui subtitle den kinh | Text hien thi dung, khong vo layout |
| FR-02 | Dich hoi thoai ngan | System/Acceptance | Noi 20 cau ngan trong moi truong test | p50 <=2.0s, p95 <=3.5s |
| FR-03 | Dich OCR tu anh chup | System/Acceptance | Chup menu/bien bao that | Ket qua hien thi <=3s |
| NFR-02 | Pin prototype | System/Acceptance | Su dung active lien tuc | >=2h active |
| NFR-03 | Do doc ngoai troi | Acceptance | 10 nguoi test doc text ngoai troi | >=80% dong y doc duoc |
| NFR-05 | Privacy | System/Acceptance | Kiem tra setting luu du lieu | Mac dinh khong luu audio/video tho |

## Timeline de xuat

| Giai doan | Thoi luong | Moc chinh |
| --- | ---: | --- |
| Spike truoc du an | 1 tuan | Phone -> BLE -> ESP32-S3 -> display pass/fail |
| Yeu cau phan tich | 2 tuan | Use case, persona, risk list |
| Dinh nghia yeu cau | 2 tuan | PRD, SRS, HRS, acceptance criteria |
| Thiet ke co ban | 2-3 tuan | Architecture, module boundary, data flow |
| Thiet ke chi tiet | 3-4 tuan | API spec, protocol, screen flow, test case |
| Coding prototype | 10-16 tuan | Display loop, conversation loop, OCR loop |
| Test va pilot | 8-12 tuan | Latency, pin, display, thermal, pilot report |

Tong thoi gian de co prototype/pilot dang tin cay: khoang 6-9 thang.

## Timeline solo-first 3 thang

| Sprint | Thoi luong | Output bat buoc |
| --- | ---: | --- |
| S0 | 1 tuan | Spike BLE/display + log latency |
| S1 | 2 tuan | App gui subtitle, diagnostics co ban |
| S2 | 2-3 tuan | STT + translation benchmark bang audio dien thoai |
| S3 | 2 tuan | OCR qua phone camera, hien thi ket qua tren display |
| S4 | 2-4 tuan | Readability test bang AR dev kit hoac wearable mock |
| S5 | 2-4 tuan | 5-10 nguoi test, report p50/p95, feedback, cost |

Muc tieu 3 thang khong phai san pham hoan chinh. Muc tieu la co evidence de quyet dinh tiep tuc custom hardware, dung dev kit AR, hay thu hep san pham.

## Phan cong vai tro de xuat

| Vai tro | Trach nhiem |
| --- | --- |
| Product lead | Use case, PRD, roadmap, pilot feedback |
| Firmware engineer | ESP32-S3, display, power, connectivity |
| Mobile engineer | App gateway, pairing, OCR capture, UI |
| Backend/AI engineer | WebSocket, STT/dich/OCR, logging |
| Hardware/mechanical engineer | Display module, pin, khung, nhiet |
| QA/test lead | Test plan, pilot, latency/power/readability report |

### Phien ban solo

| Workstream | Cach lam solo |
| --- | --- |
| Product | 1 page PRD, cap nhat sau moi sprint |
| Firmware | Chi lam BLE/display/status, khong lam audio tren kinh trong MVP |
| Mobile | App toi thieu: pairing, subtitle, audio capture, OCR capture, diagnostics |
| Backend/AI | Mot service realtime don gian, logging truoc dashboard |
| Hardware | Module/dev kit co san, khong custom PCB truoc khi spike pass |
| QA | Test checklist + log CSV/JSON, AI agent tong hop report |

## Cloud cost pilot

| Bien | Vi du |
| --- | ---: |
| Users | 50 |
| Sessions/user/day | 1 |
| Utterances/session | 10 |
| Utterances/month | 15,000 |
| Cost/utterance | 0.005-0.03 USD |
| AI cost/month | 75-450 USD |
| Infra/logging buffer | 25-100 USD |
| Tong pilot/month | 100-550 USD |

Trong pilot solo, dat hard cap usage va log chi phi theo session de tranh vuot ngan sach.

## Nguon tham khao phan cung can xac minh

| Hang muc | Nguon |
| --- | --- |
| Waveshare 0.49 inch OLED | https://www.waveshare.net/wiki/0.49inch_OLED_Module |
| Brilliant Monocle hardware | https://docs.brilliant.xyz/monocle/hardware/ |
| Vuzix developer resources | https://support.vuzix.com/docs/developer-resources |
| Vuzix Blade downloads | https://support.vuzix.com/docs/blade-downloads |

## Moc ra quyet dinh

| Moc | Cau hoi can tra loi |
| --- | --- |
| Sau thiet ke co ban | Kien truc co du don gian de prototype nhanh khong? |
| Sau display loop | Text co doc duoc tren display that khong? |
| Sau conversation loop | Latency co chap nhan duoc khong? |
| Sau wearable prototype | Kinh co deo duoc 30-60 phut khong? |
| Sau pilot | Nguoi dung co muon tiep tuc dung khong? |

## Ket luan

Thu tu phat trien nen di tu rui ro lon nhat den rui ro nho hon:

1. Chung minh display doc duoc.
2. Chung minh latency hoi thoai chap nhan duoc.
3. Chung minh pin/nhiet/trong luong co the deo that.
4. Sau do moi mo rong AI, agent, ecosystem va crowdfunding.

Neu lam dung thu tu nay, du an se tranh duoc viec xay nhieu tinh nang AI nhung that bai o trai nghiem deo va hien thi.
