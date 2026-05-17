<!--
    @author NGUYEN MINH TRI
 -->
## Bao cao ngay 2026/05/14 (S0 spike Phase A: dung khung du an)

- Thiet lap du an theo mau ADK (Agent Development Kit) 5 layer: CLAUDE.md / Skills / Hooks / Subagents / Plugins. Chon cach lam tang dan theo sprint, Phase A chi can cau hinh toi thieu (1 skill + permissions), khong setup big-bang.
- Chot ke hoach S0 spike: doi tu "1 tuan" sang "10-12 ngay lam viec". Ly do: chon Flutter (nang) + migrate hoan toan sang PlatformIO (them buoc setup).
- Chot tech stack chinh:
  - Mobile sender: **Flutter** (`flutter_blue_plus` + `permission_handler`)
  - Firmware build: **PlatformIO** (`env=esp32s3` cho board, `env=native` cho unit test)
  - BLE library: **NimBLE-Arduino** (nhe hon ESP32 BLE Arduino mac dinh)
  - OLED library: **U8g2** (chon truoc de sau nay co the load font tieng Nhat)
- Chot GATT UUID (lock - khong duoc regenerate tru khi update ca `firmware/CLAUDE.md` lan `mobile/CLAUDE.md` cung luc):
  - Service `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c`
  - Subtitle write `7c3d8b01-...`
  - ACK notify `7c3d8b02-...`
  - Ten advertise: `LingoGlass-S0`
- Trien khai Phase A (scaffold):
  - Tao project PlatformIO tai `firmware/esp32s3/`. Migrate I2C scanner tu `Test/Test.ino` sang `src/main.cpp`.
  - Viet `firmware/esp32s3/lib/ble_protocol/` voi C++ encoder/decoder, CRC-8, va thuat toan split UTF-8.
  - Them 15 Unity test trong `firmware/esp32s3/test/test_ble_protocol/` (CRC vectors, encode/decode round-trip, UTF-8 split, etc.).
  - Tao bo khung Flutter app trong `mobile/`. File `lib/ble/ble_protocol.dart` la ban mirror cua C++. Hai ben kiem chung qua `tests/ble_vectors.json` chung.
  - Tao stub UI tai `mobile/lib/screens/spike_screen.dart` voi 3 nut: Scan / Send Hello / Run 20.
  - Them 13 Dart unit test trong `mobile/test/ble_protocol_test.dart`.
- Phat hien va sua loi quan trong: draft dau tien cua `.claude/skills/ble-protocol/SKILL.md` ghi sai CRC-8 vector (`0x3E` - dung phai la `0x5B`). Da implement CRC-8 bang PowerShell de double-check, sua Skill truoc khi generate code. Tranh duoc viec sai vector lan toa sang ca C++ va Dart.
- Them quy tac `permissions.deny` trong `.claude/settings.local.json` chan `rm -rf docs*` / `firmware*` / `tests*` / `.claude*` cho ca Bash va PowerShell (tranh xoa nham docs va firmware artifact).

## Bao cao ngay 2026/05/17 (S0 spike: Phase A.1 wiring + Phase B OLED + Phase C BLE GATT + Phase D round-trip)

### Verify wiring OLED voi ESPr Developer S3 Type-C

- Bat dau bang Test.ino de scan I2C, target 0.96 inch OLED SSD1306 128x64.
- Trong qua trinh cam day, gap hien tuong: **"Cam GND vao thi may tinh khong nhan ESP nua (mat COM port)"**. Xac dinh ngay la chap mach, rut USB ngay lap tuc.
- Doc datasheet ESP32-S3-WROOM-1 (`docs/docs-pdf/4788f048-...pdf`) va schematic ESPr Developer S3 Type-C (`docs/docs-pdf/ESPr_Developer_S3_TypeC.sch.pdf`), nhung ket luan rang cach an toan nhat la doc silk-screen tren chinh board.
- Chup anh mat sau cua board de doc nhan chan, **phat hien trap nghiem trong**:
  - Tren hang pin duoi cua ESPr Developer S3 Type-C, giua `IO8` va `GND` chinh giua co them mot chan **`VIN` (~5V)** chen vao.
  - Thu tu thuc te: `... IO10 │ IO8 │ VIN │ GND │ IO9 │ IO20 ...`
  - Neu nghi "GND nam ngay canh IO8" va cam vao do, thuc te cam vao VIN (5V) → nguon 5V noi qua OLED ve GND → USB protection circuit tripped → COM port bien mat.
  - Day chinh la nguyen nhan loi truoc do.
