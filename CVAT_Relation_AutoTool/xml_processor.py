import os
import shutil
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import math
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

class PositionManager:
    """管理每个帧上关系点的位置"""
    def __init__(self, root):
        self.frame_points = {}
        for track in root.findall('track'):
            if track.get('label') == "Relation":
                for points in track.findall('points'):
                    frame = points.get('frame')
                    pt_str = points.get('points')
                    if frame and pt_str:
                        try:
                            x, y = map(float, pt_str.split(','))
                            self.add_point(frame, x, y)
                        except ValueError:
                            continue

    def add_point(self, frame, x, y):
        if frame not in self.frame_points:
            self.frame_points[frame] = set()
        self.frame_points[frame].add((x, y))

    def is_position_valid(self, frame, x, y, min_distance):
        if frame not in self.frame_points:
            return True
        for px, py in self.frame_points[frame]:
            distance = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            if distance < min_distance:
                return False
        return True

def calculate_priority_positions(left, top, right, bottom, width, height):
    """按优先级计算关系点位置：中心 > 四角 > 四边中点"""
    positions = []
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    positions.append((center_x, center_y))
    corner_offset = 5
    top_left = (left + corner_offset, top + corner_offset)
    positions.append(top_left)
    top_right = (right - corner_offset, top + corner_offset)
    positions.append(top_right)
    bottom_left = (left + corner_offset, bottom - corner_offset)
    positions.append(bottom_left)
    bottom_right = (right - corner_offset, bottom - corner_offset)
    positions.append(bottom_right)
    top_center = (center_x, top + corner_offset)
    positions.append(top_center)
    bottom_center = (center_x, bottom - corner_offset)
    positions.append(bottom_center)
    left_center = (left + corner_offset, center_y)
    positions.append(left_center)
    right_center = (right - corner_offset, center_y)
    positions.append(right_center)
    return positions

def create_custom_relation_track(track_id, subj_id, obj_id, predicate, boxes, position_manager, total_frames, all_tracks):
    """创建自定义关系轨迹（带优先级的位置选择），并确保关系点随主体或客体消亡而消亡"""
    rel_track = ET.Element('track', {
        'id': str(track_id),
        'label': "Relation",
        'source': "auto-generated"
    })
    added_points = False
    last_valid_frame = None
    obj_track = next((t for t in all_tracks if t.get('id') == obj_id), None)
    if not obj_track:
        return None
    obj_frame_states = {}
    for box in obj_track.findall('box'):
        frame = box.get('frame')
        outside = box.get('outside', '0')
        obj_frame_states[frame] = outside

    for box in boxes:
        frame = box.get('frame')
        try:
            frame_num = int(frame)
        except ValueError:
            continue
        if frame_num >= total_frames:
            continue
        subject_outside = box.get('outside', '0')
        if subject_outside == '1':
            continue
        obj_outside = obj_frame_states.get(frame, '1')
        if obj_outside == '1':
            continue
        xtl = float(box.get('xtl'))
        ytl = float(box.get('ytl'))
        xbr = float(box.get('xbr'))
        ybr = float(box.get('ybr'))
        left, top = min(xtl, xbr), min(ytl, ybr)
        right, bottom = max(xtl, xbr), max(ytl, ybr)
        width, height = right - left, bottom - top
        min_distance = min(width, height) * 0.3
        candidate_positions = calculate_priority_positions(left, top, right, bottom, width, height)

        position_found = False
        for position in candidate_positions:
            rel_x, rel_y = position
            if position_manager.is_position_valid(frame, rel_x, rel_y, min_distance):
                position_manager.add_point(frame, rel_x, rel_y)
                pt_elem = ET.Element('points', {
                    'frame': frame,
                    'keyframe': '1',
                    'outside': '0',
                    'occluded': box.get('occluded', "0"),
                    'points': f"{rel_x:.2f},{rel_y:.2f}",
                    'z_order': "5"
                })
                ET.SubElement(pt_elem, 'attribute', {'name': 'predicate'}).text = predicate
                ET.SubElement(pt_elem, 'attribute', {'name': 'subject_id'}).text = subj_id
                ET.SubElement(pt_elem, 'attribute', {'name': 'object_id'}).text = obj_id
                rel_track.append(pt_elem)
                added_points = True
                position_found = True
                last_valid_frame = frame
                break
        if not position_found:
            continue

    if last_valid_frame is not None:
        try:
            outside_frame = int(last_valid_frame) + 1
            if outside_frame >= total_frames:
                outside_frame = total_frames - 1
            outside_elem = ET.Element('points', {
                'frame': str(outside_frame),
                'keyframe': '1',
                'outside': '1',
                'occluded': "0",
                'points': "0,0",
                'z_order': "0"
            })
            ET.SubElement(outside_elem, 'attribute', {'name': 'predicate'}).text = predicate
            ET.SubElement(outside_elem, 'attribute', {'name': 'subject_id'}).text = subj_id
            ET.SubElement(outside_elem, 'attribute', {'name': 'object_id'}).text = obj_id
            rel_track.append(outside_elem)
        except ValueError:
            pass
    return rel_track if added_points else None

def add_custom_relations(root, custom_relations, max_id, position_manager, total_frames=0):
    """添加自定义关系点"""
    added_count = 0
    if not custom_relations:
        return added_count
    all_tracks = root.findall('track')
    for subj_id, rel_list in custom_relations.items():
        subj_track = root.find(f"./track[@id='{subj_id}']")
        if not subj_track:
            continue
        boxes = subj_track.findall('box')
        if not boxes:
            continue
        for obj_id, pred in rel_list:
            max_id += 1
            rel_track = create_custom_relation_track(max_id, subj_id, obj_id, pred, boxes, position_manager, total_frames, all_tracks)
            if rel_track:
                root.append(rel_track)
                added_count += 1
    return added_count

