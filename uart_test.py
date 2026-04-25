#!/usr/bin/env python3
"""
Watchdog Timer UART Test Script
================================
Giao tiếp với FPGA Watchdog qua UART (9600 8N1).
Dựa trên giao thức trong HuongDan_FPGA_Contest_2026_v2.docx

Frame format: [0x55][CMD][ADDR][LEN][DATA...][CHK]
- CHK = XOR của tất cả byte từ CMD đến hết DATA

Usage:
    python uart_test.py              # Chạy tất cả test
    python uart_test.py --port COM4  # Chỉ định cổng COM
    python uart_test.py --menu       # Chế độ interactive menu
"""

import serial
import serial.tools.list_ports
import time
import sys
import argparse

# ==================== CẤU HÌNH ====================
DEFAULT_BAUD = 9600
TIMEOUT = 1.0  # seconds

# Register addresses
REG_CTRL        = 0x00
REG_TWD_MS      = 0x04
REG_TRST_MS     = 0x08
REG_ARM_DELAY   = 0x0C
REG_STATUS      = 0x10

# Commands
CMD_WRITE  = 0x01
CMD_READ   = 0x02
CMD_KICK   = 0x03
CMD_STATUS = 0x04

# CTRL register bits
CTRL_EN_SW     = (1 << 0)  # bit0: Enable via software
CTRL_WDI_SRC   = (1 << 1)  # bit1: WDI source (1=UART only)
CTRL_CLR_FAULT = (1 << 2)  # bit2: Clear fault (write-1-to-clear)

# STATUS register bits
STATUS_EN_EFF   = (1 << 0)  # bit0: EN effective
STATUS_FAULT    = (1 << 1)  # bit1: Fault active
STATUS_ENOUT    = (1 << 2)  # bit2: ENOUT
STATUS_WDO      = (1 << 3)  # bit3: WDO (fault output)
STATUS_KICK_SRC = (1 << 4)  # bit4: Last kick source (1=UART)

# ==================== UART FUNCTIONS ====================

ser = None

