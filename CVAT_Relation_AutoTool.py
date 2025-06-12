import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import threading
import json
import webbrowser
import shutil
from datetime import datetime
# --------- 如果要读取 Excel，需要导入 pandas ---------
import pandas as pd  # pip install pandas openpyxl

# -------------------------------------------------------

# 在全局定义一个配置文件名，用于保存"实体类别 + 谓词列表"
LABELS_CONFIG_FILE = "labels_config.json"
# 默认规则
DEFAULT_RULES = {
    "bike": "parked on",
    "car": "parked on",
    "people": "walked on",
    "air conditioning": "mounted on",
    "air condition": "mounted on",
    "manhole cover": "on",
    "motorcycle": "parked on",
    "truck": "parked on",
    "van": "parked on",
    "person": "walked on",
    "pedestrian": "walked on",
    "cyclist": "walked on"
}

# 默认配置
DEFAULT_CONFIG = {
    "auto_sync_lifecycle": True,
    "auto_generate_output": True,
    "backup_original": True,
    "skip_existing": True
}


def load_labels_config():
    """
    如果当前目录存在 labels_config.json，就从里面读取 entity_classes 与 predicates 两个列表，
    并返回 (entity_classes, predicates)。否则返回 ([], [])。
    """
    if os.path.exists(LABELS_CONFIG_FILE):
        try:
            with open(LABELS_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("entity_classes", []), data.get("predicates", [])
        except Exception:
            return [], []
    else:
        return [], []


def save_labels_config(entity_classes, predicates):
    """
    将 entity_classes（列表）和 predicates（列表）写入 labels_config.json。
    """
    data = {
        "entity_classes": entity_classes,
        "predicates": predicates
    }
    with open(LABELS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    """加载配置"""
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
    except:
        pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存配置"""
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)


def load_rules():
    """加载规则配置"""
    try:
        if os.path.exists("rules.json"):
            with open("rules.json", "r") as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_RULES.copy()


def save_rules(rules):
    """保存规则配置"""
    with open("rules.json", "w") as f:
        json.dump(rules, f, indent=2)


def backup_file(file_path):
    """拷贝初始文件"""
    if not os.path.exists(file_path):
        return file_path

    backup_dir = os.path.join(os.path.dirname(file_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{file_name}_backup_{timestamp}.xml")

    shutil.copyfile(file_path, backup_path)
    return backup_path


def add_relation_points(xml_path, output_path, rules, config,
                        custom_relations=None, progress_callback=None):
    """
    为已有标注文件添加自动关系点，并根据 custom_relations 参数
    添加用户自定义关系点。custom_relations: {subject_id: [(object_id, predicate), ...], ...}
    """
    if custom_relations is None:
        custom_relations = {}

    try:
        # 备份原始文件
        if config.get("backup_original", True):
            backup_path = backup_file(xml_path)
            if progress_callback:
                progress_callback(5, f"完成备份: {os.path.basename(backup_path)}")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 获取当前最大 track ID
        track_ids = [int(track.get('id')) for track in root.findall('track')]
        max_id = max(track_ids) if track_ids else -1

        # 记录已有关系 track 中的 subject_id，以免重复自动生成
        existing_relations = set()
        for track in root.findall('track'):
            if track.get('label') == "Relation":
                for points in track.findall('points'):
                    subject_id = None
                    for attr in points.findall('attribute'):
                        if attr.get('name') == 'subject_id':
                            subject_id = str(int(attr.text) + 1)
                            break
                    if subject_id:
                        existing_relations.add(subject_id)

        # 统计需要处理的非 Relation track 数量
        all_tracks = [t for t in root.findall('track') if t.get('label') != "Relation"]
        total_tracks = len(all_tracks)
        processed = 0
        added_count = 0

        # 自动生成每个 track 的关系点（如果尚未存在）
        for track in all_tracks:
            label = track.get('label').lower()
            track_id = track.get('id')
            boxes = track.findall('box')
            if not boxes:
                processed += 1
                continue

            if track_id in existing_relations and config.get("skip_existing", True):
                processed += 1
                if progress_callback:
                    progress = int(processed / total_tracks * 90) + 5
                    progress_callback(progress, f"跳过已有关系: {label} (ID:{track_id})")
                continue

            # 创建新的 Relation track
            max_id += 1
            relation_track = ET.Element('track', {
                'id': str(max_id),
                'label': "Relation",
                'source': "auto-generated"
            })
            relation_track.text = "\n    "

            # 确定 predicate
            predicate = ""
            for rule_key, rule_value in rules.items():
                if rule_key.lower() in label:
                    predicate = rule_value
                    break

            last_point = None
            for i, box in enumerate(boxes):
                frame = box.get('frame')
                outside = box.get('outside')
                occluded = box.get('occluded')
                keyframe = box.get('keyframe', '1')

                xtl = float(box.get('xtl'))
                ytl = float(box.get('ytl'))
                xbr = float(box.get('xbr'))
                ybr = float(box.get('ybr'))
                x_center = (xtl + xbr) / 2
                y_center = (ytl + ybr) / 2

                points_elem = ET.Element('points', {
                    'frame': frame,
                    'keyframe': keyframe,
                    'outside': outside,
                    'occluded': occluded if occluded is not None else "0",
                    'points': f"{x_center:.2f},{y_center:.2f}",
                    'z_order': "0"
                })

                predicate_attr = ET.SubElement(points_elem, 'attribute', {'name': 'predicate'})
                predicate_attr.text = predicate

                subject_id_attr = ET.SubElement(points_elem, 'attribute', {'name': 'subject_id'})
                subject_id_attr.text = track_id

                object_id_attr = ET.SubElement(points_elem, 'attribute', {'name': 'object_id'})
                object_id_attr.text = ''

                if i > 0:
                    last_point.tail = "\n    "
                points_elem.tail = "\n    " if i < len(boxes) - 1 else "\n  "

                relation_track.append(points_elem)
                last_point = points_elem

            root.append(relation_track)
            relation_track.tail = "\n\n" if root[-1] == relation_track else "\n"
            added_count += 1

            processed += 1
            if progress_callback:
                progress = int(processed / total_tracks * 90) + 5
                progress_callback(progress, f"添加自动关系: {label} (ID:{track_id})")

        # 处理用户自定义关系
        # custom_relations: {subject_id: [(object_id, predicate), ...], ...}
        for subj_id, rel_list in custom_relations.items():
            # 找到对应的主体 track
            subj_track = root.find(f"./track[@id='{subj_id}']")
            if subj_track is None:
                continue
            boxes = subj_track.findall('box')
            if not boxes:
                continue

            for (obj_id, pred) in rel_list:
                max_id += 1
                rel_track = ET.Element('track', {
                    'id': str(max_id),
                    'label': "Relation",
                    'source': "custom"
                })
                rel_track.text = "\n    "

                last_pt = None
                # 为主体生命周期内每一帧添加自定义关系点
                for i, box in enumerate(boxes):
                    frame = box.get('极frame')
                    outside = box.get('outside')
                    occluded = box.get('occluded')
                    keyframe = box.get('keyframe', '1')

                    xtl = float(box.get('xtl'))
                    ytl = float(box.get('ytl'))
                    xbr = float(box.get('xbr'))
                    ybr = float(box.get('ybr'))
                    x_center = (xtl + xbr) / 2
                    y_center = (ytl + ybr) / 2

                    pt_elem = ET.Element('points', {
                        'frame': frame,
                        'keyframe': keyframe,
                        'outside': outside,
                        'occluded': occluded if occluded is not None else "0",
                        'points': f"{x_center:.2f},{y_center:.2f}",
                        'z_order': "0"
                    })

                    pred_attr = ET.SubElement(pt_elem, 'attribute', {'name': 'predicate'})
                    pred_attr.text = pred

                    subj_attr = ET.SubElement(pt_elem, 'attribute', {'name': 'subject_id'})
                    subj_attr.text = subj_id

                    obj_attr = ET.SubElement(pt_elem, 'attribute', {'name': 'object_id'})
                    obj_attr.text = str(obj_id)

                    if i > 0:
                        last_pt.tail = "\n    "
                    pt_elem.tail = "\n    " if i < len(boxes) - 1 else "\n  "

                    rel_track.append(pt_elem)
                    last_pt = pt_elem

                root.append(rel_track)
                rel_track.tail = "\n\n" if root[-1] == rel_track else "\n"
                added_count += 1

        # 生成格式化 XML
        xml_str = ET.tostring(root, encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
        pretty_xml = b'\n'.join([line for line in pretty_xml.splitlines() if line.strip()])

        with open(output_path, 'wb') as f:
            f.write(pretty_xml)

        return True, f"总共处理 {total_tracks} 个主体，添加关系轨迹共 {added_count} 个"

    except Exception as e:
        return False, f"处理出现错误: {str(e)}"


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
        save_config(self.result_config)
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
        save_rules(self.rules)
        self.destroy()


class XMLRelationApp:
    """主应用程序"""

    def __init__(self, root):
        self.root = root
        self.root.title("CVAT 关系自动标注工具 v3.1")
        self.root.geometry("800x650")

        # 加载配置和规则
        self.config = load_config()
        self.rules = load_rules()

        # ==================== 2. 初始化"自定义关系"缓存 ====================
        # custom_relations 用于存放用户在对话框里手动添加的关系：
        # { subject_id: [(object_id, predicate), (object_id2, predicate2), ...], ... }
        self.custom_relations = {}
        # ==================== 3. 从 labels_config.json 加载"实体类别 & 谓词"列表 ====================
        # load_labels_config() 应返回 (entity_classes, predicates)，
        # 例如 ["bike", "wall", ...], ["above", "at", ...]
        self.entity_classes, self.predicates = load_labels_config()
        # ==================== 4. 准备一个"类别 → [track_id1, track_id2, ...]"的映射字典 ====================
        # 当用户选择了某个 XML 文件后，我们会在 browse_input() 里更新这个字典。
        # 目前先初始化为空，等 browse_input 解析完 XML 之后再填充实际内容。
        self.category_to_trackids = {}

        # ==================== 5. 用来保存当前解析的 ElementTree ================
        # 解析完 XML 后会把整个 ElementTree、根节点暂存在这两个字段里，方便在"自定义关系"对话框中使用
        self.tree_et = None
        self.root_et = None

        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass

        # 创建菜单栏（用于"自定义关系点模式"）
        self.create_menu()
        # -------------- 创建菜单栏：加"导入标签配置" --------------
        menubar = tk.Menu(self.root)

        relation_menu = tk.Menu(menubar, tearoff=0)
        relation_menu.add_command(label="进入自定义关系点模式",
                                  command=self.open_custom_relation_dialog)
        menubar.add_cascade(label="自定义关系", menu=relation_menu)

        # 新增：导入"Excel 标签配置"的菜单
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="导入标签配置 (Excel/CSV)", command=self.import_labels_config)
        config_menu.add_command(label="清空已有标签配置", command=self.clear_labels_config)
        menubar.add_cascade(label="标签配置", menu=config_menu)

        self.root.config(menu=menubar)
        # 创建样式
        self.create_styles()

        # 创建主界面
        self.create_widgets()

        self.input_file = ""
        self.output_file = ""

    # ========== 导入标签配置 ==========
    def import_labels_config(self):
        """
        弹出文件对话框，让用户选择一个 Excel (或 CSV) 文件来导入实体类别列表 & 谓词列表
        假设 Excel 文件中至少有两列：
          - 实体类别表：列名包含 'entity' 或 'class'，例如 "Index | EntityCategory | Definition"
          - 关系谓词表：极名包含 'predicate' 或 'relation'，例如 "Index | Predicate | Definition"
        下面示例强制要求：第一个 sheet 是"实体类别表"，第二个 sheet 是"谓词表"。
        """
        file_path = filedialog.askopenfilename(
            title="选择 Excel/CSV 文件以导入实体类别与谓词",
            filetypes=[("Excel 文件", "*.xlsx;*.xls"), ("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            # 如果是 Excel，则 read_excel；如果是 CSV，则 read_csv
            if file_path.lower().endswith((".xlsx", ".xls")):
                # 默认第一个 sheet 是实体类别表；第二个 sheet 是谓词表
                xls = pd.read_excel(file_path, sheet_name=None)  # 读取所有 sheet
                sheets = list(xls.keys())
                if len(sheets) < 2:
                    messagebox.showerror("导入失败",
                                         "Excel 文件至少需要两个 sheet：\n第1个sheet包含实体类别，第2个sheet包含谓词列表。")
                    return

                df_entities = xls[sheets[0]]
                df_predicates = xls[sheets[1]]
            else:
                # 如果是 .csv，我们假设两个文件分开存储：第一行带 'Entity'，第二行带 'Predicate'
                # 示例：CSV 第一行为"entity..."，第二行为"predicate..." —— 这里简化处理。
                # 最简单的做法是：让用户先把 Excel 转成两个单独 CSV，再分别导入。
                # 下面假设这个 CSV 仅包含"谓词表"。
                df_entities = None
                df_predicates = pd.read_csv(file_path, encoding="utf-8")
            # 从 df_entities 中提取"实体类别"这一列（列名包含 'entity' 或 'class'）
            if df_entities is not None:
                # 自动寻找列名，例如如果列名里包含 'entity' 或 'class'
                found_entity_col = None
                for col in df_entities.columns:
                    if 'entity' in col.lower() or 'class' in col.lower():
                        found_entity_col = col
                        break
                if not found_entity_col:
                    messagebox.showerror("导入失败", "在第一个 sheet 中未找到列名包含 'entity' 或 'class' 的列。")
                    return
                # 提取非空且去重的实体类别列表
                new_entity_classes = df_entities[found_entity_col].dropna().astype(str).tolist()
            else:
                new_entity_classes = []

            # 从 df_predicates 中提取"谓词"这一列（列名包含 'predicate' 或 'relation'）
            found_pred_col = None
            for col in df_predicates.columns:
                if 'predicate' in col.lower() or 'relation' in col.lower():
                    found_pred_col = col
                    break
            if not found_pred_col:
                messagebox.showerror("导入失败",
                                     "在第二个 sheet (或 CSV) 中未找到列名包含 'predicate' 或 'relation' 的列。")
                return
            new_predicates = df_predicates[found_pred_col].dropna().astype(str).tolist()

            # 保存到 JSON 配置文件
            save_labels_config(new_entity_classes, new_predicates)
            # 同步更新程序内存
            self.entity_classes = new_entity_classes
            self.predicates = new_predicates
            messagebox.showinfo("提示", f"成功导入 {len(new_entity_classes)} 个实体类别，{len(new_predicates)} 个谓词。")
        except Exception as ex:
            messagebox.showerror("导入失败", f"读取 Excel/CSV 时出错：\n{ex}")

    def clear_labels_config(self):
        """清空已有的标签配置文件，并重置内存中的列表为空"""
        if os.path.exists(LABELS_CONFIG_FILE):
            try:
                os.remove(LABELS_CONFIG_FILE)
            except:
                pass
        self.entity_classes = []
        self.predicates = []
        messagebox.showinfo("提示", "已清空标签配置，下次重启程序需要重新导入。")

    def create_menu(self):
        """创建菜单栏，添加"自定义关系点模式" """
        menubar = tk.Menu(self.root)
        relation_menu = tk.Menu(menubar, tearoff=0)
        relation_menu.add_command(label="进入自定义关系点模式", command=self.open_custom_relation_dialog)
        menubar.add_cascade(label="自定义关系", menu=relation_menu)
        self.root.config(menu=menubar)

    def create_styles(self):
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")
        style.configure("Header.TLabel",
                        font=("Arial", 16, "bold"),
                        background="#4a86e8",
                        foreground="#333333",
                        padding=10)
        style.configure("TButton", padding=6)
        style.configure("Action.TButton",
                        font=("Arial", 10, "bold"),
                        background="#4a86e8",
                        foreground="#333333",
                        padding=8)
        style.configure("Secondary.TButton",
                        background="#5b9bd5",
                        foreground="#333333")
        style.configure("Tertiary.TButton",
                        background="#6d9eeb",
                        foreground="#333333")
        style.configure("Status.TLabel",
                        font=("Arial", 9),
                        background="#e0e0e0",
                        foreground="#333333",
                        padding=5)
        style.configure("Progress.Horizontal.TProgressbar",
                        background="#4a86e8",
                        troughcolor="#e0e0e0")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame,
                  text="CVAT 关系自动标注工具",
                  style="Header.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(header_frame,
                   text="帮助",
                   command=self.show_help,
                   width=8,
                   style="Tertiary.TButton").pack(side=tk.RIGHT, padx=5)

        ttk.Button(header_frame,
                   text="配置",
                   command=self.open_config,
                   width=8,
                   style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)

        ttk.Button(header_frame,
                   text="管理规则",
                   command=self.manage_rules,
                   width=10,
                   style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)

        # 文件输入输出
        file_frame = ttk.LabelFrame(main_frame, text="文件设置")
        file_frame.pack(fill=tk.X, pady=10, padx=5)

        # 输入文件
        input_frame = ttk.Frame(file_frame)
        input_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(input_frame, text="CVAT XML 文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.input_entry = ttk.Entry(input_frame, width=50)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(input_frame,
                   text="浏览...",
                   command=self.browse_input,
                   width=8).pack(side=tk.RIGHT)

        # 输出文件
        output_frame = ttk.Frame(file_frame)
        output_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(output_frame, text="输出 XML 文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.output_entry = ttk.Entry(output_frame, width=50)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(output_frame,
                   text="浏览...",
                   command=self.browse_output,
                   width=8).pack(side=tk.RIGHT)

        # 处理按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        self.process_button = ttk.Button(button_frame,
                                         text="执行自动标注",
                                         command=self.start_processing,
                                         style="Action.TButton",
                                         width=20)
        self.process_button.pack(pady=10, ipady=5)

        # 进度显示
        progress_frame = ttk.LabelFrame(main_frame, text="处理进度")
        progress_frame.pack(fill=tk.X, pady=10, padx=5)

        self.progress_bar = ttk.Progressbar(progress_frame,
                                            orient=tk.HORIZONTAL,
                                            length=100,
                                            mode='determinate',
                                            style="Progress.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(progress_frame,
                                      text="准备就绪，请选择 CVAT XML 文件",
                                      style="Status.TLabel")
        self.status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 规则预览
        rule_frame = ttk.LabelFrame(main_frame, text="当前规则预览")
        rule_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)

        columns = ("object_type", "predicate")
        self.rule_tree = ttk.Treeview(rule_frame,
                                      columns=columns,
                                      show="headings",
                                      height=6)
        self.rule_tree.heading("object_type", text="对象类型", anchor=tk.W)
        self.rule_tree.heading("predicate", text="谓词", anchor=tk.W)
        self.rule_tree.column("object_type", width=250, stretch=tk.YES)
        self.rule_tree.column("predicate", width=250, stretch=tk.YES)

        scrollbar = ttk.Scrollbar(rule_frame, orient=tk.VERTICAL, command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=scrollbar.set)

        self.rule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.populate_rule_preview()

        # 状态栏
        status_bar = ttk.Frame(self.root, height=25, style="Status.TLabel")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar,
                  text='CVAT 关系自动标注工具 v3.0 | 点击"自定义关系"菜单以添加手动关系标注',
                  style="Status.TLabel").pack(side=tk.LEFT, padx=10)

    def populate_rule_preview(self):
        """展示当前规则"""
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        for obj_type, predicate in self.rules.items():
            self.rule_tree.insert("", tk.END, values=(obj_type, predicate))

    def manage_rules(self):
        """打开规则管理窗口"""
        manager = RuleManager(self.root, self.rules)
        self.root.wait_window(manager)
        # 更新规则
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
            "   在使用自定义标注前可先在标签配置中导入标签配置。\n"
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
        """选择输入 XML 文件时，顺便更新 category_to_trackids"""
        file_path = filedialog.askopenfilename(
            filetypes=[("XML 文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            self.input_file = file_path
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, file_path)

            try:
                self.tree_et = ET.parse(self.input_file)
                self.root_et = self.tree_et.getroot()
            except Exception as e:
                messagebox.showerror("错误", f"解析 XML 文件失败：{e}")
                self.tree_et = None
                self.root_et = None
                return

            # 构建 “entity class name → [track_id1, track_id2, ...]” 映射
            # 假设每个 <track> 元素里有 label 属性，我们把它当成"类别名称"
            # 如果 label 大写/小写不一致，可转换成小写统一匹配
            self.category_to_trackids.clear()
            for track in self.root_et.findall('track'):
                if track.get('label') and track.get('label') != "Relation":
                    cls_name = track.get('label')
                    # 如果程序的 entity_classes 存储的是英文小写，可以做一下统一 lower() 比较
                    # 先把 label 也转成小写存储到字典里
                    cls_key = cls_name.lower()
                    if cls_key not in self.category_to_trackids:
                        self.category_to_trackids[cls_key] = []
                    self.category_to_trackids[cls_key].append(track.get('id'))

            # 自动生成输出路径
            if self.config.get('auto_generate_output', True):
                dir_name = os.path.dirname(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]  # 原始文件名（不带扩展）
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 比如：20250605_143210
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

    def update_progress(self, progress, message):
        """更新进度条与状态"""
        self.progress_bar['value'] = progress
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def start_processing(self):
        """开始执行自动标注任务"""
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

        processing_thread = threading.Thread(
            target=self.process_xml,
            args=(self.input_file, self.output_file)
        )
        processing_thread.daemon = True
        processing_thread.start()

    def process_xml(self, input_path, output_path):
        """后台线程：调用 add_relation_points 添加自动及自定义关系"""
        try:
            success, message = add_relation_points(
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

    def open_custom_relation_dialog(self):
        """弹出"自定义关系点模式" 对话框"""
        if not self.input_file or self.root_et is None:
            messagebox.showerror("错误", "请先选择并解析输入 XML 文件，再进入自定义关系点模式。")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("自定义关系点模式")
        dialog.geometry("650x550")

        ttk.Label(dialog, text="添加自定义关系点", font=("Arial", 14, "bold")).pack(pady=10)

        # 辅助函数：用于实时过滤Combobox的选项
        def filter_combobox_list(combobox: ttk.Combobox, full_list: list):
            """当用户在 combobox 里输入时，调用本函数实时过滤它的候选值"""
            txt = combobox.get().strip().lower()
            if not txt:
                combobox['values'] = full_list[:]
            else:
                filtered = [w for w in full_list if txt in w.lower()]
                combobox['values'] = filtered

        # --- 第一行：选择"实体类别"或直接输入 Track ID ---
        # 用一个 Frame 来放"小写检索 Combobox + 显示 Track ID 列表" 的控件
        row1 = ttk.Frame(dialog)
        row1.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(row1, text="主体类别 (输入字母筛选)：").pack(side=tk.LEFT, padx=(0, 5))

        # 1) 实体类别 Combobox，用户输入字母后下拉列表自动过滤 self.entity_classes
        subject_cls_var = tk.StringVar()
        subject_cls_combo = ttk.Combobox(row1, textvariable=subject_cls_var)
        subject_cls_combo['values'] = self.entity_classes[:]  # 全部类别列表
        subject_cls_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 2) 如果用户想直接输入 Track ID，也可以在旁边提供一个 Entry
        ttk.Label(row1, text=" 或 直接输入 Track ID:").pack(side=tk.LEFT, padx=(10, 5))
        subject_id_entry = ttk.Entry(row1, width=10)
        subject_id_entry.pack(side=tk.LEFT)

        # 当用户从"类别 Combobox"里选中某个类别后，我们可以自动填充"track IDs 列表"给他
        # 比如，弹出第三行的 Track ID 下拉菜单，里面只显示该类别对应的 track IDs
        def on_subject_cls_change(event=None):
            chosen_cls = subject_cls_var.get().strip().lower()
            if not chosen_cls:
                return
            # 如果在 category_to_trackids 里找到了，就把它的 track ID 列表提取出来
            if chosen_cls in self.category_to_trackids:
                track_ids = self.category_to_trackids[chosen_cls]
            else:
                track_ids = []
            # 把 track_ids 填到下面那行的 Combobox 中
            display_ids = [str(int(i) + 1) for i in track_ids]
            subject_id_combo['values'] = display_ids

        subject_cls_combo.bind("<<ComboboxSelected>>", on_subject_cls_change)
        subject_cls_combo.bind("<KeyRelease>", lambda e: filter_combobox_list(subject_cls_combo, self.entity_classes))

        # --- 第二行：如果上面选择了类别，这里可以列出该类别对应的 Track ID; 如果上面直接输入 Track ID，那么这里可选也可不选 ---
        row2 = ttk.Frame(dialog)
        row2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row2, text="从所选类别中选主体 ID:").pack(side=tk.LEFT, padx=(0, 5))
        subj_id_var = tk.StringVar()
        subject_id_combo = ttk.Combobox(row2, textvariable=subj_id_var)
        subject_id_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 它的值会在 on_subject_cls_change 中被更新

        # --- 第三行：客体类别选择 (输入字母筛选) ---
        row3 = ttk.Frame(dialog)
        row3.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row3, text="客体类别 (输入字母筛选):").pack(side=tk.LEFT, padx=(0, 5))

        object_cls_var = tk.StringVar()
        object_cls_combo = ttk.Combobox(row3, textvariable=object_cls_var)
        object_cls_combo['values'] = self.entity_classes[:]
        object_cls_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 当客体类别选择发生变化时，更新客体ID列表
        def on_object_cls_change(event=None):
            chosen_cls = object_cls_var.get().strip().lower()
            if not chosen_cls:
                return
            if chosen_cls in self.category_to_trackids:
                track_ids = self.category_to_trackids[chosen_cls]
            else:
                track_ids = []
            # 显示 +1 后的ID（CVAT显示的值）
            display_ids = [str(int(i) + 1) for i in track_ids]
            object_id_combo['values'] = display_ids

        object_cls_combo.bind("<<ComboboxSelected>>", on_object_cls_change)
        object_cls_combo.bind("<KeyRelease>", lambda e: filter_combobox_list(object_cls_combo, self.entity_classes))

        # --- 第四行：从客体类别中选择具体ID ---
        row4 = ttk.Frame(dialog)
        row4.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row4, text="从客体类别中选客体 ID:").pack(side=tk.LEFT, padx=(0, 5))

        object_id_var = tk.StringVar()
        object_id_combo = ttk.Combobox(row4, textvariable=object_id_var)
        object_id_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- 第五行：谓词 Combobox（可输入字母后自动过滤） ---
        row5 = ttk.Frame(dialog)
        row5.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row5, text="谓词 (Predicate)：").pack(side=tk.LEFT, padx=(0, 5))

        pred_var = tk.StringVar()
        pred_combo = ttk.Combobox(row5, textvariable=pred_var)
        pred_combo['values'] = self.predicates[:]
        pred_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        pred_combo.bind("<KeyRelease>", lambda e极: filter_combobox_list(pred_combo, self.predicates))

        # --- "添加到列表" 按钮 和 临时关系列表 Treeview ---
        add_btn = ttk.Button(dialog, text="添加到列表", width=12)
        add_btn.pack(pady=(10, 0))

        cols = ("subject_id", "object_id", "predicate")
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        tree.heading("subject_id", text="主体 ID")
        tree.heading("object_id", text="客体 ID")
        tree.heading("predicate", text="谓词")
        tree.column("subject_id", width=80, anchor=tk.CENTER)
        tree.column("object_id", width=80, anchor=tk.CENTER)
        tree.column("predicate", width=180, anchor=tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # "删除选中"按钮
        del_btn = ttk.Button(dialog, text="删除选中关系", width=15)
        del_btn.pack(pady=(0, 5))

        # "确定"和"取消"按钮
        bottom_frame = ttk.Frame(dialog)
        bottom_frame.pack(fill=tk.X, pady=10, padx=10)
        confirm_btn = ttk.Button(bottom_frame, text="确定", width=12)
        confirm_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = ttk.Button(bottom_frame, text="取消", width=12, command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # 用于临时保存本次对话框里用户添加的关系列表
        temp_relations = []  # 列表元素为 (subject_id, object_id, pred)

        # 绑定"添加到列表"回调
        def on_add():
            # 先获取"主体 ID"：如果用户在 subject_id_combo 中选了，就以它为准；
            # 否则，如果 user 在 subject_id_entry 输入了一个 track ID，就以输入框的为准
            subj_id = subj_id_var.get().strip()
            if not subj_id:
                subj_id = subject_id_entry.get().strip()
            if not subj_id:
                messagebox.showerror("错误", "请先指定主体 ID 或选择主体类别后从下拉列表中选择。")
                return

            # 客体ID - 直接从下拉菜单获取
            obj_id = object_id_var.get().strip()
            if not obj_id:
                messagebox.showerror("错误", "请从客体类别中选择客体 ID。")
                return

            # 谓词
            pred = pred_var.get().strip()
            if not pred:
                messagebox.showerror("错误", "请从谓词下拉框中选择或输入一个谓词。")
                return

            # 保存实际值（-1转换）
            tree.insert("", tk.END, values=(subj_id, obj_id, pred))
            temp_relations.append((subj_id, obj_id, pred))

            # 清空输入框，保留类别选择以便添加更多关系
            pred_var.set("")
            object_id_var.set("")

        add_btn.config(command=on_add)

        # 删除选中行
        def on_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择要删除的行。")
                return
            for it in sel:
                vals = tree.item(it, "values")
                if tuple(vals) in temp_relations:
                    temp_relations.remove(tuple(vals))
                tree.delete(it)

        del_btn.config(command=on_delete)

        # 点击"确定"后，把 temp_relations 写入 self.custom_relations
        def on_confirm():
            for subj, obj, pred in temp_relations:
                # 转换为XML存储格式，显示ID减1
                subj_id = str(int(subj) - 1)
                obj_id = str(int(obj) - 1)

                if subj_id not in self.custom_relations:
                    self.custom_relations[subj_id] = []
                self.custom_relations[subj_id].append((obj_id, pred))
            dialog.destroy()
            messagebox.showinfo("提示", "自定义关系已记录，稍后执行自动标注时会一起写入到输出文件。")

        confirm_btn.config(command=on_confirm)

    # ========== end of open_custom_relation_dialog ==========


if __name__ == "__main__":
    root = tk.Tk()
    app = XMLRelationApp(root)
    root.mainloop()