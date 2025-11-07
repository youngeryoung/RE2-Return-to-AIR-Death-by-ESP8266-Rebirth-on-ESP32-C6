# engine.py (V3.0 - In-Memory Index)
import time
import struct
import os
from ufont import BMFont
from buzzer_player import SongPlayer
from data_reader import DataReader
import ucrc32
from micropython import const
from utils import draw_image, draw_rect

# --- UI 布局常量 ---
_CHOICE_BOX_X = const(46)
_CHOICE_BOX_W = const(68)
_CHOICE_BOX_H = const(11)
_CHOICE_TEXT_X_OFFSET = const(1)

class ScriptEngine:
    def __init__(self, display, font: BMFont, music_player: SongPlayer, bg_reader: DataReader, cg_reader: DataReader):
        self.display = display
        self.font = font
        self.music_player = music_player
        self.bg_reader = bg_reader
        self.cg_reader = cg_reader
        self.sound_enabled = True
        
        self._script_file_handle = None
        self._index_data = None # 将用于存储整个索引文件内容
        self._total_lines = 0
        
        try:
            # --- [REFACTOR] 一次性加载整个索引文件 ---
            print("正在加载脚本索引到内存...")
            with open('final_script.idx', 'rb') as f_idx:
                self._index_data = f_idx.read()
            
            self._total_lines = len(self._index_data) // 4
            self._script_file_handle = open('final_script.txt', 'r', encoding='utf-8')
            
            print(f"脚本引擎: 成功加载索引 ({self._total_lines} 行) 并打开脚本。")
        except Exception as e:
            print(f"致命错误: 脚本或索引文件打开失败! {e}")
            self.stop()
            
        self._pc = 0
        self._is_running = False
        self._wait_mode = 'none'
        self._game_date = {'month': 7, 'day': 17, 'dow': 1}
        self._day_map = {0:'SUN', 1:'MON', 2:'TUE', 3:'WED', 4:'THU', 5:'FRI', 6:'SAT'}
        self._month_map = {1:"J A N", 2:"F E B", 3:"M A R", 4:"A P R", 5:"M A Y", 6:"J U N", 7:"J U LY", 8:"A U G", 9:"S E P", 10:"O C T", 11:"N O V", 12:"D E C"}
        self._screen_state = {'bg': None, 'cg_l': None, 'cg_c': None, 'cg_r': None, 'bgm_idx': 65535}
        self._choice_options = []
        self._selected_choice = 0
        self.sidebar_options = [" Q.Save ", "  Auto  ", " Q.Load ", "  HOME  ", "返回游戏"]
        self.sidebar_selection = 0
        self._save_format_ints = '<IHBBBHHHH'
        self._auto_mode = False
        self._auto_wait_until_ms = 0

    def start(self, start_line_num_0_based: int = 0):
        print(f"脚本引擎: 从第 {start_line_num_0_based + 1} 行开始执行。")
        self._pc = start_line_num_0_based
        self._is_running = True
        self._wait_mode = 'none'
        self._screen_state = {'bg': None, 'cg_l': None, 'cg_c': None, 'cg_r': None, 'bgm_idx': 65535}
        self._redraw_scene()
        self._draw_sidebar()
    
    def stop(self):
        self._is_running = False
        if self._script_file_handle: self._script_file_handle.close(); self._script_file_handle = None
        self._index_data = None # 释放内存
        print("脚本引擎: 已停止，所有文件句柄已关闭，索引内存已释放。")

    def is_running(self) -> bool:
        return self._is_running

    def _get_line(self, line_num_1_based: int) -> str:
        """
        [终极校验版] 校验从内存解包的索引值，并验证 seek 操作。
        """
        if not (self._index_data and self._script_file_handle and 1 <= line_num_1_based <= self._total_lines):
            return ""
        
        index_offset = (line_num_1_based - 1) * 4
        
        # --- 校验点 1: 解包索引值 ---
        # 我们一次性解包前几个值，看看它们是否与您的十六进制 dump 匹配
        if line_num_1_based == 1:
            offset1, offset2, offset3 = struct.unpack_from('<III', self._index_data, 0)
            print(f"  VALIDATION: Index offsets for lines 1, 2, 3 are: {offset1}, {offset2}, {offset3}")
            # 根据您提供的 dump: 应该是 0, 7, 17
            
        script_offset = struct.unpack_from('<I', self._index_data, index_offset)[0]
        
        print(f"  _get_line({line_num_1_based}): Unpacked script_offset = {script_offset}")

        # --- 校验点 2: 验证 seek 操作 ---
        current_pos_before_seek = self._script_file_handle.tell()
        self._script_file_handle.seek(script_offset)
        current_pos_after_seek = self._script_file_handle.tell()
        
        print(f"  _get_line({line_num_1_based}): Seek from {current_pos_before_seek} to {script_offset}. Position after seek: {current_pos_after_seek}")

        # --- 校验点 3: 检查 seek 是否成功 ---
        if current_pos_after_seek != script_offset:
            print(f"  FATAL ERROR: seek() FAILED! Tried to seek to {script_offset}, but ended up at {current_pos_after_seek}")
            # 可以在这里抛出异常或进入死循环来明确指示错误
            while True: pass

        line_content = self._script_file_handle.readline()
        
        print(f"  _get_line({line_num_1_based}): Read content: {repr(line_content)}")
        return line_content
    def update(self, confirm_pressed: bool, next_pressed: bool, menu_pressed: bool):
        if self._wait_mode == 'none':
            print(f"--- PC: {self._pc} ---")

        if not self._is_running: return
        
        if self._wait_mode == 'pending_load':
            self.load_state(from_title_menu=False) # 调用真正的读档逻辑
            return # 读档后立即返回，等待下一帧再开始执行脚本
        
        if menu_pressed:
            if self._wait_mode == 'menu':
                self._wait_mode = 'none'
                self._redraw_scene(); self._draw_sidebar()
            else:
                if self._auto_mode: self._auto_mode = False; self._draw_sidebar()
                self._wait_mode = 'menu'
                self.sidebar_selection = 0
                self._draw_sidebar()
            return

        if self._auto_mode and (confirm_pressed or next_pressed):
            self._auto_mode = False; self._draw_sidebar()
        
        if self._wait_mode == 'confirm':
            if confirm_pressed:
                self._pc += 1
                self._wait_mode = 'none'
            return
            
        elif self._wait_mode == 'choice':
            self._auto_mode = False
            if next_pressed:
                old_selection = self._selected_choice
                self._selected_choice = (self._selected_choice + 1) % len(self._choice_options)
                self._draw_single_choice(old_selection, is_selected=False)
                self._draw_single_choice(self._selected_choice, is_selected=True)
                self.display.show()
            elif confirm_pressed:
                target_line = self._choice_options[self._selected_choice][1]
                self._pc = target_line - 1
                self._wait_mode = 'none'
                self._redraw_scene()
            return
            
        elif self._wait_mode == 'auto':
            if time.ticks_diff(time.ticks_ms(), self._auto_wait_until_ms) > 0:
                self._pc += 1
                self._wait_mode = 'none'
            return

        elif self._wait_mode == 'menu':
            if next_pressed:
                self.sidebar_selection = (self.sidebar_selection + 1) % len(self.sidebar_options)
                self._draw_sidebar()
            elif confirm_pressed:
                self._execute_sidebar_action()
            return

        if self._pc < self._total_lines:
            line_content = self._get_line(self._pc + 1)
            line_stripped = line_content.rstrip('\r\n')

            print(f"  EXECUTING: {repr(line_stripped)}")
            
            if line_stripped:
                prev_wait_mode = self._wait_mode
                self._process_line(line_stripped)
                if self._wait_mode != prev_wait_mode:
                    print(f"    -> WAIT_MODE CHANGED TO: '{self._wait_mode}'")
            
            if self._wait_mode == 'none':
                self._pc += 1
        else:
            self.stop()

    def _execute_sidebar_action(self):
        action = self.sidebar_options[self.sidebar_selection]
        if "Q.Save" in action:
            self.save_state()
        elif "Auto" in action:
            self._auto_mode = not self._auto_mode
            print(f"自动模式: {'开启' if self._auto_mode else '关闭'}")
            self._wait_mode = 'none' # [FIX] 读档成功后退出菜单
            self._redraw_scene();
            self._draw_sidebar()
        elif "Q.Load" in action:
            if self.load_state(): # 读档成功
                self._wait_mode = 'none' # [FIX] 读档成功后退出菜单
                self._redraw_scene(); self._draw_sidebar() # [FIX] 刷新画面
                # 这里不需要手动设置 _is_running = True，因为 load_state 已经做了
            else:
                # 读档失败，可以给个提示或保持菜单
                pass # 保持菜单
        elif "HOME" in action:
            self.stop() # stop 会将 _is_running 设为 False，回到标题界面
        elif "返回" in action:
            self._wait_mode = 'none'
            self._redraw_scene(); self._draw_sidebar()

    def _draw_sidebar(self):
        self.display.fill_rect(0, 16, 32, 48, 0)
        if self._wait_mode == 'menu':
            y_coords = [16, 24, 32, 40, 48]
            for i, option in enumerate(self.sidebar_options):
                text_to_draw = "  AUTO  " if "Auto" in option and self._auto_mode else option
                is_selected = (i == self.sidebar_selection)
                self.font.text(self.display, text_to_draw, 0, y_coords[i], r=is_selected)
        else:
            month_str = self._month_map.get(self._game_date['month'], "???")
            self.font.text(self.display, month_str, 2, 28)
            day_str = f"{self._game_date['day']:02d}"
            self.font.text(self.display, day_str, 8, 36)
            dow_str = self._day_map.get(self._game_date['dow'], '???')
            self.font.text(self.display, dow_str, 12, 44)
            self.font.text(self.display, "Auto: ON" if self._auto_mode else "Auto:OFF", 0, 56)
        self.display.show()

    def _process_line(self, line):
        if not line.startswith('^'): self._handle_dialogue(line)
        else:
            parts = line.split()
            command = parts[0].upper()
            if command == '^BG': self._handle_bg(parts)
            elif command == '^CG': self._handle_cg(parts)
            elif command == '^BGM': self._handle_bgm(parts)
            elif command == '^BGMSTOP': self.music_player.stop(); self._screen_state['bgm_idx'] = 65535
            elif command == '^JUMP': self._pc = int(parts[1]) - 1
            elif command == '^CHOICE': self._handle_choice(line)
            elif command == '^END': self.stop()
            elif command == '^D':
                date_str = parts[1]
                self._game_date['month'] = int(date_str[0:2])
                self._game_date['day'] = int(date_str[2:4])
                self._game_date['dow'] = int(date_str[4])
                self._draw_sidebar()

    def _handle_dialogue(self, line: str):
        if ':' not in line:
            print(f"警告: 无效的对话行 (缺少冒号): '{line}'")
            return

        speaker, content_raw = line.split(':', 1)
        content_processed = content_raw.replace('\\n', '\n')
        self.display.fill_rect(0, 0, 128, 16, 0)
        self.font.text(self.display, speaker, 0, 16, r=1)
        self.font.text(self.display, content_processed, 0, 0)
        self.display.show()
        if self._auto_mode:
            char_count = len(content_processed.replace('\n', ''))
            delay_ms = 500 + 300 * char_count
            self._auto_wait_until_ms = time.ticks_ms() + delay_ms
            self._wait_mode = 'auto'
        else:
            self._wait_mode = 'confirm'

    def _redraw_scene(self):
        bg_index = self._screen_state['bg']
        if bg_index is not None:
            bg_data = self.bg_reader.read_chunk(bg_index)
            if bg_data: draw_image(self.display, bg_data, 32, 16, 96, 48)
        else: self.display.fill_rect(32, 16, 96, 48, 0)
        for pos_key, x_coord in [('cg_l', 33), ('cg_c', 68), ('cg_r', 105)]:
             cg_index = self._screen_state.get(pos_key)
             if cg_index is not None:
                 cg_data = self.cg_reader.read_chunk(cg_index)
                 if cg_data: draw_image(self.display, cg_data, x_coord, 16, 24, 48)

    def _handle_bg(self, parts: list):
        try:
            self._screen_state['bg'] = int(parts[1])
            self._screen_state['cg_l'] = self._screen_state['cg_c'] = self._screen_state['cg_r'] = None
            self._redraw_scene()
            self.display.show()
        except (IndexError, ValueError): pass

    def _handle_cg(self, parts: list):
        try:
            pos_char, cg_index = parts[1], int(parts[2])
            state_key = {'l': 'cg_l', 'c': 'cg_c', 'r': 'cg_r'}.get(pos_char)
            if state_key:
                self._screen_state[state_key] = cg_index
                self._redraw_scene()
                self.display.show()
        except (IndexError, ValueError): pass

    def _handle_bgm(self, parts: list):
        try:
            bgm_index_str = parts[1]
            # --- [关键修正] ---
            # 将字符串索引转换为整数后再存入状态
            self._screen_state['bgm_idx'] = int(bgm_index_str)
            if self.sound_enabled:
                self.music_player.play(bgm_index_str, loop=True)
        except (IndexError, ValueError):
            print(f"警告: 格式错误的 ^BGM 指令: {' '.join(parts)}")
            
    def _pad_and_center_text(self, text: str, max_full_width_chars: int) -> str:
        current_width = 0
        for char in text:
            current_width += 2 if ord(char) > 127 else 1
        
        max_width = max_full_width_chars * 2
        if current_width >= max_width: return text
            
        padding_needed = max_width - current_width
        left_padding = padding_needed // 2
        right_padding = padding_needed - left_padding
        return ' ' * left_padding + text + ' ' * right_padding

    def _handle_choice(self, line: str):
        self._choice_options = []
        try:
            _, payload = line.split(' ', 1) 
        except ValueError: return

        option_groups = payload.split(' ')
        for group in option_groups:
            group = group.strip()
            if not group: continue
            try:
                text, target_line_str = group.rsplit(',', 1)
                self._choice_options.append((text, int(target_line_str)))
            except (ValueError, IndexError): continue

        if self._choice_options:
            self._selected_choice = 0
            self._wait_mode = 'choice'
            self._draw_choices()

    def _draw_single_choice(self, index: int, is_selected: bool):
        text_x_start = _CHOICE_BOX_X + _CHOICE_TEXT_X_OFFSET
        
        num_options = len(self._choice_options)
        Y_POS_LAYOUTS = [(30,), (23, 37), (23, 37, 51)]
        y_positions = Y_POS_LAYOUTS[num_options - 1]
        
        y_pos = y_positions[index]
        y_text_start = y_pos + 2

        original_text = self._choice_options[index][0]
        padded_text = self._pad_and_center_text(original_text, 8)
        
        self.display.fill_rect(text_x_start, y_pos + 1, _CHOICE_BOX_W - 2, _CHOICE_BOX_H - 2, 0)
        self.font.text(self.display, padded_text, cx=text_x_start, cy=y_text_start, r=is_selected)

    def _draw_choices(self):
        self._redraw_scene()
        
        num_options = len(self._choice_options)
        Y_POS_LAYOUTS = [(30,), (23, 37), (23, 37, 51)]
        y_positions = Y_POS_LAYOUTS[num_options - 1]
        
        for i in range(num_options):
            self.display.rect(_CHOICE_BOX_X, y_positions[i], _CHOICE_BOX_W, _CHOICE_BOX_H, 1)
            self._draw_single_choice(i, i == self._selected_choice)
            
        self.display.show()

    def _play_feedback_sound(self):
        if self.sound_enabled:
            self.music_player.play_sfx([(262, 150), (330, 150), (392, 150)])

    def save_state(self):
        print("正在快速存档...")
        try:
            # --- [FIX] 确保所有待打包的值都是整数 ---
            
            pc = self._pc
            month, day, dow = self._game_date['month'], self._game_date['day'], self._game_date['dow']

            # 对于每个可能为 None 的状态值，进行检查和转换
            # 如果值是 None，就使用 65535 作为默认值，否则使用原值。
            bgm_idx = self._screen_state['bgm_idx'] if self._screen_state.get('bgm_idx') is not None else 65535
            bg_idx = self._screen_state['bg'] if self._screen_state.get('bg') is not None else 65535
            cgl_idx = self._screen_state['cg_l'] if self._screen_state.get('cg_l') is not None else 65535
            cgc_idx = self._screen_state['cg_c'] if self._screen_state.get('cg_c') is not None else 65535
            cgr_idx = self._screen_state['cg_r'] if self._screen_state.get('cg_r') is not None else 65535
            
            # 使用修正后的整数值进行打包
            int_payload = struct.pack(self._save_format_ints, pc, bgm_idx, month, day, dow, bg_idx, cgl_idx, cgc_idx, cgr_idx)
            crc = ucrc32.ucrc32(int_payload)
            data_to_write = int_payload + struct.pack('<I', crc)
            
            try:
                os.stat('save.dat'); os.rename('save.dat', 'save.bak')
            except OSError: pass
            
            with open('save.dat', 'wb') as f: f.write(data_to_write)
            
            print("存档成功！"); self._play_feedback_sound()
        except Exception as e:
            print(f"存档写入失败: {e}")

    def load_state(self, from_title_menu=False):
        if from_title_menu:
            # 从标题菜单调用时，只设置一个等待模式
            # 并确保引擎处于“运行”状态，以便 update 函数能被执行
            print("读档请求已接收，将在下一帧执行。")
            self._is_running = True
            self._wait_mode = 'pending_load' # 新的等待模式
            return True
        print("正在快速读档...")
        try:
            SAVE_FORMAT_INTS = '<IHBBBHHHH'
            CRC_FORMAT = '<I'
            SAVE_SIZE = struct.calcsize(SAVE_FORMAT_INTS) + struct.calcsize(CRC_FORMAT)

            with open('save.dat', 'rb') as f: data = f.read()
            if len(data) != SAVE_SIZE: raise ValueError("存档文件大小错误")
            
            int_payload = data[:struct.calcsize(SAVE_FORMAT_INTS)]
            saved_crc_bytes = data[struct.calcsize(SAVE_FORMAT_INTS):]
            saved_crc = struct.unpack('<I', saved_crc_bytes)[0]
            if saved_crc != ucrc32.ucrc32(int_payload): raise ValueError("存档校验和错误")
            
            pc, bgm_idx, m, d, dow, bg_idx, cgl_idx, cgc_idx, cgr_idx = struct.unpack(SAVE_FORMAT_INTS, int_payload)
            if not all(idx == 65535 or (reader and idx < len(reader)) for idx, reader in 
                       [(bg_idx, self.bg_reader), (cgl_idx, self.cg_reader), 
                        (cgc_idx, self.cg_reader), (cgr_idx, self.cg_reader)]):
                 raise ValueError("存档资源索引越界")

            self._pc = pc
            self._game_date = {'month': m, 'day': d, 'dow': dow}
            current_bgm_idx = bgm_idx if bgm_idx != 65535 else None
            self._screen_state['bgm_idx'] = current_bgm_idx
            self._screen_state['bg'] = bg_idx if bg_idx != 65535 else None
            self._screen_state['cg_l'] = cgl_idx if cgl_idx != 65535 else None
            self._screen_state['cg_c'] = cgc_idx if cgc_idx != 65535 else None
            self._screen_state['cg_r'] = cgr_idx if cgr_idx != 65535 else None
            
            if current_bgm_idx is not None and self.sound_enabled:
                music_name = f"{current_bgm_idx:02d}"
                self.music_player.play(music_name, loop=True)
            else:
                self.music_player.stop()

            self._is_running = True    # 1. 标记引擎为运行状态
            self._wait_mode = 'none'   # 2. 确保游戏可以立即开始执行
            
            self._redraw_scene()       # 3. 刷新画面
            self._draw_sidebar()
            print("读档成功！")
            self._play_feedback_sound()
            
            # --- [FIX] 读档成功后，进入等待确认模式 ---
            # 这会阻止 update() 在同一帧内立即执行下一行脚本
            self._wait_mode = 'confirm' 
            
            return True
        except Exception as e:
            print(f"读档失败: {e}")
            return False