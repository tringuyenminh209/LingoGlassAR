# Phan tich chien luoc va ky thuat LingoGlass AR

## 1. Ket luan dieu hanh

LingoGlass AR co mot use case ro: dua phu de va ban dich vao tam nhin nguoi dung de giam thao tac voi dien thoai trong du lich va giao tiep da ngon ngu. Tuy nhien, day la du an phan cung deo tren mat, nen rui ro lon nhat khong nam o viec "AI co dich duoc khong", ma nam o bon diem:

1. Text co doc duoc tren kinh trong dieu kien thuc te khong.
2. Do tre co du thap de hoi thoai tu nhien khong.
3. Pin, nhiet va trong luong co chap nhan duoc khong.
4. BOM va compliance co cho phep ban voi gia hop ly khong.

Chien luoc phu hop la bat dau bang prototype thuc dung: kinh hien thi subtitle, dien thoai lam gateway, cloud xu ly AI. Chi khi prototype dat nguong latency, readability va power moi nen mo rong sang AI agent, ecosystem hoac crowdfunding.

### Boi canh solo + AI agents

Du an hien duoc thuc thi boi mot nguoi, voi AI agents ho tro nghien cuu, lap ke hoach, coding, test case va review. Dieu nay thay doi chien luoc:

- Khong thiet ke nhu team 6 nguoi ngay tu dau.
- Uu tien dev kit/module co san hon custom hardware.
- Moi sprint chi nen tra loi mot rui ro lon.
- AI agents nen duoc dung de tang toc tai lieu, code skeleton, test matrix va phan tich log, khong thay the viec do hardware that.

### Quyet dinh cap bach

Truoc khi dau tu vao roadmap 6-9 thang, du an can hoan thanh mot spike trong tuan dau:

**Phone -> BLE -> ESP32-S3 -> micro-OLED/display: subtitle co hien thi on dinh khong?**

Neu spike nay khong dat, kien truc hardware/firmware phai duoc xem lai truoc khi lam app, backend hoac AI pipeline day du.

## 2. Co hoi thi truong

### Nhu cau cot loi

Nguoi dung khong thieu ung dung dich. Van de la ung dung dich hien tai can cam dien thoai, nhin man hinh, bam nut, va lam gian doan hoi thoai. Kinh phu de co gia tri neu no giam duoc ma sat nay.

### Thi truong phu hop ban dau

| Thi truong | Ly do hap dan | Rui ro |
| --- | --- | --- |
| Du lich Nhat Ban/Han Quoc/Dai Loan | Bien bao, menu, giao thong va dich vu co nhieu ngu can dich nhanh | Privacy khi dung camera/micro noi cong cong |
| Du hoc sinh/lao dong nuoc ngoai | Su dung lap lai hang ngay, san sang tra tien neu that su huu ich | Can gia thap va pin tot |
| Khach san/ban le/san bay | Co nhu cau B2B ro, de pilot trong moi truong kiem soat | Can admin, bao mat, SLA |
| Hoi thao/su kien | Subtitle truc tiep co gia tri cao | Can latency va do chinh xac cao hon |

### Doi thu va khoang trong

| Nhom san pham | Diem manh | Diem yeu | Co hoi cho LingoGlass |
| --- | --- | --- | --- |
| Ung dung dich tren dien thoai | Re, san co, chat luong tot | Can cam dien thoai, khong tu nhien | Giam thao tac, hien thi trong tam nhin |
| Thiet bi dich cam tay | Don gian, chuyen dung | Van lam gian doan hoi thoai | Phu de lien tuc, hands-free |
| Ray-Ban Meta | Thiet ke dep, camera/audio AI | Khong co display AR cho subtitle | Tap trung vao hien thi ban dich |
| Xreal va kinh display | Display tot cho media | Cong kenh, thuong can day/phone, khong chuyen dich | Nhe hon, use case ngon ngu ro hon |

## 3. Chien luoc san pham

San pham nen duoc xay theo ba tang, khong nhay ngay len he sinh thai day du.

### Tang 1: Subtitle Glasses

Muc tieu: hien thi ban dich ngan, doc duoc, do tre thap.

- Phu de hoi thoai.
- Dich OCR tu anh chup.
- Dieu khien ngon ngu va lich su qua app.
- Log latency, pin, loi.

### Tang 2: Context-Aware Translation

Muc tieu: dich dung ngu canh hon.

- Luu context hoi thoai ngan han neu nguoi dung cho phep.
- Tuy chinh tone/formality.
- Che do du lich, hoc tap, cong viec.
- Tom tat sau cuoc hoi thoai.

