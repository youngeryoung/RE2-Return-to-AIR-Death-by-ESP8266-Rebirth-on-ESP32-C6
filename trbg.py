# trbg.py
import cv2
import os
import numpy as np
import json
import sys

def process_background_images_adaptive(input_folder, output_folder, asset_list, density_threshold=0.6, max_attempts=5):
    """
    【背景图自适应简化策略】
    根据资产清单，按需处理并打包背景图。
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    output_dat_path = os.path.join(output_folder, 'bg.dat')
    supported_formats = ('.png', '.jpg', '.jpeg', '.bmp')
    
    with open(output_dat_path, 'wb') as f_out:
        print(f"背景图二进制数据将被写入到: {output_dat_path}")
        
        # 创建一个空的数据块列表，用于按索引顺序填充
        output_data_blocks = [None] * len(asset_list)

        for index, asset_name in enumerate(asset_list):
            found_file_path = None

            # --- 核心修改：大小写不敏感文件名匹配 ---
            folder_files_lower = {}
            for f_name in os.listdir(input_folder):
                f_base, f_ext = os.path.splitext(f_name)
                if f_ext.lower() in supported_formats:
                    folder_files_lower[f_base.lower()] = os.path.join(input_folder, f_name)
            
            target_name_lower = asset_name.lower()
            if target_name_lower in folder_files_lower:
                found_file_path = folder_files_lower[target_name_lower]
            
            if not found_file_path:
                print(f"致命错误: 清单中指定的资源 '{asset_name}' 在输入文件夹 '{input_folder}' 中未找到！")
                sys.exit(1)

            filename = os.path.basename(found_file_path)
            output_img_path = os.path.join(output_folder, f"processed_{os.path.splitext(filename)[0]}.png")
            print(f"正在处理 '{filename}' (索引: {index})...")

            try:
                img = cv2.imread(found_file_path)
                if img is None:
                    print(f"警告: 无法读取 {found_file_path}，已跳过。")
                    continue
                
                # 1. 裁剪原始图片为 2:1 宽高比
                h, w, _ = img.shape
                target_h_crop = w // 2
                crop_y_start = (h - target_h_crop) // 2 if h > target_h_crop else 0
                img_cropped_high_res = img[crop_y_start : crop_y_start + target_h_crop, :]
                target_w, target_h = 96, 48

                # 准备高分辨率灰度图用于提取边缘
                gray_high_res = cv2.cvtColor(img_cropped_high_res, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray_high_res, (5, 5), 0)
                base_median_val = np.median(blurred)
                final_image = None

                # 2. 自适应简化循环
                for attempt in range(max_attempts):
                    simplification_factor = 1.0 + (attempt * 0.4)
                    adjusted_median = base_median_val * simplification_factor
                    sigma = 0.33
                    canny_low = int(max(0, (1.0 - sigma) * adjusted_median))
                    canny_high = int(min(255, (1.0 + sigma) * adjusted_median))

                    # 3. 生成图像 (色块底图 + 重绘轮廓)
                    img_resized = cv2.resize(img_cropped_high_res, (target_w, target_h), interpolation=cv2.INTER_AREA)
                    gray_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                    base_image = cv2.adaptiveThreshold(gray_resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                    
                    edges_high_res = cv2.Canny(blurred, canny_low, canny_high)
                    line_art_overlay = np.zeros((target_h, target_w), dtype=np.uint8)
                    contours, _ = cv2.findContours(edges_high_res, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if contours:
                        scale_x, scale_y = target_w / edges_high_res.shape[1], target_h / edges_high_res.shape[0]
                        for c in contours:
                            c_scaled = (c * [scale_x, scale_y]).astype(np.int32)
                            cv2.drawContours(line_art_overlay, [c_scaled], -1, 255, 1)

                    current_image_attempt = base_image.copy()
                    current_image_attempt[line_art_overlay == 255] = 0

                    # 4. 检查黑色像素密度
                    black_pixels = np.count_nonzero(current_image_attempt == 0)
                    density = black_pixels / (target_w * target_h)
                    
                    final_image = current_image_attempt
                    if density < density_threshold:
                        break # 密度达标，跳出循环
                
                # 5. 保存预览图和二进制数据
                cv2.imwrite(output_img_path, final_image)
                # 将 (0, 255) 图像转为 (1, 0) 数组，0代表黑色
                binary_bits = (final_image == 0).astype(np.uint8)
                # 按行打包成 MONO_HLSB 格式的字节流
                packed_data = np.packbits(binary_bits, axis=1)
                
                # 按索引顺序填充数据块
                output_data_blocks[index] = packed_data.tobytes()

            except Exception as e:
                print(f"处理图片 {filename} 时发生错误: {e}")

        # 将所有数据块按顺序写入文件
        for block in output_data_blocks:
            if block:
                f_out.write(block)
            else:
                # 如果某个块处理失败，写入一个空白块以保证索引正确
                f_out.write(b'\x00' * (target_w * target_h // 8))
        
        print("\n所有必需的背景图片已打包到 bg.dat！")
# trbg.py
# ... (process_background_images_adaptive 函数与之前的版本相同) ...

if __name__ == '__main__':
    manifest_path = 'assets_manifest.json'
    input_folder_path = "pic"
    output_folder_path = "out_img"
    
    DENSITY_LIMIT = 0.5
    MAX_ATTEMPTS = 50
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        bg_asset_map = manifest.get("backgrounds_map", {})
        if not bg_asset_map:
            print("清单中没有背景图资源，跳过打包。")
        else:
            # --- 核心修改：将 map 转换为按索引排序的列表 ---
            # 创建一个正确长度的空列表
            sorted_asset_list = [""] * len(bg_asset_map)
            # 根据 map 中的 "name": index 键值对，填充列表
            for name, index in bg_asset_map.items():
                if index < len(sorted_asset_list):
                    sorted_asset_list[index] = name
                else:
                    print(f"致命错误: 资源 '{name}' 的索引 {index} 超出范围!")
                    sys.exit(1)
            
            # 确认 TITLE 在索引 0
            if sorted_asset_list[0] != 'TITLE':
                print("警告: 封面资源 'TITLE' 未在索引 0。请检查图片文件夹中是否存在 TITLE.png/jpg。")

            print(f"从清单加载了 {len(sorted_asset_list)} 个背景图资源，将按索引顺序打包。")
            process_background_images_adaptive(
                input_folder_path, 
                output_folder_path,
                asset_list=sorted_asset_list,
                density_threshold=DENSITY_LIMIT,
                max_attempts=MAX_ATTEMPTS
            )
    except FileNotFoundError:
        print(f"致命错误: 资产清单文件 '{manifest_path}' 未找到。请先运行 preprocess.py。")
    except Exception as e:
        print(f"发生未知错误: {e}")