def indent(elem, level=0):
    """自定义缩进函数，确保XML格式美观且无多余空行"""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def process_xml_file(xml_path, output_path, config, custom_relations=None, relations_to_delete=None, progress_callback=None):
    """
    处理XML文件的核心逻辑。
    参数:
        xml_path (str): 输入XML文件路径
        output_path (str): 输出XML文件路径
        config (dict): 配置参数
        custom_relations (dict, optional): 自定义关系，默认为None
        relations_to_delete (list, optional): 要删除的关系列表，默认为None
        progress_callback (callable, optional): 进度更新回调函数，默认为None
    返回:
        tuple: (success, message) - 处理是否成功及相关消息
    """
    if relations_to_delete is None:
        relations_to_delete = []
    try:
        if config.get("backup_original", True):
            backup_path = backup_file(xml_path)
            if progress_callback:
                progress_callback(5, f"完成备份: {os.path.basename(backup_path)}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        if relations_to_delete:
            delete_count = delete_relations(root, relations_to_delete)
            if progress_callback:
                progress_callback(10, f"已删除 {delete_count} 个关系点")
        else:
            delete_count = 0
            if progress_callback:
                progress_callback(10, "没有要删除的关系点")
        total_frames = 0
        meta = root.find('meta')
        if meta is not None:
            task = meta.find('task')
            if task is not None:
                size = task.find('size')
                if size is not None:
                    total_frames = int(size.text)
        if total_frames == 0:
            max_frame = 0
            for track in root.findall('track'):
                for box in track.findall('box'):
                    frame = int(box.get('frame'))
                    if frame > max_frame:
                        max_frame = frame
            total_frames = max_frame + 1
        if progress_callback:
            progress_callback(20, f"解析完成，总帧数: {total_frames}")
        track_ids = [int(track.get('id')) for track in root.findall('track')]
        max_id = max(track_ids) if track_ids else -1
        if progress_callback:
            progress_callback(30, f"计算最大ID完成: {max_id}")
        position_manager = PositionManager(root)
        all_tracks = root.findall('track')
        added_count = 0
        if custom_relations is not None:
            total_relations = sum(len(rel_list) for rel_list in custom_relations.values())
            if total_relations > 0 and progress_callback:
                progress_callback(40, f"开始添加 {total_relations} 个自定义关系点")
            current_count = 0
            for subj_id, rel_list in custom_relations.items():
                subj_track = root.find(f"./track[@id='{subj_id}']")
                if not subj_track:
                    continue
                boxes = subj_track.findall('box')
                if not boxes:
                    continue
                for obj_id, pred in rel_list:
                    current_count += 1
                    max_id += 1
                    rel_track = create_custom_relation_track(max_id, subj_id, obj_id, pred, boxes, position_manager, total_frames, all_tracks)
                    if rel_track:
                        root.append(rel_track)
                        added_count += 1
                    if progress_callback and current_count % 5 == 0:
                        progress = 40 + int(30 * current_count / total_relations)
                        progress_callback(progress, f"添加关系点: {current_count}/{total_relations}")
            if progress_callback:
                progress_callback(70, f"添加完成: {added_count} 个关系点")
            custom_relations.clear()
        else:
            if progress_callback:
                progress_callback(70, "没有自定义关系点")
        if progress_callback:
            progress_callback(80, "正在保存XML文件...")
        # 应用自定义缩进
        indent(root)
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')
        if progress_callback:
            progress_callback(90, "写入文件...")
        with open(output_path, 'wb') as f:
            f.write(xml_str)
        if progress_callback:
            progress_callback(100, "保存完成")
        return True, f"处理完成: 删除 {delete_count} 个关系点, 添加 {added_count} 个关系点"
    except Exception as e:
        return False, f"处理错误: {str(e)}"

def delete_relations(root, relations_to_delete):
    delete_count = 0
    tracks_to_remove = []
    delete_set = set()
    for del_rel in relations_to_delete:
        del_subj, del_obj, del_pred = del_rel
        obj_id = del_obj if del_obj != "" else None
        delete_set.add((del_subj, obj_id, del_pred))
    for track in root.findall('track'):
        if track.get('label') == "Relation":
            for points in track.findall('points'):
                if points.get('outside') == '1':
                    continue
                subj_id = None
                obj_id = None
                predicate = None
                for attr in points.findall('attribute'):
                    name = attr.get('name')
                    if name == 'subject_id':
                        subj_id = attr.text
                    elif name == 'object_id':
                        obj_id = attr.text
                    elif name == 'predicate':
                        predicate = attr.text
                if subj_id and predicate:
                    xml_obj_id = obj_id if obj_id is not None and obj_id != "" else None
                    match_found = False
                    for del_item in delete_set:
                        del_subj, del_obj, del_pred = del_item
                        if del_subj == subj_id and del_pred == predicate:
                            if del_obj is None:
                                if xml_obj_id is None:
                                    match_found = True
                                    break
                            else:
                                if xml_obj_id == del_obj:
                                    match_found = True
                                    break
                    if match_found:
                        tracks_to_remove.append(track)
                        delete_count += 1
                        break
    for track in tracks_to_remove:
        root.remove(track)
    return delete_count