# buzzer_player.py (V8.1 - Fixed Initialization Deadlock)
import machine
import time
import gc
import struct
from micropython import const

# --- 配置 和 Buzzer 类 (与 V8.0 相同，保持不变) ---
_BUFFER_SIZE = const(64) 
_NOTE_BYTE_SIZE = const(6)
FREQ_LUT = (33,35,37,39,41,44,46,49,52,55,58,62,65,69,73,78,82,87,92,98,104,110,117,123,131,139,147,156,165,175,185,196,208,220,233,247,262,277,294,311,330,349,370,392,415,440,466,494,523,554,587,622,659,698,740,784,831,880,932,988,1047,1109,1175,1245,1319,1397,1480,1568,1661,1760,1865,1976,2093,2217,2349,2489,2637,2794,2960,3136,3322,3520,3729,3951,4186)
MIDI_LUT_OFFSET = const(24)
_MODE_BGM = const(0)
_MODE_SFX = const(1)

def _calculate_duty_viper(duration_us: int, us_since_start: int, loudness: int) -> int:
    if us_since_start >= duration_us: return -1
    remaining_us = duration_us - us_since_start
    return (loudness * remaining_us) // duration_us

class Buzzer:
    __slots__ = ('pwm', '_note_loudness', '_note_start_us', '_note_duration_us', '_current_freq')
    def __init__(self, pin_id: int):
        self.pwm = machine.PWM(machine.Pin(pin_id), freq=440, duty=0)
        self._current_freq = 0
        self._note_loudness = 0
        self._note_start_us = 0
        self._note_duration_us = 0
    def start_note(self, freq: int, loudness: int, duration_us: int):
        self._note_start_us = time.ticks_us()
        self._note_duration_us = duration_us
        self._note_loudness = loudness
        #print(freq,loudness,duration_us)
        if freq > 0:
            if freq != self._current_freq:
                self.pwm.freq(freq)
                self._current_freq = freq
        else: self.pwm.duty(0)
    def stop(self):
        self._note_duration_us = 0; self.pwm.duty(0)
    def update_pwm(self):
        if self._note_duration_us == 0: return
        us_since_start = time.ticks_diff(time.ticks_us(), self._note_start_us)
        duty = _calculate_duty_viper(self._note_duration_us, us_since_start, self._note_loudness)
        if duty == -1: self.stop()
        else: self.pwm.duty(duty)