- Chot lai wiring dung:

  | OLED | Chan ESPr (silk-screen) |
  | --- | --- |
  | GND | `GND` (hang duoi, giua VIN va IO9) |
  | VCC | `+3V3` (hang duoi, dau cuoi ben phai) |
  | SDA | `IO8` |
  | SCL | `IO9` |

- Sau khi sua day, flash lai Test.ino va chay I2C scan. Ket qua:
  ```
  === I2C pair: baseline: SDA IO8, SCL IO9
  Line levels with ESP pullup: SDA=HIGH, SCL=HIGH
  I2C device found at 0x3c
  ```
  OLED detect duoc o `0x3C` tren baseline pair. Cac pair fallback khong co false positive. Wiring PASS.

### Ghi vao memory

- Tao file `~/.claude/projects/.../memory/espr-developer-s3-pinout-trap.md` luu "VIN/IO8 adjacency trap" duoi dang reference memory. Muc dich: lan sau khong lap lai loi nay.
- Cap nhat `MEMORY.md` index voi link toi memory moi.

### Phase B: trien khai library render OLED

- Tao moi `firmware/esp32s3/lib/oled_view/oled_view.h` va `oled_view.cpp`.
- Su dung `U8G2_SSD1306_128X64_NONAME_F_HW_I2C` full-buffer mode. Font `u8g2_font_6x10_tf` (ASCII only - font tieng Nhat de den S1+).
- Public API:
  ```cpp
  namespace oled_view {
    bool begin(uint8_t i2c_address_7bit = 0x3C);
    bool is_ready();
    void show_status(const char* line1, const char* line2);
    void show_heartbeat(uint32_t counter);
  }
  ```
- Layout: dong 1 tai y=0, dong 2 tai y=16. Dia chi I2C nhan vao dang 7-bit, ben trong shift sang 8-bit truoc khi truyen cho U8g2.
- Update `firmware/esp32s3/src/main.cpp`:
  - Sau `Wire.begin(8, 9)`, chay I2C scan. Chi goi `oled_view::begin()` neu detect duoc `0x3C` (de firmware khong hang neu khong cam OLED).
  - Cuoi `setup()` hien `oled_view::show_status("LingoGlass S0", "Phase B: OLED ok")`.
  - Trong `loop()` goi `oled_view::show_heartbeat(counter)` moi giay.
  - Tang I2C clock tu 100kHz len 400kHz (SSD1306 chiu duoc).
  - Chuan hoa log tag thanh `[i2c]` `[oled]` de grep cho de.
- Update `firmware/CLAUDE.md` section Sprint hooks: mark Phase B "done 2026-05-17", note font va layout.

### Git init va push len GitHub

- Sau khi Phase B verify trong, init git repo: `git init -b main`.
- Tao `.gitignore` root chan `.pio/`, `build/`, `.dart_tool/`, `.env`, `.claude/settings.local.json`, IDE folders, OS junk. Bo sung cho `firmware/esp32s3/.gitignore` va `mobile/.gitignore` co san.
- Commit dau tien `d71237b` (chore: initial commit for S0 spike): 51 files, full khung Phase A + B.
- Add remote `https://github.com/tringuyenminh209/LingoGlassAR.git`, push thanh cong len `main`.
- Convention commit message theo global CLAUDE.md: **conventional commits, tieng Anh** (feat:/fix:/chore:/docs:...).

### Phase C: NimBLE GATT server skeleton

- Tao moi `firmware/esp32s3/lib/ble_server/ble_server.h` va `.cpp`. Wrap thu vien NimBLE-Arduino @ ^1.4.2.
- Public API:
  ```cpp
  namespace ble_server {
    using SubtitleWriteCallback = void (*)(const uint8_t* data, size_t length);
    bool begin(const char* device_name, SubtitleWriteCallback on_subtitle);
    bool is_connected();
    bool notify_ack(const uint8_t* data, size_t length);
  }
  ```
