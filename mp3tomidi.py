# ==============================================================================
# 1. 导入所需库
# ==============================================================================
import os
import glob
import torch
from piano_transcription_inference import PianoTranscription, sample_rate, load_audio

# ==============================================================================
# 2. 全局配置区 (CONFIG)
# ==============================================================================
CONFIG = {
    "INPUT_AUDIO_DIR": "bgm",
    "OUTPUT_MIDI_DIR": "output_midi",
    "ACCEPTED_AUDIO_FORMATS": ("*.wav", "*.mp3"),
}

# ==============================================================================
# 3. 核心功能函数
# ==============================================================================

def transcribe_audio_to_midi(audio_path: str, output_midi_path: str):
    """
    使用 Bytedance 的高性能模型将单个音频文件转录为MIDI。
    """
    # 如果目标MIDI文件已存在，可以选择跳过以节省时间
    if os.path.exists(output_midi_path):
        print(f"MIDI文件已存在，跳过转录: {os.path.basename(output_midi_path)}")
        return

    try:
        # --- 1. 选择设备 (GPU 或 CPU) ---
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"使用设备: {device}")

        # --- 2. 加载音频文件 ---
        print(f"正在加载音频: {os.path.basename(audio_path)}")
        audio, _ = load_audio(audio_path, sr=sample_rate, mono=True)

        # --- 3. 初始化并运行转录模型 ---
        # 模型会自动下载并缓存，仅在第一次运行时需要时间
        transcriptor = PianoTranscription(device=device)
        
        print("开始转录 (这可能需要一些时间)...")
        # 直接调用 transcribe 函数，它会处理一切并将结果存入文件
        transcribed_dict = transcriptor.transcribe(audio, output_midi_path)
        
        print(f"转录成功 -> {os.path.basename(output_midi_path)}")

    except Exception as e:
        print(f"在转录文件 {os.path.basename(audio_path)} 时发生严重错误: {e}")
        # 如果希望在出错时停止整个程序，可以取消下面这行的注释
        # raise e

# ==============================================================================
# 4. 主执行流程
# ==============================================================================

def main():
    """
    主函数，负责批量处理文件夹中的所有音频文件。
    """
    # --- 1. 动态路径设置 ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(script_dir, CONFIG["INPUT_AUDIO_DIR"])
    output_dir = os.path.join(script_dir, CONFIG["OUTPUT_MIDI_DIR"])

    print("--- 音频到MIDI转换器 ---")
    print(f"输入文件夹: {input_dir}")
    print(f"输出文件夹: {output_dir}")
    print("-------------------------")

    # --- 2. 文件夹检查与创建 ---
    if not os.path.isdir(input_dir):
        print(f"错误: 输入文件夹 '{input_dir}' 不存在。")
        print("请在脚本所在目录下创建一个名为 'input_audio' 的文件夹，并放入音频文件。")
        return

    os.makedirs(output_dir, exist_ok=True)

    # --- 3. 查找待处理的音频文件 ---
    audio_files = []
    for fmt in CONFIG["ACCEPTED_AUDIO_FORMATS"]:
        search_path = os.path.join(input_dir, fmt)
        audio_files.extend(glob.glob(search_path))

    if not audio_files:
        print(f"在目录 {input_dir} 中未找到任何支持的音频文件 {CONFIG['ACCEPTED_AUDIO_FORMATS']}。")
        return

    # --- 4. 批量处理 ---
    print(f"\n发现 {len(audio_files)} 个音频文件，开始批量转换...")
    for audio_path in audio_files:
        filename_no_ext = os.path.splitext(os.path.basename(audio_path))[0]
        output_midi_path = os.path.join(output_dir, f"{filename_no_ext}.mid")
        
        print(f"\n----- 正在处理: {filename_no_ext} -----")
        transcribe_audio_to_midi(audio_path, output_midi_path)
    
    print("\n==========================")
    print("===== 所有转换完成 =====")
    print(f"请在 '{output_dir}' 文件夹中查找生成的MIDI文件。")
    print("==========================")

# ==============================================================================
# 5. 脚本执行入口
# ==============================================================================
if __name__ == '__main__':
    main()