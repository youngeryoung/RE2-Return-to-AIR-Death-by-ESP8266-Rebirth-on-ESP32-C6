# converter.py (V1.4 - Added Robust Data Validation)
import os
import struct
import glob
import shutil
import sys # 引入 sys 模块用于退出

# --- 配置 ---
SOURCE_DIR = 'bgm'    # [修改] 源文件夹现在是 midi转txt.py 的输出
DEST_DIR = 'bgm_c'
NOTE_FORMAT = "<HHBB"
# SOURCE_LOUDNESS_MAX 现在不再需要，因为我们直接用 pitch
# SOURCE_LOUDNESS_MAX = 511.0 # 移除

def convert_song_files(source_song_dir, dest_song_dir):
    """转换单个歌曲目录中的 .txt 文件，并进行严格的数据校验。"""
    print(f"  转换: {os.path.basename(source_song_dir)}")
    for i in range(2):
        txt_path = os.path.join(source_song_dir, f"{i}.txt")
        msc_path = os.path.join(dest_song_dir, f"{i}.msc")
        
        if not os.path.exists(txt_path):
            continue

        note_count = 0
        with open(txt_path, 'r') as f_in, open(msc_path, 'wb') as f_out:
            # --- 核心修正：添加数据校验 ---
            for line_num, line in enumerate(f_in, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    parts = list(map(int, line.split()))
                    
                    # 1. 结构校验
                    if len(parts) != 4:
                        print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 格式错误，应为4个整数。")
                        print(f"  > 问题行: '{line}'")
                        sys.exit(1)

                    start_tick, end_tick, pitch, velocity = parts

                    # 2. 时序校验
                    if start_tick < 0 or end_tick < 0:
                        print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 时间戳不能为负。")
                        print(f"  > 问题行: '{line}'")
                        sys.exit(1)
                    if start_tick >= end_tick:
                        print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: start_tick ({start_tick}) 必须小于 end_tick ({end_tick})。")
                        print(f"  > 问题行: '{line}'")
                        print(f"  > 这通常由源MIDI文件中的重叠音符或过短音符引起。请检查源MIDI。")
                        sys.exit(1)
                    if start_tick > 65535 or end_tick > 65535:
                         print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 时间戳超出范围 (最大 65535)。")
                         print(f"  > 问题行: '{line}'")
                         sys.exit(1)

                    # 3. 音高和力度校验
                    if not (0 <= pitch <= 127):
                        print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 音高 (pitch) 超出MIDI范围 (0-127)。")
                        print(f"  > 问题行: '{line}'")
                        sys.exit(1)
                    if not (0 <= velocity <= 511): # 此处 velocity 实际是 [0-511] 的 duty_cycle，我们将其映射
                        print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 力度/音量值超出范围 (0-255)。")
                        print(f"  > 问题行: '{line}'")
                        sys.exit(1)
                    
                    # [简化] 直接使用 midi转txt.py 生成的 duty_cycle，并确保它在范围内
                    # 然后将其缩放到 0-255 范围内
                    loudness_byte = int((min(velocity, 511) / 511.0) * 255)

                    packed_data = struct.pack(NOTE_FORMAT, start_tick, end_tick, pitch, loudness_byte)
                    f_out.write(packed_data)
                    note_count += 1
                except ValueError:
                    print(f"\n[致命错误] 在文件 '{txt_path}' 第 {line_num} 行: 包含非整数值。")
                    print(f"  > 问题行: '{line}'")
                    sys.exit(1)
        print(f"    - {i}.txt -> {i}.msc ({note_count} 个有效音符)")

# copy_metadata 和 main 函数保持不变，但请确认 SOURCE_DIR
def copy_metadata(source_song_dir, dest_song_dir):
    source_meta_path = os.path.join(source_song_dir, 'metadata.txt')
    dest_meta_path = os.path.join(dest_song_dir, 'metadata.txt')
    if os.path.exists(source_meta_path):
        shutil.copy2(source_meta_path, dest_meta_path)
        print(f"    - 已复制 metadata.txt")
    else:
        print(f"    - 警告: 未找到 metadata.txt！")

if __name__ == "__main__":
    if not os.path.isdir(SOURCE_DIR):
        print(f"错误: 未找到源文件夹 '{SOURCE_DIR}'。请先运行 midi转txt.py。")
    else:
        print(f"--- 准备输出文件夹: '{DEST_DIR}' ---")
        if os.path.exists(DEST_DIR):
            shutil.rmtree(DEST_DIR)
        os.makedirs(DEST_DIR)
        
        song_directories = [d for d in glob.glob(os.path.join(SOURCE_DIR, '*')) if os.path.isdir(d)]

        if not song_directories:
             print("未在 '{SOURCE_DIR}' 中找到任何歌曲文件夹。")
        else:
            print(f"--- 开始转换 {len(song_directories)} 首歌曲 ---")
            for source_dir in song_directories:
                song_name = os.path.basename(source_dir)
                dest_song_dir = os.path.join(DEST_DIR, song_name)
                os.makedirs(dest_song_dir)
                
                convert_song_files(source_dir, dest_song_dir)
                copy_metadata(source_dir, dest_song_dir)

            print("\n--- 转换完成！---")