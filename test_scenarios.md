# Kịch Bản Test Watchdog Timer — Đầy Đủ

> [!NOTE]
> Với cấu hình hiện tại: EN mặc định ON khi nhả nút (nhấn giữ S2 = tắt).
> LED active-HIGH theo test thực tế (1 = sáng, 0 = tắt).

---

## A. Test Phần Cứng (Nút nhấn + LED)

### Test 1: Power-on mặc định

| Bước | Hành động | D3 (WDO) | D4 (ENOUT) | Ghi chú |
|---|---|---|---|---|
| 1 | Nạp FPGA, không nhấn gì | ⚫ tắt | 🟢 sáng | EN=1 mặc định → ARMING → RUNNING |
| 2 | Chờ ~1.6s | 🔴 sáng | 🟢 sáng | Timeout → FAULT (không kick) |

✅ **PASS** nếu: D4 sáng ngay sau nạp, D3 sáng sau ~1.6s

---

### Test 2: Kick thành công — giữ D3 tắt

| Bước | Hành động | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Chờ D4 sáng | ⚫ | 🟢 | RUNNING |
| 2 | Nhấn rồi **nhả S1** (< 1.6s) | ⚫ | 🟢 | Timer reset 1.6s |
| 3 | Lặp lại mỗi ~1s | ⚫ | 🟢 | Kick liên tục |

✅ **PASS** nếu: D3 luôn tắt khi kick đều đặn

---

### Test 3: Timeout → D3 nhấp nháy

| Bước | Hành động | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Chờ D4 sáng (RUNNING) | ⚫ | 🟢 | |
| 2 | Không kick, chờ ~1.6s | 🔴 | 🟢 | FAULT! |
| 3 | Chờ thêm ~0.2s | ⚫ | 🟢 | tRST hết → RUNNING |
| 4 | Không kick, chờ ~1.6s | 🔴 | 🟢 | FAULT lại |

✅ **PASS** nếu: D3 nhấp nháy chu kỳ tắt 1.6s → sáng 0.2s → lặp lại

---

### Test 4: Disable bằng S2

| Bước | Hành động | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Chờ D4 sáng (RUNNING) | ⚫ | 🟢 | |
| 2 | **Nhấn giữ S2** | ⚫ | ⚫ | EN=0 → IDLE |
| 3 | **Nhả S2** | ⚫ | 🟢 | EN=1 → ARMING → RUNNING |

✅ **PASS** nếu: giữ S2 = cả 2 LED tắt, nhả = D4 sáng lại

---

### Test 5: Kick bị bỏ qua trong FAULT

| Bước | Hành động | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Để timeout (~1.6s) | 🔴 | 🟢 | FAULT |
| 2 | Nhấn+nhả S1 khi D3 sáng | 🔴 | 🟢 | Kick bị bỏ qua! |
| 3 | Chờ D3 tự tắt (~0.2s) | ⚫ | 🟢 | tRST hết → RUNNING |
| 4 | Nhấn+nhả S1 nhanh | ⚫ | 🟢 | Kick thành công |

✅ **PASS** nếu: kick trong FAULT không có tác dụng

---

### Test 6: Disable xóa FAULT

| Bước | Hành động | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Để timeout → D3 sáng | 🔴 | 🟢 | FAULT |
| 2 | **Nhấn giữ S2** | ⚫ | ⚫ | EN=0 → IDLE, xóa fault |
| 3 | **Nhả S2** | ⚫ | 🟢 | ARMING → RUNNING |

✅ **PASS** nếu: giữ S2 xóa FAULT, cả 2 LED tắt

---

## B. Test UART (Python Script)

### Giao thức UART

| Thông số | Giá trị |
|---|---|
| Baud rate | 9600 bps |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |

### Frame Format

```
[0x55] [CMD] [ADDR] [LEN] [DATA...] [CHK]
```

- `0x55` — Sync byte (cố định)
- `CMD` — Lệnh: `0x01`=WRITE, `0x02`=READ, `0x03`=KICK, `0x04`=STATUS
- `ADDR` — Địa chỉ register (0x00, 0x04, 0x08, 0x0C, 0x10)
- `LEN` — Số byte data (0–4)
- `DATA` — Data bytes (little-endian)
- `CHK` — XOR checksum của CMD đến hết DATA

### Register Map

| Addr | Tên | R/W | Mô tả |
|---|---|---|---|
| `0x00` | CTRL | R/W | bit0=EN_SW, bit1=WDI_SRC, bit2=CLR_FAULT(w1c) |
| `0x04` | tWD_ms | R/W | Watchdog timeout (ms), default=1600 |
| `0x08` | tRST_ms | R/W | WDO hold time (ms), default=200 |
| `0x0C` | arm_delay_us | R/W | Arm delay (µs), default=150 |
| `0x10` | STATUS | R | bit0=EN_EFF, bit1=FAULT, bit2=ENOUT, bit3=WDO, bit4=KICK_SRC |

### STATUS Register Bits (0x10)