### Tang 3: Assistant/Agent

Chi nen lam sau khi hai tang dau on dinh.

- Goi y cau tra loi.
- Ho tro tim duong/dat lich thong qua tich hop ngoai.
- B2B workflow cho khach san, san bay, lop hoc.

## 4. Kien truc ky thuat de xuat

### Nguyen tac

- Kinh la thiet bi hien thi va dieu khien nhe.
- Dien thoai la gateway chinh.
- Cloud xu ly AI nang va logging.
- Tranh microservices/Kubernetes trong MVP neu chua co tai that.

### Kien truc MVP

```text
User speech / phone camera
        |
        v
Mobile Gateway
  - language settings
  - audio segmentation
  - image crop/compress
  - reconnect handling
        |
        v
Backend Realtime API
  - WebSocket session
  - STT routing
  - translation routing
  - OCR routing
  - latency logging
        |
        v
Mobile Gateway
        |
        v
Glasses Controller
  - BLE/Wi-Fi
  - display layout
  - power state
        |
        v
Waveguide display
```

### Lua chon cong nghe

| Lop | Lua chon nen thu | Ly do |
| --- | --- | --- |
| Display controller | ESP32-S3 hoac MCU tuong duong | Re, nho, du cho BLE/Wi-Fi va dieu khien co ban |
| Mobile | Flutter/React Native | Prototype nhanh hai nen tang |
| Backend | FastAPI/Node.js + WebSocket | It phuc tap, de do latency |
| STT | API realtime hoac Faster-Whisper GPU cloud | Can streaming va benchmark thuc te |
| Translation | OpenAI/DeepL/Google Translate | Can A/B test theo cap ngon ngu |
| OCR | Google Vision API, ML Kit, hoac model mobile | Can so sanh cloud vs on-device |
| Storage | Postgres/S3 toi thieu | Chi luu log va setting can thiet |

## 5. Diem nghen ky thuat

### 5.1 Hien thi va quang hoc

Hien thi la rui ro san pham lon nhat. Display phai du sang, text ro, khong gay moi mat, va khong che qua nhieu tam nhin.

### Quyet dinh display module

Khong nen tiep tuc thiet ke chi tiet neu chua chon duoc display module hoac driver board co tai lieu ro. Thong tin can co:

| Hang muc | Can xac nhan |
| --- | --- |
| Interface | SPI/RGB/LVDS/MIPI/driver board rieng |
| Driver | Co SDK/sample init sequence khong |
| Power | Cong suat that o do sang doc duoc |
| Optical | Eyebox, FOV, eye relief, do sang |
| Mechanical | Kich thuoc, diem gan, can chinh quang hoc |
| Supply | Lead time mau, bao gia 100/1,000 units |
| Firmware risk | ESP32-S3 co du kha nang dieu khien khong, hay can MCU/bridge khac |

### Ung vien display/dev kit

| Lua chon | Dung de lam gi | Nhan xet |
| --- | --- | --- |
| Waveshare 0.49 inch OLED | Spike re cho ESP32/display protocol | Tot de test BLE/render, khong kiem chung AR optics |
| Brilliant Monocle | Prototype AR dev kit | Co display, Bluetooth, camera, microphone; hop de demo wearable nhanh |
| Vuzix Blade/Blade 2/Z100 | Pilot software tren smart glasses co san | Giam rui ro hardware, nhung it kiem soat custom design |

De xuat: solo founder nen dung display dev module re cho spike tuan dau, sau do quyet dinh co mua/dev kit AR nhu Monocle/Vuzix de validate trai nghiem that hay khong.

Can test:

- Do doc ngoai troi, trong nha, tren nen phuc tap.
- Kich thuoc font toi thieu.
- So dong phu de toi da.
- Mau text/nen hoac outline de tranh mat chu.
- Eyebox voi nguoi deo kinh can.
- Can chinh co khi khi di chuyen.

### 5.2 Latency

Pipeline hoi thoai can du nhanh. Neu do tre tren 3 giay, nguoi dung se quay lai dung dien thoai.

| Buoc | Muc tieu | Rui ro |
| --- | ---: | --- |
| VAD/cat doan am thanh | 100-300 ms | Cat sai lam mat ngu canh |
| Upload | 100-300 ms | Mang di dong khong on dinh |
| STT streaming | 500-1,000 ms | Accent, tieng on, cau dai |
| Translation | 200-600 ms | Context va formal/informal |
| Gui ve kinh | 50-200 ms | BLE reconnect, packet loss |
| Render | <100 ms | Layout nhay khi text cap nhat |