- Implementation:
  - 3 callback class: `ServerCallbacks` (onConnect / onDisconnect / onMTUChange), `SubtitleWriteCallbacks` (onWrite).
  - Khi disconnect → tu dong restart advertising. Phone reconnect ngay duoc.
  - Request MTU 247 ngay sau `NimBLEDevice::init`. Phone se negotiate xuong neu khong support (Android cu thuong tra ve 185).
  - Subtitle characteristic: WRITE + WRITE_NR (Write Without Response - throughput cao hon, khong cho ACK BLE L2CAP).
  - ACK characteristic: NOTIFY + READ. Phase C chua wire, san sang cho Phase D.
  - Advertising interval 100-200ms (0x06 - 0x12 trong don vi 0.625ms). Phone tim ra trong ~1 giay.
- Update `firmware/esp32s3/src/main.cpp`:
  - Sau OLED init → goi `ble_server::begin("LingoGlass-S0", onSubtitleWrite)`.
  - `onSubtitleWrite` callback hien tai chi log raw bytes (max 16 byte dau hex) va tang counter. **Khong decode** - Phase D moi wire `ble_protocol::decode_fragment`.
  - Track `g_total_write_count` va `g_total_write_bytes` (volatile uint32_t).
  - Loop hien dynamic 2 dong tren OLED:
    - Khi adv (chua co central): `LingoGlass S0` / `Adv #N`
    - Khi connected: `LingoGlass S0` / `BLE OK rx=N`
  - Serial log moi giay: `Heartbeat N | heap=... | ble=adv|CONNECTED | rx_count=... rx_bytes=...`.
- Update `firmware/CLAUDE.md` Sprint hooks: mark Phase C "in progress 2026-05-17" voi day du chi tiet API.

### Verify Phase C voi nRF Connect

- Flash firmware len ESPr S3 (build them ~5MB cho thu vien NimBLE, lan dau ~30s).
- Cai app **nRF Connect for Mobile** cua Nordic Semiconductor tren dien thoai.
- Quy trinh verify:
  1. Tab SCANNER → thay device `LingoGlass-S0` xuat hien trong ~1 giay → bam CONNECT.
  2. ESP Serial log: `[ble] central connected` + `[ble] negotiated mtu=...`.
  3. OLED chuyen sang `LingoGlass S0 / BLE OK rx=0`.
  4. Expand service `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c` → 2 characteristic xuat hien dung UUID `7c3d8b01-...` (WRITE) va `7c3d8b02-...` (NOTIFY).
  5. Write hex bytes vao char `7c3d8b01-...` → ESP Serial log `[ble] rx[N]: XX XX XX ...` → OLED `rx=1` tang.
  6. Disconnect tu app → ESP log `[ble] central disconnected, restart advertising` → quay ve trang thai adv.
- Tat ca buoc PASS. Phase C verified.

### Commit Phase C va push

- Commit `9d53740` (feat(ble): add NimBLE GATT server for Phase C): 4 files thay doi, +185 dong code.
- Push len GitHub thanh cong (`d71237b..9d53740`).

### Setup IDE / Dev environment

- IDE goc la **Antigravity** (Google fork cua VS Code). Antigravity dung Open VSX lam marketplace mac dinh, search ranking xau nen luc dau khong tim duoc PlatformIO IDE.
- Cuoi cung quay lai **VS Code chinh thong** + Microsoft VS Marketplace, cai PlatformIO IDE thanh cong.
- Cai them:
  - Python 3.12 (qua Microsoft Store, tu add PATH)
  - Microsoft C/C++ extension (PlatformIO IDE phu thuoc)
- Setup multi-root workspace: ngoai folder goc `LingoGlass AR/`, them folder `firmware/esp32s3/` qua "Add Folder to Workspace". Nho do PlatformIO IDE detect duoc `platformio.ini` va hien notification `Configuring project: Project has been successfully updated!`.
- Loi `pio --version` khong nhan trong terminal: do PlatformIO IDE cai Core vao penv rieng (`~/.platformio/penv/Scripts/`), khong nam trong PATH global. Cach giai quyet: `Ctrl+Shift+P` → `PlatformIO: New Terminal` de mo terminal da co PATH. Hoac dung truc tiep nut `→ Upload` tren status bar.

### Phase D: round-trip Hello tu dien thoai len OLED

- **Muc tieu Phase D**: gui text "Hello" tu Flutter app → ESP nhan → decode → render len OLED → ACK ve app. Verify end-to-end single-fragment path tren MTU 247.

#### Firmware: wire decode_fragment + ACK

