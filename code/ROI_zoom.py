import cv2
import numpy as np
import os
from PIL import Image

class SimpleROIEditor:
    def __init__(self, preset_params, colors=None):
        self.preset_params = preset_params
        self.num_rois = len(preset_params)

        self.colors = [
            (0, 0, 255), (0, 255, 0), (255, 0, 0),
            (255, 255, 0), (255, 0, 255)
        ]
        if colors is not None:
            self.colors = colors

        self.absolute_rois = []  # 存储绝对坐标
        self.current_roi = None
        self.img = None
        self.clone = None

    def select_rois(self, image_path):
        # self.img = cv2.imread(image_path)
        # self.img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), -1)
        pil_image = Image.open(image_path)
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        self.img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        if self.img is None:
            raise ValueError(f"无法读取图像: {image_path}")

        self.clone = self.img.copy()
        self.absolute_rois = []  # 存储绝对坐标

        cv2.namedWindow("ROI Editor")
        cv2.setMouseCallback("ROI Editor", self.mouse_callback)

        print("操作指南:")
        print("1. 左键拖动: 选择ROI区域")
        print("2. 右键单击: 撤销上一个ROI")
        print(f"3. 需要选择 {self.num_rois} 个ROI区域")
        print("4. 按 's' 保存并处理所有图像")
        print("5. 按 'q' 退出")

        remaining = self.num_rois

        while True:
            display_img = self.clone.copy()
            h, w = display_img.shape[:2]

            # 绘制已选择的ROI（使用绝对坐标）
            for i, (x, y, w_rect, h_rect) in enumerate(self.absolute_rois):
                color = self.colors[i % len(self.colors)]
                cv2.rectangle(display_img, (x, y), (x + w_rect - 1, y + h_rect - 1), color, 2)

                # 获取预设参数
                position_code, relative_size, is_relative_weight = self.preset_params[i]

                # 计算放大区域尺寸
                if is_relative_weight:
                    display_size = int(w * relative_size)
                else:
                    display_size = int(h * relative_size)

                # 调整大小以保持宽高比
                aspect_ratio = w_rect / h_rect
                if aspect_ratio > 1:  # 宽大于高
                    display_w = display_size
                    display_h = int(display_w / aspect_ratio)
                else:
                    display_h = display_size
                    display_w = int(display_h * aspect_ratio)


                # 计算放置位置
                place_x, place_y = calculate_position(position_code, w, h, display_w, display_h)

                # 确保位置在图像范围内
                place_x = max(0, min(place_x, w - display_w))
                place_y = max(0, min(place_y, h - display_h))

                # 绘制放大区域边框
                cv2.rectangle(display_img, (place_x, place_y),
                              (place_x + display_w, place_y + display_h), color, 2)

                # 在放大区域内显示ROI的放大预览
                if 0 <= y < h and 0 <= x < w and h_rect > 0 and w_rect > 0:
                    roi_area = self.img[y:y + h_rect, x:x + w_rect]
                    if roi_area.size > 0:
                        zoomed_preview = cv2.resize(roi_area, (display_w - 2, display_h - 2))
                        display_img[place_y + 1:place_y + display_h - 1, place_x + 1:place_x + display_w - 1] = zoomed_preview

            # 绘制当前正在选择的ROI
            if self.current_roi:
                x1, y1, x2, y2 = self.current_roi
                cv2.rectangle(display_img, (x1, y1), (x2 - 1, y2 - 1), (200, 200, 200), 2)

            # 显示ROI序号
            status = f"ROI: {len(self.absolute_rois)}/{self.num_rois}"
            cv2.putText(display_img, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("ROI Editor", display_img)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                if len(self.absolute_rois) == self.num_rois:
                    break
                else:
                    print(f"需要选择 {self.num_rois} 个ROI，当前只有 {len(self.absolute_rois)} 个")
            elif key == ord('q'):
                self.absolute_rois = []
                break

        cv2.destroyAllWindows()
        return self.absolute_rois

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_roi = [x, y, x, y]

        elif event == cv2.EVENT_MOUSEMOVE and flags == cv2.EVENT_FLAG_LBUTTON:
            if self.current_roi:
                self.current_roi[2] = x
                self.current_roi[3] = y

        elif event == cv2.EVENT_LBUTTONUP:
            if self.current_roi and len(self.absolute_rois) < self.num_rois:
                x1, y1, x2, y2 = self.current_roi
                # 获取ROI的绝对坐标
                x = min(x1, x2)
                y = min(y1, y2)
                w_rect = abs(x2 - x1)
                h_rect = abs(y2 - y1)


                self.absolute_rois.append((x, y, w_rect, h_rect))
                print(f"添加ROI {len(self.absolute_rois)}: 位置=({x}, {y}), 尺寸={w_rect}x{h_rect}")

                self.current_roi = None

        elif event == cv2.EVENT_RBUTTONDOWN:
            if self.absolute_rois:
                print(f"撤销ROI {len(self.absolute_rois)}")
                self.absolute_rois.pop()
                self.current_roi = None


def apply_rois_to_image(img, absolute_rois, preset_params, colormap=None):
    if img is None or not absolute_rois:
        return img

    result = img.copy()
    h, w = img.shape[:2]

    # 颜色盘
    colors = [
        (0, 0, 255), (0, 255, 0), (255, 0, 0),
        (255, 255, 0), (255, 0, 255)
    ]
    if colormap is not None:
        colors = colormap

    for i, (roi_x, roi_y, roi_w, roi_h) in enumerate(absolute_rois):
        if i >= len(preset_params):
            break

        position_code, relative_size, is_relative_weight = preset_params[i]

        # 确保ROI在图像范围内
        roi_x = max(0, min(roi_x, w - 1))
        roi_y = max(0, min(roi_y, h - 1))
        roi_w = min(roi_w, w - 1 - roi_x)
        roi_h = min(roi_h, h - 1 - roi_y)

        if roi_w <= 0 or roi_h <= 0:
            continue

        # 提取ROI区域
        roi_img = result[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
        if roi_img.size == 0:
            continue

        # 计算放大后的显示尺寸
        if is_relative_weight:
            display_size = int(w * relative_size)
        else:
            display_size = int(h * relative_size)

        # 调整大小以保持宽高比
        aspect_ratio = roi_w / roi_h
        if aspect_ratio > 1:  # 宽大于高
            display_w = display_size
            display_h = int(display_w / aspect_ratio)
        else:
            display_h = display_size
            display_w = int(display_h * aspect_ratio)

        # 直接缩放ROI到显示尺寸（包含放大效果）
        display_img = cv2.resize(roi_img, (display_w, display_h))

        # 计算放置位置
        place_x, place_y = calculate_position(position_code, w, h, display_w, display_h)

        # 确保位置在图像范围内
        place_x = max(0, min(place_x, w - display_w))
        place_y = max(0, min(place_y, h - display_h))

        # 放置放大后的ROI
        result[place_y:place_y + display_h, place_x:place_x + display_w] = display_img

        # 获取颜色
        color = colors[i % len(colors)]

        # 绘制原始ROI和放大区域的边框
        cv2.rectangle(result, (roi_x, roi_y), (roi_x + roi_w - 1, roi_y + roi_h - 1), color, 2)
        cv2.rectangle(result, (place_x, place_y),
                      (place_x + display_w - 1, place_y + display_h - 1), color, 2)

    return result


def calculate_position(position_code, img_w, img_h, disp_w, disp_h):
    """根据位置代码计算放大区域的放置位置"""
    # 对于边界位置，使用特殊处理
    if position_code == 5:  # 上边界全覆盖
        return (1, 1)
    elif position_code == 6:  # 下边界全覆盖
        return (1, img_h - 1 - disp_h)
    elif position_code == 7:  # 左边界全覆盖
        return (1, 1)
    elif position_code == 8:  # 右边界全覆盖
        return (img_w - 1 - disp_w, 1)

    # 其他位置使用标准布局
    if position_code == 1:  # 左上
        return (1, 1)
    elif position_code == 2:  # 右上
        return (img_w - 1 - disp_w, 1)
    elif position_code == 3:  # 左下
        return (1, img_h - 1 - disp_h)
    elif position_code == 4:  # 右下
        return (img_w - 1 - disp_w, img_h - 1 - disp_h)
    else:  # 默认为左上
        return (1, 1)


def process_folder(image_paths, output_folder, absolute_rois, preset_params, is_saved=False, colormap=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for i, img_path in enumerate(image_paths):
        # img = cv2.imread(img_path)

        pil_img = Image.open(img_path)
        if pil_img.mode == 'RGBA':
            pil_img = pil_img.convert('RGB')
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        if img is None:
            print(f"无法读取图像: {img_path}")
            continue

        # 应用ROI时使用绝对坐标
        result = apply_rois_to_image(img, absolute_rois, preset_params, colormap=colormap)

        # 显示处理结果
        filename = os.path.basename(img_path)
        print(f"已处理: {filename} ({i + 1}/{len(image_paths)})")


        cv2.namedWindow(filename.split('.')[0])
        cv2.imshow(filename.split('.')[0], result)
        cv2.waitKey(0)
        cv2.destroyWindow(filename.split('.')[0])

        # 保存结果
        if is_saved:
            output_path = os.path.join(output_folder, f"enhanced_{filename}")
            # cv2.imwrite(output_path, result)

            # Use PIL to save to handle Chinese paths
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            result_pil = Image.fromarray(result_rgb)
            result_pil.save(output_path)

            print(f"已保存: {output_path} ")

    print("处理完成!")
    if is_saved:
        print(f"结果保存在：{output_folder}")
    else:
        print(f"结果未保存!")


if __name__ == "__main__":
    # input_folder = "input_images"
    # output_folder = "output_images"

    input_folder = r"F:\学习\github相关\研究生\科研论文中多张图片局部区域批量放大\示例图像\ROI_zoom\输入"
    output_folder = r"F:\学习\github相关\研究生\科研论文中多张图片局部区域批量放大\示例图像\ROI_zoom\输出"

    is_saved = False

    # 颜色盘
    colormap = [
        (255, 255, 0), (0, 255, 0), (0, 0, 255),
        (255, 0, 0), (255, 0, 255)
    ]

    # 预设参数：每个元组为 (位置代码, 相对大小, 相对大小是否参考图像宽度（True：宽度；False：高度）)
    # 位置代码: 1=左上, 2=右上, 3=左下, 4=右下, 5=上边界, 6=下边界, 7=左边界, 8=右边界
    preset_params = [
        (1, 0.25, True),  # 左上位置, 大小为图像宽度的25%
        (6, 1.0, True),  # 下边界全覆盖
    ]



    image_paths = [os.path.join(input_folder, name) for name in os.listdir(input_folder)]
    image_paths = [path for path in image_paths if os.path.isfile(path)]

    if not image_paths:
        print(f"在 {input_folder} 中未找到图像")
        exit()
    print(f"处理 {len(image_paths)} 张图像...")

    first_image = image_paths[0]
    editor = SimpleROIEditor(preset_params, colors=colormap)

    print("-" * 20)
    print("在第一张图像上选择ROI区域")
    print("-" * 20)
    absolute_rois = editor.select_rois(first_image)

    if not absolute_rois:
        print("未完成ROI区域选择和放大任务，退出程序！")
        exit()

    # preview_img = cv2.imread(first_image)
    pil_img = Image.open(first_image)
    if pil_img.mode == 'RGBA':
        pil_img = pil_img.convert('RGB')
    preview_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    preview_result = apply_rois_to_image(preview_img, absolute_rois, preset_params, colormap=colormap)

    if preview_result is not None and preview_result.size > 0:
        cv2.namedWindow("Preview (Press any key)")
        cv2.imshow("Preview (Press any key)", preview_result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    confirm = input("是否应用设置到所有图像? (y/n): ").strip().lower()
    if confirm != 'y':
        print("取消处理")
        exit()

    print("\n" + "-" * 20)
    print("开始处理所有图像")
    print("-" * 20)
    process_folder(image_paths, output_folder, absolute_rois, preset_params, is_saved=is_saved, colormap=colormap)