MVP can log p50/p90/p95 latency, khong chi do mot demo tot nhat.

### 5.3 Pin va nhiet

Kinh deo tren mat rat nhay cam voi nhiet va trong luong. Muc tieu 8-12 gio active la khong thuc te cho prototype co display lien tuc.

Huong giam rui ro:

- Bat display theo ngu canh, khong luon-on.
- Su dung dien thoai cho camera/OCR trong MVP.
- Giam tan suat Wi-Fi, uu tien BLE cho text ngan.
- Ghi ro active time va standby time rieng.
- Do nhiet tai canh kinh, thai duong, song mui.

### 5.4 Audio trong moi truong that

STT tot trong phong yen tinh khong du. Can test san bay, nha ga, quan ca phe, duong pho.

Can quyet dinh:

- Micro tren kinh hay micro dien thoai cho MVP.
- Co can beamforming that trong ban dau khong.
- Co can nut/push-to-talk de tranh ghi am lien tuc khong.
- Hien thi trang thai dang nghe de giam lo ngai privacy.

Khuyen nghi: MVP nen lock microphone dien thoai lam nguon audio chinh. Ly do la giam rui ro phan cung, khong can codec/I2S/beamforming tren kinh ngay lap tuc, va co the benchmark STT nhanh hon. Micro tren kinh nen la milestone sau khi display loop va conversation loop qua nguong.

### 5.5 BLE subtitle payload

BLE khong duoc gia dinh la "gui text la xong". Neu MTU thap, subtitle 20-100 ky tu se bi chia goi va co the gay tre/loi thu tu.

Rui ro can xu ly:

- ATT MTU 23 bytes (BLE minimum) trong dieu kien mac dinh; usable ATT payload chi 20 bytes (MTU 23 minus 3-byte ATT header).
- Fragment bi mat hoac den sai thu tu.
- Subtitle cu den sau subtitle moi.
- Text dai lam nhay layout.
- Reconnect lam lap lai message.

Huong thiet ke:

- Moi subtitle co sequence_id.
- Payload co fragment_index va fragment_count.
- Firmware chi render khi du fragment.
- Subtitle moi hon huy subtitle cu chua render.
- Test tren MTU 23/185/247 bytes va do latency p50/p95.

### 5.6 Plan B cho spike fail

| Neu fail | Huong xu ly |
| --- | --- |
| BLE qua cham | Tang MTU, binary protocol, giam subtitle length, fallback Wi-Fi local |
| Fragment loi | ACK type=0x03 voi status code (0x01 OK / 0x03 error), retry theo sequence_id, render chi khi du fragment |
| ESP32-S3 khong du | Thu ESP32-P4, STM32, RP2040 hoac driver board rieng |
| Display dev qua nho | Dung no cho pipeline, dung AR dev kit/phone mock cho readability |
| Waveguide khong doc duoc | Giam scope sang indoor/B2B, thu module khac, hoac pilot tren Vuzix/Monocle |
| Khong co datasheet | Loai module do khoi MVP |

## 6. Unit economics va chi phi

### BOM can theo doi

| Hang muc | Muc rui ro | Ghi chu |
| --- | --- | --- |
| Waveguide/display module | Rat cao | Quyet dinh gia ban, do sang, trong luong |
| Khung co khi | Cao | Deo thoai mai kho hon demo tren ban |
| Battery/charging | Cao | Anh huong an toan, nhiet, thoi luong |
| MCU/wireless | Thap-trung binh | ESP32-S3 hop ly cho controller |
| Microphone/audio | Trung binh | Chat luong audio quyet dinh STT |
| PCB/custom cable | Trung binh | Rui ro khi ket noi display interface |
| Cloud/API | Trung binh | Co the an bien loi nhuan neu usage cao |

### Gia ban

Gia ban 499-699 USD chi kha thi neu:

- Module quang hoc co gia san xuat hop ly.
- Ti le loi/yield khong qua cao.
- Bao hanh va doi tra duoc tinh vao margin.
- Chi phi cloud cho goi co ban duoc gioi han.

Nen tinh rieng:

- Gross margin phan cung.
- Gross margin goi SaaS.
- Chi phi ho tro/bao hanh.
- Chi phi compliance theo thi truong.

### Cloud cost model cho pilot

