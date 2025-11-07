# preprocess.py
import sys
import re
import argparse
import json
import struct
from typing import List, Dict, Set

# --- 全局常量 ---
LABEL_PREFIX = "^LABEL"; JUMP_PREFIX = "^JUMP"; CHOICE_PREFIX = "^CHOICE"; END_PREFIX = "^END"
BG_PREFIX = "^BG"; CG_PREFIX = "^CG"; BGM_PREFIX = "^BGM"; DATE_PREFIX = "^DATE"
TITLE_BG_NAME = "air" # 约定好的封面资源名

# 屏幕与字体尺寸常量 (单位: 半角字符宽度)
DIALOGUE_LINE_WIDTH_LIMIT = 32
SPEAKER_CHAR_WIDTH_UNITS = 8
CONTENT_LINE1_LIMIT = DIALOGUE_LINE_WIDTH_LIMIT
CONTENT_LINE2_LIMIT = DIALOGUE_LINE_WIDTH_LIMIT

def get_char_width(char: str) -> int:
    """计算字符占用的半角单位宽度 (1 or 2)"""
    if '\u4e00' <= char <= '\u9fff' or char in '，。！？：；“”（）《》……「」':
        return 2
    return 1

def format_speaker(name: str) -> str:
    """将说话人姓名用空格补全并居中，至4个全角字符宽度。"""
    name = name.strip()
    current_width = sum(get_char_width(c) for c in name)
    padding_needed = SPEAKER_CHAR_WIDTH_UNITS - current_width
    if padding_needed > 0:
        left_padding = padding_needed // 2
        right_padding = padding_needed - left_padding
        return ' ' * left_padding + name + ' ' * right_padding
    return name

def layout_dialogue(content: str) -> List[str]:
    """核心文本布局引擎，将长文本分割成多页，每页最多两行。"""
    final_pages = []
    PUNCTUATION = "，。！？…」,.?!"; ELLIPSIS = "……"
    remaining_content = content.strip()
    while remaining_content:
        page_lines = []
        # --- 处理第一行 ---
        if sum(get_char_width(c) for c in remaining_content) <= CONTENT_LINE1_LIMIT:
            page_lines.append(remaining_content); remaining_content = ""
        else:
            width, prelim_break = 0, -1
            for i, char in enumerate(remaining_content):
                width += get_char_width(char)
                if width > CONTENT_LINE1_LIMIT: prelim_break = i; break
            best_break = prelim_break
            ellipsis_pos = remaining_content.rfind(ELLIPSIS, 0, prelim_break)
            if ellipsis_pos != -1 and ellipsis_pos + 2 >= prelim_break - 1: best_break = ellipsis_pos + 2
            else:
                for i in range(prelim_break - 1, 0, -1):
                    if remaining_content[i] in PUNCTUATION: best_break = i + 1; break
            if prelim_break > 0 and remaining_content[best_break - 1:best_break + 1] == ELLIPSIS:
                best_break -= 1; remaining_content = remaining_content[:best_break] + '…' + remaining_content[best_break + 1:]
            page_lines.append(remaining_content[:best_break]); remaining_content = remaining_content[best_break:].lstrip()
        # --- 处理第二行 ---
        if remaining_content:
            if sum(get_char_width(c) for c in remaining_content) <= CONTENT_LINE2_LIMIT:
                page_lines.append(remaining_content); remaining_content = ""
            else:
                width, prelim_break_2 = 0, -1
                for i, char in enumerate(remaining_content):
                    width += get_char_width(char)
                    if width > CONTENT_LINE2_LIMIT: prelim_break_2 = i; break
                best_break_2 = prelim_break_2
                ellipsis_pos_2 = remaining_content.rfind(ELLIPSIS, 0, prelim_break_2)
                if ellipsis_pos_2 != -1 and ellipsis_pos_2 + 2 >= prelim_break_2 - 1: best_break_2 = ellipsis_pos_2 + 2
                else:
                    for i in range(prelim_break_2 - 1, 0, -1):
                        if remaining_content[i] in PUNCTUATION: best_break_2 = i + 1; break
                if prelim_break_2 > 0 and remaining_content[best_break_2 - 1:best_break_2 + 1] == ELLIPSIS:
                    best_break_2 -= 1; remaining_content = remaining_content[:best_break_2] + '…' + remaining_content[best_break_2 + 1:]
                page_lines.append(remaining_content[:best_break_2]); remaining_content = remaining_content[best_break_2:].lstrip()
        final_pages.append('\\n'.join(page_lines))
    return final_pages

