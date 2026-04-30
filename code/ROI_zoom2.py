import cv2
import numpy as np
import os
from PIL import Image

class EnhancedROIEditor:
    def __init__(self, num_rois, colors=None):
        self.num_rois = num_rois
        self.colors = [
            (0, 0, 255), (0, 255, 0), (255, 0, 0),
            (255, 255, 0), (255, 0, 255)
        ]
        if colors is not None:
            self.colors = colors

        self.original_rois = []  # 存储原始ROI信息
        self.zoom_rois = []  # 存储放大区域信息
        self.position_codes = []  # 存储位置代码

        self.current_roi = None
        self.current_zoom = None
        self.current_position = None
        self.current_roi_index = -1

        self.img = None
        self.clone = None
        self.aspect_ratio = None
        self.state = "select_roi"  # 状态: select_roi, input_position, select_zoom
        self.fixed_corner = None  # 存储固定角落坐标

    def run(self, image_path):
        # self.img = cv2.imread(image_path)
        # self.img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), -1)
        pil_image = Image.open(image_path)
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        self.img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        if self.img is None:
            raise ValueError(f"无法读取图像: {image_path}")

        self.clone = self.img.copy()
        self.original_rois = []
        self.zoom_rois = []
        self.position_codes = []
        self.current_roi_index = -1
        self.fixed_corner = None

        cv2.namedWindow("ROI Editor")
        cv2.setMouseCallback("ROI Editor", self.mouse_callback)

        print("=" * 50)
        print("交互式ROI编辑器")
        print("=" * 50)
        print("操作指南:")
        print("1. 左键拖动: 选择ROI区域")
        print("2. 需要选择区域后，按1-8选择放大区域位置")
        print("   (1=左上, 2=右上, 3=左下, 4=右下, 5=上, 6=下, 7=左, 8=右)")
        print("3. 对于位置1-4: 鼠标拖动选择放大区域尺寸（从固定角落开始）")
        print("4. 右键单击:")
        print("   - ROI选择状态: 返回上一个ROI的方向选择状态")
        print("   - 位置选择状态: 撤销整个当前ROI")
        print("   - 放大区域选择状态: 返回位置选择状态")
        print("5. 按 's' 保存并处理所有图像")
        print("6. 按 'q' 退出")

        while True:
            display_img = self.clone.copy()
            h, w = display_img.shape[:2]

            # 绘制已选择的ROI和放大区域
            for i, (roi, zoom_rect, pos_code) in enumerate(zip(self.original_rois, self.zoom_rois, self.position_codes)):

                color = self.colors[i % len(self.colors)]

                # 绘制原始ROI
                x, y, w_rect, h_rect = roi
                cv2.rectangle(display_img, (x, y), (x + w_rect, y + h_rect), color, 2)

                # 绘制放大区域
                if zoom_rect:
                    zx, zy, zw, zh = zoom_rect
                    cv2.rectangle(display_img, (zx, zy), (zx + zw - 1, zy + zh - 1), color, 2)

                    # Display zoomed content preview
                    if i < len(self.original_rois):
                        roi_x, roi_y, roi_w, roi_h = self.original_rois[i]
                        if 0 <= roi_y < h and 0 <= roi_x < w and roi_h > 0 and roi_w > 0:
                            roi_area = self.img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
                            if roi_area.size > 0:
                                try:
                                    zoomed_preview = cv2.resize(roi_area, (zw - 2, zh - 2))
                                    display_img[zy + 1:zy + zh - 1, zx + 1:zx + zw - 1] = zoomed_preview
                                except:
                                    pass

            # 绘制当前正在选择的ROI
            if self.current_roi:
                x1, y1, x2, y2 = self.current_roi
                cv2.rectangle(display_img, (x1, y1), (x2, y2), (200, 200, 200), 2)

            # 绘制当前正在选择的放大区域
            if self.current_zoom and self.fixed_corner:
                x1, y1, x2, y2 = self.current_zoom
                # 绘制固定角落标记
                cv2.circle(display_img, self.fixed_corner, 5, (0, 255, 255), -1)
                cv2.rectangle(display_img, (x1, y1), (x2 - 1, y2 - 1), (150, 150, 255), 2)

            # 显示状态信息
            status = f"State: {self.state} | ROI: {len(self.original_rois)}/{self.num_rois}"
            cv2.putText(display_img, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("ROI Editor", display_img)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                if len(self.original_rois) == self.num_rois:
                    break
                else:
                    print(f"需要选择 {self.num_rois} 个ROI，当前只有 {len(self.original_rois)} 个")
            elif key == ord('q'):
                self.original_rois = []
                break
            elif self.state == "input_position" and key in [ord(str(i)) for i in range(1, 9)]:
                pos_code = int(chr(key))
                self.handle_position_input(pos_code)

        cv2.destroyAllWindows()
        return self.original_rois, self.zoom_rois, self.position_codes

    def mouse_callback(self, event, x, y, flags, param):
        if self.state == "select_roi":
            self.handle_roi_selection(event, x, y, flags)
        elif self.state == "input_position":
            self.handle_position_selection(event, x, y, flags)
        elif self.state == "select_zoom":
            self.handle_zoom_selection(event, x, y, flags)

    def handle_roi_selection(self, event, x, y, flags):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_roi = [x, y, x, y]

        elif event == cv2.EVENT_MOUSEMOVE and flags == cv2.EVENT_FLAG_LBUTTON:
            if self.current_roi:
                self.current_roi[2] = x
                self.current_roi[3] = y

        elif event == cv2.EVENT_LBUTTONUP:
            if self.current_roi and len(self.original_rois) < self.num_rois:
                x1, y1, x2, y2 = self.current_roi
                # 获取ROI的绝对坐标
                x = min(x1, x2)
                y = min(y1, y2)
                w_rect = abs(x2 - x1)
                h_rect = abs(y2 - y1)

                self.original_rois.append((x, y, w_rect, h_rect))
                self.zoom_rois.append(None)
                self.position_codes.append(None)
                self.current_roi_index = len(self.original_rois) - 1
                self.aspect_ratio = w_rect / h_rect
                print(f"添加ROI {len(self.original_rois)}: 位置=({x}, {y}), 尺寸={w_rect}x{h_rect}")
                print("请按1-8选择放大区域位置:")
                print("1=左上, 2=右上, 3=左下, 4=右下, 5=上, 6=下, 7=左, 8=右")
                self.state = "input_position"

                self.current_roi = None

        elif event == cv2.EVENT_RBUTTONDOWN:
            if self.original_rois and self.zoom_rois[self.current_roi_index] is not None:
                # 返回上一个ROI的方向选择状态
                self.zoom_rois[self.current_roi_index] = None
                self.position_codes[self.current_roi_index] = None
                self.state = "input_position"
                print(f"返回ROI {self.current_roi_index + 1}的方向选择状态")

    def handle_position_selection(self, event, x, y, flags):
        """处理位置选择状态下的鼠标事件"""
        if event == cv2.EVENT_RBUTTONDOWN:
            if self.original_rois:
                print(f"撤销ROI {len(self.original_rois)}")

                # 撤销整个当前ROI
                self.original_rois.pop()
                self.zoom_rois.pop()
                self.position_codes.pop()
                self.current_roi_index = len(self.original_rois) - 1
                self.state = "select_roi"

    def handle_zoom_selection(self, event, x, y, flags):
        img_h, img_w = self.img.shape[:2]
        pos_code = self.position_codes[self.current_roi_index]

        # 根据位置代码设置固定角落
        if event == cv2.EVENT_LBUTTONDOWN:
            if pos_code == 1:  # 左上
                self.fixed_corner = (1, 1)
                self.current_zoom = [1, 1, x, y]
            elif pos_code == 2:  # 右上
                self.fixed_corner = (img_w-1, 1)
                self.current_zoom = [img_w-1, 1, x, y]
            elif pos_code == 3:  # 左下
                self.fixed_corner = (1, img_h-1)
                self.current_zoom = [1, img_h-1, x, y]
            elif pos_code == 4:  # 右下
                self.fixed_corner = (img_w-1, img_h-1)
                self.current_zoom = [img_w-1, img_h-1, x, y]

        elif event == cv2.EVENT_MOUSEMOVE and flags == cv2.EVENT_FLAG_LBUTTON:
            if self.current_zoom:
                # 更新终点为当前鼠标位置
                if pos_code in [1, 2, 3, 4]:  # 左上、右上、左下、右下
                    self.current_zoom[2] = x
                    self.current_zoom[3] = y

                # 实时计算保持宽高比的矩形
                fx, fy = self.fixed_corner
                x1, y1, x2, y2 = self.current_zoom

                # 计算初始宽度和高度
                if pos_code in [1, 2, 3, 4]:  # 左上、右上、左下、右下
                    zw = abs(x2 - fx)
                    zh = abs(y2 - fy)

                # 保持宽高比
                if self.aspect_ratio > 0:
                    if zw / self.aspect_ratio > zh:
                        zh = int(zw / self.aspect_ratio)
                    else:
                        zw = int(zh * self.aspect_ratio)

                # 根据位置代码重新计算终点坐标
                # 更新当前矩形（显示保持宽高比的预览）
                if pos_code == 1:  # 左上
                    self.current_zoom[2] = fx + zw
                    self.current_zoom[3] = fy + zh
                elif pos_code == 2:  # 右上
                    self.current_zoom[2] = fx - zw
                    self.current_zoom[3] = fy + zh
                elif pos_code == 3:  # 左下
                    self.current_zoom[2] = fx + zw
                    self.current_zoom[3] = fy - zh
                elif pos_code == 4:  # 右下
                    self.current_zoom[2] = fx - zw
                    self.current_zoom[3] = fy - zh

        elif event == cv2.EVENT_LBUTTONUP:
            if self.current_zoom and self.current_roi_index >= 0:
                x1, y1, x2, y2 = self.current_zoom

                # 确定矩形的左上角和宽高
                if pos_code == 1:  # 左上: 从(0,0)到(x,y)
                    zx = min(1, x2)
                    zy = min(1, y2)
                    zw = max(1, x2) - zx
                    zh = max(1, y2) - zy
                elif pos_code == 2:  # 右上: 从(img_w,0)到(x,y)
                    zx = min(img_w-1, x2)
                    zy = min(1, y2)
                    zw = max(img_w-1, x2) - zx
                    zh = max(1, y2) - zy
                elif pos_code == 3:  # 左下: 从(0,img_h)到(x,y)
                    zx = min(1, x2)
                    zy = min(img_h-1, y2)
                    zw = max(1, x2) - zx
                    zh = max(img_h-1, y2) - zy
                elif pos_code == 4:  # 右下: 从(img_w,img_h)到(x,y)
                    zx = min(img_w-1, x2)
                    zy = min(img_h-1, y2)
                    zw = max(img_w-1, x2) - zx
                    zh = max(img_h-1, y2) - zy

                # 保持宽高比
                if self.aspect_ratio > 0:
                    if zw / self.aspect_ratio > zh:
                        zh = int(zw / self.aspect_ratio)
                    else:
                        zw = int(zh * self.aspect_ratio)

                # 检查是否超出图像边界
                if (zx < 0 or zy < 0 or zx + zw > img_w or zy + zh > img_h):
                    print("警告: 放大区域超出图像边界! 请重新选择位置")
                    self.state = "input_position"
                    self.current_zoom = None
                    self.fixed_corner = None
                    print("请重新按1-8选择放大区域位置:")
                    return

                self.zoom_rois[self.current_roi_index] = (zx, zy, zw, zh)
                print(f"添加放大区域: 位置=({zx}, {zy}), 尺寸={zw}x{zh}")
                self.state = "select_roi"
                self.fixed_corner = None

                self.current_zoom = None

        elif event == cv2.EVENT_RBUTTONDOWN:
            # 返回位置选择状态
            self.state = "input_position"
            self.current_zoom = None
            self.fixed_corner = None
            print("返回位置选择状态，请按1-8选择放大区域位置:")

    def handle_position_input(self, pos_code):
        if self.current_roi_index < 0:
            return

        self.position_codes[self.current_roi_index] = pos_code
        img_h, img_w = self.img.shape[:2]
        x, y, w, h = self.original_rois[self.current_roi_index]

        # 对于边界位置(5-8)，自动计算放大区域
        if 5 <= pos_code <= 8:
            if pos_code == 5:  # 上边界
                zw = img_w-1
                zh = int(zw / self.aspect_ratio)
                zx = 1
                zy = 1
            elif pos_code == 6:  # 下边界
                zw = img_w-1
                zh = int(zw / self.aspect_ratio)
                zx = 1
                zy = img_h - 1 - zh
            elif pos_code == 7:  # 左边界
                zh = img_h-1
                zw = int(zh * self.aspect_ratio)
                zx = 1
                zy = 1
            else:  # 右边界
                zh = img_h-1
                zw = int(zh * self.aspect_ratio)
                zx = img_w - 1 - zw
                zy = 1

            # 检查边界
            if (zx < 0 or zy < 0 or zx + zw > img_w or zy + zh > img_h):
                print("警告: 自动生成的放大区域超出图像边界! 请重新选择位置")
                self.position_codes[self.current_roi_index] = None
                self.zoom_rois[self.current_roi_index] = None
                self.state = "input_position"
                print("请重新按1-8选择放大区域位置:")
                return

            self.zoom_rois[self.current_roi_index] = (zx, zy, zw, zh)
            print(f"自动生成放大区域: 位置=({zx}, {zy}), 尺寸={zw}x{zh}")
            self.state = "select_roi"
        else:  # 对于角落位置(1-4)，需要用户选择尺寸
            print("请用鼠标拖动选择放大区域尺寸 (从固定角落开始)")
            self.state = "select_zoom"


def apply_rois_to_image(img, original_rois, zoom_rois, position_codes, colormap=None):
    if img is None or not original_rois:
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

    for i, (roi, zoom_rect, pos_code) in enumerate(zip(original_rois, zoom_rois, position_codes)):

        if not roi or not zoom_rect or not pos_code:
            continue

        roi_x, roi_y, roi_w, roi_h = roi
        zoom_x, zoom_y, zoom_w, zoom_h = zoom_rect

        # 确保ROI在图像范围内
        roi_x = max(0, min(roi_x, w - 1))
        roi_y = max(0, min(roi_y, h - 1))
        roi_w = min(roi_w, w - 1 - roi_x)
        roi_h = min(roi_h, h - 1 - roi_y)

        if roi_w <= 0 or roi_h <= 0:
            continue

        # 提取ROI区域
        roi_img = img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
        if roi_img.size == 0:
            continue

        # 放大ROI区域
        zoomed_img = cv2.resize(roi_img, (zoom_w, zoom_h))

        # 获取颜色
        color = colors[i % len(colors)]

        # 放置放大后的ROI
        if zoom_y + zoom_h <= h and zoom_x + zoom_w <= w:
            result[zoom_y:zoom_y + zoom_h, zoom_x:zoom_x + zoom_w] = zoomed_img

        # 绘制原始ROI和放大区域的边框
        cv2.rectangle(result, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), color, 2)
        cv2.rectangle(result, (zoom_x, zoom_y),
                      (zoom_x + zoom_w - 1, zoom_y + zoom_h - 1), color, 2)

    return result


