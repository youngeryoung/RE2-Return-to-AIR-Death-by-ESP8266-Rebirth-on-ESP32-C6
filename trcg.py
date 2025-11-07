# trcg.py
import cv2
import os
import numpy as np
import json
import sys

def process_cg_for_mcu(input_folder, output_folder, asset_list):
    """
    【轮廓重绘方案】根据资产清单，按需处理并打包CG图片。
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    output_dat_path = os.path.join(output_folder, 'cg.dat')
    supported_formats = ('.png', '.jpg', '.jpeg', '.bmp')
    
    with open(output_dat_path, 'wb') as f_out:
        print(f"CG 二进制数据将被写入到: {output_dat_path}")
        
        # 创建一个空的数据块列表，用于按索引顺序填充
        output_data_blocks = [None] * len(asset_list)

        for index, asset_name in enumerate(asset_list):
            found_file = None
            for ext in supported_formats:
                potential_path = os.path.join(input_folder, asset_name + ext)
                if os.path.exists(potential_path):
                    found_file = potential_path
                    break
            
            if not found_file:
                print(f"致命错误: 清单中指定的资源 '{asset_name}' 在输入文件夹 '{input_folder}' 中未找到！")
                sys.exit(1)

            filename = os.path.basename(found_file)
            output_img_path = os.path.join(output_folder, f"processed_{os.path.splitext(filename)[0]}.png")
            print(f"正在处理 '{filename}' (索引: {index})...")

            try:
                img = cv2.imread(found_file)
                if img is None:
                    print(f"警告: 无法读取 {found_file}，已跳过。")
                    continue
                
                # 1. 裁剪并获取高分辨率的边缘图
                h_orig, w_orig, _ = img.shape
                crop_w, crop_h = 216, 360 # 假设源图是 640x480 或类似比例
                x_start = (w_orig - crop_w) // 2
                y_start = (h_orig - crop_h) // 2
                img_cropped = img[y_start:y_start+crop_h, x_start:x_start+crop_w]

                gray_cropped = cv2.cvtColor(img_cropped, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray_cropped, (5, 5), 0)
                median_val = np.median(blurred)
                sigma = 0.33
                canny_low = int(max(0, (1.0 - sigma) * median_val))
                canny_high = int(min(255, (1.0 + sigma) * median_val))
                edges = cv2.Canny(blurred, canny_low, canny_high)
                
                # 2. 创建一个空白的目标尺寸画布 (黑底)
                target_w, target_h = 24, 48
                final_image_black_bg = np.zeros((target_h, target_w), dtype=np.uint8)

                # 3. 在高分辨率边缘图中查找所有轮廓的坐标
                contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                # 4. 计算缩放比例
                scale_x = target_w / crop_w
                scale_y = target_h / crop_h

                # 5. 遍历每个轮廓，将其坐标按比例缩小，然后在新画布上重绘
                if contours:
                    for c in contours:
                        c_scaled = (c * [scale_x, scale_y]).astype(np.int32)
                        cv2.drawContours(final_image_black_bg, [c_scaled], -1, 255, 1)

                # 6. 将生成的 "白线黑底" 图像反色为 "黑线白底"
                final_bw_inverted = cv2.bitwise_not(final_image_black_bg)

                # 7. 保存最终结果和二进制数据
                cv2.imwrite(output_img_path, final_bw_inverted)
                # 将 (0, 255) 图像转为 (1, 0) 数组，0代表黑色
                binary_bits = (final_bw_inverted == 0).astype(np.uint8)
                # 按行打包成 MONO_HLSB 格式的字节流
                packed_data = np.packbits(binary_bits, axis=1)
                
                output_data_blocks[index] = packed_data.tobytes()

            except Exception as e:
                print(f"处理图片 {filename} 时发生错误: {e}")

        # 将所有数据块按顺序写入文件
        for block in output_data_blocks:
            if block:
                f_out.write(block)
            else:
                f_out.write(b'\x00' * (target_w * target_h // 8))

        print("\n所有必需的CG图片已打包到 cg.dat！")

if __name__ == '__main__':
    manifest_path = 'assets_manifest.json'
    input_folder_path = "pic"         # 包含源 CG 图的文件夹
    output_folder_path = "outcg"      # 输出处理后的预览图和 .dat 文件
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        cg_asset_map = manifest.get("characters_map", {})
        if not cg_asset_map:
            print("清单中没有CG资源，跳过打包。")
        else:
            # 将 map 转换为按索引排序的列表
            sorted_asset_list = [""] * len(cg_asset_map)
            for name, index in cg_asset_map.items():
                sorted_asset_list[index] = name
            
            print(f"从清单加载了 {len(sorted_asset_list)} 个CG资源。")
            process_cg_for_mcu(
                input_folder_path, 
                output_folder_path,
                asset_list=sorted_asset_list
            )
    except FileNotFoundError:
        print(f"致命错误: 资产清单文件 '{manifest_path}' 未找到。请先运行 preprocess.py。")
    except Exception as e:
        print(f"发生未知错误: {e}")