import json
import os
import pandas as pd
from tkinter import messagebox

# 标签配置文件
LABELS_CONFIG_FILE = "labels_config.json"


def load_labels_config():
    """
    加载实体类别与谓词配置
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


def import_labels_config(file_path):
    """
    从Excel/CSV导入标签配置
    """
    try:
        # Excel处理逻辑
        if file_path.lower().endswith((".xlsx", ".xls")):
            xls = pd.read_excel(file_path, sheet_name=None)
            sheets = list(xls.keys())
            if len(sheets) < 2:
                return False, "Excel文件至少需要两个sheet：第1个sheet包含实体类别，第2个sheet包含谓词列表。"

            df_entities = xls[sheets[0]]
            df_predicates = xls[sheets[1]]
        # CSV处理逻辑
        else:
            df_entities = None
            df_predicates = pd.read_csv(file_path, encoding="utf-8")

        # 从数据框中提取实体类别
        new_entity_classes = []
        if df_entities is not None:
            for col in df_entities.columns:
                if 'entity' in col.lower() or 'class' in col.lower():
                    new_entity_classes = df_entities[col].dropna().astype(str).tolist()
                    break

        # 从数据框中提取谓词
        new_predicates = []
        for col in df_predicates.columns:
            if 'predicate' in col.lower() or 'relation' in col.lower():
                new_predicates = df_predicates[col].dropna().astype(str).tolist()
                break

        return True, (new_entity_classes, new_predicates)

    except Exception as ex:
        return False, f"导入失败: {str(ex)}"


def clear_labels_config():
    """清空标签配置"""
    if os.path.exists(LABELS_CONFIG_FILE):
        try:
            os.remove(LABELS_CONFIG_FILE)
        except:
            pass
    return [], []