- Update `firmware/esp32s3/src/main.cpp` `onSubtitleWrite`:
  - Goi `ble_protocol::decode_fragment(data, length, packet)` tren raw bytes vua nhan.
  - Neu status != Ok → tang counter `g_total_decode_errors`, log status code, return.
  - Neu type != Subtitle → log va bo qua.
  - Neu `fragment_count > 1` → log "deferred to Phase E", van gui ACK nhung khong render (tranh hien text mot nua).
  - Neu single fragment → copy payload sang buffer null-terminated `g_last_subtitle[64]`, render `oled_view::show_status("LingoGlass S0", g_last_subtitle)`, goi `sendAck(sequence_id)`.
- Ham `sendAck(uint16_t seq)`:
  - Dung `ble_protocol::encode_fragment` voi `MessageType::Ack`, payload 2 byte `[0x01, 0x00]` (status=ok, reserved).
  - Goi `ble_server::notify_ack(buffer, written)`.
- Track counters mo rong: `g_total_write_count`, `g_total_write_bytes`, `g_total_subtitles`, `g_total_decode_errors`. Heartbeat log moi giay in tat ca + `last="..."`.
- Loop dynamic: neu chua co subtitle (`g_total_subtitles == 0`) thi hien "Adv #N" hoac "BLE conn heap=...k". Sau khi co subtitle thi giu nguyen text tren OLED toi luc nhan packet moi.

#### Mobile: BleTransport + UI wire

- Tao moi `mobile/lib/ble/ble_transport.dart`:
  - `scanAndConnect()`: dung `FlutterBluePlus.scanResults` listen, filter `r.device.platformName == 'LingoGlass-S0'`, complete khi tim ra. Co timeout 5s + buffer 1s.
  - Sau connect → `device.requestMtu(247)` (Android only, iOS auto-negotiate).
  - `discoverServices()` → lay service `7c3d8b00-...`, sau do `firstWhere` 2 characteristic theo UUID.
  - Bat notify cho ACK char, subscribe stream `onValueReceived.listen(_handleAck)`.
  - `sendSubtitle(text, seq, mtu)`: encode UTF-8 bang `utf8.encode`, goi `splitUtf8(bytes, perFragment)` voi `perFragment = effectiveMtu - 3 - packetOverhead = 236`. Gui tung fragment voi `char.write(packet, withoutResponse: true)`.
  - `_handleAck`: `decodeFragment` packet ACK, lay status byte 0, emit `AckEvent` co `receivedAtMicros` cho Phase F latency.
- Update `mobile/lib/screens/spike_screen.dart`:
  - State quan ly `_transport`, `_nextSeq`, `_busy`.
  - `_onScanPressed` async goi `_transport.scanAndConnect()`, try/catch va disable nut khi busy.
  - `_onSendPressed` async goi `_transport.sendSubtitle('Hello', seq++)`, log ket qua.
  - Header AppBar hien `idle` / `CONN` (xanh) theo `_transport.isConnected`.
  - Log ListView dao nguoc thu tu (line moi nhat o tren).
- Sua loi `pubspec.yaml`: chuoi description co `S0 spike:` (dau hai cham) lam YAML parser fail. Quote bang `"..."`.
- `flutter create . --project-name lingoglass_mobile --org com.lingoglass --platforms=android,ios` tao 70 file Android + iOS shells.
- `flutter pub get` tai dependencies (flutter_blue_plus 1.36.8, permission_handler 11.4.0, va nhieu transitive deps).
- Them 3 permission vao `android/app/src/main/AndroidManifest.xml`:
  - `BLUETOOTH_SCAN` voi `usesPermissionFlags="neverForLocation"`
  - `BLUETOOTH_CONNECT`
  - `ACCESS_FINE_LOCATION` (Android 11 va thap hon)

#### Verify Phase D end-to-end

- Flash firmware moi len ESPr S3.
- Cam dien thoai Samsung **SC-56B** qua USB, bat USB debugging.
- `flutter run` build APK debug + install (~3-5 phut). App launch.
- Warning bo qua duoc:
  - `flutter_blue_plus_android requires NDK 27.0.12077973` (current 26.x). Khong chan build, fix optional sau bang `android { ndkVersion = "27.0.12077973" }` trong `build.gradle.kts`.
  - `gralloc4 ERROR Format 38` la graphics warning cua Samsung device, khong anh huong app.