def find_com_port():
    """Tự động tìm cổng COM khả dụng."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ Không tìm thấy cổng COM nào!")
        print("   → Kiểm tra kết nối USB-C UART (cổng dưới) của Kiwi 1P5")
        sys.exit(1)
    
    print("📌 Các cổng COM khả dụng:")
    for i, p in enumerate(ports):
        print(f"   [{i}] {p.device} — {p.description}")
    
    if len(ports) == 1:
        print(f"   → Tự chọn: {ports[0].device}")
        return ports[0].device
    
    choice = input("Chọn cổng (số): ").strip()
    return ports[int(choice)].device


def open_serial(port=None, baud=DEFAULT_BAUD):
    """Mở kết nối serial."""
    global ser
    if port is None:
        port = find_com_port()
    
    ser = serial.Serial(port, baud, timeout=TIMEOUT)
    time.sleep(0.1)  # Chờ kết nối ổn định
    ser.reset_input_buffer()
    print(f"✅ Đã kết nối {port} @ {baud} bps\n")
    return ser


def close_serial():
    """Đóng kết nối serial."""
    global ser
    if ser and ser.is_open:
        ser.close()
        print("🔌 Đã đóng kết nối serial")


def xor_checksum(data_list):
    """Tính XOR checksum."""
    chk = 0
    for b in data_list:
        chk ^= b
    return chk


def send_frame(cmd, addr, data_bytes):
    """
    Gửi frame UART và nhận response.
    
    Frame: [0x55][CMD][ADDR][LEN][DATA...][CHK]
    CHK = XOR(CMD, ADDR, LEN, DATA...)
    """
    payload = [cmd, addr, len(data_bytes)] + list(data_bytes)
    chk = xor_checksum(payload)
    frame = bytes([0x55] + payload + [chk])
    
    ser.reset_input_buffer()
    ser.write(frame)
    
    # Chờ response (tối đa 8 bytes)
    resp = ser.read(8)
    return resp


def write_reg(addr, val_32):
    """Ghi giá trị 32-bit vào register (little-endian)."""
    data = [(val_32 >> (8 * i)) & 0xFF for i in range(4)]
    resp = send_frame(CMD_WRITE, addr, data)
    
    addr_name = {0x00: "CTRL", 0x04: "tWD_ms", 0x08: "tRST_ms", 0x0C: "arm_delay_us"}.get(addr, f"0x{addr:02X}")
    print(f"  📝 WRITE {addr_name} = {val_32} (0x{val_32:08X})")
    
    if resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     ⚠️  Không nhận được response!")
    return resp


def read_reg(addr):
    """Đọc giá trị từ register."""
    resp = send_frame(CMD_READ, addr, [])
    
    addr_name = {
        0x00: "CTRL", 0x04: "tWD_ms", 0x08: "tRST_ms",
        0x0C: "arm_delay_us", 0x10: "STATUS"
    }.get(addr, f"0x{addr:02X}")
    
    print(f"  📖 READ  {addr_name}")
    if resp and len(resp) >= 8:
        # Parse response value (little-endian, bytes 4-7 are data)
        val = 0
        for i in range(4):
            if 4 + i < len(resp):
                val |= resp[4 + i] << (8 * i)
        print(f"     Response: {resp.hex(' ')}")
        print(f"     Value: {val} (0x{val:08X})")
        return val
    elif resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     ⚠️  Không nhận được response!")
    return None


def kick():
    """Gửi lệnh kick watchdog qua UART."""
    resp = send_frame(CMD_KICK, 0x00, [])
    print(f"  🦵 KICK")
    if resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     ⚠️  Không nhận được response!")
    return resp


def get_status():
    """Đọc và parse STATUS register."""
    resp = send_frame(CMD_STATUS, REG_STATUS, [])
    
    print(f"  📊 STATUS")
    if resp and len(resp) >= 8:
        val = 0
        for i in range(4):
            if 4 + i < len(resp):
                val |= resp[4 + i] << (8 * i)
        
        print(f"     Raw: {resp.hex(' ')}")
        print(f"     Value: 0x{val:08X}")
        print(f"     ├── EN_EFF       = {(val >> 0) & 1}  {'(Enabled)' if val & STATUS_EN_EFF else '(Disabled)'}")
        print(f"     ├── FAULT_ACTIVE = {(val >> 1) & 1}  {'⚠️ FAULT!' if val & STATUS_FAULT else '✅ OK'}")
        print(f"     ├── ENOUT        = {(val >> 2) & 1}  {'(Running)' if val & STATUS_ENOUT else '(Idle)'}")
        print(f"     ├── WDO          = {(val >> 3) & 1}  {'🔴 Fault Output' if val & STATUS_WDO else '⚫ Normal'}")
        print(f"     └── KICK_SRC     = {(val >> 4) & 1}  {'(UART)' if val & STATUS_KICK_SRC else '(Button)'}")
        return val
    elif resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     ⚠️  Không nhận được response!")
    return None


# ==================== TEST CASES ====================

def test_7_read_defaults():
    """Test 7: Đọc giá trị mặc định."""
    print("\n" + "=" * 60)
    print("🧪 TEST 7: Đọc giá trị mặc định")
    print("=" * 60)
    
    passed = True
    
    val = read_reg(REG_TWD_MS)
    if val is not None and val != 1600:
        print(f"     ❌ FAIL: tWD_ms = {val}, expected 1600")
        passed = False
    
    val = read_reg(REG_TRST_MS)
    if val is not None and val != 200:
        print(f"     ❌ FAIL: tRST_ms = {val}, expected 200")
        passed = False
    
    val = read_reg(REG_ARM_DELAY)
    if val is not None and val != 150:
        print(f"     ❌ FAIL: arm_delay_us = {val}, expected 150")
        passed = False
    
    val = read_reg(REG_CTRL)
    
    if passed:
        print("\n  ✅ TEST 7 PASSED — Tất cả giá trị mặc định đúng")
    else:
        print("\n  ❌ TEST 7 FAILED")
    return passed


def test_8_write_read():
    """Test 8: Ghi và đọc lại tham số."""
    print("\n" + "=" * 60)
    print("🧪 TEST 8: Ghi/Đọc tham số mới")
    print("=" * 60)
    
    passed = True
    
    # Ghi tWD = 3000ms
    write_reg(REG_TWD_MS, 3000)
    time.sleep(0.1)
    val = read_reg(REG_TWD_MS)
    if val is not None and val != 3000:
        print(f"     ❌ FAIL: tWD_ms read back = {val}, expected 3000")
        passed = False
    
    # Ghi tRST = 1000ms
    write_reg(REG_TRST_MS, 1000)
    time.sleep(0.1)
    val = read_reg(REG_TRST_MS)
    if val is not None and val != 1000:
        print(f"     ❌ FAIL: tRST_ms read back = {val}, expected 1000")
        passed = False
    
    # Khôi phục giá trị mặc định
    write_reg(REG_TWD_MS, 1600)
    write_reg(REG_TRST_MS, 200)
    
    if passed:
        print("\n  ✅ TEST 8 PASSED — Ghi/đọc tham số đúng")
    else:
        print("\n  ❌ TEST 8 FAILED")
    return passed


def test_9_en_sw():
    """Test 9: Enable/Disable qua EN_SW."""
    print("\n" + "=" * 60)
    print("🧪 TEST 9: EN_SW Toggle")
    print("=" * 60)
    print("  ⚡ Nhấn giữ S2 trên board trước khi tiếp tục...")
    input("     Nhấn Enter khi đã giữ S2...")
    
    # Bật EN_SW
    write_reg(REG_CTRL, CTRL_EN_SW)
    time.sleep(0.2)
    
    print("\n  → Kiểm tra D4 (ENOUT) có sáng không?")
    get_status()
    
    # Tắt EN_SW
    print("\n  → Tắt EN_SW...")
    write_reg(REG_CTRL, 0x00)
    time.sleep(0.2)
    
    print("  → Kiểm tra D4 tắt (vẫn đang giữ S2)?")
    get_status()
    
    print("\n  ✅ TEST 9 — Kiểm tra bằng mắt: D4 sáng khi EN_SW=1, tắt khi EN_SW=0")


def test_10_uart_kick():
    """Test 10: Kick qua UART."""
    print("\n" + "=" * 60)
    print("🧪 TEST 10: UART Kick liên tục")
    print("=" * 60)
    
    print("  → Kick 5 lần, mỗi lần cách 1s...")
    for i in range(5):
        kick()
        print(f"     Kick {i + 1}/5")
        time.sleep(1.0)
    
    print("\n  → Kiểm tra: D3 phải TẮT suốt quá trình kick")
    get_status()
    
    print("\n  → Dừng kick, chờ timeout...")
    twd = 1600  # ms
    wait_time = (twd / 1000) + 0.5
    print(f"     Chờ {wait_time}s...")
    time.sleep(wait_time)
    
    print("\n  → Kiểm tra: D3 phải SÁNG (FAULT)")
    status = get_status()
    
    if status is not None and (status & STATUS_FAULT):
        print("\n  ✅ TEST 10 PASSED — Kick giữ watchdog, dừng kick → FAULT")
    else:
        print("\n  ⚠️  TEST 10 — Kiểm tra bằng mắt")


def test_11_clr_fault():
    """Test 11: CLR_FAULT qua UART."""
    print("\n" + "=" * 60)
    print("🧪 TEST 11: CLR_FAULT")
    print("=" * 60)
    
    print("  → Chờ FAULT...")
    time.sleep(2.0)
    
    print("  → Đọc STATUS (kỳ vọng FAULT=1):")
    get_status()
    
    print("\n  → Gửi CLR_FAULT (EN_SW=1 + CLR_FAULT=1)...")
    write_reg(REG_CTRL, CTRL_EN_SW | CTRL_CLR_FAULT)
    time.sleep(0.1)
    
    print("\n  → Đọc STATUS (kỳ vọng FAULT=0):")
    status = get_status()
    
    if status is not None and not (status & STATUS_FAULT):
        print("\n  ✅ TEST 11 PASSED — CLR_FAULT hoạt động")
    else:
        print("\n  ⚠️  TEST 11 — Kiểm tra bằng mắt")


def test_12_timing_change():
    """Test 12: Thay đổi timing on-the-fly."""
    print("\n" + "=" * 60)
    print("🧪 TEST 12: Thay đổi timing on-the-fly")
    print("=" * 60)
    
    print("  → Đặt tWD = 500ms, tRST = 2000ms...")
    write_reg(REG_TWD_MS, 500)
    write_reg(REG_TRST_MS, 2000)
    
    print("\n  → Quan sát D3 nhấp nháy:")
    print("     Chu kỳ mong đợi: TẮT 0.5s → SÁNG 2s → lặp lại")
    print("     Quan sát trong 10 giây...")
    
    for i in range(10):
        time.sleep(1.0)
        get_status()
    
    # Khôi phục mặc định
    print("\n  → Khôi phục giá trị mặc định...")
    write_reg(REG_TWD_MS, 1600)
    write_reg(REG_TRST_MS, 200)
    
    print("\n  ✅ TEST 12 — Kiểm tra bằng mắt: chu kỳ D3 thay đổi")


# ==================== INTERACTIVE MENU ====================

def interactive_menu():
    """Chế độ interactive để test thủ công."""
    print("\n" + "=" * 60)
    print("🎮 INTERACTIVE MENU — Watchdog UART Control")
    print("=" * 60)
    
    while True:
        print("\n┌─────────────────────────────────────┐")
        print("│  1. Đọc tất cả registers            │")
        print("│  2. Đọc STATUS                       │")
        print("│  3. KICK watchdog                     │")
        print("│  4. Bật EN_SW (enable via UART)       │")
        print("│  5. Tắt EN_SW                         │")
        print("│  6. CLR_FAULT                         │")
        print("│  7. Ghi tWD_ms                        │")
        print("│  8. Ghi tRST_ms                       │")
        print("│  9. Ghi arm_delay_us                  │")
        print("│  k. Kick liên tục (Ctrl+C để dừng)    │")
        print("│  0. Thoát                             │")
        print("└─────────────────────────────────────┘")
        
        choice = input("Chọn: ").strip().lower()
        
        if choice == '1':
            read_reg(REG_CTRL)
            read_reg(REG_TWD_MS)
            read_reg(REG_TRST_MS)
            read_reg(REG_ARM_DELAY)
            get_status()
        
        elif choice == '2':
            get_status()
        
        elif choice == '3':
            kick()
        
        elif choice == '4':
            write_reg(REG_CTRL, CTRL_EN_SW)
        
        elif choice == '5':
            write_reg(REG_CTRL, 0x00)
        
        elif choice == '6':
            # Đọc CTRL hiện tại để giữ EN_SW, thêm CLR_FAULT
            write_reg(REG_CTRL, CTRL_EN_SW | CTRL_CLR_FAULT)
        
        elif choice == '7':
            val = int(input("  tWD_ms = "))
            write_reg(REG_TWD_MS, val)
        
        elif choice == '8':
            val = int(input("  tRST_ms = "))
            write_reg(REG_TRST_MS, val)
        
        elif choice == '9':
            val = int(input("  arm_delay_us = "))
            write_reg(REG_ARM_DELAY, val)
        
        elif choice == 'k':
            interval = float(input("  Kick mỗi (giây, ví dụ 0.5): ") or "1.0")
            print(f"  → Kick liên tục mỗi {interval}s. Nhấn Ctrl+C để dừng...")
            try:
                count = 0
                while True:
                    count += 1
                    kick()
                    print(f"     Kick #{count}")
                    time.sleep(interval)
            except KeyboardInterrupt:
                print(f"\n  ⏹️  Dừng sau {count} kicks")
        
        elif choice == '0':
            break
        
        else:
            print("  ❓ Lựa chọn không hợp lệ")


# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description="Watchdog Timer UART Test")
    parser.add_argument("--port", type=str, help="Cổng COM (ví dụ: COM4)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Baud rate (default: 9600)")
    parser.add_argument("--menu", action="store_true", help="Chế độ interactive menu")
    parser.add_argument("--test", type=int, nargs="*", help="Chạy test cụ thể (7-12)")
    args = parser.parse_args()
    
    print("╔══════════════════════════════════════════╗")
    print("║   🐕 Watchdog Timer — UART Test Script   ║")
    print("║   Board: Kiwi 1P5 | UART: 9600 8N1      ║")
    print("╚══════════════════════════════════════════╝")
    
    try:
        open_serial(args.port, args.baud)
        
        if args.menu:
            interactive_menu()
        elif args.test:
            test_map = {
                7: test_7_read_defaults,
                8: test_8_write_read,
                9: test_9_en_sw,
                10: test_10_uart_kick,
                11: test_11_clr_fault,
                12: test_12_timing_change,
            }
            for t in args.test:
                if t in test_map:
                    test_map[t]()
                else:
                    print(f"⚠️  Test {t} không tồn tại (chọn 7-12)")
        else:
            # Chạy tất cả test tự động
            results = {}
            results[7] = test_7_read_defaults()
            results[8] = test_8_write_read()
            test_9_en_sw()
            test_10_uart_kick()
            test_11_clr_fault()
            test_12_timing_change()
            
            print("\n" + "=" * 60)
            print("📋 KẾT QUẢ TỔNG HỢP")
            print("=" * 60)
            for t, r in results.items():
                status = "✅ PASS" if r else "❌ FAIL"
                print(f"  Test {t}: {status}")
            print("  Test 9-12: Kiểm tra bằng mắt")
    
    except serial.SerialException as e:
        print(f"❌ Lỗi Serial: {e}")
    except KeyboardInterrupt:
        print("\n⏹️  Dừng bởi người dùng")
    finally:
        close_serial()


if __name__ == "__main__":
    main()
