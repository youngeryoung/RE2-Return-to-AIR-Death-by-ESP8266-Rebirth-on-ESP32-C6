# ucrc32.py
def ucrc32(data, crc=0):
    crc ^= 0xffffffff
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xffffffff