def pass_one_build_maps_and_collect_assets(script_lines: List[str]) -> (Dict, Dict, List, List, List):
    print("[第一步] 正在构建标签映射并搜集资源...")
    label_to_output_line, label_to_input_line = {}, {}
    bg_assets: Set[str] = {TITLE_BG_NAME}
    cg_assets, bgm_assets = set(), set()
    output_line_counter = 1
    
    for i, line in enumerate(script_lines):
        input_line_num, stripped_line = i + 1, line.strip()
        if not stripped_line: continue
        
        if stripped_line.upper().startswith(LABEL_PREFIX):
            try:
                label_name = stripped_line.split()[1]
                if label_name in label_to_output_line:
                    print(f"致命错误: 标签 '{label_name}' 在第 {input_line_num} 行重复定义。"); sys.exit(1)
                label_to_output_line[label_name] = output_line_counter
                label_to_input_line[label_name] = input_line_num
            except IndexError:
                print(f"警告: 第 {input_line_num} 行的 ^LABEL 格式错误。")
        else:
            if not stripped_line.startswith('^'):
                try:
                    _, content = stripped_line.split(':', 1)
                    output_line_counter += len(layout_dialogue(content))
                except ValueError:
                    output_line_counter += 1
            else:
                output_line_counter += 1
        
        try:
            parts = stripped_line.split()
            if not parts: continue
            command = parts[0].upper()
            if command == BG_PREFIX and len(parts) > 1: bg_assets.add(parts[1])
            elif command == CG_PREFIX and len(parts) > 2: cg_assets.add(parts[2])
            elif command == BGM_PREFIX and len(parts) > 1: bgm_assets.add(parts[1])
        except IndexError: pass

    sorted_bg = sorted(list(bg_assets - {TITLE_BG_NAME}))
    final_bg_list = [TITLE_BG_NAME] + sorted_bg

    print(f"[第一步] 成功: 找到 {len(label_to_output_line)} 个标签并完成资源搜集。")
    return label_to_output_line, label_to_input_line, final_bg_list, sorted(list(cg_assets)), sorted(list(bgm_assets))

def resolve_jump_chains(script_lines: List[str], label_to_input_line: Dict[str, int]) -> Dict[str, str]:
    print("[第二步] 正在解析与优化跳转链...")
    resolved_labels = {}
    for start_label in label_to_input_line.keys():
        current_label, path_tracker = start_label, {start_label}
        while True:
            first_exec_line = ""
            for i in range(label_to_input_line[current_label] - 1, len(script_lines)):
                line = script_lines[i].strip()
                if line and not line.upper().startswith(LABEL_PREFIX):
                    first_exec_line = line; break
            if first_exec_line.upper().startswith(JUMP_PREFIX):
                match = re.search(r'\[JUMP_TO_([^\]]+)\]', first_exec_line, re.IGNORECASE)
                if match:
                    next_label = match.group(1)
                    if next_label not in label_to_input_line:
                        print(f"致命错误: 从 '{current_label}' 跳转到未定义的标签 '{next_label}'。"); sys.exit(1)
                    if next_label in path_tracker:
                        print(f"致命错误: 检测到无限跳转循环: {' -> '.join(path_tracker)} -> {next_label}"); sys.exit(1)
                    path_tracker.add(next_label); current_label = next_label; continue
            resolved_labels[start_label] = current_label; break
    optimizations = sum(1 for k, v in resolved_labels.items() if k != v)
    print(f"[第二步] 成功: 优化了 {optimizations} 条跳转链。")
    return resolved_labels

