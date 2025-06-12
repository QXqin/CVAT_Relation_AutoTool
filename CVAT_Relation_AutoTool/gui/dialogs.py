import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import pandas as pd
from config import DEFAULT_CONFIG
from rules import DEFAULT_RULES


class ConfigDialog(tk.Toplevel):
    """配置对话框"""

    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("修改配置")
        self.geometry("500x400")
        self.config = config
        self.result_config = config.copy()
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="修改配置", font=("Arial", 14, "bold")).pack(pady=10)

        config_frame = tk.LabelFrame(main_frame, text="自动化选项")
        config_frame.pack(fill=tk.X, pady=10)

        self.sync_var = tk.BooleanVar(value=self.config.get('auto_sync_lifecycle', True))
        sync_cb = ttk.Checkbutton(
            config_frame,
            text="自动同步生命周期 (关联自动生成/删除)",
            variable=self.sync_var,
            onvalue=True, offvalue=False
        )
        sync_cb.pack(anchor=tk.W, padx=10, pady=5)

        self.skip_var = tk.BooleanVar(value=self.config.get('skip_existing', True))
        skip_cb = ttk.Checkbutton(
            config_frame,
            text="跳过已有关系的主体 (避免重复添加)",
            variable=self.skip_var,
            onvalue=True, offvalue=False
        )
        skip_cb.pack(anchor=tk.W, padx=10, pady=5)

        self.gen_var = tk.BooleanVar(value=self.config.get('auto_generate_output', True))
        gen_cb = ttk.Checkbutton(
            config_frame,
            text="自动生成输出文件路径",
            variable=self.gen_var,
            onvalue=True, offvalue=False
        )
        gen_cb.pack(anchor=tk.W, padx=10, pady=5)

        self.backup_var = tk.BooleanVar(value=self.config.get('backup_original', True))
        backup_cb = ttk.Checkbutton(
            config_frame,
            text="处理前备份原始文件",
            variable=self.backup_var,
            onvalue=True, offvalue=False
        )
        backup_cb.pack(anchor=tk.W, padx=10, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(button_frame, text="保存配置", command=self.save_config, width=12).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="恢复默认", command=self.reset_defaults, width=12).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="关闭", command=self.destroy, width=12).pack(side=tk.RIGHT, padx=10)

    def save_config(self):
        self.result_config = {
            'auto_sync_lifecycle': self.sync_var.get(),
            'skip_existing': self.skip_var.get(),
            'auto_generate_output': self.gen_var.get(),
            'backup_original': self.backup_var.get()
        }
        with open("config.json", "w") as f:
            json.dump(self.result_config, f, indent=2)
        messagebox.showinfo("成功", "配置已保存！")
        self.destroy()

    def reset_defaults(self):
        self.sync_var.set(DEFAULT_CONFIG['auto_sync_lifecycle'])
        self.skip_var.set(DEFAULT_CONFIG['skip_existing'])
        self.gen_var.set(DEFAULT_CONFIG['auto_generate_output'])
        self.backup_var.set(DEFAULT_CONFIG['backup_original'])
        messagebox.showinfo("提示", "已恢复默认配置")


