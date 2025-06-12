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
class XMLRelationApp:
    """主应用程序窗口"""

    def __init__(self, root):
        self.root = root
        self.root.title("CVAT 关系自动标注工具 v3.1")
        self.root.geometry("800x650")

        # 初始化配置
        self.config = load_config()
        self.rules = load_rules()
        self.entity_classes, self.predicates = load_labels_config()
        self.category_to_trackids = {}
        self.custom_relations = {}
        self.tree_et = None
        self.root_et = None

        # 创建界面
        self.create_menu()
        self.create_widgets()

        self.input_file = ""
        self.output_file = ""

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)

        # 自定义关系菜单
        relation_menu = tk.Menu(menubar, tearoff=0)
        relation_menu.add_command(label="进入自定义关系点模式", command=self.open_custom_relation_dialog)
        menubar.add_cascade(label="自定义关系", menu=relation_menu)

        # 标签配置菜单
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="导入标签配置 (Excel/CSV)", command=self.handle_import_labels)
        config_menu.add_command(label="清空已有标签配置", command=self.handle_clear_labels)
        menubar.add_cascade(label="标签配置", menu=config_menu)

        self.root.config(menu=menubar)

    def create_widgets(self):
        """创建主界面控件"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 头部区域
        self.create_header(main_frame)

        # 文件设置区域
        self.create_file_section(main_frame)

        # 处理按钮
        self.create_action_button(main_frame)

        # 进度显示
        self.progress_bar = ttk.Progressbar(
            main_frame,
            orient=tk.HORIZONTAL,
            length=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(
            main_frame,
            text="准备就绪，请选择 CVAT XML 文件",
            padding=5
        )
        self.status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 规则预览
        self.create_rules_preview(main_frame)

        # 状态栏
        self.create_status_bar()

        # 填充规则预览
        self.populate_rule_preview()

    def create_header(self, parent):
        """创建顶部标题区域"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="CVAT 关系自动标注工具",
            font=("Arial", 16, "bold"),
            foreground="#333333",
            background="#4a86e8",
            padding=10
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            header_frame, text="帮助",
            command=self.show_help,
            width=8
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame, text="配置",
            command=self.open_config,
            width=8
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame, text="管理规则",
            command=self.manage_rules,
            width=10
        ).pack(side=tk.RIGHT, padx=5)

    def create_file_section(self, parent):
        """创建文件设置区域"""
        file_frame = ttk.LabelFrame(parent, text="文件设置")
        file_frame.pack(fill=tk.X, pady=10, padx=5)

        # 输入文件
        input_frame = ttk.Frame(file_frame)
        input_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(input_frame, text="CVAT XML 文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.input_entry = ttk.Entry(input_frame, width=50)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Button(
            input_frame, text="浏览...",
            command=self.browse_input,
            width=8
        ).pack(side=tk.RIGHT)

        # 输出文件
        output_frame = ttk.Frame(file_frame)
        output_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(output_frame, text="输出 XML 文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.output_entry = ttk.Entry(output_frame, width=50)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Button(
            output_frame, text="浏览...",
            command=self.browse_output,
            width=8
        ).pack(side=tk.RIGHT)

    def create_action_button(self, parent):
        """创建操作按钮"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=15)

        self.process_button = ttk.Button(
            button_frame,
            text="执行自动标注",
            command=self.start_processing,
            width=20
        )
        self.process_button.pack(pady=10, ipady=5)

    def create_rules_preview(self, parent):
        """创建规则预览区域"""
        rule_frame = ttk.LabelFrame(parent, text="当前规则预览")
        rule_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)

        columns = ("object_type", "predicate")
        self.rule_tree = ttk.Treeview(
            rule_frame,
            columns=columns,
            show="headings",
            height=6
        )
        self.rule_tree.heading("object_type", text="对象类型", anchor=tk.W)
        self.rule_tree.heading("predicate", text="谓词", anchor=tk.W)
        self.rule_tree.column("object_type", width=250)
        self.rule_tree.column("predicate", width=250)

        scrollbar = ttk.Scrollbar(rule_frame, orient=tk.VERTICAL, command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=scrollbar.set)

        self.rule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    def create_status_bar(self):
        """创建状态栏"""
        status_bar = ttk.Frame(self.root, height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Label(
            status_bar,
            text='CVAT 关系自动标注工具 v3.1 | 点击"自定义关系"菜单以添加手动关系标注'
        ).pack(side=tk.LEFT, padx=10)

    def populate_rule_preview(self):
        """填充规则预览"""
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        for obj_type, predicate in self.rules.items():
            self.rule_tree.insert("", tk.END, values=(obj_type, predicate))

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

    def show_help(self):
        """显示帮助信息"""
        help_text = (
            "CVAT 关系自动标注工具 使用指南：\n\n"
            "1. 点击“浏览...”选择一个 CVAT 导出的 XML 标注文件\n"
            "2. 如果需要保存输出路径，可在“输出 XML 文件”中指定。\n"
            "   - 如果勾选“自动生成输出路径”，则会自动在同目录生成带前缀的文件\n"
            "3. 点击“执行自动标注”按钮，程序会自动根据规则为每个主体添加关系点。\n"
            "4. 如需手动添加其它关系点，请点击窗口顶部“自定义关系”菜单 → “进入自定义关系点模式”，\n"
            "   在弹出的对话框中：\n"
            "   a) 选择或输入主体 ID（可输入关键词过滤列表）\n"
            "   b) 选择或输入客体 ID（可输入关键词筛选客体类别）\n"
            "   c) 输入自定义谓词（如“on”、“parked on”等）\n"
            "   d) 点击“添加到列表”可将该条记录加入临时表格，可多次添加\n"
            "   e) 全部添加完成后，点击“确定”，自定义关系将与自动生成的关系一起写入输出文件\n"
            "   f) 关闭对话框后，可继续点击“执行自动标注”生成最终结果\n\n"
            "5. 输出的 XML 文件将包含自动及自定义的 Relation track。"
        )
        messagebox.showinfo("使用帮助", help_text)

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

            except Exception as e:
                messagebox.showerror("错误", f"解析 XML 文件失败：{e}")
                self.tree_et = None
                self.root_et = None
                return

            # 自动生成输出路径
            if self.config.get('auto_generate_output', True):
                dir_name = os.path.dirname(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"{base_name}_{timestamp}.xml"
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
        if not self.input_file:
            messagebox.showerror("错误", "请选择输入 XML 文件")
            return
        if not self.output_file:
            messagebox.showerror("错误", "请选择输出 XML 文件")
            return

        # 禁用按钮
        self.process_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0
        self.status_label.config(text="开始处理...")

        # 在后台线程中执行处理
        processing_thread = threading.Thread(
            target=self.process_xml,
            args=(self.input_file, self.output_file)
        )
        processing_thread.daemon = True
        processing_thread.start()

    def process_xml(self, input_path, output_path):
        """处理XML文件的后台任务"""
        try:
            success, message = process_xml_file(
                input_path,
                output_path,
                self.rules,
                self.config,
                custom_relations=self.custom_relations,
                progress_callback=self.update_progress
            )
            if success:
                self.progress_bar['value'] = 100
                self.status_label.config(text=message)
                messagebox.showinfo("成功", f"处理完成！\n{message}\n\n输出文件: {output_path}")
            else:
                self.status_label.config(text=f"错误: {message}")
                messagebox.showerror("处理错误", message)
        except Exception as e:
            self.status_label.config(text=f"运行异常: {e}")
            messagebox.showerror("运行异常", f"处理过程中发生异常:\n{e}")
        finally:
            self.process_button.config(state=tk.NORMAL)

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
                messagebox.showinfo("成功", f"导入 {len(new_entity_classes)} 个实体类别和 {len(new_predicates)} 个谓词")

            else:
                messagebox.showerror("错误", "仅支持Excel文件导入")

        except Exception as e:
            messagebox.showerror("导入失败", f"导入标签配置时出错: {str(e)}")

    def handle_clear_labels(self):
        """清空标签配置"""
        self.entity_classes, self.predicates = [], []
        if os.path.exists("labels_config.json"):
            os.remove("labels_config.json")
        messagebox.showinfo("提示", "已清空标签配置")

    def open_custom_relation_dialog(self):
        """打开自定义关系点对话框"""
        if not self.input_file or not self.root_et:
            messagebox.showerror("错误", "请先选择并解析输入 XML 文件")
            return

        dialog = CustomRelationDialog(
            self.root,
            self.input_file,
            self.root_et,
            self.entity_classes,
            self.predicates,
            self.category_to_trackids,
            self.custom_relations
        )
        self.root.wait_window(dialog)