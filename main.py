# main.py
from machine import I2C, Pin, reset
import time
import ufont
import ssd1306
import gc
import re
import os
import struct
import ucrc32
from data_reader import DataReader
from buzzer_player import SongPlayer
from cg_player import CGPlayer
from buttons import Button
from engine import ScriptEngine
from utils import draw_image, draw_rect
Pin(8,Pin.OUT).value(0)
# =============================================================================
# 1. 底层硬件初始化 & 欢迎界面
# =============================================================================
print("正在初始化硬件...")
i2c = I2C(0, scl=Pin(7), sda=Pin(6),freq=400000)
display = ssd1306.SSD1306_I2C(128, 64, i2c)
font = ufont.BMFont("1.bmf")
print("正在显示欢迎界面...")
display.fill(0)
font.text(display, "Re2:再次从零开始的AIRESP32C6移植", cx=0, cy=0, r=1)
font.text(display, "♦ Crafted by Young ♦", cx=48, cy=8)
font.text(display, "如你所见，单片机的右下角焊接了↘", cx=0, cy=16)
font.text(display, "  三个按钮。他们的功能依次是：", cx=0, cy=24)
font.text(display, "☀  确定  ☀ 下一项 ☀  菜单", cx=4, cy=35)
font.text(display, "请用确定键翻页,菜单键唤出离开菜单", cx=-1, cy=45)
font.text(display, ">> 长按 [确定],奔赴千年之约 <<", cx=4, cy=56, r=1)
display.show()
gc.collect()
# =============================================================================
# 2. 存档系统检查
# =============================================================================
def check_and_init_save():
    """检查存档完整性，并在必要时创建或恢复。"""
    SAVE_FILE = 'save.dat'; BACKUP_FILE = 'save.bak'
    
    SAVE_FORMAT_INTS = '<IHBBBHHHH'
    CRC_FORMAT = '<I'
    SAVE_SIZE = struct.calcsize(SAVE_FORMAT_INTS) + struct.calcsize(CRC_FORMAT)

    def is_valid(filepath):
        try:
            with open(filepath, 'rb') as f: data = f.read()
            if len(data) != SAVE_SIZE: return False
            
            int_payload = data[:struct.calcsize(SAVE_FORMAT_INTS)]
            saved_crc_bytes = data[struct.calcsize(SAVE_FORMAT_INTS):]
            
            saved_crc = struct.unpack('<I', saved_crc_bytes)[0]
            return saved_crc == ucrc32.ucrc32(int_payload)
        except:
            return False

    if not is_valid(SAVE_FILE):
        print(f"'{SAVE_FILE}' 损坏或不存在。正在检查备份...")
        if is_valid(BACKUP_FILE):
            print("备份文件正常，正在从备份恢复...")
            try:
                with open(BACKUP_FILE, 'rb') as f_bak, open(SAVE_FILE, 'wb') as f_sav:
                    f_sav.write(f_bak.read())
                print("恢复成功！")
            except Exception as e:
                print(f"从备份恢复失败: {e}")
        else:
            print("备份文件也异常。正在创建新的空白存档...")
            try:
                # --- 核心修正：使用完全展开后的格式打包 ---
                initial_payload = struct.pack(SAVE_FORMAT_INTS, 0, 65535, 7, 17, 1, 65535, 65535, 65535, 65535)
                crc = ucrc32.ucrc32(initial_payload)
                with open(SAVE_FILE, 'wb') as f:
                    f.write(initial_payload + struct.pack('<I', crc))
                print("新存档创建成功。")
            except Exception as e:
                print(f"创建新存档失败: {e}")

check_and_init_save()

# --- 按钮状态初始化 ---
DEBOUNCE_MS = const(20)
LONG_PRESS_MS = const(500)

# inverted=False 因为 PULL_DOWN 时，按下是高电平
btn_confirm = Button(pin_id=15, pull=Pin.PULL_DOWN, inverted=False, debounce_ms=DEBOUNCE_MS, long_press_ms=LONG_PRESS_MS)
btn_next = Button(pin_id=19, pull=Pin.PULL_DOWN, inverted=False, debounce_ms=DEBOUNCE_MS, long_press_ms=LONG_PRESS_MS)
btn_menu = Button(pin_id=20, pull=Pin.PULL_DOWN, inverted=False, debounce_ms=DEBOUNCE_MS, long_press_ms=LONG_PRESS_MS)