Pilot 50 nguoi co the ton chi phi dang ke neu moi cau hoi thoai goi STT va translation realtime. Nen tinh theo utterance thay vi chi tinh theo user.

| Bien | Vi du |
| --- | ---: |
| Users | 50 |
| Sessions/user/day | 1 |
| Utterances/session | 10 |
| Utterances/month | 15,000 |
| Cost/utterance thap | 0.005 USD |
| Cost/utterance cao | 0.03 USD |
| AI cost/month | 75-450 USD |
| Infra/logging buffer | 25-100 USD |
| Tong pilot/month | 100-550 USD |

Can cap nhat bang gia API thuc te truoc pilot, vi gia model thay doi nhanh. Trong pilot, bat usage cap va log chi phi theo user/session.

## 7. Quyen rieng tu, phap ly va compliance

### Privacy by design

| Rui ro | Bien phap |
| --- | --- |
| Ghi am/ghi hinh nguoi xung quanh | LED vat ly, trang thai trong app/OLED va che do push-to-talk |
| Luu du lieu nhay cam | Mac dinh khong luu audio/video tho |
| Xu ly cloud | Cong khai nha cung cap va khu vuc xu ly |
| Tre em/truong hoc/y te | Khong target ban dau neu chua co chinh sach rieng |
| B2B | Can admin console, data retention, audit log |

Privacy indicator nen co thiet ke vat ly ngay trong prototype: LED o mat truoc hoac canh gong kinh, bat khi microphone/camera duoc dung. Chi hien thi icon tren OLED la chua du, vi nguoi xung quanh khong nhin thay.

### Compliance phan cung

Truoc khi ban ra thi truong can lap danh sach chung nhan theo khu vuc:

- Hoa Ky: FCC, an toan pin, canh bao privacy.
- EU: CE, RoHS, RED, GDPR neu xu ly du lieu ca nhan.
- Nhat Ban: PSE neu lien quan nguon/pin/sac, radio certification, yeu cau dai dien/noi dia tuy kenh ban.
- Han Quoc: KC va yeu cau dai dien/ho so dia phuong neu ban online.

### Crowdfunding

Neu dung Kickstarter hoac nen tang tuong tu:

- Phai co prototype hoat dong that.
- Khong dung render photorealistic de lam nguoi xem tuong la san pham da hoan thien.
- Noi ro tinh nang nao da hoat dong, tinh nang nao con R&D.
- Cong khai viec dung AI, nha cung cap AI va gioi han cua he thong.

## 8. Risk register

| Rui ro | Xac suat | Tac dong | Cach giam rui ro |
| --- | --- | --- | --- |
| Display khong du sang/doc ngoai troi | Cao | Rat cao | Test module that som, do readability ngoai troi |
| Chua chon duoc display module phu hop | Cao | Rat cao | Spike module trong tuan dau, yeu cau datasheet/interface ro |
| Latency hoi thoai qua cao | Cao | Rat cao | Streaming STT, cat audio thong minh, log p95 |
| Pin active qua ngan | Cao | Cao | Thin-client, display duty cycle, BLE text payload |
| BOM vuot gia ban muc tieu | Cao | Cao | Bao gia 1k units som, can nhac ban B2B gia cao |
| Kinh nong/kho deo | Trung binh-cao | Cao | Do nhiet, tach xu ly sang phone/cloud |
| STT kem trong tieng on | Trung binh-cao | Cao | Test moi truong that, push-to-talk, mic placement |
| BLE subtitle protocol loi/tre | Trung binh-cao | Cao | Fragmentation, sequence_id, MTU test |
| Privacy backlash | Trung binh | Cao | Den bao trang thai, default no raw recording |
| Compliance cham | Trung binh | Cao | Lap checklist FCC/CE/PSE/KC tu dau |
| Cloud cost cao | Trung binh | Trung binh | Usage cap, cache, routing model re hon |
| Crowdfunding bi tu choi/phan ung xau | Trung binh | Cao | Demo that, disclosure ro, khong overpromise |

## 9. Ke hoach validate

### Prototype A: Display loop

Muc tieu: chung minh text tu app co the hien thi ro tren kinh.

Can do:

- Spike tuan dau: phone -> BLE -> ESP32-S3 -> display text.
- Chon display module/driver board co tai lieu interface ro.
- BLE/Wi-Fi round trip.
- Kich thuoc font va so dong toi uu.
- Test ngoai troi/trong nha.
- Quay video demo that.

### Prototype B: Conversation loop

Muc tieu: chung minh luong hoi thoai co the dung duoc.