| Bit | Tên | Ý nghĩa khi = 1 |
|---|---|---|
| 0 | EN_EFF | Watchdog đang enabled |
| 1 | FAULT_ACTIVE | Đang ở trạng thái FAULT |
| 2 | ENOUT | Watchdog đang RUNNING hoặc FAULT |
| 3 | WDO | wdo_n = 0 (fault output active) |
| 4 | KICK_SRC | Kick cuối cùng từ UART (1) hay nút (0) |

---

### Test 7: UART — Đọc giá trị mặc định

| Bước | Lệnh Python | Kết quả mong đợi |
|---|---|---|
| 1 | `read_reg(0x04)` | tWD_ms = 1600 (0x640) |
| 2 | `read_reg(0x08)` | tRST_ms = 200 (0xC8) |
| 3 | `read_reg(0x0C)` | arm_delay_us = 150 (0x96) |
| 4 | `read_reg(0x00)` | CTRL = 0x00 (EN_SW=0, WDI_SRC=0) |

✅ **PASS** nếu: tất cả giá trị đọc về đúng default

---

### Test 8: UART — Ghi tham số mới

| Bước | Lệnh Python | Kiểm tra |
|---|---|---|
| 1 | `write_reg(0x04, 3000)` | Ghi tWD = 3000ms |
| 2 | `read_reg(0x04)` | Đọc lại = 3000 |
| 3 | `write_reg(0x08, 1000)` | Ghi tRST = 1000ms |
| 4 | `read_reg(0x08)` | Đọc lại = 1000 |

✅ **PASS** nếu: đọc lại đúng giá trị đã ghi

---

### Test 9: UART — Enable/Disable qua EN_SW

| Bước | Lệnh Python | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Nhấn giữ S2 (disable HW) | ⚫ | ⚫ | IDLE |
| 2 | `write_reg(0x00, 0x01)` — EN_SW=1 | ⚫ | 🟢 | EN_SW override → RUNNING |
| 3 | `get_status()` | | | EN_EFF=1, ENOUT=1 |
| 4 | `write_reg(0x00, 0x00)` — EN_SW=0 | ⚫ | ⚫ | Nhả S2 đã disabled |

✅ **PASS** nếu: EN_SW bật/tắt được watchdog độc lập với nút

---

### Test 10: UART — Kick qua UART

| Bước | Lệnh Python | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Chờ RUNNING (D4 sáng) | ⚫ | 🟢 | |
| 2 | Lặp `kick()` mỗi 1s trong 5s | ⚫ | 🟢 | Không timeout |
| 3 | Dừng kick, chờ 2s | 🔴 | 🟢 | Timeout → FAULT |
| 4 | `get_status()` | | | FAULT=1, KICK_SRC=1 |

✅ **PASS** nếu: kick UART giữ D3 tắt, dừng kick → timeout

---

### Test 11: UART — CLR_FAULT

| Bước | Lệnh Python | D3 | D4 | Ghi chú |
|---|---|---|---|---|
| 1 | Để timeout → FAULT | 🔴 | 🟢 | |
| 2 | `get_status()` | | | FAULT=1 |
| 3 | `write_reg(0x00, 0x05)` — EN_SW=1, CLR_FAULT=1 | ⚫ | 🟢 | Xóa fault |
| 4 | `get_status()` | | | FAULT=0 |

✅ **PASS** nếu: CLR_FAULT xóa được fault, D3 tắt ngay

---

### Test 12: UART — Thay đổi timing on-the-fly

| Bước | Lệnh Python | Quan sát |
|---|---|---|
| 1 | `write_reg(0x04, 500)` — tWD=500ms | Timeout nhanh hơn |
| 2 | `write_reg(0x08, 2000)` — tRST=2000ms | D3 sáng lâu hơn (2s) |
| 3 | Quan sát D3 nhấp nháy | Chu kỳ: tắt 0.5s → sáng 2s |

✅ **PASS** nếu: thời gian nhấp nháy thay đổi đúng theo tham số mới

---

## C. Bảng Tổng Hợp

| Test | Loại | Mục đích | Thời gian |
|---|---|---|---|
| 1 | HW | Power-on mặc định | 3s |
| 2 | HW | Kick liên tục | 10s |
| 3 | HW | Timeout chu kỳ | 5s |
| 4 | HW | Enable/Disable S2 | 3s |
| 5 | HW | Kick trong FAULT | 5s |
| 6 | HW | Disable xóa FAULT | 3s |
| 7 | UART | Đọc default | 5s |
| 8 | UART | Ghi/Đọc params | 5s |
| 9 | UART | EN_SW toggle | 10s |
| 10 | UART | Kick UART | 10s |
| 11 | UART | CLR_FAULT | 5s |
| 12 | UART | Timing on-the-fly | 10s |

> [!IMPORTANT]
> Nhớ kiểm tra đúng cổng COM trong Device Manager trước khi chạy test UART.
> Cổng UART là USB-C **dưới**, cổng JTAG (nạp) là USB-C **trên**.
