import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import pandas as pd
from config import DEFAULT_CONFIG


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
                            if object_id_attr and object_id_attr.strip():
                                display_obj_id = str(int(object_id_attr) + 1)
                            else:
                                display_obj_id = ""
                        except ValueError:
                            continue

                        # 获取主体类别
                        subj_class = self.id_to_category.get(subject_id_attr, "未知")
                        # 获取客体类别（如果有）
                        obj_class = "未知"
                        if object_id_attr and object_id_attr.strip():
                            obj_class = self.id_to_category.get(object_id_attr, "未知")

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

        # 使用PanedWindow分割主体列表和关系管理区域
        paned = tb.PanedWindow(content_frame, bootstyle="light", orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧：主体列表
        left_frame = tb.Frame(paned, padding=5)
        paned.add(left_frame)

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
            height=12
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
            font=("微软雅黑", 10),
            bootstyle="light"
        )
        self.subject_info_label.pack(padx=5, pady=(0, 5))

        # 添加新关系区域
        add_relation_frame = tb.Labelframe(
            right_frame,
            text="添加新关系",
            bootstyle="success"
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
            width=15
        ).pack(pady=5)

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
        max_relations = max(self.subject_relation_counts.values()) if self.subject_relation_counts and len(self.subject_relation_counts) > 0 else 1

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
            return

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

            # 验证obj_id是否为有效数字
            if not obj_id.isdigit():
                # 如果obj_id不是数字，跳过这个关系
                continue

            try:
                # 尝试将obj_id转换为整数
                int(obj_id)
            except ValueError:
                # 如果转换失败，跳过这个关系
                continue

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
        """显示右键菜单"""
        item = self.subject_tree.identify_row(event.y)
        if item:
            self.subject_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

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

        tb.dialogs.Messagebox.show_info(f"已复制 {len(self.copied_relations)} 条关系", "复制成功", parent=self)

    def paste_relations(self):
        """将复制的所有关系粘贴到当前选中的主体"""
        if not self.copied_relations:
            return

        # 保存当前状态用于撤销
        self.save_state()

        selected_items = self.subject_tree.selection()
        if not selected_items:
            return

        added_count = 0

        for item in selected_items:
            values = self.subject_tree.item(item, "values")
            if not values:
                continue
            subj_display_id = values[0]  # 当前主体的显示ID
            subj_class = values[1]  # 当前主体的类别

            # 将复制的每个关系添加到当前主体
            for rel in self.copied_relations:
                obj_display_id, obj_class, predicate = rel

                # 检查该关系是否已经存在
                exists = False
                for existing_rel in self.temp_relations:
                    if (existing_rel[0] == subj_display_id and
                            existing_rel[2] == obj_display_id and
                            existing_rel[4] == predicate):
                        exists = True
                        break

                if not exists:
                    # 添加新关系
                    new_rel = (subj_display_id, subj_class, obj_display_id, obj_class, predicate)
                    self.temp_relations.append(new_rel)
                    self.new_relations.append(new_rel)  # 同时添加到 new_relations
                    added_count += 1

                    # 更新关系计数
                    if subj_display_id in self.subject_relation_counts:
                        self.subject_relation_counts[subj_display_id] += 1
                    else:
                        self.subject_relation_counts[subj_display_id] = 1

        # 更新当前主体的关系列表
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