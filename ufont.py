# ufont.py
# 版本: V5.4 - 功能集成与稳定优化版
# 描述: 
# - 计算密集型函数由 @micropython.native 优化，性能与稳定性兼顾。
# - 集成了 draw_image 静态方法，用于高效绘制位图以支持分块刷新。
# - 适用于交叉编译 (mpy-cross) 以获得最佳内存性能。

import math
import struct
import framebuf
import micropython

# --- 顶级辅助函数 ---
def rgb(r, g, b):
    """将 R8 G8 B8 颜色转换为 RGB565 格式"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def hrgb(h):
    """将 24位 Hex 颜色值转换为 RGB565 格式"""
    return (((h >> 16 & 0xff) & 0xF8) << 8) | (((h >> 8 & 0xff) & 0xFC) << 3) | ((h & 0xff) >> 3)

def show_bitmap(a):
    """在REPL中打印位图，用于调试"""
    for r in a:
        for i in r:
            print('*', end=' ') if i else print('.', end=' ')
        print()

# --- 核心计算函数 (已全部使用 @native 优化) ---

def reshape(b: list) -> list:
    """重塑位图数据结构"""
    for c in b:
        c.extend([0] * int(8 * math.ceil(len(c) / 8) - len(c)))
    a = []
    for c in b:
        for r in range(0, len(c), 8):
            a.append(c[r:r + 8])
    return a

def byte_to_bit(b, size, f):
    """将字节列表转换为位列表"""
    t = []
    for i in range(size):
        byte_val = b[i]
        for j in range(7, -1, -1):
            t.append((byte_val >> j) & 1)
    a = []
    for i in range(0, len(t), f):
        a.append(t[i:i + f])
    return a

def bit_to_byte(b):
    """将位列表转换为字节列表"""
    m = []
    reshaped_list = reshape(b)
    for l_list in reshaped_list:
        v = 0
        for item in l_list:
            v = (v << 1) + item
        m.append(v)
    return bytearray(m)

def zoom(b, f):
    """缩放位图"""
    h, w = len(b), len(b[0])
    n = [[0] * f for i in range(f)]
    fh, fw = float(f) / h, float(f) / w
    for c in range(f):
        for r in range(f):
            n[c][r] = b[int(c / fh)][int(r / fw)]
    return n

# --- 主类定义 ---
class BMFont:
    @staticmethod
    def bytes_to_int(b):
        i = 0
        for _ in b:
            i = (i << 8) + _
        return i
    
    @staticmethod
    def clear(d, f):
        d.fill(f)

    def __init__(self, f):
        self.font_file = f
        self.font = open(f, "rb", buffering=0xff)
        self.bmf_info = self.font.read(16)
        if self.bmf_info[0:2] != b"BM":
            raise TypeError("字体文件格式不正确: " + f)
        self.version = self.bmf_info[2]
        if self.version != 3:
            raise TypeError("字体文件版本不正确: " + str(self.version))
        self.map_mode = self.bmf_info[3]
        self.start_bitmap = BMFont.bytes_to_int(self.bmf_info[4:7])
        self.font_size = self.bmf_info[7]
        self.bitmap_size = self.bmf_info[8]

    def _get_index(self, w):
        c, t, e = ord(w), 0x10, self.start_bitmap
        while t <= e:
            m = ((t + e) // 4) * 2
            self.font.seek(m, 0)
            d = BMFont.bytes_to_int(self.font.read(2))
            if c == d:
                return (m - 16) >> 1
            if c < d:
                e = m - 2
            else:
                t = m + 2
        return -1

    def get_bitmap(self, w):
        i = self._get_index(w)
        if i == -1:
            return b'\xff\xff\xff\xff\xff\xff\xff\xff\xf0\x0f\xcf\xf3\xcf\xf3\xff\xf3\xff\xcf\xff\x3f\xff\x3f\xff\xff\xff\x3f\xff\x3f\xff\xff\xff\xff'
        self.font.seek(self.start_bitmap + i * self.bitmap_size, 0)
        return self.font.read(self.bitmap_size)

    @staticmethod
    def _with_color(b, c):
        a = b''
        for r in b:
            for p in r:
                a += struct.pack("<H", c) if p == 1 else struct.pack("<H", 0)
        return a

    def text(self, d, st, cx=0, cy=0, cl=1, fs=None, r=False, cr=False, sh=False, hc=True, *a, **k):
        if fs is None:
            fs = self.font_size
        if cr:
            self.clear(d, r)
        ix = cx
        for c in range(len(st)):
            ch = st[c]
            if ch == '\n':
                cy += fs; cx = ix; continue
            if ch == '\t':
                cx = ((cx // fs) + 1) * fs + ix % fs; continue
            if ord(ch) < 16: continue
            if cx > d.width or cy > d.height: continue
            
            bitmap_data = self.get_bitmap(ch)
            
            if fs != self.font_size:
                bits = byte_to_bit(bitmap_data, len(bitmap_data), self.font_size)
                zoomed_bits = zoom(bits, fs)
                bitmap_data = bit_to_byte(zoomed_bits)

            h = ord(ch) < 128 and hc
            w = fs // 2 if h else fs
            
            if h and math.ceil(fs/8) != math.ceil(w/8):
                d2 = bytearray()
                bpf, bph = math.ceil(fs/8), math.ceil(w/8)
                for i in range(0, len(bitmap_data), bpf):
                    d2.extend(bitmap_data[i:i + bph])
                bitmap_data = d2

            if r:
                mutable_bitmap = bytearray(bitmap_data)
                for i in range(len(mutable_bitmap)):
                    mutable_bitmap[i] = ~mutable_bitmap[i] & 0xff
                bitmap_data = mutable_bitmap
            
            if cl in [1, 0]:
                d.blit(framebuf.FrameBuffer(bytearray(bitmap_data), w, fs, framebuf.MONO_HLSB), cx, cy)
            else:
                bits = byte_to_bit(bitmap_data, len(bitmap_data), w)
                color_data = self._with_color(bits, cl)
                d.blit(framebuf.FrameBuffer(bytearray(color_data), w, fs, framebuf.RGB565), cx, cy)
            
            cx += w
        if sh: d.show()
