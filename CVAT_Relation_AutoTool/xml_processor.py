import os
import shutil
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
from config import DEFAULT_CONFIG


def backup_file(file_path):
    """备份XML文件"""
    if not os.path.exists(file_path):
        return file_path

    backup_dir = os.path.join(os.path.dirname(file_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{file_name}_backup_{timestamp}.xml")

    shutil.copyfile(file_path, backup_path)
    return backup_path


def process_xml_file(xml_path, output_path, rules, config, custom_relations=None, progress_callback=None):
    """
    处理XML文件的核心逻辑
    """
    try:
        # 备份文件
        if config.get("backup_original", True):
            backup_path = backup_file(xml_path)
            if progress_callback:
                progress_callback(5, f"完成备份: {os.path.basename(backup_path)}")

        # 解析XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 计算最大track ID
        track_ids = [int(track.get('id')) for track in root.findall('track')]
        max_id = max(track_ids) if track_ids else -1

        # 识别已有的关系点
        existing_relations = set()
        for track in root.findall('track'):
            if track.get('label') == "Relation":
                for points in track.findall('points'):
                    for attr in points.findall('attribute'):
                        if attr.get('name') == 'subject_id':
                            existing_relations.add(attr.text)
                            break

        # 添加自动关系点
        processed_count, added_count = add_auto_relations(root, rules, config, existing_relations, max_id,
                                                          progress_callback)
        added_count += add_custom_relations(root, custom_relations, max_id)

        # 保存处理后的XML
        xml_str = ET.tostring(root, encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
        with open(output_path, 'wb') as f:
            f.write(pretty_xml)

        return True, f"处理完成: {processed_count} 个主体，添加 {added_count} 个关系点"

    except Exception as e:
        return False, f"处理错误: {str(e)}"


def add_auto_relations(root, rules, config, existing_relations, max_id, progress_callback=None):
    """添加自动关系点"""
    all_tracks = [t for t in root.findall('track') if t.get('label') != "Relation"]
    total_tracks = len(all_tracks)
    processed = 0
    added_count = 0

    for track in all_tracks:
        label = track.get('label').lower()
        track_id = track.get('id')
        boxes = track.findall('box')

        if not boxes or (track_id in existing_relations and config.get("skip_existing", True)):
            processed += 1
            continue

        max_id += 1
        relation_track = create_relation_track(max_id, track_id, boxes, rules, label)
        root.append(relation_track)
        added_count += 1
        processed += 1

        if progress_callback:
            progress = int(processed / total_tracks * 90) + 5
            progress_callback(progress, f"添加关系: {label} (ID:{track_id})")

    return processed, added_count


def create_relation_track(track_id, subject_id, boxes, rules, label):
    """创建关系轨迹"""
    # 确定谓词
    predicate = next((rule_value for rule_key, rule_value in rules.items()
                      if rule_key.lower() in label), "")

    # 创建轨迹元素
    relation_track = ET.Element('track', {
        'id': str(track_id),
        'label': "Relation",
        'source': "auto-generated"
    })

    # 添加关系点
    for i, box in enumerate(boxes):
        # 计算中心点坐标
        xtl, ytl, xbr, ybr = map(float, (box.get(attr) for attr in ['xtl', 'ytl', 'xbr', 'ybr']))
        x_center, y_center = (xtl + xbr) / 2, (ytl + ybr) / 2

        # 创建点元素
        points_elem = ET.Element('points', {
            'frame': box.get('frame'),
            'keyframe': box.get('keyframe', '1'),
            'outside': box.get('outside'),
            'occluded': box.get('occluded', "0"),
            'points': f"{x_center:.2f},{y_center:.2f}",
            'z_order': "0"
        })

        # 添加属性
        ET.SubElement(points_elem, 'attribute', {'name': 'predicate'}).text = predicate
        ET.SubElement(points_elem, 'attribute', {'name': 'subject_id'}).text = subject_id
        ET.SubElement(points_elem, 'attribute', {'name': 'object_id'}).text = ''

        relation_track.append(points_elem)

    return relation_track


def add_custom_relations(root, custom_relations, max_id):
    """添加自定义关系点"""
    added_count = 0
    if not custom_relations:
        return added_count

    for subj_id, rel_list in custom_relations.items():
        subj_track = root.find(f"./track[@id='{subj_id}']")
        if not subj_track:
            continue

        boxes = subj_track.findall('box')
        if not boxes:
            continue

        for obj_id, pred in rel_list:
            max_id += 1
            rel_track = create_custom_relation_track(max_id, subj_id, obj_id, pred, boxes)
            root.append(rel_track)
            added_count += 1

    return added_count


def create_custom_relation_track(track_id, subj_id, obj_id, predicate, boxes):
    """创建自定义关系轨迹"""
    rel_track = ET.Element('track', {
        'id': str(track_id),
        'label': "Relation",
        'source': "custom"
    })

    for box in boxes:
        # 计算中心点坐标
        xtl, ytl, xbr, ybr = map(float, (box.get(attr) for attr in ['xtl', 'ytl', 'xbr', 'ybr']))
        x_center, y_center = (xtl + xbr) / 2, (ytl + ybr) / 2

        # 创建点元素
        pt_elem = ET.Element('points', {
            'frame': box.get('frame'),
            'keyframe': box.get('keyframe', '1'),
            'outside': box.get('outside'),
            'occluded': box.get('occluded', "0"),
            'points': f"{x_center:.2f},{y_center:.2f}",
            'z_order': "0"
        })

        # 添加属性
        ET.SubElement(pt_elem, 'attribute', {'name': 'predicate'}).text = predicate
        ET.SubElement(pt_elem, 'attribute', {'name': 'subject_id'}).text = subj_id
        ET.SubElement(pt_elem, 'attribute', {'name': 'object_id'}).text = obj_id

        rel_track.append(pt_elem)

    return rel_track