def pass_three_generate_final_script(script_lines, label_map_output, resolved_labels, asset_maps, output_filepath):
    print("[第三步] 正在生成最终脚本、索引和应用重索引...")
    final_lines_to_write = []
    jump_pattern = re.compile(r'\[JUMP_TO_([^\]]+)\]', re.IGNORECASE)
    
    def replacer(match):
        original_label = match.group(1)
        if original_label not in label_map_output:
            print(f"致命错误: 在替换时找不到标签 '{original_label}'。"); sys.exit(1)
        final_label = resolved_labels.get(original_label, original_label)
        return str(label_map_output[final_label])

    for line in script_lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.upper().startswith(LABEL_PREFIX): continue
        
        processed_line = jump_pattern.sub(replacer, stripped_line)
        
        if not processed_line.startswith('^'):
            try:
                speaker, content = processed_line.split(':', 1)
                formatted_speaker = format_speaker(speaker)
                paged_content = layout_dialogue(content)
                for page in paged_content:
                    final_lines_to_write.append(f"{formatted_speaker}:{page}")
            except ValueError:
                final_lines_to_write.append(processed_line)
        else:
            parts = processed_line.split()
            command = parts[0].upper()
            if command == BG_PREFIX and len(parts) > 1:
                processed_line = f"^BG {asset_maps['backgrounds'][parts[1]]}"
            elif command == CG_PREFIX and len(parts) > 2:
                processed_line = f"^CG {parts[1]} {asset_maps['characters'][parts[2]]}"
            elif command == DATE_PREFIX and len(parts) > 1:
                try:
                    m, d, dow_str = parts[1].split(',')
                    dow_map = {"SUN":0, "MON":1, "TUE":2, "WED":3, "THU":4, "FRI":5, "SAT":6}
                    processed_line = f"^D {int(m):02d}{int(d):02d}{dow_map[dow_str.upper()]}"
                except Exception as e:
                    print(f"致命错误: 格式错误的 ^DATE 命令: {line} -> {e}"); sys.exit(1)
            final_lines_to_write.append(processed_line)

    base_filepath = output_filepath.rsplit('.', 1)[0]
    index_filepath = base_filepath + '.idx'
    try:
        with open(output_filepath, 'w', encoding='utf-8', newline='\n') as txt_f, open(index_filepath, 'wb') as idx_f:
            offset = 0
            for line in final_lines_to_write:
                idx_f.write(struct.pack('<I', offset))
                line_with_nl = line + '\n'
                encoded_line = line_with_nl.encode('utf-8')
                txt_f.write(line_with_nl)
                offset += len(encoded_line)
        print(f"[第三步] 成功: 脚本已写入 '{output_filepath}'。")
        print(f"[第三步] 成功: 索引已写入 '{index_filepath}'。")
    except IOError as e:
        print(f"致命错误: 无法写入输出文件: {e}"); sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="视觉小说脚本预处理器和资产管理器。")
    parser.add_argument("input_file", help="输入的原始脚本文件路径。")
    parser.add_argument("output_file", help="处理后输出的脚本文件路径 (例如 'final_script.txt')。")
    args = parser.parse_args()

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f: script_lines = f.readlines()
    except FileNotFoundError:
        print(f"致命错误: 输入文件未找到: '{args.input_file}'"); sys.exit(1)

    label_map_output, label_map_input, bg_list, cg_list, bgm_list = pass_one_build_maps_and_collect_assets(script_lines)
    
    bg_map = {name: i for i, name in enumerate(bg_list)}
    cg_map = {name: i for i, name in enumerate(cg_list)}
    
    manifest = {
        "bg_count": len(bg_list), "cg_count": len(cg_list),
        "backgrounds_map": bg_map, "characters_map": cg_map,
        "music": bgm_list
    }
    manifest_path = 'assets_manifest.json'
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)
        print(f"资产清单已生成: '{manifest_path}'。")
    except IOError as e:
        print(f"致命错误: 无法写入清单文件: {e}")

    resolved_labels = resolve_jump_chains(script_lines, label_map_input)
    pass_three_generate_final_script(script_lines, label_map_output, resolved_labels, {"backgrounds": bg_map, "characters": cg_map}, args.output_file)
    print("\n预处理成功完成！")

if __name__ == "__main__":
    main()