Can do:

- STT streaming.
- Dich cau ngan.
- Log p50/p90/p95.
- Test 5-10 cap ngon ngu uu tien.

### Prototype C: OCR loop

Muc tieu: dich bien bao/menu nhanh.

Can do:

- Chup/crop tren mobile.
- OCR cloud/on-device.
- Hien thi ket qua rut gon, khong day text qua dai len kinh.

### Prototype D: Wearable loop

Muc tieu: chung minh co the deo va di chuyen.

Can do:

- Khung co khi tam.
- Pin that.
- Do nhiet.
- Test 30-60 phut lien tuc.

## 10. KPI cho pilot

| KPI | Muc tieu ban dau |
| --- | ---: |
| Latency p50 hoi thoai | <= 2.0 giay |
| Latency p95 hoi thoai | <= 3.5 giay |
| Ty le cau dich chap nhan duoc | >= 80% trong ngu canh test |
| Thoi gian active | >= 2 gio |
| Thoi gian mixed use | >= 6-8 gio |
| Doc duoc ngoai troi sang vua | >= 80% nguoi test dong y |
| Loi ket noi trong 30 phut | <= 2 lan |
| Nguoi dung muon dung lai | >= 40% trong pilot som |

## 11. Lo trinh khuyen nghi

### 0-2 tuan

- Chay spike phone -> BLE -> ESP32-S3 -> display.
- Chon module display co the mua va co tai lieu interface.
- Lock audio MVP: microphone dien thoai.
- Dinh nghia BLE subtitle protocol so bo.
- Tao technical spec ngan cho firmware/app/backend.

### Roadmap solo 3 thang

| Sprint | Thoi luong | Ket qua |
| --- | ---: | --- |
| S0 | 1 tuan | BLE/display spike pass/fail |
| S1 | 2 tuan | Mobile app gui subtitle + diagnostics |
| S2 | 2-3 tuan | STT/translation latency benchmark |
| S3 | 2 tuan | OCR loop qua phone camera |
| S4 | 2-4 tuan | AR/dev kit hoac wearable mock readability test |
| S5 | 2-4 tuan | 5-10 nguoi test, log usage va feedback |

### 3-8 tuan

- Lam display loop.
- App gateway gui text len kinh.
- Backend WebSocket don gian.

### 9-16 tuan

- Them STT/dich realtime.
- Them OCR qua mobile camera.
- Bat dau logging latency va loi.

### 17-28 tuan

- Lam khung deo duoc.
- Do pin/nhiet/trong luong.
- Test moi truong thuc: duong pho, nha ga, quan ca phe.

### 29-40 tuan

- Pilot 20-50 nguoi.
- Lap lai thiet ke display/audio/app.
- Tinh BOM va cloud cost theo usage that.

### 41-52 tuan

- Quyet dinh huong tiep theo:
  - Neu KPI dat: chuan bi ban dev kit/pilot B2B/crowdfunding.
  - Neu KPI khong dat: thu hep san pham thanh mobile-assisted subtitle device hoac B2B niche.

## 12. Khuyen nghi cuoi

LingoGlass AR nen tranh mo rong som sang "AI agent ecosystem". Gia tri dau tien can chung minh la mot trai nghiem rat cu the: nguoi dung nghe mot cau noi nuoc ngoai va doc duoc ban dich tren kinh nhanh, ro, khong kho chiu.

Thu tu uu tien dung:

1. Display readability.
2. End-to-end latency.
3. Pin/nhiet/trong luong.
4. Privacy va compliance.
5. BOM va unit economics.
6. Mo rong AI/agent/ecosystem.

Neu sau prototype, ba chi so dau dat nguong chap nhan, du an co nen tang tot de tiep tuc. Neu mot trong ba chi so dau that bai, cac tinh nang AI nang cao se khong cuu duoc trai nghiem san pham.

## 13. Nguon tham khao phan cung can xac minh

| Hang muc | Nguon |
| --- | --- |
| Waveshare 0.49 inch OLED | https://www.waveshare.net/wiki/0.49inch_OLED_Module |
| Brilliant Monocle hardware | https://docs.brilliant.xyz/monocle/hardware/ |
| Vuzix developer resources | https://support.vuzix.com/docs/developer-resources |
| Vuzix Blade downloads | https://support.vuzix.com/docs/blade-downloads |

Day la danh sach ung vien ban dau, khong phai quyet dinh mua. Can xac minh gia, tinh san co, SDK/license va shipping truoc khi chot.
