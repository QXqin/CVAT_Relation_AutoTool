import tkinter as tk
import ttkbootstrap as tb
from PIL import Image, ImageDraw, ImageFont, ImageTk
import os
import xml.etree.ElementTree as ET


class ImageViewer(tb.Frame):
    """图片查看器组件 - 支持显示标注"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.image_folder = None
        self.image_files = []
        self.current_frame = 0
        self.xml_root = None
        self.original_image = None
        self.display_image = None
        self.zoom_scale = 1.0
        
        # 颜色映射（根据类别分配颜色）
        self.color_map = {}
        self.default_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
            '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788'
        ]
        
        # 鼠标拖动相关
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        
        # 高亮相关
        self.hovered_box = None  # (track_id, frame)
        self.mouse_x = 0
        self.mouse_y = 0
        
        # 性能优化
        self.last_hover_check = 0  # 上次检查高亮的时间
        self.hover_check_interval = 0.1  # 检查间隔（秒）100ms，减少检查频率
        self.boxes_cache = {}  # 缓存当前帧的框信息 {frame: [(track_id, xtl, ytl, xbr, ybr, area, label), ...]}
        self.pending_hover_update = None  # 待处理的高亮更新
        
        self.create_widgets()
        
    def create_widgets(self):
        """创建控件"""
        # 工具栏
        toolbar = tb.Frame(self, bootstyle="light")
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # 左侧：导入图片按钮
        tb.Button(
            toolbar,
            text="导入图片文件夹",
            command=self.load_image_folder,
            bootstyle="primary-outline",
            width=15
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # 中间：帧导航
        nav_frame = tb.Frame(toolbar)
        nav_frame.pack(side=tk.LEFT, padx=10)
        
        tb.Button(
            nav_frame,
            text="◀ 上一帧",
            command=self.prev_frame,
            bootstyle="info-outline",
            width=10
        ).pack(side=tk.LEFT, padx=2)
        
        self.frame_label = tb.Label(
            nav_frame,
            text="帧: 0/0",
            bootstyle="inverse-light",
            padding=(10, 5)
        )
        self.frame_label.pack(side=tk.LEFT, padx=5)
        
        tb.Button(
            nav_frame,
            text="下一帧 ▶",
            command=self.next_frame,
            bootstyle="info-outline",
            width=10
        ).pack(side=tk.LEFT, padx=2)
        
        # 跳转到指定帧
        jump_frame = tb.Frame(toolbar)
        jump_frame.pack(side=tk.LEFT, padx=10)
        
        tb.Label(jump_frame, text="跳转到:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.frame_entry = tb.Entry(jump_frame, width=8, bootstyle="primary")
        self.frame_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.frame_entry.bind("<Return>", lambda e: self.jump_to_frame())
        
        tb.Button(
            jump_frame,
            text="跳转",
            command=self.jump_to_frame,
            bootstyle="success-outline",
            width=6
        ).pack(side=tk.LEFT)
        
        # 右侧：显示选项
        options_frame = tb.Frame(toolbar)
        options_frame.pack(side=tk.RIGHT, padx=10)
        
        self.show_boxes_var = tk.BooleanVar(value=True)
        tb.Checkbutton(
            options_frame,
            text="显示边界框",
            variable=self.show_boxes_var,
            command=self.update_display,
            bootstyle="primary-round-toggle"
        ).pack(side=tk.LEFT, padx=5)
        
        self.show_relations_var = tk.BooleanVar(value=True)
        tb.Checkbutton(
            options_frame,
            text="显示关系点",
            variable=self.show_relations_var,
            command=self.update_display,
            bootstyle="success-round-toggle"
        ).pack(side=tk.LEFT, padx=5)
        
        self.show_labels_var = tk.BooleanVar(value=True)
        tb.Checkbutton(
            options_frame,
            text="显示标签",
            variable=self.show_labels_var,
            command=self.update_display,
            bootstyle="info-round-toggle"
        ).pack(side=tk.LEFT, padx=5)
        
        # 缩放控制
        zoom_frame = tb.Frame(toolbar)
        zoom_frame.pack(side=tk.RIGHT, padx=10)
        
        tb.Button(
            zoom_frame,
            text="−",
            command=self.zoom_out,
            bootstyle="secondary-outline",
            width=3
        ).pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = tb.Label(
            zoom_frame,
            text="100%",
            bootstyle="inverse-light",
            width=6
        )
        self.zoom_label.pack(side=tk.LEFT, padx=5)
        
        tb.Button(
            zoom_frame,
            text="+",
            command=self.zoom_in,
            bootstyle="secondary-outline",
            width=3
        ).pack(side=tk.LEFT, padx=2)
        
        # 画布容器（带滚动条）
        canvas_container = tb.Frame(self, bootstyle="light")
        canvas_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建Canvas
        self.canvas = tk.Canvas(
            canvas_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        
        # 滚动条
        v_scrollbar = tb.Scrollbar(
            canvas_container,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
            bootstyle="round"
        )
        h_scrollbar = tb.Scrollbar(
            canvas_container,
            orient=tk.HORIZONTAL,
            command=self.canvas.xview,
            bootstyle="round"
        )
        
        self.canvas.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        
        # 布局
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # 绑定鼠标事件
        self.bind_mouse_events()
        
        # 状态栏
        status_frame = tb.Frame(self, bootstyle="light")
        status_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.status_label = tb.Label(
            status_frame,
            text="未加载图片",
            bootstyle="inverse-secondary",
            padding=(10, 5)
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 统计信息
        self.stats_label = tb.Label(
            status_frame,
            text="",
            bootstyle="inverse-info",
            padding=(10, 5)
        )
        self.stats_label.pack(side=tk.RIGHT, padx=(10, 0))
        
    def load_image_folder(self):
        """加载图片文件夹"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if not folder:
            return
            
        self.image_folder = folder
        
        # 获取所有图片文件（支持常见格式）
        extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
        self.image_files = sorted([
            f for f in os.listdir(folder)
            if f.lower().endswith(extensions)
        ])
        
        if not self.image_files:
            from tkinter import messagebox
            messagebox.showwarning("警告", "该文件夹中没有找到图片文件")
            return
        
        self.current_frame = 0
        self.zoom_scale = 1.0
        self.load_current_frame()
        self.status_label.config(
            text=f"已加载 {len(self.image_files)} 张图片"
        )
        
    def load_xml(self, xml_path):
        """加载XML标注文件"""
        try:
            tree = ET.parse(xml_path)
            self.xml_root = tree.getroot()
            
            # 重新生成颜色映射
            self.generate_color_map()
            
            self.update_display()
        except Exception as e:
            print(f"加载XML失败: {e}")
            
    def generate_color_map(self):
        """为不同类别生成颜色映射"""
        if not self.xml_root:
            return
            
        labels = set()
        for track in self.xml_root.findall('track'):
            label = track.get('label')
            if label and label != 'Relation':
                labels.add(label)
        
        # 分配颜色
        for i, label in enumerate(sorted(labels)):
            self.color_map[label] = self.default_colors[i % len(self.default_colors)]
            
    def load_current_frame(self):
        """加载当前帧的图片"""
        if not self.image_files or self.current_frame >= len(self.image_files):
            return
            
        image_path = os.path.join(
            self.image_folder,
            self.image_files[self.current_frame]
        )
        
        try:
            self.original_image = Image.open(image_path)
            
            # 清空高亮状态
            self.hovered_box = None
            
            # 清空缓存（切换帧时）
            # 只保留当前帧和相邻帧的缓存以节省内存
            frames_to_keep = {
                self.current_frame - 1,
                self.current_frame,
                self.current_frame + 1
            }
            self.boxes_cache = {
                k: v for k, v in self.boxes_cache.items()
                if k in frames_to_keep
            }
            
            self.update_display()
            self.update_frame_label()
        except Exception as e:
            print(f"加载图片失败: {e}")
            
    def update_display(self):
        """更新显示（绘制标注）"""
        if not self.original_image:
            return
            
        # 创建图片副本用于绘制
        img = self.original_image.copy()
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # 尝试加载字体
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = font
        
        # 统计信息
        box_count = 0
        relation_count = 0
        
        if self.xml_root:
            # 绘制边界框
            if self.show_boxes_var.get():
                box_count = self.draw_boxes(draw, font)
            
            # 绘制关系点
            if self.show_relations_var.get():
                relation_count = self.draw_relations(draw, small_font)
        
        # 应用缩放
        if self.zoom_scale != 1.0:
            new_size = (
                int(img.width * self.zoom_scale),
                int(img.height * self.zoom_scale)
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 转换为PhotoImage
        self.display_image = ImageTk.PhotoImage(img)
        
        # 更新Canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.display_image)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        
        # 更新统计信息
        self.stats_label.config(
            text=f"边界框: {box_count} | 关系点: {relation_count}"
        )
        
    def draw_boxes(self, draw, font):
        """绘制边界框"""
        count = 0
        
        for track in self.xml_root.findall('track'):
            label = track.get('label')
            if label == 'Relation':
                continue
                
            track_id = track.get('id')
            color = self.color_map.get(label, '#FFFFFF')
            
            # 检查是否是高亮框
            is_hovered = (track_id == self.hovered_box)
            
            # 查找当前帧的box
            for box in track.findall('box'):
                frame = int(box.get('frame'))
                if frame != self.current_frame:
                    continue
                    
                outside = box.get('outside', '0')
                if outside == '1':
                    continue
                
                # 获取坐标
                xtl = float(box.get('xtl'))
                ytl = float(box.get('ytl'))
                xbr = float(box.get('xbr'))
                ybr = float(box.get('ybr'))
                
                # 根据是否高亮调整样式
                if is_hovered:
                    # 高亮：更粗的边框，更明显的填充
                    line_width = 5
                    fill_alpha = '40'  # 更明显的填充
                else:
                    # 普通：正常边框，淡填充
                    line_width = 3
                    fill_alpha = '20'
                
                # 绘制矩形边框
                draw.rectangle(
                    [(xtl, ytl), (xbr, ybr)],
                    outline=color,
                    width=line_width
                )
                
                # 绘制半透明填充
                draw.rectangle(
                    [(xtl, ytl), (xbr, ybr)],
                    fill=color + fill_alpha
                )
                
                # 绘制标签（新样式：无背景，带描边）
                if self.show_labels_var.get():
                    text = f"{label} #{int(track_id)+1}"
                    
                    # 标签位置
                    text_x = xtl + 5
                    text_y = ytl + 5
                    
                    # 优化的描边绘制：只绘制8个方向而不是25次
                    # 这样可以大幅提升性能
                    outline_offsets = [
                        (-1, -1), (0, -1), (1, -1),
                        (-1, 0),           (1, 0),
                        (-1, 1),  (0, 1),  (1, 1)
                    ]
                    
                    for dx, dy in outline_offsets:
                        draw.text(
                            (text_x + dx, text_y + dy),
                            text,
                            fill='white',
                            font=font
                        )
                    
                    # 绘制文字主体（使用边框颜色）
                    draw.text(
                        (text_x, text_y),
                        text,
                        fill=color,
                        font=font
                    )
                
                count += 1
                break
        
        return count
    
    def draw_relations(self, draw, font):
        """绘制关系点"""
        count = 0
        
        for track in self.xml_root.findall('track'):
            if track.get('label') != 'Relation':
                continue
            
            # 查找当前帧的点
            for points in track.findall('points'):
                frame = int(points.get('frame'))
                if frame != self.current_frame:
                    continue
                    
                outside = points.get('outside', '0')
                if outside == '1':
                    continue
                
                # 获取点坐标
                points_str = points.get('points')
                if not points_str or points_str == "0.00,0.00":
                    continue
                
                try:
                    x, y = map(float, points_str.split(','))
                except:
                    continue
                
                # 获取关系属性
                predicate = ""
                subject_id = ""
                object_id = ""
                
                for attr in points.findall('attribute'):
                    name = attr.get('name')
                    if name == 'predicate':
                        predicate = attr.text or ""
                    elif name == 'subject_id':
                        subject_id = attr.text or ""
                    elif name == 'object_id':
                        object_id = attr.text or ""
                
                # 绘制关系点（圆形）
                radius = 8
                draw.ellipse(
                    [(x-radius, y-radius), (x+radius, y+radius)],
                    fill='#FF6B6B',
                    outline='white',
                    width=2
                )
                
                # 绘制关系信息
                if self.show_labels_var.get():
                    try:
                        text = f"#{int(subject_id)+1} {predicate} #{int(object_id)+1}"
                    except:
                        text = predicate
                    
                    # 背景
                    bbox = draw.textbbox((x + 15, y - 10), text, font=font)
                    draw.rectangle(
                        [bbox[0]-3, bbox[1]-2, bbox[2]+3, bbox[3]+2],
                        fill='#FF6B6B',
                        outline='white',
                        width=1
                    )
                    
                    # 文字
                    draw.text(
                        (x + 15, y - 10),
                        text,
                        fill='white',
                        font=font
                    )
                
                count += 1
                break
        
        return count
    
    def prev_frame(self):
        """上一帧"""
        if self.current_frame > 0:
            self.current_frame -= 1
            self.load_current_frame()
            
    def next_frame(self):
        """下一帧"""
        if self.current_frame < len(self.image_files) - 1:
            self.current_frame += 1
            self.load_current_frame()
            
    def jump_to_frame(self):
        """跳转到指定帧"""
        try:
            frame = int(self.frame_entry.get())
            if 0 <= frame < len(self.image_files):
                self.current_frame = frame
                self.load_current_frame()
            else:
                from tkinter import messagebox
                messagebox.showwarning(
                    "警告",
                    f"帧号必须在 0 到 {len(self.image_files)-1} 之间"
                )
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("错误", "请输入有效的帧号")
            
    def update_frame_label(self):
        """更新帧标签"""
        total = len(self.image_files)
        self.frame_label.config(text=f"帧: {self.current_frame}/{total-1}")
        self.frame_entry.delete(0, tk.END)
        self.frame_entry.insert(0, str(self.current_frame))
        
    def zoom_in(self):
        """放大"""
        if self.zoom_scale < 3.0:
            self.zoom_scale += 0.05  # 改为5%步进
            self.zoom_label.config(text=f"{int(self.zoom_scale*100)}%")
            self.update_display()
            
    def zoom_out(self):
        """缩小"""
        if self.zoom_scale > 0.3:
            self.zoom_scale -= 0.05  # 改为5%步进
            self.zoom_label.config(text=f"{int(self.zoom_scale*100)}%")
            self.update_display()
    
    def bind_mouse_events(self):
        """绑定鼠标事件"""
        # 滚轮缩放
        # Windows和macOS
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        # Linux
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        
        # 鼠标拖动
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        
        # 鼠标移动（用于高亮）
        self.canvas.bind("<Motion>", self.on_mouse_move)
        
        # 鼠标进入/离开（改变光标样式）
        self.canvas.bind("<Enter>", self.on_canvas_enter)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
    
    def on_mouse_wheel(self, event):
        """鼠标滚轮事件 - 缩放"""
        if not self.original_image:
            return
        
        # 缩放时取消待处理的高亮更新，避免性能问题
        if self.pending_hover_update:
            self.after_cancel(self.pending_hover_update)
            self.pending_hover_update = None
        
        # 获取鼠标在canvas上的位置
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 保存缩放前的滚动位置比例
        x_ratio = x / (self.canvas.winfo_width() * self.zoom_scale) if self.zoom_scale > 0 else 0
        y_ratio = y / (self.canvas.winfo_height() * self.zoom_scale) if self.zoom_scale > 0 else 0
        
        # 确定缩放方向
        if event.num == 5 or event.delta < 0:  # 向下滚动 - 缩小
            if self.zoom_scale > 0.3:
                old_scale = self.zoom_scale
                self.zoom_scale -= 0.05  # 改为5%步进
                self.zoom_scale = max(0.3, self.zoom_scale)
        else:  # 向上滚动 - 放大
            if self.zoom_scale < 3.0:
                old_scale = self.zoom_scale
                self.zoom_scale += 0.05  # 改为5%步进
                self.zoom_scale = min(3.0, self.zoom_scale)
        
        # 更新显示
        self.zoom_label.config(text=f"{int(self.zoom_scale*100)}%")
        self.update_display()
        
        # 调整滚动位置，使缩放中心接近鼠标位置
        self.canvas.update_idletasks()
        if hasattr(self, 'display_image') and self.display_image:
            new_x = x_ratio * (self.canvas.winfo_width() * self.zoom_scale)
            new_y = y_ratio * (self.canvas.winfo_height() * self.zoom_scale)
            
            # 计算新的滚动位置
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            scroll_x = (new_x - event.x) / (self.display_image.width())
            scroll_y = (new_y - event.y) / (self.display_image.height())
            
            if self.display_image.width() > canvas_width:
                self.canvas.xview_moveto(max(0, min(1, scroll_x)))
            if self.display_image.height() > canvas_height:
                self.canvas.yview_moveto(max(0, min(1, scroll_y)))
    
    def on_drag_start(self, event):
        """开始拖动"""
        if not self.original_image:
            return
        
        self.is_dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        
        # 拖动时取消待处理的高亮更新
        if self.pending_hover_update:
            self.after_cancel(self.pending_hover_update)
            self.pending_hover_update = None
        
        # 改变鼠标样式为抓手
        self.canvas.config(cursor="fleur")
    
    def on_drag_motion(self, event):
        """拖动中"""
        if not self.is_dragging or not self.original_image:
            return
        
        # 计算移动距离
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        
        # 更新起始位置
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        
        # 移动canvas视图
        if hasattr(self, 'display_image') and self.display_image:
            # 获取当前滚动位置
            x_view = self.canvas.xview()
            y_view = self.canvas.yview()
            
            # 计算图片和canvas的尺寸
            img_width = self.display_image.width()
            img_height = self.display_image.height()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # 只有在图片大于canvas时才允许滚动
            if img_width > canvas_width:
                # 计算新的x滚动位置
                scroll_fraction_x = -dx / img_width
                new_x = x_view[0] + scroll_fraction_x
                new_x = max(0, min(1 - (canvas_width / img_width), new_x))
                self.canvas.xview_moveto(new_x)
            
            if img_height > canvas_height:
                # 计算新的y滚动位置
                scroll_fraction_y = -dy / img_height
                new_y = y_view[0] + scroll_fraction_y
                new_y = max(0, min(1 - (canvas_height / img_height), new_y))
                self.canvas.yview_moveto(new_y)
    
    def on_drag_end(self, event):
        """结束拖动"""
        self.is_dragging = False
        # 恢复鼠标样式
        self.canvas.config(cursor="")
        # 延迟触发高亮检查，避免立即重绘
        self.after(100, lambda: self._do_hover_check(event.x, event.y))
    
    def on_canvas_enter(self, event):
        """鼠标进入canvas"""
        if self.original_image:
            self.canvas.config(cursor="hand2")
    
    def on_canvas_leave(self, event):
        """鼠标离开canvas"""
        if not self.is_dragging:
            self.canvas.config(cursor="")
        # 清除高亮
        if self.hovered_box:
            self.hovered_box = None
            self.update_display()
    
    def on_mouse_move(self, event):
        """鼠标移动事件 - 用于高亮（优化版）"""
        if self.is_dragging or not self.original_image:
            return
        
        # 防抖：限制检查频率
        import time
        current_time = time.time()
        if current_time - self.last_hover_check < self.hover_check_interval:
            # 取消之前的待处理更新
            if self.pending_hover_update:
                self.after_cancel(self.pending_hover_update)
            # 安排延迟更新
            self.pending_hover_update = self.after(
                int(self.hover_check_interval * 1000),
                lambda: self._do_hover_check(event.x, event.y)
            )
            return
        
        self.last_hover_check = current_time
        self._do_hover_check(event.x, event.y)
    
    def _do_hover_check(self, x, y):
        """实际执行高亮检查"""
        if not self.original_image:
            return
        
        # 获取鼠标在原始图片上的坐标
        canvas_x = self.canvas.canvasx(x)
        canvas_y = self.canvas.canvasy(y)
        
        # 转换为原始图片坐标
        img_x = canvas_x / self.zoom_scale
        img_y = canvas_y / self.zoom_scale
        
        # 查找鼠标位置的框（使用缓存）
        new_hovered = self.find_box_at_position_cached(img_x, img_y)
        
        # 只在高亮框改变时重新绘制
        if new_hovered != self.hovered_box:
            self.hovered_box = new_hovered
            self.update_display()
    
    def find_box_at_position(self, x, y):
        """查找指定位置的最小边界框（原始版本，保留用于兼容）"""
        return self.find_box_at_position_cached(x, y)
    
    def find_box_at_position_cached(self, x, y):
        """查找指定位置的最小边界框（使用缓存优化）"""
        # 构建当前帧的缓存（如果需要）
        if self.current_frame not in self.boxes_cache:
            self._build_boxes_cache()
        
        # 从缓存中查找
        cache = self.boxes_cache.get(self.current_frame, [])
        candidates = []
        
        for track_id, xtl, ytl, xbr, ybr, area, label in cache:
            # 检查点是否在框内
            if xtl <= x <= xbr and ytl <= y <= ybr:
                candidates.append((track_id, area))
        
        # 返回面积最小的框
        if candidates:
            candidates.sort(key=lambda item: item[1])
            return candidates[0][0]
        
        return None
    
    def _build_boxes_cache(self):
        """构建当前帧的框缓存"""
        if not self.xml_root:
            return
        
        cache = []
        
        for track in self.xml_root.findall('track'):
            label = track.get('label')
            if label == 'Relation':
                continue
            
            track_id = track.get('id')
            
            # 查找当前帧的box
            for box in track.findall('box'):
                frame = int(box.get('frame'))
                if frame != self.current_frame:
                    continue
                
                outside = box.get('outside', '0')
                if outside == '1':
                    continue
                
                # 获取坐标
                xtl = float(box.get('xtl'))
                ytl = float(box.get('ytl'))
                xbr = float(box.get('xbr'))
                ybr = float(box.get('ybr'))
                
                # 计算面积
                area = (xbr - xtl) * (ybr - ytl)
                
                cache.append((track_id, xtl, ytl, xbr, ybr, area, label))
                break
        
        # 存储到缓存
        self.boxes_cache[self.current_frame] = cache