- Test quy trinh:
  1. Bam **Scan** → app hien permission popup (Bluetooth + Location) → Allow → log:
     ```
     scan start (filter: LingoGlass-S0)
     connecting to LingoGlass-S0 (34:85:18:99:D2:3D)
     mtu=247
     connected, write+notify wired
     ```
     Header `idle` → **CONN** (xanh).
  2. ESP Serial: `[ble] central connected` + `[ble] negotiated mtu=247`. OLED: `BLE conn heap=...k`.
  3. Bam **Send Hello** → app log:
     ```
     send seq=1 len=5 frags=1 max_payload=236
       frag 0/1 bytes=13
     > sent "Hello" seq=1 frags=1
     ack seq=1 status=0x1
     < ACK seq=1 ok=true
     ```
     ESP Serial:
     ```
     [ble] write 13 bytes
     [ble] rx[13]: 01 01 01 00 00 01 05 48 65 6C 6C 6F XX
     [decode] type=1 seq=1 frag=1/1 payload_len=5
     [subtitle] seq=1 text="Hello"
     [ack] notified seq=1 (12 bytes)
     ```
  4. **OLED hien `LingoGlass S0` / `Hello`** ← Phase D milestone PASS.
- Tat ca buoc PASS. **End-to-end Hello round-trip da hoat dong.**

#### Commit Phase D va push

- Commit `f036438` (feat(ble): Phase D round-trip - decode + render + ACK): 4 files thay doi (+383, -37). Files: firmware/esp32s3/src/main.cpp, mobile/CLAUDE.md, mobile/lib/ble/ble_transport.dart (moi), mobile/lib/screens/spike_screen.dart.
- Push len GitHub: `85c9ce2..f036438`.

### Native unit test bi block

- Chay `pio test -e native` bi loi `'gcc' khong duoc nhan dang` - may Windows chua co C++ compiler cho host (PlatformIO native env compile bang GCC cua host, khong dung cross-compiler).
- Quyet dinh **defer**: khong cai MinGW-w64 ngay, di thang Phase C truoc. Protocol library da co 13 Dart test pass, va se duoc verify end-to-end qua Phase D-E (Hello round-trip + 100-char JP fragmentation).
- Neu sau nay can debug protocol thi cai WinLibs portable (~150MB) va add PATH: `[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\mingw64\bin", "User")`.

### Tom tat ngay 2026/05/17

- **4 phase xong trong 1 ngay**: A.1 wiring + B OLED + C BLE GATT + D round-trip.
- Plan ban dau S0 du kien 10-12 ngay → toc do thuc te nhanh hon nhieu nho AI-assisted dev loop, hardware da chot truoc, va commit/push tung phase nho.
- 3 commit chinh:
  - `d71237b` chore: initial commit S0 spike (Phase A + B)
  - `9d53740` feat(ble): NimBLE GATT server for Phase C
  - `f036438` feat(ble): Phase D round-trip - decode + render + ACK
- Memory cap nhat:
  - `espr-developer-s3-pinout-trap.md` (reference) - tranh nham VIN voi GND lan sau.
  - `s0-spike-plan.md` (project) - mark Phase A→D done, con E va F.

### Viec can lam tiep (Phase E, Day 8-9)

- Firmware: them `SubtitleAssembler` class quan ly multi-fragment buffer theo `sequence_id`:
  - Drop incomplete buffer khi nhan packet co `sequence_id` cao hon → render fragment moi.
  - Maximum 4-8 fragment per subtitle (~1KB), du cho moi case tieng Nhat 100 char.
  - Khi du tat ca fragment → render text len OLED, gui ACK.
- Mobile: them nut "Send Japanese" gui chuoi tieng Nhat ~100 ky tu (vd "こんにちは、世界。今日は天気がいい。これはテストメッセージです。"). `splitUtf8` se tu split thanh 2-3 fragment voi max_payload theo MTU hien tai.
- MTU matrix test: thu lan luot voi MTU 20 / 185 / 247 de verify split UTF-8 dung tai codepoint boundary:
  - MTU 20 → max_payload = 20 - 3 - 8 = 9 byte per fragment. Chuoi 100 char JP (~300 byte UTF-8) chia ~34 fragment.
  - MTU 185 → max_payload = 174 byte per fragment.
  - MTU 247 → max_payload = 236 byte per fragment.
- Phase F (Day 10-12) sau Phase E: latency harness, gui 20 subtitle lien tiep, log timestamp tu `BleTransport` (send_ts) va match voi ACK (`receivedAtMicros`), export CSV voi p50/p90/p95. Viet `docs/S0_spike_report.md` voi Go/No-Go decision.
