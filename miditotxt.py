# ==============================================================================
# 1. 导入所需库
# ==============================================================================
import os
import glob
import pretty_midi
import numpy as np
from collections import defaultdict

# ==============================================================================
# 2. 全局配置区 (CONFIG)
# ==============================================================================
CONFIG = {
    "INPUT_MIDI_DIR": "midi",
    "OUTPUT_DIR": "output_final",
    "TICKS_PER_BEAT": 16,
}

# ==============================================================================
# 3. 辅助函数
# ==============================================================================

def velocity_to_duty_cycle(velocity: int) -> int:
    """将MIDI力度（0-127）非线性映射到蜂鸣器占空比（0-511）。"""
    EXPONENTIAL_FACTOR = 2.8
    if velocity == 0: return 0
    if 1 <= velocity <= 16: return 1
    in_min, in_max = 17, 127
    out_min, out_max = 1, 511
    normalized_velocity = (velocity - in_min) / (in_max - in_min)
    curved_value = normalized_velocity ** EXPONENTIAL_FACTOR
    final_duty_cycle = out_min + curved_value * (out_max - in_min)
    return round(final_duty_cycle)

# ==============================================================================
# 4. 核心处理函数
# ==============================================================================

def process_corrected_midi_v2(midi_path: str):
    """
    将手动修正后的MIDI文件转换为最终的三文件格式。
    (V2版本: 使用轨道保持算法，不再区分旋律/伴奏)
    """
    filename_no_ext = os.path.splitext(os.path.basename(midi_path))[0]
    print(f"\n===== [START] 开始处理文件: {filename_no_ext} =====")

    try:
        # --- 1. 准备路径和加载MIDI ---
        song_output_dir = os.path.join(CONFIG["OUTPUT_DIR"], filename_no_ext)
        os.makedirs(song_output_dir, exist_ok=True)
        track0_txt_path = os.path.join(song_output_dir, "0.txt")
        track1_txt_path = os.path.join(song_output_dir, "1.txt")
        metadata_txt_path = os.path.join(song_output_dir, "metadata.txt")

        midi_data = pretty_midi.PrettyMIDI(midi_path)
        all_notes = sorted([note for inst in midi_data.instruments for note in inst.notes], key=lambda n: n.start)

        if not all_notes:
            print("警告: MIDI文件中无音符。")
            return

        bpm = midi_data.estimate_tempo()
        if bpm is None or bpm <= 0: bpm = 120.0
            
        with open(metadata_txt_path, 'w', encoding='utf-8') as f:
            f.write(f"BPM: {bpm}")

        # --- 2. 核心逻辑: 轨道保持分配 ---
        track0_notes = []
        track1_notes = []
        
        # 跟踪每个轨道上最后一个音符的结束时间
        track0_end_time = -1.0
        track1_end_time = -1.0

        for note in all_notes:
            # 检查哪个轨道先空闲出来
            is_track0_free = note.start >= track0_end_time
            is_track1_free = note.start >= track1_end_time

            if is_track0_free and is_track1_free:
                # 如果两个轨道都空闲，优先分配给结束得更早的那个轨道，以保持连续性
                if track0_end_time <= track1_end_time:
                    track0_notes.append(note)
                    track0_end_time = note.end
                else:
                    track1_notes.append(note)
                    track1_end_time = note.end
            elif is_track0_free:
                # 只有轨道0空闲
                track0_notes.append(note)
                track0_end_time = note.end
            elif is_track1_free:
                # 只有轨道1空闲
                track1_notes.append(note)
                track1_end_time = note.end
            else:
                # 这是一个错误情况（同一时间超过2个音符），但在手动修正后应该不会发生。
                # 作为保险，我们强制分配给即将结束的轨道。
                print(f"分配冲突警告: 在 {note.start:.2f}s, 两个轨道都繁忙。")
                if track0_end_time <= track1_end_time:
                    track0_notes.append(note)
                    track0_end_time = note.end
                else:
                    track1_notes.append(note)
                    track1_end_time = note.end

        # --- 3. 格式化输出 ---
        track0_txt_content = format_notes_to_txt_v2(track0_notes, "Track 0", bpm)
        track1_txt_content = format_notes_to_txt_v2(track1_notes, "Track 1", bpm)

        with open(track0_txt_path, 'w', encoding='utf-8') as f: f.write(track0_txt_content)
        with open(track1_txt_path, 'w', encoding='utf-8') as f: f.write(track1_txt_content)

        print(f"===== [SUCCESS] 文件处理成功: {filename_no_ext} =====")

    except Exception as e:
        import traceback
        print(f"处理文件 {midi_path} 时发生错误: {e}")
        traceback.print_exc()

def format_notes_to_txt_v2(notes: list, track_name: str, bpm: float) -> str:
    """将音符列表格式化为TXT。"""
    if not notes: return ""
    seconds_per_tick = (60.0 / bpm) / CONFIG["TICKS_PER_BEAT"]
    if seconds_per_tick <= 0: return ""

    output_lines = []
    # 此时音符已经是分配好的，直接按时间排序即可
    for note in sorted(notes, key=lambda n: n.start):
        start_tick = round(note.start / seconds_per_tick)
        end_tick = round(note.end / seconds_per_tick)
        if end_tick <= start_tick: end_tick = start_tick + 1
        mapped_velocity = velocity_to_duty_cycle(note.velocity)
        line = f"{start_tick} {end_tick} {note.pitch} {mapped_velocity}"
        output_lines.append(line)
        
    print(f"格式化输出完成 ({track_name})。BPM: {bpm:.2f}, 最终音符数: {len(output_lines)}")
    return "\n".join(output_lines)

def main():
    """主函数，批量处理修正后的MIDI文件。"""
    input_dir = CONFIG["INPUT_MIDI_DIR"]
    output_dir = CONFIG["OUTPUT_DIR"]
    
    print(f"--- MIDI到TXT转换器 V2 (轨道保持) ---")
    print(f"输入文件夹: {input_dir}")
    print(f"输出文件夹: {output_dir}")
    print("---------------------------------------")

    if not os.path.isdir(input_dir):
        print(f"错误: 输入文件夹 '{input_dir}' 不存在。请创建它并放入MIDI文件。")
        return
    os.makedirs(output_dir, exist_ok=True)

    midi_files = glob.glob(os.path.join(input_dir, "*.mid"))
    if not midi_files:
        print(f"在目录 {input_dir} 中未找到任何 .mid 文件。")
        return

    print(f"\n发现 {len(midi_files)} 个MIDI文件，开始处理...")
    for midi_path in midi_files:
        process_corrected_midi_v2(midi_path)
    
    print("\n===== 所有文件处理完毕 =====")

if __name__ == '__main__':
    main()