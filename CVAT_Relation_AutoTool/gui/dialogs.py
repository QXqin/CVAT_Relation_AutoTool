import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import pandas as pd
from config import DEFAULT_CONFIG
import glob
import re
import os
from PIL import Image, ImageDraw, ImageFont,ImageTk
import numpy as np

class ConfigDialog(tb.Toplevel):
    """配置对话框 - 使用ttkbootstrap美化"""

    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("修改配置")
        self.geometry("500x400")
        self.config = config
        self.result_config = config.copy()

        # 设置样式 - 直接使用全局样式对象
        #self.style = parent.style  # 使用父窗口的样式

        self.create_widgets()

class CustomRelationDialog(tb.Toplevel):
    """自定义关系点对话框 - 改进版 - 使用ttkbootstrap美化"""

    def __init__(self, parent, input_file, root_et, entity_classes, predicates, category_to_trackids, custom_relations,relations_to_delete,relations_to_delete_details,parent_app):
        super().__init__(parent)

        self.parent = parent
        self.input_file = input_file
        self.root_et = root_et
        self.entity_classes = entity_classes
        self.predicates = predicates
        self.category_to_trackids = category_to_trackids
        self.custom_relations = custom_relations
        self.title("自定义关系点模式")
        self.geometry("1000x650")  # 增加宽度以容纳更多列
        self.relations_to_delete = relations_to_delete  # 主窗口的删除列表引用
        self.relations_to_delete_details = relations_to_delete_details  # 主窗口的删除详情列表引用
        self.parent_app = parent_app  # 保存对主应用程序的引用
        # 构建ID到类别的映射字典（双向映射）
        self.id_to_category = {}
        self.display_id_to_raw = {}  # 显示ID到原始ID的映射
        self.all_track_ids = []  # 存储所有主体的track_id（显示ID）
        self.temp_deletion_details = []  # 存储本次会话中删除的关系点（用于传递给主程序）
        # 使用临时变量存储修改，而不是直接修改主窗口的引用
        self.temp_custom_relations = custom_relations.copy()  # 使用副本而不是引用
        self.temp_relations_to_delete = relations_to_delete[:]  # 使用副本
        self.temp_relations_to_delete_details = relations_to_delete_details[:]  # 使用副本
        self.temp_relations = []  # 临时存储本次添加的关系
        # 添加多选状态变量
        self.context_menu_selection = []  # 用于存储右键菜单触发时的选中项
        # 收集所有track_id（除relation之外的所有id）
        for category, track_ids in category_to_trackids.items():
            for track_id in track_ids:
                self.id_to_category[track_id] = category
                try:
                    # 安全地将track_id转换为整数，然后加1
                    display_id = str(int(track_id) + 1)
                    self.display_id_to_raw[display_id] = track_id
                    self.all_track_ids.append(display_id)
                except ValueError:
                    # 如果track_id不是有效的整数，跳过
                    continue
        self.copied_relations = []  # 存储复制的客体和谓词
        self.history = []  # 存储操作历史用于撤销
        self.current_state = []  # 存储当前状态
        # 按数字顺序排序track_ids
        self.all_track_ids.sort(key=lambda x: int(x))
        self.filtered_predicates = predicates[:]  # 谓词过滤缓存
        self.current_subject = None  # 当前选中的主体ID（显示ID）
        # 初始化关系计数字典
        self.subject_relation_counts = {}
        # 解析XML中已有的关系点
        self.parse_existing_relations()
        # 初始化本次添加的关系点列表
        self.new_relations = []  # 专门存储本次添加的关系点
        self.parent_app = parent_app  # 保存对主应用程序的引用
        self.current_annotated_image = None  # 带标注的图像
        self.create_widgets()
        # 从临时自定义关系中加载
        self.load_temp_custom_relations()

    def load_temp_custom_relations(self):
        """从临时自定义关系加载"""
        for raw_subj_id, relations in self.temp_custom_relations.items():
            try:
                display_subj_id = str(int(raw_subj_id) + 1)
                subj_class = self.id_to_category.get(raw_subj_id, "未知")

                for (raw_obj_id, pred) in relations:
                    try:
                        display_obj_id = str(int(raw_obj_id) + 1)
                        obj_class = self.id_to_category.get(raw_obj_id, "未知")

                        self.temp_relations.append((
                            display_subj_id,
                            subj_class,
                            display_obj_id,
                            obj_class,
                            pred
                        ))
                    except ValueError:
                        continue
            except ValueError:
                continue

    def load_current_custom_relations(self):
        """从主应用加载当前自定义关系"""
        for raw_subj_id, relations in self.custom_relations.items():
            # 获取显示ID
            try:
                display_subj_id = str(int(raw_subj_id) + 1)
            except ValueError:
                continue

            # 获取主体类别
            subj_class = self.id_to_category.get(raw_subj_id, "未知")

            for (raw_obj_id, pred) in relations:
                # 获取客体显示ID
                try:
                    display_obj_id = str(int(raw_obj_id) + 1)
                except ValueError:
                    continue

                # 获取客体类别
                obj_class = self.id_to_category.get(raw_obj_id, "未知")

                # 添加到临时关系列表
                self.temp_relations.append((
                    display_subj_id,
                    subj_class,
                    display_obj_id,
                    obj_class,
                    pred
                ))

    def parse_existing_relations(self):
        """解析XML中已有的关系点（不包括上次的自定义关系）"""
        # 遍历所有关系轨迹
        for track in self.root_et.findall('track'):
            if track.get('label') == "Relation":
                # 提取关系轨迹中的第一个点（获取关系信息）
                for points in track.findall('points'):
                    # 跳过消亡帧
                    if points.get('outside') == '1':
                        continue

                    predicate_attr = None
                    subject_id_attr = None
                    object_id_attr = None

                    # 提取属性值
                    for attr in points.findall('attribute'):
                        name = attr.get('name')
                        if name == 'predicate':
                            predicate_attr = attr.text
                        elif name == 'subject_id':
                            subject_id_attr = attr.text
                        elif name == 'object_id':
                            object_id_attr = attr.text

                    # 确保所有属性都存在
                    if subject_id_attr and predicate_attr:
                        # 获取显示ID
                        try:
                            display_subj_id = str(int(subject_id_attr) + 1)
                            # 处理空对象ID的情况
                            if object_id_attr and object_id_attr.strip():
                                display_obj_id = str(int(object_id_attr) + 1)
                            else:
                                display_obj_id = ""  # 保持为空字符串
                        except ValueError:
                            continue

                        # 获取主体类别
                        subj_class = self.id_to_category.get(subject_id_attr, "未知")
                        # 获取客体类别（如果有）
                        obj_class = "未知"
                        if object_id_attr and object_id_attr.strip():
                            obj_class = self.id_to_category.get(object_id_attr, "未知")
                        else:
                            obj_class = "未知"  # 特殊标记表示客体为空

                        # 添加到临时关系列表
                        self.temp_relations.append((
                            display_subj_id,
                            subj_class,
                            display_obj_id,
                            obj_class,
                            predicate_attr
                        ))
                        break  # 只需一个点就能获取关系信息

    def convert_existing_relations(self):
        """将已有的自定义关系转换为临时关系格式"""
        for raw_subj_id, relations in self.custom_relations.items():
            # 获取显示ID
            display_subj_id = str(int(raw_subj_id) + 1)
            # 获取主体类别
            subj_class = self.id_to_category.get(raw_subj_id, "未知")

            for (raw_obj_id, pred) in relations:
                # 获取客体显示ID
                display_obj_id = str(int(raw_obj_id) + 1)
                # 获取客体类别
                obj_class = self.id_to_category.get(raw_obj_id, "未知")

                # 添加到临时关系列表
                self.temp_relations.append((
                    display_subj_id,
                    subj_class,
                    display_obj_id,
                    obj_class,
                    pred
                ))

    def create_widgets(self):
        main_frame = tb.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 使用垂直分栏容器确保底部按钮始终可见
        container = tb.PanedWindow(main_frame, orient=tk.VERTICAL, bootstyle="light")
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 内容区域（可滚动）
        content_frame = tb.Frame(container)
        container.add(content_frame, weight=3)

        # 标题
        tb.Label(
            content_frame,
            text="添加自定义关系点",
            font=("微软雅黑", 14, "bold"),
            bootstyle="primary"
        ).pack(pady=(0, 10))

        # 使用PanedWindow分割图片浏览区域、主体列表和关系管理区域
        paned = tb.PanedWindow(content_frame, bootstyle="light", orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加图片浏览区域 (左侧)
        image_frame = tb.Frame(paned, width=300, padding=5)
        paned.add(image_frame, weight=7)  # 权重较小

        # 图片浏览区域的控件
        tb.Label(
            image_frame,
            text="图片浏览",
            font=("微软雅黑", 10, "bold"),
            bootstyle="inverse-light"
        ).pack(fill=tk.X, pady=(0, 5))

        # 创建顶部工具栏容器
        toolbar_frame = tb.Frame(image_frame)
        toolbar_frame.pack(fill=tk.X, pady=5)

        # 左侧：图片文件夹选择按钮
        tb.Button(
            toolbar_frame,
            text="选择图片文件夹",
            command=self.select_image_folder,
            bootstyle="primary",
            width=15
        ).pack(side=tk.LEFT, padx=(0, 10))

        # 中间：图片导航按钮
        nav_frame = tb.Frame(toolbar_frame)
        nav_frame.pack(side=tk.LEFT, padx=(0, 10))
        tb.Button(
            nav_frame,
            text="◀",  # 使用符号代替文字以节省空间
            command=self.prev_image,
            bootstyle="secondary",
            width=3
        ).pack(side=tk.LEFT, padx=(0, 2))
        tb.Button(
            nav_frame,
            text="▶",  # 使用符号代替文字以节省空间
            command=self.next_image,
            bootstyle="secondary",
            width=3
        ).pack(side=tk.LEFT)

        # 图片计数器标签
        self.image_counter = tb.Label(
            toolbar_frame,
            text="0/0",
            bootstyle="inverse-light",
            width=6
        )
        self.image_counter.pack(side=tk.LEFT, padx=(0, 10))

        # 右侧：缩放控件
        zoom_frame = tb.Frame(toolbar_frame)
        zoom_frame.pack(side=tk.LEFT)
        tb.Label(zoom_frame, text="缩放:").pack(side=tk.LEFT)
        self.scale_var = tk.StringVar(value="100%")
        zoom_combo = tb.Combobox(
            zoom_frame,
            textvariable=self.scale_var,
            values=["25%", "50%", "75%", "100%", "150%", "200%"],
            width=7,  # 减小宽度
            bootstyle="primary"
        )
        zoom_combo.pack(side=tk.LEFT, padx=(5, 0))
        zoom_combo.bind("<<ComboboxSelected>>", self.update_image_scale)

        # 图片显示区域
        self.image_container = tb.Frame(image_frame)
        self.image_container.pack(fill=tk.BOTH, expand=True, pady=5)

        # 创建Canvas用于显示图片
        self.canvas = tk.Canvas(self.image_container, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 添加滚动条
        self.v_scroll = tb.Scrollbar(
            self.image_container,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
            bootstyle="round"
        )
        self.h_scroll = tb.Scrollbar(
            self.image_container,
            orient=tk.HORIZONTAL,
            command=self.canvas.xview,
            bootstyle="round"
        )
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        # 网格布局
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        # 配置权重
        self.image_container.grid_rowconfigure(0, weight=1)
        self.image_container.grid_columnconfigure(0, weight=1)

        # 绑定鼠标滚轮缩放
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mousewheel)  # Linux
        self.canvas.bind("<Button-5>", self.on_mousewheel)  # Linux

        # 初始变量
        self.image_folder = None
        self.image_files = []
        self.current_image_index = -1
        self.current_image = None
        self.image_tk = None
        self.scale_factor = 1.0
        self.canvas_image = None

        # 主体列表和关系管理区域容器 (占30%)
        right_container = tb.PanedWindow(paned, orient=tk.VERTICAL, bootstyle="light")
        paned.add(right_container, weight=3)  # 权重3表示30%
        # 主体列表区域 (占30%中的40%)
        left_frame = tb.Frame(right_container, padding=5)
        right_container.add(left_frame, weight=2)  # 权重2表示40%
        # 关系管理区域 (占30%中的60%)
        right_frame = tb.Frame(right_container, padding=5)
        right_container.add(right_frame, weight=3)  # 权重3表示60%

        tb.Label(
            left_frame,
            text="主体列表 (选择主体进行关系管理)",
            font=("微软雅黑", 10, "bold"),
            bootstyle="inverse-light"
        ).pack(fill=tk.X, pady=(0, 5))

        # 添加主体搜索区域
        subject_search_frame = tb.Frame(left_frame)
        subject_search_frame.pack(fill=tk.X, pady=(0, 5))

        tb.Label(
            subject_search_frame,
            text="搜索主体:",
            bootstyle="inverse-light"
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.subject_filter_var = tk.StringVar()  # 修正：使用新的变量名
        self.subject_filter_entry = tb.Entry(
            subject_search_frame,
            textvariable=self.subject_filter_var,
            width=20,
            bootstyle="primary"
        )
        self.subject_filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.subject_filter_entry.bind("<KeyRelease>", self.filter_subjects)
        self.subject_filter_entry.bind("<Return>", self.filter_subjects)  # 添加回车键绑定

        # 主体列表（Treeview）
        subject_tree_frame = tb.Frame(left_frame)
        subject_tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "category")
        self.subject_tree = tb.Treeview(
            subject_tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            bootstyle="light",
            height=8
        )
        self.subject_tree.heading("id", text="ID", anchor=tk.CENTER)
        self.subject_tree.heading("category", text="类别", anchor=tk.W)
        self.subject_tree.column("id", width=70, anchor=tk.CENTER)
        self.subject_tree.column("category", width=150, anchor=tk.W)

        vsb = tb.Scrollbar(
            subject_tree_frame,
            orient=tk.VERTICAL,
            command=self.subject_tree.yview,
            bootstyle="round"
        )
        self.subject_tree.configure(yscrollcommand=vsb.set)

        # 使用grid布局
        self.subject_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # 配置网格权重
        subject_tree_frame.grid_rowconfigure(0, weight=1)
        subject_tree_frame.grid_columnconfigure(0, weight=1)

        # 存储所有主体数据用于筛选
        self.all_subjects = []

        # 初始化关系计数（如果尚未初始化）
        if not hasattr(self, 'subject_relation_counts'):
            self.subject_relation_counts = {}

        # 统计每个主体的关系数量
        for display_id in self.all_track_ids:
            raw_id = str(int(display_id) - 1)
            category = self.id_to_category.get(raw_id, "未知")
            self.all_subjects.append((display_id, category))

            # 统计该主体的关系数量
            count = sum(1 for rel in self.temp_relations if rel[0] == display_id)
            self.subject_relation_counts[display_id] = count

        # 初始填充主体列表
        self.filter_subjects()

        # 绑定选择事件
        self.subject_tree.bind("<<TreeviewSelect>>", self.on_subject_selected)

        # 右侧：关系管理区域
        right_frame = tb.Frame(paned, padding=5)
        paned.add(right_frame)

        # 当前主体信息
        self.subject_info_frame = tb.Labelframe(
            right_frame,
            text="当前主体",
            bootstyle="info"
        )
        self.subject_info_frame.pack(fill=tk.X, pady=(0, 5))

        # 添加主体搜索区域
        subject_search_frame = tb.Frame(self.subject_info_frame)
        subject_search_frame.pack(fill=tk.X, padx=5, pady=5)

        tb.Label(
            subject_search_frame,
            text="主体ID:",
            bootstyle="inverse-light"
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.subject_search_var = tk.StringVar()
        self.subject_search_combo = tb.Combobox(
            subject_search_frame,
            textvariable=self.subject_search_var,
            values=self.all_track_ids,
            bootstyle="primary"
        )
        self.subject_search_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.subject_search_combo.bind("<KeyRelease>", self.on_subject_search_keyrelease)
        self.subject_search_combo.bind("<<ComboboxSelected>>", self.on_subject_search_selected)
        self.subject_search_combo.bind("<Return>", self.on_subject_search_selected)

        # 查找按钮
        tb.Button(
            subject_search_frame,
            text="查找",
            command=self.on_subject_search_selected,
            bootstyle="primary",
            width=8
        ).pack(side=tk.LEFT, padx=5)

        # 主体信息标签
        self.subject_info_label = tb.Label(
            self.subject_info_frame,
            text="未选择主体",
            font=("微软雅黑", 9),
            bootstyle="light"
        )
        self.subject_info_label.pack(padx=5, pady=(0, 3))

        # 添加新关系区域
        add_relation_frame = tb.Labelframe(
            right_frame,
            text="添加新关系",
            bootstyle="success",
            padding = (5, 3)  # 减小内边距
        )
        add_relation_frame.pack(fill=tk.X, pady=5)

        # 客体选择
        object_frame = tb.Frame(add_relation_frame)
        object_frame.pack(fill=tk.X, padx=5, pady=5)

        tb.Label(
            object_frame,
            text="客体ID:",
            bootstyle="inverse-light"
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.object_id_var = tk.StringVar()
        self.object_id_combo = tb.Combobox(
            object_frame,
            textvariable=self.object_id_var,
            values=self.all_track_ids,
            bootstyle="primary"
        )
        self.object_id_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.object_id_combo.bind("<KeyRelease>", self.on_combobox_keyrelease)
        self.object_id_combo.bind("<<ComboboxSelected>>", self.on_object_selected)

        # 客体类别显示
        self.object_class_label = tb.Label(
            object_frame,
            text="类别: 未知",
            bootstyle="dark"
        )
        self.object_class_label.pack(side=tk.LEFT, padx=10)

        # 谓词选择
        pred_frame = tb.Frame(add_relation_frame)
        pred_frame.pack(fill=tk.X, padx=5, pady=5)

        tb.Label(
            pred_frame,
            text="谓词:",
            bootstyle="inverse-light"
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.pred_var = tk.StringVar()
        self.pred_combo = tb.Combobox(
            pred_frame,
            textvariable=self.pred_var,
            values=self.predicates,
            bootstyle="primary"
        )
        self.pred_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.pred_combo.bind("<KeyRelease>", self.on_combobox_keyrelease)
        self.pred_combo.bind("<<ComboboxSelected>>", self.on_combobox_selected)

        # 添加到列表按钮
        add_btn_frame = tb.Frame(add_relation_frame)
        add_btn_frame.pack(fill=tk.X, pady=5)

        tb.Button(
            add_btn_frame,
            text="添加关系",
            command=self.on_add,
            bootstyle="success",
            padding=(3, 1)  # 减小内边距
        ).pack(pady=3)  # 减小外边距

        # 当前主体的关系列表
        relation_list_frame = tb.Labelframe(
            right_frame,
            text="当前主体的关系",
            bootstyle="info"
        )
        relation_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 关系列表（Treeview）
        cols = ("object_id", "object_class", "predicate")
        self.relation_tree = tb.Treeview(
            relation_list_frame,
            columns=cols,
            show="headings",
            bootstyle="light",
            height=6
        )
        self.relation_tree.heading("object_id", text="客体 ID")
        self.relation_tree.heading("object_class", text="客体类别")
        self.relation_tree.heading("predicate", text="谓词")

        # 设置列宽
        self.relation_tree.column("object_id", width=70, anchor=tk.CENTER)
        self.relation_tree.column("object_class", width=100, anchor=tk.W)
        self.relation_tree.column("predicate", width=150, anchor=tk.W)

        vsb = tb.Scrollbar(
            relation_list_frame,
            orient=tk.VERTICAL,
            command=self.relation_tree.yview,
            bootstyle="round"
        )
        hsb = tb.Scrollbar(
            relation_list_frame,
            orient=tk.HORIZONTAL,
            command=self.relation_tree.xview,
            bootstyle="round"
        )
        self.relation_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 使用grid布局
        self.relation_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # 配置网格权重
        relation_list_frame.grid_rowconfigure(0, weight=1)
        relation_list_frame.grid_columnconfigure(0, weight=1)

        # "删除选中"按钮
        del_btn_frame = tb.Frame(relation_list_frame)
        del_btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        tb.Button(
            del_btn_frame,
            text="删除选中关系",
            command=self.on_delete,
            bootstyle="danger",
            width=15
        ).pack(pady=5)

        # 底部按钮容器
        button_container = tb.Frame(container)
        container.add(button_container, weight=1)

        # "确定"和"取消"按钮（固定在底部容器）
        bottom_frame = tb.Frame(button_container)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=10)

        tb.Button(
            bottom_frame,
            text="确定",
            width=12,
            command=self.on_confirm,
            bootstyle="success"
        ).pack(side=tk.RIGHT, padx=5)

        tb.Button(
            bottom_frame,
            text="取消",
            width=12,
            command=self.on_cancel,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT, padx=5)

        # 绑定右键菜单和键盘事件
        self.subject_tree.bind("<Button-3>", self.show_context_menu)
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-Z>", self.undo)

        # 创建右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制关系", command=self.copy_relations)
        self.context_menu.add_command(label="粘贴关系", command=self.paste_relations)
        # 鼠标拖动功能变量
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.dragging = False
        self.scroll_start_x = 0
        self.scroll_start_y = 0

        # 绑定鼠标事件
        self.canvas.bind("<ButtonPress-1>", self.start_drag)  # 左键按下
        self.canvas.bind("<ButtonPress-2>", self.start_drag)  # 中键按下（Linux/macOS）
        self.canvas.bind("<ButtonPress-3>", self.start_drag)  # 右键按下（Windows）
        self.canvas.bind("<B1-Motion>", self.on_drag)  # 左键拖动
        self.canvas.bind("<B2-Motion>", self.on_drag)  # 中键拖动（Linux/macOS）
        self.canvas.bind("<B3-Motion>", self.on_drag)  # 右键拖动（Windows）
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)  # 左键释放
        self.canvas.bind("<ButtonRelease-2>", self.end_drag)  # 中键释放（Linux/macOS）
        self.canvas.bind("<ButtonRelease-3>", self.end_drag)  # 右键释放（Windows）

    # +++ 新增筛选方法 +++
    def filter_subjects(self, event=None):
        """根据搜索条件筛选主体"""
        # 获取搜索词并转换为小写
        search_term = self.subject_filter_var.get().strip().lower()

        # 清空当前显示
        for item in self.subject_tree.get_children():
            self.subject_tree.delete(item)

        # 确保关系计数字典存在
        if not hasattr(self, 'subject_relation_counts'):
            self.subject_relation_counts = {}

        # 计算最大关系数用于颜色渐变
        max_relations = max(self.subject_relation_counts.values()) if self.subject_relation_counts and len(
            self.subject_relation_counts) > 0 else 1

        # 如果没有搜索词，显示所有主体
        if not search_term:
            for display_id, category in self.all_subjects:
                # 获取关系数量
                count = self.subject_relation_counts.get(display_id, 0)

                # 计算渐变色 (从浅蓝色到深蓝色)
                ratio = count / max_relations
                r = int(230 * (1 - ratio))  # 红色分量减少
                g = int(240 * (1 - ratio))  # 绿色分量减少
                b = 255  # 蓝色保持较高
                color = f'#{r:02x}{g:02x}{b:02x}'

                # 插入行并设置背景色
                item = self.subject_tree.insert("", tk.END, values=(display_id, category))
                self.subject_tree.tag_configure(color, background=color, foreground='black')
                self.subject_tree.item(item, tags=(color,))
            return  # 直接返回，不执行后面的筛选逻辑

        # 筛选并添加匹配项
        for display_id, category in self.all_subjects:
            # 匹配ID或类别（都转换为小写比较）
            if (search_term in display_id.lower() or
                    search_term in category.lower()):
                # 获取关系数量
                count = self.subject_relation_counts.get(display_id, 0)

                # 计算渐变色 (从浅蓝色到深蓝色)
                ratio = count / max_relations
                r = int(230 * (1 - ratio))  # 红色分量减少
                g = int(240 * (1 - ratio))  # 绿色分量减少
                b = 255  # 蓝色保持较高
                color = f'#{r:02x}{g:02x}{b:02x}'

                # 插入行并设置背景色
                item = self.subject_tree.insert("", tk.END, values=(display_id, category))
                self.subject_tree.tag_configure(color, background=color, foreground='black')
                self.subject_tree.item(item, tags=(color,))

    # +++ 添加更新主体关系计数的方法 +++
    def update_relation_counts(self):
        """更新每个主体的关系计数"""
        # 重置所有计数
        for display_id in self.subject_relation_counts:
            self.subject_relation_counts[display_id] = 0

        # 重新计数
        for rel in self.temp_relations:
            subject_id = rel[0]
            if subject_id in self.subject_relation_counts:
                self.subject_relation_counts[subject_id] += 1

    def on_combobox_keyrelease(self, event):
        """统一的键盘释放事件处理"""
        combo = event.widget
        # 只处理字母数字和空格键
        if len(event.keysym) > 1 and event.keysym not in ('BackSpace', 'Delete'):
            return

        # 获取当前值
        input_text = combo.get().strip().lower()

        # 根据当前下拉框类型确定要过滤的列表
        if combo in [self.subject_search_combo, self.object_id_combo]:
            full_list = self.all_track_ids
        elif combo == self.pred_combo:
            full_list = self.predicates
        else:
            return

        # 过滤并设置下拉值
        filtered = self.get_filtered_items(input_text, full_list)
        combo['values'] = filtered

        # 重新插入光标位置
        combo.icursor(tk.END)

        # 按回车时选择第一项并关闭下拉
        if event.keysym == 'Return' and filtered:
            combo.set(filtered[0])
            if combo == self.subject_search_combo:
                self.on_subject_search_selected()
            elif combo == self.object_id_combo:
                self.on_object_selected()
            return 'break'

    def on_subject_search_keyrelease(self, event):
        """主体搜索框键盘释放事件处理"""
        # 只处理字母数字和空格键
        if len(event.keysym) > 1 and event.keysym not in ('BackSpace', 'Delete'):
            return

        # 获取当前值
        input_text = self.subject_search_var.get().strip().lower()

        # 过滤并设置下拉值
        filtered = self.get_filtered_items(input_text, self.all_track_ids)
        self.subject_search_combo['values'] = filtered

        # 重新插入光标位置
        self.subject_search_combo.icursor(tk.END)

        # 按回车时选择第一项并关闭下拉
        if event.keysym == 'Return' and filtered:
            self.subject_search_combo.set(filtered[0])
            self.on_subject_search_selected()
            return 'break'

    def on_combobox_selected(self, event):
        """统一的选择事件处理"""
        combo = event.widget

        # 处理客体ID选择
        if combo == self.object_id_combo:
            self.on_object_selected()

    def on_object_selected(self, event=None):
        """客体ID选择事件处理"""
        obj_id = self.object_id_var.get().strip()
        if not obj_id:
            self.object_class_label.config(text="类别: 未知")
            return

        try:
            # 转换为原始ID
            raw_obj_id = str(int(obj_id) - 1)
            # 获取客体类别
            obj_class = self.id_to_category.get(raw_obj_id, "未知")
            self.object_class_label.config(text=f"类别: {obj_class}")
        except ValueError:
            self.object_class_label.config(text="类别: 无效ID")

    def on_subject_search_selected(self, event=None):
        """主体搜索选择事件处理"""
        subject_id = self.subject_search_var.get().strip()
        if not subject_id:
            return

        # 在主体树中查找该ID
        items = self.subject_tree.get_children()
        found_item = None

        for item in items:
            values = self.subject_tree.item(item, "values")
            if values and values[0] == subject_id:
                found_item = item
                break

        if found_item:
            # 选中该主体
            self.subject_tree.selection_set(found_item)
            self.subject_tree.focus(found_item)
            self.subject_tree.see(found_item)
            self.on_subject_selected(None)  # 触发选择事件
        else:
            tb.dialogs.Messagebox.show_warning(f"未找到ID为 {subject_id} 的主体", "提示", parent=self)

    def get_filtered_items(self, input_text, full_list):
        """获取过滤后的项列表"""
        if not input_text:
            return full_list[:]
        return [item for item in full_list if input_text.lower() in item.lower()]

    def on_subject_selected(self, event):
        """主体选择事件处理"""
        selected = self.subject_tree.selection()
        if not selected:
            self.current_subject = None
            self.subject_info_label.config(text="未选择主体")
            # 清空关系列表
            self.relation_tree.delete(*self.relation_tree.get_children())
            return

        item = selected[0]
        values = self.subject_tree.item(item, "values")
        if values:  # 确保有值
            display_id, category = values
            self.current_subject = display_id
            self.subject_search_var.set(display_id)  # 更新搜索框
            self.subject_info_label.config(text=f"ID: {display_id}, 类别: {category}")
            self.update_relation_list()

    def update_relation_list(self):
        """更新当前主体的关系列表"""
        # 清空现有关系
        self.relation_tree.delete(*self.relation_tree.get_children())

        if not self.current_subject:
            return

        # 获取当前主体的所有关系
        subject_relations = [
            rel for rel in self.temp_relations
            if rel[0] == self.current_subject
        ]

        # 添加到关系列表
        for rel in subject_relations:
            _, _, obj_id, obj_class, predicate = rel

            # 直接添加关系，不再验证obj_id是否为有效数字
            self.relation_tree.insert("", tk.END, values=(obj_id, obj_class, predicate))

    # ====== 按钮事件处理函数 ======

    def on_add(self):
        """添加关系按钮事件"""
        # 检查是否选择了主体
        if not self.current_subject:
            tb.dialogs.Messagebox.show_error("请先选择主体", "错误", parent=self)
            return

        # 获取客体ID
        obj_id = self.object_id_var.get().strip()
        if not obj_id:
            tb.dialogs.Messagebox.show_error("请输入客体ID", "错误", parent=self)
            return

        # 验证客体ID有效性
        try:
            # 确保obj_id是有效的数字
            if not obj_id.isdigit():
                tb.dialogs.Messagebox.show_error("客体ID必须是数字", "错误", parent=self)
                return

            # 转换为原始ID
            raw_obj_id = str(int(obj_id) - 1)

            # 检查客体是否存在
            if raw_obj_id not in self.id_to_category:
                tb.dialogs.Messagebox.show_error("客体ID不存在", "错误", parent=self)
                return

        except ValueError:
            tb.dialogs.Messagebox.show_error("客体ID格式错误", "错误", parent=self)
            return

        # 获取客体类别
        obj_class = self.id_to_category.get(raw_obj_id, "未知")

        # 获取谓词
        pred = self.pred_var.get().strip()
        if not pred:
            tb.dialogs.Messagebox.show_error("请选择或输入谓词", "错误", parent=self)
            return

        # 检查是否已存在相同关系
        existing = [
            rel for rel in self.temp_relations
            if rel[0] == self.current_subject and rel[2] == obj_id and rel[4] == pred
        ]

        if existing:
            tb.dialogs.Messagebox.show_warning("该关系已存在", "提示", parent=self)
            return

        # 获取主体类别
        try:
            raw_subj_id = str(int(self.current_subject) - 1)
            subj_class = self.id_to_category.get(raw_subj_id, "未知")
        except ValueError:
            subj_class = "未知"

        # 添加到临时关系列表（用于对话框显示）
        self.temp_relations.append((
            self.current_subject,  # 主体ID（显示ID）
            subj_class,  # 主体类别
            obj_id,  # 客体ID（显示ID）
            obj_class,  # 客体类别
            pred  # 谓词
        ))
        # 同时添加到本次新添加的关系列表（用于传递给主窗口）
        self.new_relations.append((
            self.current_subject,
            subj_class,
            obj_id,
            obj_class,
            pred
        ))
        # 更新关系计数
        if self.current_subject in self.subject_relation_counts:
            self.subject_relation_counts[self.current_subject] += 1
        else:
            self.subject_relation_counts[self.current_subject] = 1
        # 更新关系列表
        self.update_relation_list()
        # 更新主体列表显示（刷新颜色）
        self.filter_subjects()

        # 清空输入控件
        self.object_id_var.set('')
        self.pred_var.set('')
        self.object_class_label.config(text="类别: 未知")

    def on_delete(self):
        """删除选中关系 - 现在删除整个关系轨迹"""
        if not self.current_subject:
            tb.dialogs.Messagebox.show_warning("请先选择主体", "提示", parent=self)
            return

        sel = self.relation_tree.selection()
        if not sel:
            tb.dialogs.Messagebox.show_warning("请先选择要删除的关系", "提示", parent=self)
            return

        # 收集要删除的关系
        to_delete = []
        for it in sel:
            values = self.relation_tree.item(it, "values")
            if len(values) >= 3:
                obj_id = values[0]
                predicate = values[2]
                to_delete.append((obj_id, predicate))

                # 添加到删除列表（使用显示ID）
                self.temp_relations_to_delete_details.append(
                    (self.current_subject, obj_id, predicate)
                )

                # 添加到删除列表（使用原始ID）
                try:
                    raw_subj_id = str(int(self.current_subject) - 1)
                    # 处理空对象ID的情况
                    raw_obj_id = str(int(obj_id) - 1) if obj_id and obj_id != "" else ""
                    self.temp_relations_to_delete.append((raw_subj_id, raw_obj_id, predicate))
                except ValueError:
                    continue

        # 从临时关系中移除
        for rel in to_delete:
            obj_id, predicate = rel
            self.temp_relations = [
                r for r in self.temp_relations
                if not (r[0] == self.current_subject and
                        r[2] == obj_id and
                        r[4] == predicate)
            ]

            # 更新关系计数
            if self.current_subject in self.subject_relation_counts:
                self.subject_relation_counts[self.current_subject] = max(0, self.subject_relation_counts[
                    self.current_subject] - 1)

        # 同时从新添加的关系中移除（如果存在）
        for rel in to_delete:
            obj_id, predicate = rel
            self.new_relations = [
                r for r in self.new_relations
                if not (r[0] == self.current_subject and
                        r[2] == obj_id and
                        r[4] == predicate)
            ]

        # 更新关系列表
        self.update_relation_list()
        # 更新主体列表显示（刷新颜色）
        self.filter_subjects()

    def on_confirm(self):
        """确认按钮事件"""
        # 将本次新添加的关系点转换为custom_relations格式
        self.convert_new_relations_to_custom()

        # 更新主窗口的数据 - 只添加本次会话的关系
        for subj_id, rel_list in self.temp_custom_relations.items():
            if subj_id not in self.parent_app.custom_relations:
                self.parent_app.custom_relations[subj_id] = []
            self.parent_app.custom_relations[subj_id].extend(rel_list)

        # 更新删除列表
        self.parent_app.relations_to_delete = self.temp_relations_to_delete
        self.parent_app.relations_to_delete_details = self.temp_relations_to_delete_details

        # 更新主窗口的显示
        self.parent_app.update_custom_relations_display()
        self.parent_app.update_deletion_list()

        # 显示提示并关闭
        tb.dialogs.Messagebox.show_info(
            "自定义关系已记录，稍后执行自动标注时会一起写入到输出文件",
            "提示",
            parent=self
        )
        self.destroy()

    def convert_new_relations_to_custom(self):
        """将本次新添加的关系列表转换为custom_relations字典格式"""
        self.temp_custom_relations = {}
        for rel in self.new_relations:
            display_subj_id, _, display_obj_id, _, predicate = rel
            try:
                # 将显示ID转换为原始ID
                raw_subj_id = str(int(display_subj_id) - 1)
                raw_obj_id = str(int(display_obj_id) - 1)

                if raw_subj_id not in self.temp_custom_relations:
                    self.temp_custom_relations[raw_subj_id] = []

                # 添加关系 (客体ID, 谓词)
                self.temp_custom_relations[raw_subj_id].append((raw_obj_id, predicate))
            except ValueError:
                continue  # 跳过无效ID

    def on_cancel(self):
        """取消按钮事件 - 同时清空临时关系列表"""
        self.temp_relations = []
        self.destroy()

    def save_config(self):
        self.result_config = {
            'auto_sync_lifecycle': self.sync_var.get(),
            'skip_existing': self.skip_var.get(),
            'auto_generate_output': self.gen_var.get(),
            'backup_original': self.backup_var.get()
        }
        with open("config.json", "w") as f:
            json.dump(self.result_config, f, indent=2)
        tb.dialogs.Messagebox.show_info("配置已保存！", "成功", parent=self)
        self.destroy()

    def convert_temp_relations_to_custom(self):
        """将临时关系列表转换为custom_relations字典格式"""
        self.temp_custom_relations = {}
        for rel in self.temp_relations:
            display_subj_id, _, display_obj_id, _, predicate = rel
            try:
                # 将显示ID转换为原始ID
                raw_subj_id = str(int(display_subj_id) - 1)
                raw_obj_id = str(int(display_obj_id) - 1)

                if raw_subj_id not in self.temp_custom_relations:
                    self.temp_custom_relations[raw_subj_id] = []

                # 添加关系 (客体ID, 谓词)
                self.temp_custom_relations[raw_subj_id].append((raw_obj_id, predicate))
            except ValueError:
                continue  # 跳过无效ID

    def convert_new_relations_to_custom(self):
        """将本次新添加的关系列表转换为custom_relations字典格式"""
        self.temp_custom_relations = {}
        for rel in self.new_relations:
            display_subj_id, _, display_obj_id, _, predicate = rel
            try:
                # 将显示ID转换为原始ID
                raw_subj_id = str(int(display_subj_id) - 1)
                raw_obj_id = str(int(display_obj_id) - 1)

                if raw_subj_id not in self.temp_custom_relations:
                    self.temp_custom_relations[raw_subj_id] = []

                # 添加关系 (客体ID, 谓词)
                self.temp_custom_relations[raw_subj_id].append((raw_obj_id, predicate))
            except ValueError:
                continue  # 跳过无效ID

    def show_context_menu(self, event):
        """显示右键菜单 - 防止多选状态丢失"""
        # 获取鼠标位置下的项目
        item = self.subject_tree.identify_row(event.y)

        # 如果点击在项目上，确保它被包含在选中项中
        if item:
            # 获取当前所有选中项
            current_selection = set(self.subject_tree.selection())

            # 如果点击的项目不在当前选中项中
            if item not in current_selection:
                # 清除所有选中项，只选中当前点击的项目
                self.subject_tree.selection_set(item)
                self.context_menu_selection = [item]
            else:
                # 保持当前多选状态
                self.context_menu_selection = list(current_selection)

            # 显示菜单
            self.context_menu.post(event.x_root, event.y_root)
        else:
            # 点击在空白区域，不显示菜单
            return

    def copy_relations(self):
        """复制选中主体的所有关系"""
        selected_items = self.subject_tree.selection()
        if not selected_items:
            return

        # 保存当前状态用于撤销
        self.save_state()

        # 清空之前的复制
        self.copied_relations = []

        # 收集所有选中主体的关系
        for item in selected_items:
            values = self.subject_tree.item(item, "values")
            if not values:
                continue
            subj_display_id = values[0]  # 主体显示ID

            # 从临时关系中找出该主体的所有关系
            for rel in self.temp_relations:
                if rel[0] == subj_display_id:
                    # 存储关系：客体ID、客体类别、谓词
                    self.copied_relations.append((rel[2], rel[3], rel[4]))

        #tb.dialogs.Messagebox.show_info(f"已复制 {len(self.copied_relations)} 条关系", "复制成功", parent=self)

    def paste_relations(self):
        """将复制的所有关系粘贴到当前选中的多个主体 - 使用存储的多选状态"""
        if not self.copied_relations:
            return

        # 使用保存的选中项而不是当前选择
        selected_items = self.context_menu_selection
        if not selected_items:
            return

        # 保存当前状态用于撤销
        self.save_state()

        added_count = 0

        # 收集所有主体ID和类别
        subjects = []
        for item in selected_items:
            values = self.subject_tree.item(item, "values")
            if values:
                subjects.append({
                    "id": values[0],
                    "class": values[1]
                })

        # 如果当前选中的主体在粘贴列表中，更新其关系显示
        current_subject_in_selection = self.current_subject in [s["id"] for s in subjects]

        # 创建关系存在性检查的缓存
        existing_relations_cache = {}
        for rel in self.temp_relations:
            key = (rel[0], rel[2], rel[4])  # (subject, object, predicate)
            existing_relations_cache[key] = True

        # 为每个主体添加复制的每个关系
        for subject in subjects:
            subj_display_id = subject["id"]
            subj_class = subject["class"]

            for rel in self.copied_relations:
                obj_display_id, obj_class, predicate = rel

                # 检查关系是否已存在（使用缓存）
                key = (subj_display_id, obj_display_id, predicate)
                if key in existing_relations_cache:
                    continue  # 跳过已存在的关系

                # 添加新关系
                new_rel = (subj_display_id, subj_class, obj_display_id, obj_class, predicate)
                self.temp_relations.append(new_rel)
                self.new_relations.append(new_rel)  # 同时添加到 new_relations
                added_count += 1

                # 添加到缓存
                existing_relations_cache[key] = True

                # 更新关系计数
                if subj_display_id in self.subject_relation_counts:
                    self.subject_relation_counts[subj_display_id] += 1
                else:
                    self.subject_relation_counts[subj_display_id] = 1

        # 如果有选中的主体在粘贴列表中，更新其关系列表
        if self.current_subject and current_subject_in_selection:
            self.update_relation_list()

        # 更新主体列表显示（刷新颜色）
        self.filter_subjects()

    def save_state(self):
        """保存当前状态到历史记录"""
        # 最多保存10个历史状态
        if len(self.history) >= 10:
            self.history.pop(0)

        # 保存当前状态
        self.history.append(self.temp_relations.copy())

    def undo(self, event=None):
        """撤销上一步操作"""
        if not self.history:
            return

        # 恢复上一步的状态
        self.temp_relations = self.history.pop()

        # 更新关系列表显示
        self.update_relation_list()

        # 提示用户
        self.status_label.config(text="已撤销上一步操作")

    def select_image_folder(self):
        """选择图片文件夹"""
        folder_path = tk.filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            self.image_folder = folder_path
            # 获取所有支持的图片格式
            image_exts = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif"]
            self.image_files = []
            for ext in image_exts:
                self.image_files.extend(glob.glob(os.path.join(folder_path, ext)))
            self.image_files.sort()

            if self.image_files:
                self.current_image_index = 0
                self.load_image(self.image_files[0])
                # 更新计数器
                self.update_counter()
            else:
                tk.messagebox.showwarning("无图片", "该文件夹中没有找到图片文件")
                self.image_counter.config(text="0/0")

    def load_image(self, image_path):
        """加载并显示图片（添加标注）"""
        try:
            # 打开图片
            self.current_image = Image.open(image_path)

            # 提取帧索引
            frame_index = self.extract_frame_index(image_path)

            # 绘制标注
            annotated_image = self.draw_annotations(self.current_image, frame_index)

            # 更新显示
            self.current_annotated_image = annotated_image
            self.update_image_display()

            # 更新标题显示当前图片信息
            filename = os.path.basename(image_path)
            self.title(f"自定义关系点模式 - {filename} ({self.current_image_index + 1}/{len(self.image_files)})")

            # 更新计数器
            self.update_counter()

        except Exception as e:
            tk.messagebox.showerror("图片加载错误", f"无法加载图片: {str(e)}")

    def update_image_display(self):
        """根据缩放比例更新图片显示（包含标注）"""
        if not hasattr(self, 'current_annotated_image') or self.current_annotated_image is None:
            return

        # 获取缩放比例
        scale_text = self.scale_var.get().replace("%", "")
        try:
            scale_factor = float(scale_text) / 100.0
        except ValueError:
            scale_factor = 1.0

        # 计算新尺寸
        width, height = self.current_annotated_image.size
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        # 缩放图片（保持高质量）
        resized_img = self.current_annotated_image.resize(
            (new_width, new_height),
            Image.LANCZOS
        )

        # 转换为PhotoImage
        self.image_tk = ImageTk.PhotoImage(resized_img)

        # 更新Canvas
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, new_width, new_height))
        self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)

    def update_image_scale(self, event=None):
        """更新图片缩放比例"""
        self.update_image_display()

    def prev_image(self):
        """显示上一张图片"""
        if self.image_files and self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_image(self.image_files[self.current_image_index])
            self.update_counter()

    def next_image(self):
        """显示下一张图片"""
        if self.image_files and self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.load_image(self.image_files[self.current_image_index])
            self.update_counter()

    def update_counter(self):
        """更新图片计数器显示"""
        if self.image_files:
            count = f"{self.current_image_index + 1}/{len(self.image_files)}"
            self.image_counter.config(text=count)
        else:
            self.image_counter.config(text="0/0")

    def on_mousewheel(self, event):
        """鼠标滚轮事件处理 - 缩放图片"""
        if event.num == 5 or event.delta < 0:  # 向下滚轮或Linux Button-5
            # 缩小
            current_scale = float(self.scale_var.get().replace("%", "")) / 100
            new_scale = max(0.25, current_scale - 0.1)
            self.scale_var.set(f"{int(new_scale * 100)}%")
        elif event.num == 4 or event.delta > 0:  # 向上滚轮或Linux Button-4
            # 放大
            current_scale = float(self.scale_var.get().replace("%", "")) / 100
            new_scale = min(2.0, current_scale + 0.1)
            self.scale_var.set(f"{int(new_scale * 100)}%")

        self.update_image_display()
        return "break"  # 阻止事件继续传播

    def start_drag(self, event):
        """开始拖动图片"""
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.scroll_start_x = self.canvas.canvasx(0)
        self.scroll_start_y = self.canvas.canvasy(0)
        self.canvas.config(cursor="fleur")  # 更改光标为拖动样式

    def on_drag(self, event):
        """拖动图片过程中"""
        if self.dragging:
            # 计算拖动距离
            delta_x = event.x - self.drag_start_x
            delta_y = event.y - self.drag_start_y

            # 计算新的滚动位置
            new_x = self.scroll_start_x - delta_x
            new_y = self.scroll_start_y - delta_y

            # 应用滚动位置
            self.canvas.xview_moveto(new_x / self.canvas.winfo_width())
            self.canvas.yview_moveto(new_y / self.canvas.winfo_height())

    def end_drag(self, event):
        """结束拖动"""
        self.dragging = False
        self.canvas.config(cursor="")  # 恢复默认光标

    def draw_annotations(self, image, frame_index):
        """在图像上绘制XML标注"""
        if not hasattr(self, 'root_et') or self.root_et is None:
            return image

        # 创建图像副本用于绘制
        img_with_annotations = image.copy()
        draw = ImageDraw.Draw(img_with_annotations)

        try:
            # 设置字体
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()

            # 遍历所有轨迹
            for track in self.root_et.findall('track'):
                # 跳过关系轨迹
                if track.get('label') == "Relation":
                    continue

                track_id = track.get('id')
                label = track.get('label', 'object')

                # 查找当前帧的边界框
                for box in track.findall('box'):
                    if int(box.get('frame')) == frame_index and box.get('outside') == '0':
                        xtl = float(box.get('xtl'))
                        ytl = float(box.get('ytl'))
                        xbr = float(box.get('xbr'))
                        ybr = float(box.get('ybr'))

                        # 绘制边界框
                        draw.rectangle([(xtl, ytl), (xbr, ybr)], outline="red", width=2)

                        # 绘制标签文本
                        text = f"{label} {track_id}"

                        # 兼容不同Pillow版本
                        try:
                            # 新版本使用textbbox
                            bbox = draw.textbbox((0, 0), text, font=font)
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                        except AttributeError:
                            # 旧版本使用textsize
                            text_width, text_height = draw.textsize(text, font=font)

                        # 绘制文本背景
                        draw.rectangle([(xtl, ytl - text_height),
                                        (xtl + text_width, ytl)],
                                       fill="red")
                        draw.text((xtl, ytl - text_height), text, fill="white", font=font)

            # 绘制关系点
            for track in self.root_et.findall('track'):
                if track.get('label') == "Relation":
                    for points in track.findall('points'):
                        if int(points.get('frame')) == frame_index and points.get('outside') == '0':
                            point_str = points.get('points')
                            if point_str:
                                x, y = map(float, point_str.split(','))

                                # 绘制关系点
                                radius = 5
                                draw.ellipse([(x - radius, y - radius),
                                              (x + radius, y + radius)],
                                             fill="blue")

                                # 查找关系谓词
                                predicate = "relation"
                                for attr in points.findall('attribute'):
                                    if attr.get('name') == 'predicate':
                                        predicate = attr.text
                                        break

                                # 绘制谓词文本
                                text = predicate

                                # 兼容不同Pillow版本
                                try:
                                    # 新版本使用textbbox
                                    bbox = draw.textbbox((0, 0), text, font=font)
                                    text_width = bbox[2] - bbox[0]
                                    text_height = bbox[3] - bbox[1]
                                except AttributeError:
                                    # 旧版本使用textsize
                                    text_width, text_height = draw.textsize(text, font=font)

                                draw.text((x + radius + 2, y - text_height // 2),
                                          text, fill="blue", font=font)

        except Exception as e:
            print(f"绘制标注时出错: {e}")

        return img_with_annotations

    def extract_frame_index(self, filename):
        """从图片文件名中提取帧索引"""
        try:
            # 尝试从文件名中提取数字
            basename = os.path.basename(filename)
            base = os.path.splitext(basename)[0]

            # 匹配文件名中的数字序列
            numbers = re.findall(r'\d+', base)
            if numbers:
                return int(numbers[-1])

            # 如果没有数字，尝试使用文件名作为索引
            return hash(base) % 1000000

        except:
            return 0
