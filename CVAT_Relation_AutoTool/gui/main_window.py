import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import xml.etree.ElementTree as ET
from config import load_config, save_config
from rules import load_rules, save_rules
from labels_manager import load_labels_config
from xml_processor import process_xml_file
from .dialogs import ConfigDialog, RuleManager, CustomRelationDialog
import pandas as pd
from datetime import datetime
import json
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk


class XMLRelationApp:
    """主应用程序窗口 - 使用ttkbootstrap美化"""

    def __init__(self, root):
        self.root = root
        self.root.title("CVAT 关系自动标注工具 v3.1")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        # 设置ttkbootstrap主题
        self.style = tb.Style(theme="minty")
        self.style.configure("TButton", font=("微软雅黑", 10))
        self.style.configure("TLabel", font=("微软雅黑", 10))
        self.style.configure("Treeview", font=("微软雅黑", 9))
        self.style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"))

        # 加载图标
        self.load_icons()

        # 初始化配置
        self.config = load_config()
        self.rules = load_rules()
        self.entity_classes, self.predicates = load_labels_config()
        self.category_to_trackids = {}
        self.custom_relations = {}
        self.relations_to_delete = []  # 存储要删除的关系点（原始ID）
        self.relations_to_delete_details = []  # 存储要删除的关系点的详细信息（显示ID
        self.tree_et = None
        self.root_et = None

        # 创建界面
        self.create_menu()
        self.create_widgets()

        self.input_file = ""
        self.output_file = ""

    def load_icons(self):
        """加载图标资源"""
        try:
            # 使用PIL加载和调整图标大小
            self.help_icon = self.create_icon("?", size=(16, 16))
            self.config_icon = self.create_icon("⚙️", size=(16, 16))
            self.rules_icon = self.create_icon("📝", size=(16, 16))
            self.process_icon = self.create_icon("▶️", size=(20, 20))
            self.folder_icon = self.create_icon("📂", size=(16, 16))
        except:
            # 如果图标加载失败，使用文本
            self.help_icon = "?"
            self.config_icon = "⚙️"
            self.rules_icon = "📝"
            self.process_icon = "▶️"
            self.folder_icon = "📂"

    def create_icon(self, text, size=(24, 24)):
        """创建文本图标 - 修复stretch问题"""
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        return ImageTk.PhotoImage(img)

    def create_menu(self):
        """创建菜单栏"""
        menubar = tb.Menu(self.root)

        # 文件菜单
        file_menu = tb.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开文件", command=self.browse_input)
        file_menu.add_command(label="保存配置", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        # 自定义关系菜单
        relation_menu = tb.Menu(menubar, tearoff=0)
        relation_menu.add_command(
            label="进入自定义关系点模式",
            command=self.open_custom_relation_dialog,
            accelerator="Ctrl+R"
        )
        menubar.add_cascade(label="自定义关系", menu=relation_menu)

        # 标签配置菜单
        config_menu = tb.Menu(menubar, tearoff=0)
        config_menu.add_command(
            label="导入标签配置 (Excel/CSV)",
            command=self.handle_import_labels,
            accelerator="Ctrl+I"
        )
        config_menu.add_command(
            label="清空已有标签配置",
            command=self.handle_clear_labels
        )
        menubar.add_cascade(label="标签配置", menu=config_menu)

        # 帮助菜单
        help_menu = tb.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用指南", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

        # 添加快捷键
        self.root.bind("<Control-r>", lambda e: self.open_custom_relation_dialog())
        self.root.bind("<Control-i>", lambda e: self.handle_import_labels())

    def create_file_settings(self, parent):
        """创建文件设置区域"""
        file_frame = tb.Labelframe(
            parent,
            text="文件设置",
            bootstyle="info",
            padding=(10, 5)
        )
        file_frame.pack(fill=tk.X, pady=5)

        # 网格布局 - 更精确地控制间距
        file_frame.columnconfigure(1, weight=1)  # 输入框列可扩展

        # 输入文件
        tb.Label(file_frame, text="CVAT XML 文件:").grid(
            row=0, column=0, padx=5, pady=7, sticky="e")

        self.input_entry = tb.Entry(file_frame, width=40, bootstyle="primary")
        self.input_entry.grid(
            row=0, column=1, padx=(0, 5), pady=5, sticky="ew")

        tb.Button(
            file_frame, text="浏览...",
            command=self.browse_input,
            bootstyle="primary-outline",
            width=8
        ).grid(row=0, column=2, padx=5, pady=5)

        # 输出文件
        tb.Label(file_frame, text="输出 XML 文件:").grid(
            row=1, column=0, padx=5, pady=5, sticky="e")

        self.output_entry = tb.Entry(file_frame, width=40, bootstyle="primary")
        self.output_entry.grid(
            row=1, column=1, padx=(0, 5), pady=5, sticky="ew")

        tb.Button(
            file_frame, text="浏览...",
            command=self.browse_output,
            bootstyle="primary-outline",
            width=8
        ).grid(row=1, column=2, padx=5, pady=5)

    def create_widgets(self):
        """创建主界面控件 - 优化布局"""
        # 创建主容器
        main_container = tb.Frame(self.root, bootstyle="default")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 顶部文件设置区域
        top_frame = tb.Frame(main_container, bootstyle="light")
        top_frame.pack(fill=tk.X, padx=5, pady=(0, 15))

        # 文件设置区域
        self.create_file_settings(top_frame)

        # 主内容区域 - 使用PanedWindow支持手动调整大小
        self.main_paned = tb.PanedWindow(
            main_container,
            orient=tk.HORIZONTAL,
            bootstyle="light"
        )
        self.main_paned.pack(fill=tk.BOTH, expand=True, pady=5)

        # 左侧面板
        left_panel = tb.Frame(self.main_paned, bootstyle="light", width=550)
        self.create_left_panel(left_panel)
        self.main_paned.add(left_panel)

        # 分隔符
        self.main_paned.add(tb.Separator(self.main_paned, orient=tk.VERTICAL))

        # 右侧面板
        right_panel = tb.Frame(self.main_paned, bootstyle="light", width=350)
        self.create_right_panel(right_panel)
        self.main_paned.add(right_panel)

        # 底部操作区域
        bottom_frame = tb.Frame(main_container)
        bottom_frame.pack(fill=tk.X, padx=5, pady=(15, 5))
        self.create_bottom_controls(bottom_frame)

    def create_bottom_controls(self, parent):
        """创建底部操作控件"""
        # 进度条容器
        progress_container = tb.Frame(parent, bootstyle="light")
        progress_container.pack(fill=tk.X, pady=(0, 15))

        tb.Label(
            progress_container,
            text="处理进度:",
            bootstyle="inverse-light"
        ).pack(side=tk.LEFT, padx=(0, 10), pady=5)

        self.progress_bar = tb.Progressbar(
            progress_container,
            orient=tk.HORIZONTAL,
            length=100,
            mode='determinate',
            bootstyle="success-striped"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15), pady=5)

        # 主要操作按钮
        self.process_button = tb.Button(
            parent,
            text="执行自动标注",
            command=self.start_processing,
            bootstyle="success",
            padding=(15, 5),
            width=15
        )
        self.process_button.pack(side=tk.LEFT, padx=(10, 0))

        # 状态标签
        self.status_label = tb.Label(
            parent,
            text="准备就绪，请选择 CVAT XML 文件",
            bootstyle="dark",
            padding=(10, 5),
            anchor="center"
        )
        self.status_label.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 10))

    def create_left_panel(self, parent):
        """创建左侧面板内容 - 优化布局"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)  # 让整个面板在父容器中扩展

        # 使用Frame作为容器，使用grid布局
        container = tb.Frame(parent, bootstyle="light")
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)  # 预添加区域
        container.rowconfigure(1, weight=1)  # 预删除区域

        ##################################
        # 预添加关系点区域
        ##################################
        add_frame = tb.Labelframe(container, text="预添加关系点", bootstyle="info")
        add_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=(0, 5))
        add_frame.columnconfigure(0, weight=1)
        add_frame.rowconfigure(1, weight=1)  # 树形视图区域

        tb.Label(
            add_frame,
            text="自定义添加的关系点将会在这里显示",
            bootstyle="inverse-light"
        ).grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # 关系点树形视图容器
        tree_container = tb.Frame(add_frame)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        # 创建树形视图显示关系点
        cols = ("subject_id", "subject_class", "object_id", "predicate")
        self.relations_tree = tb.Treeview(
            tree_container,
            columns=cols,
            show="headings",
            height=5,  # 高度调整
            bootstyle="light",
            selectmode="extended"
        )
        self.relations_tree.heading("subject_id", text="主体 ID")
        self.relations_tree.heading("subject_class", text="主体类别")
        self.relations_tree.heading("object_id", text="客体 ID")
        self.relations_tree.heading("predicate", text="谓词")

        # 设置列宽比例 - 移除stretch选项
        self.relations_tree.column("subject_id", width=80, anchor=tk.CENTER)
        self.relations_tree.column("subject_class", width=120, anchor=tk.W)
        self.relations_tree.column("object_id", width=80, anchor=tk.CENTER)
        self.relations_tree.column("predicate", width=150, anchor=tk.W)

        # 滚动条
        vsb = tb.Scrollbar(
            tree_container,
            orient=tk.VERTICAL,
            command=self.relations_tree.yview,
            bootstyle="round"
        )
        self.relations_tree.configure(yscrollcommand=vsb.set)

        # 使用grid布局放置组件
        self.relations_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # 操作按钮容器
        add_btn_container = tb.Frame(add_frame)
        add_btn_container.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        tb.Button(
            add_btn_container,
            text="管理自定义关系",
            command=self.open_custom_relation_dialog,
            bootstyle="primary-outline",
        ).pack(side=tk.LEFT, padx=(0, 5))

        tb.Button(
            add_btn_container,
            text="清空列表",
            command=self.clear_custom_relations,
            bootstyle="danger-outline",
        ).pack(side=tk.LEFT)

        ##################################
        # 预删除关系点区域
        ##################################
        delete_frame = tb.Labelframe(container, text="预删除关系点", bootstyle="danger")
        delete_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        delete_frame.columnconfigure(0, weight=1)
        delete_frame.rowconfigure(1, weight=1)  # 树形视图区域

        tb.Label(
            delete_frame,
            text="计划删除的关系点将会在这里显示",
            bootstyle="inverse-danger"
        ).grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # 删除关系点树形视图容器
        del_tree_container = tb.Frame(delete_frame)
        del_tree_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        del_tree_container.columnconfigure(0, weight=1)
        del_tree_container.rowconfigure(0, weight=1)

        # 创建树形视图显示要删除的关系点
        del_cols = ("subject_id", "object_id", "predicate")
        self.deletion_tree = tb.Treeview(
            del_tree_container,
            columns=del_cols,
            show="headings",
            height=5,  # 高度调整
            bootstyle="danger",
            selectmode="extended"
        )
        self.deletion_tree.heading("subject_id", text="主体 ID")
        self.deletion_tree.heading("object_id", text="客体 ID")
        self.deletion_tree.heading("predicate", text="谓词")

        # 设置列宽比例 - 移除stretch选项
        self.deletion_tree.column("subject_id", width=80, anchor=tk.CENTER)
        self.deletion_tree.column("object_id", width=80, anchor=tk.CENTER)
        self.deletion_tree.column("predicate", width=150, anchor=tk.W)

        # 滚动条
        del_vsb = tb.Scrollbar(
            del_tree_container,
            orient=tk.VERTICAL,
            command=self.deletion_tree.yview,
            bootstyle="round-danger"
        )
        self.deletion_tree.configure(yscrollcommand=del_vsb.set)

        # 使用grid布局放置组件
        self.deletion_tree.grid(row=0, column=0, sticky="nsew")
        del_vsb.grid(row=0, column=1, sticky="ns")

        # 操作按钮容器
        del_btn_container = tb.Frame(delete_frame)
        del_btn_container.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        tb.Button(
            del_btn_container,
            text="清空删除列表",
            command=self.clear_deletion_list,
            bootstyle="danger",
        ).pack(side=tk.LEFT)

    def update_custom_relations_display(self):
        """更新预添加关系点的显示"""
        # 清除现有显示
        for item in self.relations_tree.get_children():
            self.relations_tree.delete(item)

        # 添加所有自定义关系点（使用原始ID）
        for subj_id, rel_list in self.custom_relations.items():
            # 获取主体类别
            subj_class = "未知"
            if hasattr(self, 'root_et') and self.root_et:
                for track in self.root_et.findall('track'):
                    if track.get('id') == subj_id:
                        subj_class = track.get('label', '未知')
                        break

            for obj_id, pred in rel_list:
                # 添加显示项目（显示为CVAT格式ID+1）
                self.relations_tree.insert("", tk.END, values=(
                    str(int(subj_id) + 1),
                    subj_class,
                    str(int(obj_id) + 1),
                    pred
                ))

    def clear_custom_relations(self):
        """清空自定义关系点列表"""
        self.custom_relations.clear()
        self.update_custom_relations_display()
        self.status_label.config(text="已清空自定义关系点列表")

        # 同时清空临时关系
        if hasattr(self, 'temp_relations'):
            self.temp_relations = []

    def create_right_panel(self, parent):
        """创建右侧面板内容 - 优化布局"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)  # 规则树形区域可扩展

        # 规则预览标签
        tb.Label(
            parent,
            text="当前规则预览",
            font=("微软雅黑", 10, "bold"),
            bootstyle="info"
        ).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 2))

        # 规则树形视图容器
        rule_container = tb.Frame(parent, bootstyle="default")
        rule_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        rule_container.columnconfigure(0, weight=1)
        rule_container.rowconfigure(0, weight=1)

        # 规则树形视图
        columns = ("object_type", "predicate")
        self.rule_tree = tb.Treeview(
            rule_container,
            columns=columns,
            show="headings",
            height=12,  # 适当增加高度
            bootstyle="light"
        )
        self.rule_tree.heading("object_type", text="对象类型", anchor=tk.W)
        self.rule_tree.heading("predicate", text="谓词", anchor=tk.W)

        # 设置列宽比例 - 移除stretch选项
        self.rule_tree.column("object_type", width=150, anchor=tk.W)
        self.rule_tree.column("predicate", width=150, anchor=tk.W)

        # 滚动条
        rule_scroll = tb.Scrollbar(
            rule_container,
            orient=tk.VERTICAL,
            command=self.rule_tree.yview,
            bootstyle="round"
        )
        self.rule_tree.configure(yscrollcommand=rule_scroll.set)

        # 布局
        self.rule_tree.grid(row=0, column=0, sticky="nsew")
        rule_scroll.grid(row=0, column=1, sticky="ns")

        # 操作按钮容器
        btn_container = tb.Frame(parent)
        btn_container.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        tb.Button(
            btn_container,
            text="管理规则",
            command=self.manage_rules,
            bootstyle="primary-outline",
            width=12
        ).pack(side=tk.RIGHT, padx=(5, 0))

        tb.Button(
            btn_container,
            text="编辑配置",
            command=self.open_config,
            bootstyle="secondary-outline",
            width=12
        ).pack(side=tk.RIGHT, padx=5)

    def update_stats(self):
        """更新统计信息"""
        rule_count = len(self.rules)
        entity_count = len(self.entity_classes)
        predicate_count = len(self.predicates)
        status = f"就绪 | {rule_count} 条规则 | {entity_count} 个实体类别 | {predicate_count} 个谓词"
        self.stats_label.config(text=status)

    def populate_rule_preview(self):
        """填充规则预览"""
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        for obj_type, predicate in self.rules.items():
            self.rule_tree.insert("", tk.END, values=(obj_type, predicate))

        # 更新统计信息
        self.update_stats()

    def manage_rules(self):
        """打开规则管理窗口"""
        manager = RuleManager(self.root, self.rules)
        self.root.wait_window(manager)
        self.rules = load_rules()
        self.populate_rule_preview()

    def open_config(self):
        """打开配置窗口"""
        config_dialog = ConfigDialog(self.root, self.config)
        self.root.wait_window(config_dialog)
        self.config = load_config()

    def save_config(self):
        """保存配置"""
        save_config(self.config)
        messagebox.showinfo("成功", "配置已保存！")

    def show_help(self):
        """显示帮助信息"""
        help_text = (
            "CVAT 关系自动标注工具 使用指南\n\n"
            "1. 文件设置\n"
            "   - 点击“浏览...”选择一个 CVAT 导出的 XML 标注文件\n"
            "   - 指定输出 XML 文件路径\n\n"
            "2. 规则管理\n"
            "   - 在右侧面板查看当前规则\n"
            "   - 点击“管理规则”按钮添加/编辑规则\n\n"
            "3. 自动标注\n"
            "   - 点击“执行自动标注”按钮开始处理\n"
            "   - 处理进度将在底部显示\n\n"
            "4. 自定义关系\n"
            "   - 通过菜单“自定义关系”->“进入自定义关系点模式”添加额外关系\n\n"
            "5. 标签配置\n"
            "   - 通过菜单“标签配置”导入或清空标签配置"
        )
        messagebox.showinfo("使用帮助", help_text)

    def show_about(self):
        """显示关于信息"""
        about_text = (
            "CVAT 关系自动标注工具 v3.1\n\n"
            "该工具用于自动化处理 CVAT 标注文件，添加关系标注点。\n"
            "支持自动生成关系点和自定义关系点。\n\n"
            "开发团队: DeepSeek AI\n"
            "发布日期: 2024年5月\n"
            "许可证: MIT"
        )
        messagebox.showinfo("关于", about_text)

    def browse_input(self):
        """选择输入 XML 文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("XML 文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            self.input_file = file_path
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, file_path)

            try:
                # 解析XML并构建类别映射
                self.tree_et = ET.parse(self.input_file)
                self.root_et = self.tree_et.getroot()

                # 构建类别到track ID的映射
                self.category_to_trackids = {}
                for track in self.root_et.findall('track'):
                    label = track.get('label')
                    track_id = track.get('id')
                    if label and label != "Relation":
                        key = label.lower()
                        if key not in self.category_to_trackids:
                            self.category_to_trackids[key] = []
                        self.category_to_trackids[key].append(track_id)

                self.status_label.config(text=f"已加载文件: {os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("错误", f"解析 XML 文件失败：{e}")
                self.tree_et = None
                self.root_et = None
                self.status_label.config(text="文件解析错误")
                return

            # 自动生成输出路径
            if self.config.get('auto_generate_output', True):
                dir_name = os.path.dirname(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"{base_name}_processed_{timestamp}.xml"
                self.output_file = os.path.join(dir_name, output_name)
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, self.output_file)

    def browse_output(self):
        """选择输出 XML 文件路径"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML 文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            self.output_file = file_path
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, file_path)

    def start_processing(self):
        """开始执行自动标注"""
        # 获取输入输出文件路径
        self.input_file = self.input_entry.get()
        self.output_file = self.output_entry.get()

        if not self.input_file:
            messagebox.showerror("错误", "请选择输入 XML 文件")
            return
        if not self.output_file:
            messagebox.showerror("错误", "请选择输出 XML 文件")
            return

        # 禁用按钮
        self.process_button.config(state=tk.DISABLED, bootstyle="secondary")
        self.progress_bar['value'] = 0
        self.status_label.config(text="开始处理...")

        # 在后台线程中执行处理
        processing_thread = threading.Thread(
            target=self.process_xml,
            args=(self.input_file, self.output_file)
        )
        processing_thread.daemon = True
        processing_thread.start()

        # 在后台线程结束后更新UI
        self.root.after(100, self.check_thread_status, processing_thread)

    def check_thread_status(self, thread):
        """检查线程状态并更新UI"""
        if thread.is_alive():
            self.root.after(100, self.check_thread_status, thread)
        else:
            # 更新自定义关系显示
            self.update_custom_relations_display()
            # 更新删除列表
            self.update_deletion_list()

    def process_xml(self, input_file, output_file):
        # 处理XML文件
        try:
            # 获取配置和规则
            config = self.config  # 使用已有的配置
            rules = self.rules  # 使用已有的规则

            # 进度回调函数
            def progress_callback(progress, message):
                self.update_progress(progress, message)

            # 处理XML文件
            success, message = process_xml_file(
                input_file,
                output_file,
                rules,
                config,
                self.custom_relations,  # 传递当前自定义关系
                self.relations_to_delete,  # 传递当前删除列表
                progress_callback
            )

            if success:
                # 处理成功后清空自定义关系和删除列表
                self.custom_relations = {}
                self.relations_to_delete = []
                self.relations_to_delete_details = []

                # 更新UI显示
                self.update_custom_relations_display()
                self.update_deletion_list()

                messagebox.showinfo("成功", message)
            else:
                messagebox.showerror("错误", message)

        except Exception as e:
            messagebox.showerror("错误", f"处理XML文件失败: {str(e)}")
        finally:
            # 重新启用处理按钮
            self.process_button.config(state=tk.NORMAL, bootstyle="success")
            self.status_label.config(text="处理完成")

    def update_progress(self, progress, message):
        """更新进度信息"""
        if self.root:  # 确保窗口仍然存在
            self.progress_bar['value'] = progress
            self.status_label.config(text=message)
            self.root.update_idletasks()

    def handle_import_labels(self):
        """导入标签配置"""
        file_path = filedialog.askopenfilename(
            title="选择 Excel/CSV 文件以导入实体类别与谓词",
            filetypes=[("Excel 文件", "*.xlsx;*.xls"), ("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            # 尝试导入标签
            if file_path.lower().endswith((".xlsx", ".xls")):
                # 解析Excel文件
                xls = pd.ExcelFile(file_path)

                # 假设第一个sheet包含实体类别
                entity_df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])
                new_entity_classes = []
                for col in entity_df.columns:
                    if 'entity' in col.lower() or 'class' in col.lower():
                        new_entity_classes = entity_df[col].dropna().astype(str).tolist()
                        break

                # 第二个sheet包含谓词
                pred_df = pd.read_excel(xls, sheet_name=xls.sheet_names[1])
                new_predicates = []
                for col in pred_df.columns:
                    if 'predicate' in col.lower() or 'relation' in col.lower():
                        new_predicates = pred_df[col].dropna().astype(str).tolist()
                        break

                # 保存配置
                data = {
                    "entity_classes": new_entity_classes,
                    "predicates": new_predicates
                }
                with open("labels_config.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 更新内存中的配置
                self.entity_classes = new_entity_classes
                self.predicates = new_predicates

                # 更新UI
                self.update_stats()

                messagebox.showinfo("成功", f"导入 {len(new_entity_classes)} 个实体类别和 {len(new_predicates)} 个谓词")

                self.status_label.config(text="标签配置已更新")

            else:
                messagebox.showerror("错误", "仅支持Excel文件导入")

        except Exception as e:
            messagebox.showerror("导入失败", f"导入标签配置时出错: {str(e)}")
            self.status_label.config(text=f"导入失败: {str(e)}")

    def handle_clear_labels(self):
        """清空标签配置"""
        self.entity_classes, self.predicates = [], []
        if os.path.exists("labels_config.json"):
            os.remove("labels_config.json")

        # 更新UI
        self.update_stats()

        messagebox.showinfo("提示", "已清空标签配置")
        self.status_label.config(text="标签配置已清空")

    def open_custom_relation_dialog(self):
        # 获取当前选择的XML文件
        input_file = self.input_entry.get()  # 从输入框获取
        #self.relations_to_delete = []  # 清空原始ID删除列表
        #self.relations_to_delete_details = []  # 清空显示ID删除列表
        if not input_file:
            messagebox.showwarning("警告", "请先选择XML文件")
            return

        # 解析XML文件
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()

            # 获取实体类别和谓词列表
            entity_classes = self.entity_classes
            predicates = self.predicates

            # 构建类别到track ID的映射
            category_to_trackids = {}
            for track in root.findall('track'):
                label = track.get('label')
                track_id = track.get('id')
                if label and label != "Relation":
                    key = label.lower()
                    if key not in category_to_trackids:
                        category_to_trackids[key] = []
                    category_to_trackids[key].append(track_id)

            # 打开自定义关系对话框
            custom_dialog = CustomRelationDialog(
                self.root,
                input_file,
                root,
                entity_classes,
                predicates,
                category_to_trackids,
                self.custom_relations,  # 传递已有的自定义关系
                self.relations_to_delete,
                self.relations_to_delete_details,
                self
            )
            self.root.wait_window(custom_dialog)

            # 更新自定义关系显示
            self.update_custom_relations_display()
            # 新加：更新删除列表显示
            self.update_deletion_list()

        except Exception as e:
            messagebox.showerror("错误", f"解析XML文件失败: {str(e)}")

    def clear_deletion_list(self):
        """清空预删除关系点列表"""
        self.relations_to_delete = []
        self.relations_to_delete_details = []
        self.update_deletion_list()
        self.status_label.config(text="已清空预删除关系点列表")

    def update_deletion_list(self):
        """更新删除列表显示"""
        # 清除现有显示
        for item in self.deletion_tree.get_children():
            self.deletion_tree.delete(item)

        # 添加所有删除项（使用显示ID）
        for relation in self.relations_to_delete_details:
            if len(relation) >= 3:
                subj_id, obj_id, predicate = relation[:3]
                self.deletion_tree.insert("", tk.END, values=(
                    subj_id,
                    obj_id,
                    predicate
                ))