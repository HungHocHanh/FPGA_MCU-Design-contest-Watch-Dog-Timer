import serial, time

# Đổi 'COM4' thành cổng COM thực tế trên máy bạn
ser = serial.Serial('COM9', 9600, timeout=1)
time.sleep(0.5)  # Đợi board ổn định
def xor_chk(data_list):
    chk = 0
    for b in data_list: chk ^= b
    return chk

def send_frame(cmd, addr, data_bytes):
    payload = [cmd, addr, len(data_bytes)] + list(data_bytes)
    chk = xor_chk(payload)
    frame = bytes([0x55] + payload + [chk])
    ser.write(frame)
    resp = ser.read(8)
    return resp

def write_reg(addr, val_32):
    data = [(val_32 >> (8*i)) & 0xFF for i in range(4)]
    r = send_frame(0x01, addr, data)
    print(f'WRITE 0x{addr:02X}={val_32} -> {r.hex()}')

def read_reg(addr):
    r = send_frame(0x02, addr, [])
    print(f'READ  0x{addr:02X} -> {r.hex()}')
    return r

def kick():
    r = send_frame(0x03, 0x00, [])
    print(f'KICK  -> {r.hex()}')

def get_status():
    r = send_frame(0x04, 0x10, [])
    print(f'STATUS-> {r.hex()}')

# === TEST CASES ===
# 1. Đặt tWD = 500ms để test nhanh hơn
write_reg(0x04, 500)

# 2. Bật EN qua UART (EN_SW bit0 của CTRL)
write_reg(0x00, 0x01)  # EN_SW = 1

# 3. Kick watchdog
kick()
time.sleep(2)
kick()
time.sleep(2)
kick()
time.sleep(2)
kick()
time.sleep(2)
kick()
# 4. Đọc STATUS
get_status()

# 5. Để timeout (không kick 500ms) rồi xem WDO
time.sleep(0.7)
get_status()  # Kỳ vọng: FAULT_ACTIVE=1, WDO=0

# 6. CLR_FAULT
write_reg(0x00, 0x05)  # EN_SW=1, CLR_FAULT=1

ser.close()