class RuleManager(tk.Toplevel):
    """规则管理对话框"""

    def __init__(self, parent, rules):
        super().__init__(parent)
        self.parent = parent
        self.rules = rules
        self.title("管理关系谓词规则")
        self.geometry("600x500")

        self.create_widgets()
        self.populate_rules()

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        header = ttk.Label(main_frame, text="管理关系谓词规则", font=("Arial", 14, "bold"))
        header.pack(fill=tk.X, pady=(0, 15))

        list_frame = ttk.LabelFrame(main_frame, text="当前规则")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("object_type", "predicate")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("object_type", text="对象类型", anchor=tk.W)
        self.tree.heading("predicate", text="谓词", anchor=tk.W)
        self.tree.column("object_type", width=250, stretch=tk.YES)
        self.tree.column("predicate", width=250, stretch=tk.YES)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)

        ttk.Button(button_frame, text="添加规则", command=self.add_rule, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑规则", command=self.edit_rule, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除规则", command=self.delete_rule, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="保存并关闭", command=self.save_and_close, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="重置默认", command=self.reset_defaults, width=12).pack(side=tk.RIGHT, padx=5)

    def populate_rules(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for obj_type, predicate in self.rules.items():
            self.tree.insert("", tk.END, values=(obj_type, predicate))

    def add_rule(self):
        add_dialog = tk.Toplevel(self)
        add_dialog.title("添加规则")
        add_dialog.geometry("400x200")

        form_frame = ttk.Frame(add_dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(form_frame, text="对象类型:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        obj_type_entry = ttk.Entry(form_frame, width=30)
        obj_type_entry.grid(row=0, column=1, padx=5, pady=10, sticky=tk.EW)

        ttk.Label(form_frame, text="谓词:").grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)
        predicate_entry = ttk.Entry(form_frame, width=30)
        predicate_entry.grid(row=1, column=1, padx=5, pady=10, sticky=tk.EW)

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        def save_rule():
            obj_type = obj_type_entry.get().strip()
            predicate = predicate_entry.get().strip()
            if not obj_type or not predicate:
                messagebox.showerror("错误", "对象类型和谓词不能为空")
                return
            if obj_type in self.rules:
                messagebox.showerror("错误", f"对象类型 '{obj_type}' 已存在")
                return
            self.rules[obj_type] = predicate
            self.populate_rules()
            add_dialog.destroy()

        ttk.Button(button_frame, text="保存", command=save_rule).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=add_dialog.destroy).pack(side=tk.RIGHT, padx=10)

    def edit_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要编辑的规则")
            return
        item = selected[0]
        values = self.tree.item(item, "values")
        obj_type, predicate = values

        edit_dialog = tk.Toplevel(self)
        edit_dialog.title("编辑规则")
        edit_dialog.geometry("400x200")

        form_frame = ttk.Frame(edit_dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(form_frame, text="对象类型:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        obj_type_label = ttk.Label(form_frame, text=obj_type, font=("Arial", 10, "bold"))
        obj_type_label.grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)

        ttk.Label(form_frame, text="谓词:").grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)
        predicate_entry = ttk.Entry(form_frame, width=30)
        predicate_entry.insert(0, predicate)
        predicate_entry.grid(row=1, column=1, padx=5, pady=10, sticky=tk.EW)

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        def save_edit():
            new_predicate = predicate_entry.get().strip()
            if not new_predicate:
                messagebox.showerror("错误", "谓词不能为空")
                return
            self.rules[obj_type] = new_predicate
            self.populate_rules()
            edit_dialog.destroy()

        ttk.Button(button_frame, text="保存", command=save_edit).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=edit_dialog.destroy).pack(side=tk.RIGHT, padx=10)

    def delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的规则")
            return
        item = selected[0]
        values = self.tree.item(item, "values")
        obj_type, _ = values
        if not messagebox.askyesno("确认删除", f"确定要删除对象类型 '{obj_type}' 的规则？"):
            return
        if obj_type in self.rules:
            del self.rules[obj_type]
            self.populate_rules()

    def reset_defaults(self):
        if not messagebox.askyesno("确认重置", "确定要恢复为默认规则？"):
            return
        self.rules = DEFAULT_RULES.copy()
        self.populate_rules()

    def save_and_close(self):
        with open("rules.json", "w") as f:
            json.dump(self.rules, f, indent=2)
        self.destroy()


