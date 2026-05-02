#!/usr/bin/env python3
"""
Watchdog Timer UART Test Script
================================
Communicates with FPGA Watchdog via UART (9600 8N1).
Based on protocol from HuongDan_FPGA_Contest_2026_v2.docx

Frame format: [0x55][CMD][ADDR][LEN][DATA...][CHK]
- CHK = XOR of all bytes from CMD to end of DATA

Usage:
    python uart_test.py              # Run all tests
    python uart_test.py --port COM9  # Specify COM port
    python uart_test.py --menu       # Interactive menu mode
"""

import serial
import serial.tools.list_ports
import time
import sys
import argparse

# ==================== CONFIGURATION ====================
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
    """Auto-detect available COM port."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("ERROR: No COM ports found!")
        print("   -> Check USB-C UART connection (bottom port) on Kiwi 1P5")
        sys.exit(1)

    print("Available COM ports:")
    for i, p in enumerate(ports):
        print(f"   [{i}] {p.device} - {p.description}")

    if len(ports) == 1:
        print(f"   -> Auto-selected: {ports[0].device}")
        return ports[0].device

    choice = input("Select port (number): ").strip()
    return ports[int(choice)].device


def open_serial(port=None, baud=DEFAULT_BAUD):
    """Open serial connection."""
    global ser
    if port is None:
        port = find_com_port()

    ser = serial.Serial(port, baud, timeout=TIMEOUT)
    time.sleep(0.1)  # Wait for connection to stabilize
    ser.reset_input_buffer()
    print(f"Connected to {port} @ {baud} bps\n")
    return ser


def close_serial():
    """Close serial connection."""
    global ser
    if ser and ser.is_open:
        ser.close()
        print("Serial connection closed.")


def xor_checksum(data_list):
    """Calculate XOR checksum."""
    chk = 0
    for b in data_list:
        chk ^= b
    return chk


def send_frame(cmd, addr, data_bytes):
    """
    Send UART frame and receive response.

    Frame: [0x55][CMD][ADDR][LEN][DATA...][CHK]
    CHK = XOR(CMD, ADDR, LEN, DATA...)
    """
    payload = [cmd, addr, len(data_bytes)] + list(data_bytes)
    chk = xor_checksum(payload)
    frame = bytes([0x55] + payload + [chk])

    ser.reset_input_buffer()
    ser.write(frame)

    # Wait for response (max 8 bytes)
    resp = ser.read(8)
    return resp


def write_reg(addr, val_32):
    """Write a 32-bit value to a register (little-endian)."""
    data = [(val_32 >> (8 * i)) & 0xFF for i in range(4)]
    resp = send_frame(CMD_WRITE, addr, data)

    addr_name = {0x00: "CTRL", 0x04: "tWD_ms", 0x08: "tRST_ms", 0x0C: "arm_delay_us"}.get(addr, f"0x{addr:02X}")
    print(f"  WRITE {addr_name} = {val_32} (0x{val_32:08X})")

    if resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     WARNING: No response received!")
    return resp


def read_reg(addr):
    """Read value from a register."""
    resp = send_frame(CMD_READ, addr, [])

    addr_name = {
        0x00: "CTRL", 0x04: "tWD_ms", 0x08: "tRST_ms",
        0x0C: "arm_delay_us", 0x10: "STATUS"
    }.get(addr, f"0x{addr:02X}")

    print(f"  READ  {addr_name}")
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
        print(f"     WARNING: No response received!")
    return None


def kick():
    """Send watchdog kick command via UART."""
    resp = send_frame(CMD_KICK, 0x00, [])
    print(f"  KICK")
    if resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     WARNING: No response received!")
    return resp


def get_status():
    """Read and parse STATUS register."""
    resp = send_frame(CMD_STATUS, REG_STATUS, [])

    print(f"  STATUS")
    if resp and len(resp) >= 8:
        val = 0
        for i in range(4):
            if 4 + i < len(resp):
                val |= resp[4 + i] << (8 * i)

        print(f"     Raw: {resp.hex(' ')}")
        print(f"     Value: 0x{val:08X}")
        print(f"     +-- EN_EFF       = {(val >> 0) & 1}  {'(Enabled)'  if val & STATUS_EN_EFF  else '(Disabled)'}")
        print(f"     +-- FAULT_ACTIVE = {(val >> 1) & 1}  {'[FAULT!]'   if val & STATUS_FAULT   else '[OK]'}")
        print(f"     +-- ENOUT        = {(val >> 2) & 1}  {'(Running)'  if val & STATUS_ENOUT   else '(Idle)'}")
        print(f"     +-- WDO          = {(val >> 3) & 1}  {'[Fault Out]' if val & STATUS_WDO    else '[Normal]'}")
        print(f"     +-- KICK_SRC     = {(val >> 4) & 1}  {'(UART)'     if val & STATUS_KICK_SRC else '(Button)'}")
        return val
    elif resp:
        print(f"     Response: {resp.hex(' ')}")
    else:
        print(f"     WARNING: No response received!")
    return None


# ==================== TEST CASES ====================

def test_7_read_defaults():
    """Test 7: Read default register values."""
    print("\n" + "=" * 60)
    print("TEST 7: Read Default Values")
    print("=" * 60)

    passed = True

    val = read_reg(REG_TWD_MS)
    if val is not None and val != 1600:
        print(f"     FAIL: tWD_ms = {val}, expected 1600")
        passed = False

    val = read_reg(REG_TRST_MS)
    if val is not None and val != 200:
        print(f"     FAIL: tRST_ms = {val}, expected 200")
        passed = False

    val = read_reg(REG_ARM_DELAY)
    if val is not None and val != 150:
        print(f"     FAIL: arm_delay_us = {val}, expected 150")
        passed = False

    val = read_reg(REG_CTRL)

    if passed:
        print("\n  TEST 7 PASSED - All default values correct")
    else:
        print("\n  TEST 7 FAILED")
    return passed


def test_8_write_read():
    """Test 8: Write and read back parameters."""
    print("\n" + "=" * 60)
    print("TEST 8: Write/Read Parameters")
    print("=" * 60)

    passed = True

    # Write tWD = 3000ms
    write_reg(REG_TWD_MS, 3000)
    time.sleep(0.1)
    val = read_reg(REG_TWD_MS)
    if val is not None and val != 3000:
        print(f"     FAIL: tWD_ms read back = {val}, expected 3000")
        passed = False

    # Write tRST = 1000ms
    write_reg(REG_TRST_MS, 1000)
    time.sleep(0.1)
    val = read_reg(REG_TRST_MS)
    if val is not None and val != 1000:
        print(f"     FAIL: tRST_ms read back = {val}, expected 1000")
        passed = False

    # Restore defaults
    write_reg(REG_TWD_MS, 1600)
    write_reg(REG_TRST_MS, 200)

    if passed:
        print("\n  TEST 8 PASSED - Write/read back correct")
    else:
        print("\n  TEST 8 FAILED")
    return passed


def test_9_en_sw():
    """Test 9: Enable/Disable via EN_SW."""
    print("\n" + "=" * 60)
    print("TEST 9: EN_SW Toggle")
    print("=" * 60)
    print("  ACTION: Press and hold S2 on board before continuing...")
    input("     Press Enter when S2 is held...")

    # Enable EN_SW
    write_reg(REG_CTRL, CTRL_EN_SW)
    time.sleep(0.2)

    print("\n  -> Check: D4 (ENOUT) should be ON?")
    get_status()

    # Disable EN_SW
    print("\n  -> Disabling EN_SW...")
    write_reg(REG_CTRL, 0x00)
    time.sleep(0.2)

    print("  -> Check: D4 should be OFF (S2 still held)?")
    get_status()

    print("\n  TEST 9 - Visual check: D4 ON when EN_SW=1, OFF when EN_SW=0")


def test_10_uart_kick():
    """Test 10: Kick via UART."""
    print("\n" + "=" * 60)
    print("TEST 10: Continuous UART Kick")
    print("=" * 60)

    print("  -> Kicking 5 times, 1s apart...")
    for i in range(5):
        kick()
        print(f"     Kick {i + 1}/5")
        time.sleep(1.0)

    print("\n  -> Check: D3 should be OFF during kick sequence")
    get_status()

    print("\n  -> Stopping kicks, waiting for timeout...")
    twd = 1600  # ms
    wait_time = (twd / 1000) + 0.5
    print(f"     Waiting {wait_time}s...")
    time.sleep(wait_time)

    print("\n  -> Check: D3 should be ON (FAULT)")
    status = get_status()

    if status is not None and (status & STATUS_FAULT):
        print("\n  TEST 10 PASSED - Kick kept watchdog alive, stop kick -> FAULT")
    else:
        print("\n  TEST 10 - Visual check required")


def test_11_clr_fault():
    """Test 11: CLR_FAULT via UART."""
    print("\n" + "=" * 60)
    print("TEST 11: CLR_FAULT")
    print("=" * 60)

    print("  -> Waiting for FAULT...")
    time.sleep(2.0)

    print("  -> Read STATUS (expect FAULT=1):")
    get_status()

    print("\n  -> Send CLR_FAULT (EN_SW=1 + CLR_FAULT=1)...")
    write_reg(REG_CTRL, CTRL_EN_SW | CTRL_CLR_FAULT)
    time.sleep(0.1)

    print("\n  -> Read STATUS (expect FAULT=0):")
    status = get_status()

    if status is not None and not (status & STATUS_FAULT):
        print("\n  TEST 11 PASSED - CLR_FAULT working correctly")
    else:
        print("\n  TEST 11 - Visual check required")


def test_12_timing_change():
    """Test 12: Change timing on-the-fly."""
    print("\n" + "=" * 60)
    print("TEST 12: Timing Change On-The-Fly")
    print("=" * 60)

    print("  -> Set tWD = 500ms, tRST = 2000ms...")
    write_reg(REG_TWD_MS, 500)
    write_reg(REG_TRST_MS, 2000)

    print("\n  -> Observe D3 blinking:")
    print("     Expected cycle: OFF 0.5s -> ON 2s -> repeat")
    print("     Observing for 10 seconds...")

    for i in range(10):
        time.sleep(1.0)
        get_status()

    # Restore defaults
    print("\n  -> Restoring default values...")
    write_reg(REG_TWD_MS, 1600)
    write_reg(REG_TRST_MS, 200)

    print("\n  TEST 12 - Visual check: D3 blink cycle should change")


# ==================== INTERACTIVE MENU ====================

def interactive_menu():
    """Interactive mode for manual testing."""
    print("\n" + "=" * 60)
    print("INTERACTIVE MENU - Watchdog UART Control")
    print("=" * 60)

    while True:
        print("\n+-------------------------------------+")
        print("|  1. Read all registers              |")
        print("|  2. Read STATUS                     |")
        print("|  3. KICK watchdog                   |")
        print("|  4. Enable EN_SW (via UART)         |")
        print("|  5. Disable EN_SW                   |")
        print("|  6. CLR_FAULT                       |")
        print("|  7. Write tWD_ms                    |")
        print("|  8. Write tRST_ms                   |")
        print("|  9. Write arm_delay_us              |")
        print("|  k. Continuous kick (Ctrl+C to stop)|")
        print("|  0. Exit                            |")
        print("+-------------------------------------+")

        choice = input("Select: ").strip().lower()

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
            # Keep EN_SW bit, set CLR_FAULT
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
            interval = float(input("  Kick every (seconds, e.g. 0.5): ") or "1.0")
            print(f"  -> Kicking every {interval}s. Press Ctrl+C to stop...")
            try:
                count = 0
                while True:
                    count += 1
                    kick()
                    print(f"     Kick #{count}")
                    time.sleep(interval)
            except KeyboardInterrupt:
                print(f"\n  Stopped after {count} kicks")

        elif choice == '0':
            break

        else:
            print("  Invalid selection")


# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description="Watchdog Timer UART Test")
    parser.add_argument("--port", type=str, help="COM port (e.g. COM9)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Baud rate (default: 9600)")
    parser.add_argument("--menu", action="store_true", help="Interactive menu mode")
    parser.add_argument("--test", type=int, nargs="*", help="Run specific test(s) (7-12)")
    args = parser.parse_args()

    print("=" * 44)
    print("   Watchdog Timer - UART Test Script")
    print("   Board: Kiwi 1P5 | UART: 9600 8N1")
    print("=" * 44)

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
                    print(f"WARNING: Test {t} does not exist (choose 7-12)")
        else:
            # Run all tests automatically
            results = {}
            results[7] = test_7_read_defaults()
            results[8] = test_8_write_read()
            test_9_en_sw()
            test_10_uart_kick()
            test_11_clr_fault()
            test_12_timing_change()

            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            for t, r in results.items():
                status = "PASS" if r else "FAIL"
                print(f"  Test {t}: {status}")
            print("  Test 9-12: Visual inspection required")

    except serial.SerialException as e:
        print(f"Serial Error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        close_serial()


if __name__ == "__main__":
    main()