def process_folder(image_paths, output_folder, original_rois, zoom_rois, position_codes, is_saved=False, colormap=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for i, img_path in enumerate(image_paths):

        # Use PIL to handle Chinese paths

        # img = cv2.imread(img_path)

        pil_image = Image.open(img_path)
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        if img is None:
            print(f"无法读取图像: {img_path}")
            continue

        # 应用ROI处理
        result = apply_rois_to_image(img, original_rois, zoom_rois, position_codes, colormap=colormap)

        if result is None or result.size == 0:
            print(f"Failed to process: {os.path.basename(img_path)} - empty result")
            continue

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
        #     cv2.imwrite(output_path, result)

            # Use PIL to save to handle Chinese paths
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            result_pil = Image.fromarray(result_rgb)
            result_pil.save(output_path)
            print(f"已保存: {output_path}")

    print("处理完成!")
    if is_saved:
        print(f"结果保存在：{output_folder}")
    else:
        print(f"结果未保存!")


if __name__ == "__main__":
    # input_folder = "input_images"
    # output_folder = "output_images"

    input_folder = r"F:\学习\github相关\研究生\科研论文中多张图片局部区域批量放大\示例图像\ROI_zoom2\输入"
    output_folder = r"F:\学习\github相关\研究生\科研论文中多张图片局部区域批量放大\示例图像\ROI_zoom2\输出"

    num_rois = 3  # 需要选择的ROI数量
    is_saved = False

    # 颜色盘
    colormap = [
        (255, 255, 0), (0, 255, 0), (0, 0, 255),
        (255, 0, 0), (255, 0, 255)
    ]

    image_paths = [os.path.join(input_folder, name) for name in os.listdir(input_folder)]
    image_paths = [path for path in image_paths if os.path.isfile(path)]

    if not image_paths:
        print(f"在 {input_folder} 中未找到图像")
        exit()
    print(f"处理 {len(image_paths)} 张图像...")

    first_image = image_paths[0]
    editor = EnhancedROIEditor(num_rois, colors=colormap)

    print("-" * 20)
    print("在第一张图像上选择ROI区域并设置放大位置")
    print("-" * 20)
    original_rois, zoom_rois, position_codes = editor.run(first_image)

    if not original_rois:
        print("未完成ROI区域选择和放大任务，退出程序！")
        exit()

    # preview_img = cv2.imread(first_image)

    pil_img = Image.open(first_image)
    if pil_img.mode == 'RGBA':
        pil_img = pil_img.convert('RGB')
    preview_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    preview_result = apply_rois_to_image(preview_img, original_rois, zoom_rois, position_codes, colormap=colormap)

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
    process_folder(image_paths, output_folder, original_rois, zoom_rois, position_codes, is_saved=is_saved, colormap=colormap)