class CustomRelationDialog(tk.Toplevel):
    """自定义关系点对话框 - 改进版"""

    def __init__(self, parent, input_file, root_et, entity_classes, predicates, category_to_trackids, custom_relations):
        super().__init__(parent)
        self.parent = parent
        self.input_file = input_file
        self.root_et = root_et
        self.entity_classes = entity_classes
        self.predicates = predicates
        self.category_to_trackids = category_to_trackids
        self.custom_relations = custom_relations

        self.title("自定义关系点模式")
        self.geometry("650x550")

        self.temp_relations = []  # 临时存储本次添加的关系
        self.filtered_entity_classes = entity_classes[:]  # 实体类别过滤缓存
        self.filtered_predicates = predicates[:]  # 谓词过滤缓存

        self.create_widgets()

    def create_widgets(self):
        ttk.Label(self, text="添加自定义关系点", font=("Arial", 14, "bold")).pack(pady=10)

        # 使用notebook管理主体和客体输入
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.X, padx=10, pady=10)

        # 主体框架
        subject_frame = ttk.Frame(self.notebook)
        self.notebook.add(subject_frame, text="主体")

        # --- 主体输入区域 ---
        subject_input_frame = ttk.LabelFrame(subject_frame, text="主体选择")
        subject_input_frame.pack(fill=tk.X, padx=5, pady=5)

        # 选择方式标签
        ttk.Label(subject_input_frame, text="选择方式:").pack(side=tk.LEFT, padx=(0, 5))

        # 选择方式单选按钮
        self.subject_selector = tk.StringVar(value="by_class")

        rb_frame = ttk.Frame(subject_input_frame)
        rb_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Radiobutton(rb_frame, text="按类别", variable=self.subject_selector,
                        value="by_class", command=self.update_subject_inputs).pack(side=tk.LEFT)
        ttk.Radiobutton(rb_frame, text="直接输入ID", variable=self.subject_selector,
                        value="by_id", command=self.update_subject_inputs).pack(side=tk.LEFT, padx=(10, 0))

        # 主体类别输入区域
        self.subject_cls_frame = ttk.Frame(subject_frame)
        self.subject_cls_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(self.subject_cls_frame, text="实体类别 (输入筛选):").pack(side=tk.LEFT, padx=(0, 5))

        self.subject_cls_var = tk.StringVar()
        self.subject_cls_combo = ttk.Combobox(
            self.subject_cls_frame,
            textvariable=self.subject_cls_var,
            values=self.entity_classes
        )
        self.subject_cls_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.subject_cls_combo.bind("<KeyRelease>", self.on_subject_cls_keyrelease)
        self.subject_cls_combo.bind("<<ComboboxSelected>>", self.on_subject_cls_change)

        # 主体类别选择后的ID选择
        self.subject_id_frame = ttk.Frame(subject_frame)
        self.subject_id_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(self.subject_id_frame, text="选择主体ID:").pack(side=tk.LEFT, padx=(0, 5))

        self.subject_id_var = tk.StringVar()
        self.subject_id_combo = ttk.Combobox(
            self.subject_id_frame,
            textvariable=self.subject_id_var
        )
        self.subject_id_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.subject_id_combo.bind("<KeyRelease>", self.on_subject_id_keyrelease)

        # 直接输入ID的控件
        self.direct_id_frame = ttk.Frame(subject_frame)
        self.direct_id_frame.pack(fill=tk.X, padx=5, pady=5)
        self.direct_id_frame.pack_forget()  # 初始隐藏

        ttk.Label(self.direct_id_frame, text="输入主体ID:").pack(side=tk.LEFT, padx=(0, 5))

        self.subject_direct_id_var = tk.StringVar()
        ttk.Entry(self.direct_id_frame, textvariable=self.subject_direct_id_var).pack(side=tk.LEFT, fill=tk.X,
                                                                                      expand=True)

        # 初始化输入状态
        self.update_subject_inputs()

        # --- 客体框架 ---
        object_frame = ttk.Frame(self.notebook)
        self.notebook.add(object_frame, text="客体")

        # 客体类别输入
        object_cls_frame = ttk.Frame(object_frame)
        object_cls_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(object_cls_frame, text="客体类别 (输入筛选):").pack(side=tk.LEFT, padx=(0, 5))

        self.object_cls_var = tk.StringVar()
        self.object_cls_combo = ttk.Combobox(
            object_cls_frame,
            textvariable=self.object_cls_var,
            values=self.entity_classes
        )
        self.object_cls_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.object_cls_combo.bind("<KeyRelease>", self.on_object_cls_keyrelease)
        self.object_cls_combo.bind("<<ComboboxSelected>>", self.on_object_cls_change)

        # 客体ID选择
        object_id_frame = ttk.Frame(object_frame)
        object_id_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(object_id_frame, text="选择客体ID:").pack(side=tk.LEFT, padx=(0, 5))

        self.object_id_var = tk.StringVar()
        self.object_id_combo = ttk.Combobox(
            object_id_frame,
            textvariable=self.object_id_var
        )
        self.object_id_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.object_id_combo.bind("<KeyRelease>", self.on_object_id_keyrelease)

        # --- 谓词框架 ---
        pred_frame = ttk.Frame(self.notebook)
        self.notebook.add(pred_frame, text="谓词")

        pred_input_frame = ttk.Frame(pred_frame)
        pred_input_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(pred_input_frame, text="选择谓词 (输入筛选):").pack(side=tk.LEFT, padx=(0, 5))

        self.pred_var = tk.StringVar()
        self.pred_combo = ttk.Combobox(
            pred_input_frame,
            textvariable=self.pred_var,
            values=self.predicates
        )
        self.pred_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pred_combo.bind("<KeyRelease>", self.on_pred_keyrelease)

        # --- 添加到列表按钮和临时关系列表 ---
        add_btn = ttk.Button(self, text="添加到列表", width=12, command=self.on_add)
        add_btn.pack(pady=(10, 0))

        cols = ("subject_id", "object_id", "predicate")
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        self.tree.heading("subject_id", text="主体 ID")
        self.tree.heading("object_id", text="客体 ID")
        self.tree.heading("predicate", text="谓词")
        self.tree.column("subject_id", width=80, anchor=tk.CENTER)
        self.tree.column("object_id", width=80, anchor=tk.CENTER)
        self.tree.column("predicate", width=180, anchor=tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # "删除选中"按钮
        del_btn = ttk.Button(self, text="删除选中关系", width=15, command=self.on_delete)
        del_btn.pack(pady=(0, 5))

        # "确定"和"取消"按钮
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill=tk.X, pady=10, padx=10)
        confirm_btn = ttk.Button(bottom_frame, text="确定", width=12, command=self.on_confirm)
        confirm_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = ttk.Button(bottom_frame, text="取消", width=12, command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

    def update_subject_inputs(self):
        """根据选择方式更新主体输入界面"""
        if self.subject_selector.get() == "by_class":
            self.subject_cls_frame.pack(fill=tk.X, padx=5, pady=5)
            self.subject_id_frame.pack(fill=tk.X, padx=5, pady=5)
            self.direct_id_frame.pack_forget()
        else:
            self.subject_cls_frame.pack_forget()
            self.subject_id_frame.pack_forget()
            self.direct_id_frame.pack(fill=tk.X, padx=5, pady=5)

    def get_filtered_items(self, input_text, full_list):
        """获取过滤后的项列表"""
        if not input_text:
            return full_list[:]
        return [item for item in full_list if input_text.lower() in item.lower()]

    def set_combo_values(self, combo, values):
        """安全设置下拉框值并重置"""
        current_val = combo.get()
        combo['values'] = values
        combo.set(current_val)

        # 输入长度>0且匹配项>0时自动弹出
        if len(current_val) > 0 and len(values) > 0:
            combo.event_generate('<Down>')

    # ====== 键盘事件处理函数 ======

    def on_subject_cls_keyrelease(self, event):
        """主体类别键盘释放事件"""
        input_text = self.subject_cls_var.get().strip().lower()
        self.filtered_entity_classes = self.get_filtered_items(input_text, self.entity_classes)
        self.set_combo_values(self.subject_cls_combo, self.filtered_entity_classes)

    def on_subject_cls_change(self, event=None):
        """主体类别变化事件"""
        chosen_cls = self.subject_cls_var.get().strip().lower()
        if chosen_cls and chosen_cls in self.category_to_trackids:
            track_ids = self.category_to_trackids[chosen_cls]
            # 显示+1后的ID（CVAT显示值）
            display_ids = [str(int(i) + 1) for i in track_ids]
            self.set_combo_values(self.subject_id_combo, display_ids)
        else:
            self.subject_id_combo['values'] = []

    def on_subject_id_keyrelease(self, event):
        """主体ID键盘释放事件"""
        input_text = self.subject_id_var.get().strip().lower()
        current_values = self.subject_id_combo['values']
        filtered = self.get_filtered_items(input_text, current_values)
        self.set_combo_values(self.subject_id_combo, filtered)

    def on_object_cls_keyrelease(self, event):
        """客体类别键盘释放事件"""
        input_text = self.object_cls_var.get().strip().lower()
        self.filtered_entity_classes = self.get_filtered_items(input_text, self.entity_classes)
        self.set_combo_values(self.object_cls_combo, self.filtered_entity_classes)

    def on_object_cls_change(self, event=None):
        """客体类别变化事件"""
        chosen_cls = self.object_cls_var.get().strip().lower()
        if chosen_cls and chosen_cls in self.category_to_trackids:
            track_ids = self.category_to_trackids[chosen_cls]
            display_ids = [str(int(i) + 1) for i in track_ids]
            self.set_combo_values(self.object_id_combo, display_ids)
        else:
            self.object_id_combo['values'] = []

    def on_object_id_keyrelease(self, event):
        """客体ID键盘释放事件"""
        input_text = self.object_id_var.get().strip().lower()
        current_values = self.object_id_combo['values']
        filtered = self.get_filtered_items(input_text, current_values)
        self.set_combo_values(self.object_id_combo, filtered)

    def on_pred_keyrelease(self, event):
        """谓词键盘释放事件"""
        input_text = self.pred_var.get().strip().lower()
        self.filtered_predicates = self.get_filtered_items(input_text, self.predicates)
        self.set_combo_values(self.pred_combo, self.filtered_predicates)

    # ====== 按钮事件处理函数 ======

    def on_add(self):
        """添加关系按钮事件"""
        # 获取主体ID
        if self.subject_selector.get() == "by_class":
            subj_id = self.subject_id_var.get().strip()
            if not subj_id:
                messagebox.showerror("错误", "请选择主体类别并指定主体ID")
                return
        else:
            subj_id = self.subject_direct_id_var.get().strip()
            if not subj_id:
                messagebox.showerror("错误", "请输入主体ID")
                return
            try:
                int(subj_id)  # 验证是数字
            except ValueError:
                messagebox.showerror("错误", "主体ID必须是数字")
                return

        # 获取客体ID
        obj_id = self.object_id_var.get().strip()
        if not obj_id:
            messagebox.showerror("错误", "请选择客体类别并指定客体ID")
            return
        try:
            int(obj_id)  # 验证是数字
        except ValueError:
            messagebox.showerror("错误", "客体ID必须是数字")
            return

        # 获取谓词
        pred = self.pred_var.get().strip()
        if not pred:
            messagebox.showerror("错误", "请选择或输入谓词")
            return

        # 添加到临时列表和树视图
        self.tree.insert("", tk.END, values=(subj_id, obj_id, pred))
        self.temp_relations.append((subj_id, obj_id, pred))

        # 清空输入控件
        self.subject_id_var.set('')
        self.subject_direct_id_var.set('')
        self.object_id_var.set('')
        self.pred_var.set('')

        # 重置下拉框到完整列表
        self.subject_id_combo['values'] = []
        self.object_id_combo['values'] = []
        self.filtered_predicates = self.predicates[:]
        self.set_combo_values(self.pred_combo, self.filtered_predicates)

        # 焦点回到主体选择
        self.notebook.select(0)
        self.subject_cls_combo.focus_set()

    def on_delete(self):
        """删除选中行"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要删除的行")
            return
        for it in sel:
            vals = self.tree.item(it, "values")
            if tuple(vals) in self.temp_relations:
                self.temp_relations.remove(tuple(vals))
            self.tree.delete(it)

    def on_confirm(self):
        """确认按钮事件"""
        for subj, obj, pred in self.temp_relations:
            # 转换为XML存储格式（显示ID-1）
            subj_id = str(int(subj) - 1)
            obj_id = str(int(obj) - 1)

            if subj_id not in self.custom_relations:
                self.custom_relations[subj_id] = []
            self.custom_relations[subj_id].append((obj_id, pred))

        messagebox.showinfo("提示", "自定义关系已记录，稍后执行自动标注时会一起写入到输出文件")
        self.destroy()