class SongPlayer:
    def __init__(self, pin0: int, pin1: int):
        self._players = [Buzzer(pin0), Buzzer(pin1)]
        self._timer = machine.Timer(0)
        self._is_playing_flag = False
        buffer_byte_size = _BUFFER_SIZE * _NOTE_BYTE_SIZE
        self._buffers = ((bytearray(buffer_byte_size), bytearray(buffer_byte_size)), (bytearray(buffer_byte_size), bytearray(buffer_byte_size)))
        self._file_handles = [None, None]
        self._active_buf_idx = [0, 0]
        self._note_idx = [0, 0]
        self._buffer_is_full = [[False, False], [False, False]]
        self._file_fully_read = [False, False]
        self._64th_note_duration_us = 0
        self._loop = False
        self.last_song_info = None
        self._channel_mode = [_MODE_BGM, _MODE_BGM]
        self._sfx_queue = [None, None]

    # _timer_callback, _process_sfx, _process_bgm 保持不变
    def _timer_callback(self, timer_instance):
        if not self._is_playing_flag: return
        self._players[0].update_pwm(); self._players[1].update_pwm()
        current_bgm_us = time.ticks_diff(time.ticks_us(), self._start_time_us)
        for track_id in range(2):
            if self._channel_mode[track_id] == _MODE_SFX: self._process_sfx(track_id)
            else: self._process_bgm(track_id, current_bgm_us)
        if self._file_fully_read[0] and self._file_fully_read[1]:
            is_track0_finished = not self._buffer_is_full[0][self._active_buf_idx[0]]
            is_track1_finished = not self._buffer_is_full[1][self._active_buf_idx[1]]
            if is_track0_finished and is_track1_finished:
                if self._loop: self._reset_and_play(self.last_song_info)
                else: self.stop()

    def _process_sfx(self, track_id):
        sfx_task = self._sfx_queue[track_id]
        if not sfx_task: return
        notes_list, current_note_idx, start_time_ms = sfx_task
        elapsed_ms = time.ticks_diff(time.ticks_ms(), start_time_ms)
        total_sfx_duration = sum(note[1] for note in notes_list)
        if elapsed_ms >= total_sfx_duration:
            self._sfx_queue[track_id] = None; self._channel_mode[track_id] = _MODE_BGM; return
        time_cursor, note_to_play_idx = 0, -1
        for i in range(len(notes_list)):
            if elapsed_ms >= time_cursor: note_to_play_idx = i
            time_cursor += notes_list[i][1]
        if note_to_play_idx != -1 and note_to_play_idx > sfx_task[1]:
            sfx_task[1] = note_to_play_idx
            freq, duration_ms = notes_list[note_to_play_idx]
            self._players[track_id].start_note(freq, 200, duration_ms * 1000)

    def _process_bgm(self, track_id, current_bgm_us):
        active_buf_index = self._active_buf_idx[track_id]
        if not self._buffer_is_full[track_id][active_buf_index]: return
        current_read_buf = self._buffers[track_id][active_buf_index]
        note_offset = self._note_idx[track_id] * _NOTE_BYTE_SIZE
        try:
            start_ts_64th, end_ts_64th, pitch, loudness = struct.unpack_from("<HHBB", current_read_buf, note_offset)
        except IndexError: return
        if start_ts_64th == 0 and end_ts_64th == 0:
            self._buffer_is_full[track_id][active_buf_index] = False; return
        start_us = start_ts_64th * self._64th_note_duration_us
        if current_bgm_us >= start_us:
            duration_us = (end_ts_64th - start_ts_64th) * self._64th_note_duration_us
            freq = 0
            if pitch >= MIDI_LUT_OFFSET:
                lut_index = pitch - MIDI_LUT_OFFSET
                if lut_index < len(FREQ_LUT): freq = FREQ_LUT[lut_index]
            #print(track_id)
            self._players[track_id].start_note(freq, loudness, duration_us)
            self._note_idx[track_id] += 1
            if self._note_idx[track_id] == _BUFFER_SIZE:
                self._buffer_is_full[track_id][active_buf_index] = False
                self._active_buf_idx[track_id] = 1 - active_buf_index
                self._note_idx[track_id] = 0

    # --- 核心修正：修改 _fill_buffer 和 _reset_and_play ---
    
    def _fill_buffer(self, track_id: int, buffer_to_fill_idx: int):
        """
        [修改] 填充指定的缓冲区 (0 or 1)。
        """
        if self._file_fully_read[track_id] or self._buffer_is_full[track_id][buffer_to_fill_idx]:
            return # 如果文件已读完，或此缓冲区已是满的，则不操作

        buf = self._buffers[track_id][buffer_to_fill_idx]
        bytes_read = self._file_handles[track_id].readinto(buf)
        #print('polling')
        if bytes_read > 0:
            self._buffer_is_full[track_id][buffer_to_fill_idx] = True

        if bytes_read < len(buf):
            self._file_fully_read[track_id] = True
            mv = memoryview(buf)
            for i in range(bytes_read, len(buf)): mv[i] = 0

    def _reset_and_play(self, song_info):
        
        self.stop(); time.sleep_ms(20); gc.collect()
        
        self._active_buf_idx, self._note_idx = [0, 0], [0, 0]
        self._file_fully_read = [False, False]
        self._buffer_is_full = [[False, False], [False, False]]
        self._channel_mode = [_MODE_BGM, _MODE_BGM]
        
        self.last_song_info = song_info
        music_name, self._loop, precision = song_info
        song_dir = f"/bgm/{music_name}"
        
        try:
            with open(f"{song_dir}/metadata.txt", "r") as f: bpm = float(f.readline().split(':')[1].strip())
            self._64th_note_duration_us = int(60.0 * 1000000 / bpm / 16.0)
            self._file_handles[0] = open(f"{song_dir}/0.msc", "rb")
            self._file_handles[1] = open(f"{song_dir}/1.msc", "rb")
        except (OSError, ValueError) as e:
            print(f"错误: 无法加载 '{music_name}': {e}"); return
            
        #print(f"音频管理器: 加载 '{music_name}'...")
        # --- 核心修正：初始化时，填满两个缓冲区 (0 和 1) ---
        for track_id in range(2):
            self._fill_buffer(track_id, 0) # 填充 0 号缓冲区
            self._fill_buffer(track_id, 1) # 填充 1 号缓冲区
        
        self._start_time_us = time.ticks_us()
        self._is_playing_flag = True
        
        freq_hz = max(20, min(500, int(bpm / 60.0 * 16 * precision)))
        #print(f"BPM: {bpm}, 定时器频率: {freq_hz} Hz")
        self._timer.init(freq=freq_hz, mode=machine.Timer.PERIODIC, callback=self._timer_callback)

    def play(self, music_name: str, loop: bool = False, precision: int = 4):
        self._reset_and_play((music_name, loop, precision))
        
    def poll(self):
        if not self._is_playing_flag: return
        
        # --- 核心修正：poll() 的任务是填充非活动缓冲区 ---
        for track_id in range(2):
            inactive_buf_idx = 1 - self._active_buf_idx[track_id]
            self._fill_buffer(track_id, inactive_buf_idx)

    # stop() 和 is_playing() 保持不变
    def stop(self):
        if not self._is_playing_flag: return
        self._is_playing_flag = False; self._timer.deinit()
        self._players[0].stop(); self._players[1].stop()
        for i, f in enumerate(self._file_handles):
            if f: f.close(); self._file_handles[i] = None
        self._sfx_queue = [None, None]; self._channel_mode = [_MODE_BGM, _MODE_BGM]
        #print("音频管理器: 已停止。")
    def play_sfx(self, notes_list: list, channel: int = 0):
        if not (0 <= channel < 2) or self._sfx_queue[channel] is not None:
            return

        # 如果定时器完全没有初始化过，就用默认频率启动它
        # .deinit() 之后，timer 表现为 None-like
        # 我们用 try-except 来安全地检查定时器状态
        try:
            self._timer.freq() 
        except: # 如果定时器未激活 (e.g., after deinit)
            self._timer.init(freq=100, mode=machine.Timer.PERIODIC, callback=self._timer_callback)
        
        # 只要定时器在跑，我们就可以调度SFX
        #print(f"音频管理器: 在通道 {channel} 上调度音效。")
        self._sfx_queue[channel] = [notes_list, -1, time.ticks_ms()]
        self._channel_mode[channel] = _MODE_SFX
        self._players[channel].stop() # 为SFX让路
    def is_playing(self) -> bool:
        return self._is_playing_flag