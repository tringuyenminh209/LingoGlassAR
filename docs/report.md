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

## Bao cao ngay 2026/05/17 (S0 spike Phase A.1: verify wiring + Phase B: render OLED)

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

### Setup IDE / Dev environment

- IDE goc la **Antigravity** (Google fork cua VS Code). Antigravity dung Open VSX lam marketplace mac dinh, search ranking xau nen luc dau khong tim duoc PlatformIO IDE.
- Cuoi cung quay lai **VS Code chinh thong** + Microsoft VS Marketplace, cai PlatformIO IDE thanh cong.
- Cai them:
  - Python 3.12 (qua Microsoft Store, tu add PATH)
  - Microsoft C/C++ extension (PlatformIO IDE phu thuoc)
- Setup multi-root workspace: ngoai folder goc `LingoGlass AR/`, them folder `firmware/esp32s3/` qua "Add Folder to Workspace". Nho do PlatformIO IDE detect duoc `platformio.ini` va hien notification `Configuring project: Project has been successfully updated!`.
- Loi `pio --version` khong nhan trong terminal: do PlatformIO IDE cai Core vao penv rieng (`~/.platformio/penv/Scripts/`), khong nam trong PATH global. Cach giai quyet: `Ctrl+Shift+P` → `PlatformIO: New Terminal` de mo terminal da co PATH. Hoac dung truc tiep nut `→ Upload` tren status bar.

### Viec can lam tiep

- Flash firmware Phase B len board, verify OLED hien `LingoGlass S0` + `Heartbeat: N` (task #9).
- Chay `pio test -e native -d firmware/esp32s3` de verify 15 Unity test pass het (task #10).
- `git init` truoc khi viet BLE code de co safety net (task #11, dang cho user quyet dinh).
- Phase C: NimBLE GATT server skeleton. Them `lib/ble_server/`, advertise ten `LingoGlass-S0`, expose 2 characteristic (subtitle write + ACK notify). Verify connect duoc bang app nRF Connect tren dien thoai truoc khi viet Flutter sender (task #12).
