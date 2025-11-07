# utils.py
# 描述: 包含项目中所有通用的、无状态的辅助函数。

import framebuf
import math

def draw_rect(display, x1, y1, x2, y2, c=1, b=1, f=False, sh=False):
    """在 display 对象上绘制矩形。"""
    if x1 > x2: x1, x2 = x2, x1
    if y1 > y2: y1, y2 = y2, y1
    w, h = x2 - x1 + 1, y2 - y1 + 1
    if f:
        display.fill_rect(x1, y1, w, h, c)
    elif b > 0:
        for i in range(b):
            if (x1 + i) > (x2 - i) or (y1 + i) > (y2 - i): break
            display.rect(x1 + i, y1 + i, w - 2 * i, h - 2 * i, c)
    if sh: display.show()

def draw_image(display, image_data, x, y, width, height, show=False):
    """
    将一块指定尺寸的单色位图数据写入到 FrameBuffer 的指定位置。
    """
    if image_data is None: return
    try:
        # 检查数据长度是否匹配，这是一个可选的健壮性检查
        # expected_bytes = math.ceil(width * height / 8)
        # if len(image_data) != expected_bytes:
        #     print(f"警告: draw_image 数据长度不匹配 (预期 {expected_bytes}, 得到 {len(image_data)})")
        #     return
        
        image_buffer = framebuf.FrameBuffer(
            bytearray(image_data),
            width,
            height,
            framebuf.MONO_HLSB
        )
        display.blit(image_buffer, x, y)
        if show:
            display.show()
    except Exception as e:
        print(f"警告: draw_image 失败: {e}")

# 如果未来有其他通用函数，也可以放在这里。例如：
# def get_char_width(char: str) -> int: ...