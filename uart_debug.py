"""Test Frame Parser — full system."""
import serial, time

ser = serial.Serial('COM9', 9600, timeout=2)
time.sleep(0.5)
ser.reset_input_buffer()

def xor_chk(data_list):
    chk = 0
    for b in data_list: chk ^= b
    return chk

def send_frame(cmd, addr, data_bytes, resp_len=9):
    payload = [cmd, addr, len(data_bytes)] + list(data_bytes)
    chk = xor_chk(payload)
    frame = bytes([0x55] + payload + [chk])
    print(f'  TX: {frame.hex(" ")}')
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(0.5)
    avail = ser.in_waiting
    if avail > 0:
        resp = ser.read(avail)
        print(f'  RX: {resp.hex(" ")}  ({avail} bytes)')
        return resp
    else:
        print(f'  RX: (empty)')
        return b''

print('='*50)
print('  Frame Parser Test')
print('='*50)

# Test 1: KICK
print('\n🦵 KICK:')
r = send_frame(0x03, 0x00, [])

# Test 2: READ tWD_ms (default=1600)
print('\n📖 READ tWD_ms:')
r = send_frame(0x02, 0x04, [])
if len(r) >= 8:
    val = r[4] | (r[5]<<8) | (r[6]<<16) | (r[7]<<24)
    print(f'  Value = {val} (expect 1600)')

# Test 3: STATUS
print('\n📊 STATUS:')
r = send_frame(0x04, 0x10, [])
if len(r) >= 8:
    val = r[4] | (r[5]<<8) | (r[6]<<16) | (r[7]<<24)
    print(f'  EN={val&1} FAULT={(val>>1)&1} ENOUT={(val>>2)&1} WDO={(val>>3)&1}')

ser.close()
print('\n✅ Done')
