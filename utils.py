import os
import pandas as pd
from datetime import datetime


def generate_output_path(input_path):
    """生成输出文件路径"""
    dir_name = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(dir_name, f"{base_name}_{timestamp}.xml")


def parse_xml_for_categories(xml_path):
    """解析XML文件，获取类别到track ID的映射"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        category_map = {}

        for track in root.findall('track'):
            if track.get('label') and track.get('label') != "Relation":
                cls_name = track.get('label').lower()
                category_map.setdefault(cls_name, []).append(track.get('id'))

        return tree, root, category_map

    except Exception as e:
        return None, None, {}