# =============================================================================
# 3. “幕后”核心模块实例化
# =============================================================================
print("正在预加载核心模块...")
if 1:
    # --- 核心修正：不再加载和使用 assets_manifest.json ---
    bg_reader = DataReader('/bg.dat', 96 * 48 // 8)
    cg_reader = DataReader('/cg.dat', 24 * 48 // 8)
    op_reader = DataReader('/op.dat', 96 * 48 // 8)
    
    music_player = SongPlayer(pin0=0, pin1=3)
    op_player = CGPlayer(display, font, music_player=music_player, image_reader=op_reader)
    # --- 核心修正：不再传递 config 给 ScriptEngine ---
    game_engine = ScriptEngine(display, font, music_player, bg_reader, cg_reader)
    
    gc.collect() # 尽早回收内存
    
    print("核心模块加载完毕。")

# =============================================================================
# 4. 进入主循环
# =============================================================================
MODE_WELCOME = 0; MODE_TITLE = 1; MODE_OP = 2; MODE_GAME = 3
current_mode = MODE_WELCOME

title_selection = 0
title_options = ["从头开始", "读取存档", "声音", "—重置—"]
sound_enabled = True

def draw_title_menu():
    """绘制标题菜单界面。"""
    display.fill(0)
    try:
        # 封面背景的索引硬编码为 0
        bg_data = bg_reader.read_chunk(0)
        if bg_data: draw_image(display, bg_data, 32, 16, 96, 48) # 调用导入的函数
    except Exception: pass

    font.text(display, "Summer stretches on endlessly.", 4, 0)
    font.text(display, "BeneathTheAirInWhichSheAwaits.", 4, 8)
    
    y_coords = [18, 28, 38, 48]
    for i, option in enumerate(title_options):
        text_to_draw = option
        if "声音" in option:
            text_to_draw = f"声音：{'开' if sound_enabled else '关'}"
        
        is_selected = (i == title_selection)
        font.text(display, text_to_draw, 2, y_coords[i], r=is_selected)
            
    display.show()

print("进入主循环...")
loop_counter = 0
while True:
    # B. 统一更新输入
    btn_confirm.update()
    btn_next.update()
    btn_menu.update()
    
    if current_mode == MODE_WELCOME:
        if btn_confirm.was_long_pressed():
            print("欢迎界面已确认，切换到标题模式。")
            current_mode = MODE_TITLE
            title_selection = 0
            draw_title_menu()


            
    elif current_mode == MODE_TITLE:
        redraw_menu = False
        if btn_next.was_pressed():
            title_selection = (title_selection + 1) % len(title_options)
            redraw_menu = True
        
        if btn_confirm.was_pressed():
            if title_selection == 0: # 从头开始
                current_mode = MODE_OP
                op_player.play()
                time.sleep_ms(100) # [FIX] 添加短延迟
            elif title_selection == 1: # 读取存档
                # --- [NEW] 新的调用方式 ---
                if game_engine.load_state(from_title_menu=True):
                    current_mode = MODE_GAME
                else: 
                    redraw_menu = True
                time.sleep_ms(100) # [FIX] 添加短延迟
            elif title_selection == 2: # 声音
                sound_enabled = not sound_enabled
                game_engine.sound_enabled = sound_enabled
                if not sound_enabled: music_player.stop()
                redraw_menu = True
                time.sleep_ms(100) # [FIX] 添加短延迟
            elif title_selection == 3: # 重置
                print("正在重置存档并重启...")
                try: os.remove('save.dat')
                except OSError: pass
                try: os.remove('save.bak')
                except OSError: pass
                display.clear(); font.text(display, "重置完成...", 0, 0, r=1); display.show()
                time.sleep(1)
                reset()
                
        if redraw_menu:
            draw_title_menu()
            time.sleep_ms(150) # 防止按键过快连发
            
    elif current_mode == MODE_OP:
        op_player.update()
        music_player.poll()
        if btn_confirm.was_pressed() or btn_next.was_pressed() or btn_menu.was_pressed():
            op_player.skip()
        if not op_player.is_playing():
            current_mode = MODE_GAME
            game_engine.start(0)

    elif current_mode == MODE_GAME:
        # --- [关键修正] ---
        # 在处理游戏逻辑之前，确保画面是最新的
        # (这行代码可能不是必须的，但加上更保险)
        if game_engine.is_running() and game_engine._wait_mode == 'none':
             game_engine._redraw_scene()
             game_engine._draw_sidebar()

        game_engine.update(
            btn_confirm.was_pressed(), 
            btn_next.was_pressed(),
            btn_menu.was_pressed()
        )
        music_player.poll()
        if not game_engine.is_running():
            print("游戏脚本结束，返回标题界面。")
            current_mode = MODE_TITLE
            title_selection = 0
            music_player.stop()
            draw_title_menu()
    # D. 垃圾回收与延时
    gc.collect()
    time.sleep_ms(20)