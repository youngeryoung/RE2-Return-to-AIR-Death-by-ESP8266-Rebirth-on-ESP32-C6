# cg_player.py
# 版本: V4.0 - 独立、健壮的OP播放器
import time
import gc
from data_reader import DataReader
from buzzer_player import SongPlayer
from ufont import BMFont
from utils import draw_image, draw_rect

class CGPlayer:
    # --- 内部常量,定义了动画的时间线和图像序列 ---
    _DATA_FILE = '/op.dat'
    _CHUNK_SIZE = 576
    _MUSIC_NAME = 'air+'
    _MUSIC_PRECISION = 2
    
    # 时间戳 (毫秒)
    _OP_TIMESTAMPS = [5000, 18500, 21500, 32000, 35000, 43000, 43266, 43532, 43798, 44064, 44330, 44596, 44862, 45128, 45394, 45660, 45926, 46192, 46458, 46724, 46990, 52000, 55000, 57000, 59000, 61000, 68000, 70000, 72000, 74000, 76000, 84000, 84428, 84856, 85284, 85712, 86140, 86568, 86996, 87424, 87852, 88280, 88708, 89136, 89564, 89992, 90420, 90848, 91276, 91704, 92132, 92560, 92988, 93416, 93844, 94272, 94700, 95128, 95556, 95984, 96412, 96840, 97268, 97696, 98124, 98552, 98980, 99500, 102000, 105000, 107000, 112000, 114000, 115000, 115571, 116142, 116713, 117284, 117855, 118426, 118997, 119568, 120139, 120710, 121281, 121852, 122423, 122994, 123000, 125000, 127000, 129000, 131000, 131380, 131760, 132140, 132520, 132900, 133280, 133660, 134040, 134420, 134800, 135180, 135560, 135940, 136320, 136700, 137080, 137460, 137840, 138220, 138600, 138980, 139360, 139740, 140120, 140500, 140880, 141260, 141640, 142020, 142400, 142780, 143160, 143540, 143920, 144300, 144680, 145060, 145440, 145820, 146200, 146580, 146960, 147200, 152000, 166000, 176000, 186000]
    # 图像索引
    _OP_INDICES = [0, 1, 0, 2, 0, 11, 12, 13, 14, 15, 16, 17, 18, 4, 5, 6, 7, 8, 9, 10, 3, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 3, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 3, 13, 81, 82, 83, 84]

    def __init__(self, display, font: BMFont, music_player: SongPlayer, image_reader: DataReader):
        self._display = display
        self._font = font
        self._image_reader = image_reader # 使用传入的 reader 实例
        self._music_player = music_player
        
        self._is_playing = False
        self._start_time_ms = 0
        self._current_frame_index = 0
        self._last_drawn_frame = -1

    def play(self):
        f = self._font
        d = self._display
        d.fill(0)
        f.text(d, "----------Bird's  Poem----------", cx=0, cy=0,r=1)
        f.text(d, "           Is playing           ", cx=0, cy=8)
        f.text(d, "---OP---", cx=0, cy=16,r = 1)
        f.text(d, "按下按键", cx=0, cy=48)
        f.text(d, " 跳过OP ", cx=0, cy=56,sh=1)
        if self._is_playing: return
        print("开始播放 OP 动画...")
        
        self._music_player.play(music_name=self._MUSIC_NAME, loop=False, precision=self._MUSIC_PRECISION)

        self._start_time_ms = time.ticks_ms()
        self._current_frame_index = 0
        self._last_drawn_frame = -1
        self._is_playing = True
        gc.collect()

    def stop(self):
        if not self._is_playing and not self._music_player: return
        print("正在停止 OP 播放并清理资源...")
        self._is_playing = False
        
        if self._music_player:
            self._music_player.stop()
        
        gc.collect()
        print("OP 资源已清理。")

    def skip(self):
        """跳过动画。"""
        print("动画被用户跳过。")
        self.stop()

    def is_playing(self) -> bool:
        return self._is_playing

    def update(self):
        if not self._is_playing: return

        # 以音乐播放器的状态作为动画结束的最终判断依据
        if self._music_player and not self._music_player.is_playing():
            self.stop()
            return

        elapsed_ms = time.ticks_diff(time.ticks_ms(), self._start_time_ms)
        
        # 推进帧索引以匹配当前时间
        target_frame = 0
        while (target_frame < len(self._OP_TIMESTAMPS) and 
               elapsed_ms >= self._OP_TIMESTAMPS[target_frame]):
            target_frame += 1
        self._current_frame_index = target_frame
        
        # 仅在需要绘制新一帧时才执行绘图操作
        if self._current_frame_index != self._last_drawn_frame:
            self._draw_frame()
            self._last_drawn_frame = self._current_frame_index

    def _draw_frame(self):
        # 如果帧索引为0或超出图像索引范围,则不绘制
        if self._current_frame_index == 0 or self._current_frame_index > len(self._OP_INDICES):
            return
            
        i = self._current_frame_index
        image_idx = self._OP_INDICES[i - 1]
        image_data = self._image_reader.read_chunk(image_idx)
        
        f = self._font
        d = self._display
        
        # 先绘制图像,再叠加文本
        if image_data:
            # 精确按照我们设计的布局绘制在蓝色图形区
            draw_image(d, image_data, 32, 16, 96, 48)
        
        # 硬编码的文本叠加层
        if i == 21: f.text(d, "the 1000th Summer——", cx=39, cy=36)
        elif i == 23: f.text(d, "「无法飞翔的翅膀,", cx=35, cy=32); f.text(d, "还存在任何的意义吗」", cx=32, cy=40)
        elif i == 26: f.text(d, "远野 美凪", cx=35, cy=36)
        elif i == 28: f.text(d, "「你有没有想过,", cx=57, cy=32); f.text(d, "要是能用魔法就好了」", cx=50, cy=40)
        elif i == 31: f.text(d, "雾岛 佳乃", cx=72, cy=36)
        elif 35 <= i <= 42: f.text(d, "青年是位旅人.", cx=56, cy=56)
        elif 43 <= i <= 50: f.text(d, "他有两个旅伴.", cx=56, cy=56)
        elif 51 <= i <= 58: f.text(d, "一个是无需触碰", cx=51, cy=48); f.text(d, "就能独立行走的陈旧人偶.", cx=35, cy=56)
        elif 59 <= i <= 66: f.text(d, "另一个,则是有\"力量\"之人", cx=33, cy=48); f.text(d, "的古老约定.", cx=58, cy=56)
        elif i == 70: f.text(d, "「只是…在那里,", cx=33, cy=28); f.text(d, "好像存在着另外一个自己。", cx=33, cy=36); f.text(d, "我总有这样的感觉」", cx=39, cy=44)
        elif i == 73: f.text(d, "神尾 观铃", cx=35, cy=36)
        elif 115 <= i <= 137: f.text(d, "请一定…", cx=35, cy=24); f.text(d, "为她留下幸福的回忆.", cx=33, cy=32)
        elif i == 138: f.text(d, "夏日仿佛无止境的延续着", cx=35, cy=32); f.text(d, "在蔚蓝广阔的天空之下", cx=39, cy=40); f.text(d, "在她所等待的那片大气之下", cx=35, cy=48)
        
        d.show()
        gc.collect()