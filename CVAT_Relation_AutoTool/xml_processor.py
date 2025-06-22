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

        # 创建位置管理器来跟踪每个帧上的关系点位置
        position_manager = PositionManager(root)

        # 添加自动关系点
        processed_count, added_count = add_auto_relations(
            root, rules, config, max_id, position_manager, progress_callback
        )

        # 添加自定义关系点
        if custom_relations is not None:
            added_count += add_custom_relations(
                root, custom_relations, max_id, position_manager
            )

            # 添加此行：处理完成后清空自定义关系列表
            custom_relations.clear()

        # 保存处理后的XML
        xml_str = ET.tostring(root, encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
        with open(output_path, 'wb') as f:
            f.write(pretty_xml)

        return True, f"处理完成: {processed_count} 个主体，添加 {added_count} 个关系点"

    except Exception as e:
        return False, f"处理错误: {str(e)}"


class PositionManager:
    """管理每个帧上关系点的位置"""

    def __init__(self, root):
        # frame_points: {frame: set((x, y))}
        self.frame_points = {}

        # 初始化时解析已有关系点
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
        """添加一个新点"""
        if frame not in self.frame_points:
            self.frame_points[frame] = set()
        self.frame_points[frame].add((x, y))

    def is_position_valid(self, frame, x, y, min_distance):
        """检查位置是否有效（没有重叠）"""
        if frame not in self.frame_points:
            return True

        for px, py in self.frame_points[frame]:
            distance = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            if distance < min_distance:
                return False
        return True


def add_auto_relations(root, rules, config, max_id, position_manager, progress_callback=None):
    """添加自动关系点（带智能位置计算）"""
    all_tracks = [t for t in root.findall('track') if t.get('label') != "Relation"]
    total_tracks = len(all_tracks)
    processed = 0
    added_count = 0

    # 修复：正确收集已有关系点的主体ID
    existing_relations = set()
    for track in root.findall('track'):
        if track.get('label') == "Relation":
            for points in track.findall('points'):
                for attr in points.findall('attribute'):
                    if attr.get('name') == 'subject_id' and attr.text:
                        existing_relations.add(attr.text)

    for track in all_tracks:
        track_id = track.get('id')

        # 跳过已经有关系点的主体
        if config.get("skip_existing", True) and track_id in existing_relations:
            processed += 1
            if progress_callback:
                progress = int(processed / total_tracks * 90) + 5
                progress_callback(progress, f"跳过已有关系: {track.get('label')} (ID:{track_id})")
            continue

        label = track.get('label').lower()
        boxes = track.findall('box')

        if not boxes:
            processed += 1
            continue

        max_id += 1
        relation_track = create_relation_track(
            max_id, track_id, boxes, rules, label, position_manager
        )
        if relation_track is not None:
            root.append(relation_track)
            added_count += 1

        processed += 1

        if progress_callback:
            progress = int(processed / total_tracks * 90) + 5
            progress_callback(progress, f"添加关系: {label} (ID:{track_id})")

    return processed, added_count


def calculate_priority_positions(left, top, right, bottom, width, height):
    """按优先级计算关系点位置：中心 > 四角 > 四边中点"""
    positions = []

    # 1. 中心点 (最高优先级)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    positions.append((center_x, center_y))

    # 2. 四角位置
    corner_offset = 5  # 稍微离开角落一点点，避免完全在角落上
    # 左上角
    top_left = (left + corner_offset, top + corner_offset)
    positions.append(top_left)
    # 右上角
    top_right = (right - corner_offset, top + corner_offset)
    positions.append(top_right)
    # 左下角
    bottom_left = (left + corner_offset, bottom - corner_offset)
    positions.append(bottom_left)
    # 右下角
    bottom_right = (right - corner_offset, bottom - corner_offset)
    positions.append(bottom_right)

    # 3. 四边中点
    # 上边中点
    top_center = (center_x, top + corner_offset)
    positions.append(top_center)
    # 下边中点
    bottom_center = (center_x, bottom - corner_offset)
    positions.append(bottom_center)
    # 左边中点
    left_center = (left + corner_offset, center_y)
    positions.append(left_center)
    # 右边中点
    right_center = (right - corner_offset, center_y)
    positions.append(right_center)

    return positions


def create_relation_track(track_id, subject_id, boxes, rules, label, position_manager, total_frames):
    """创建关系轨迹（带优先级的位置选择），并确保关系点随主体消亡而消亡"""
    predicate = next(
        (rule_value for rule_key, rule_value in rules.items()
         if rule_key.lower() in label),
        ""
    )
    if not predicate:
        return None

    relation_track = ET.Element('track', {
        'id': str(track_id),
        'label': "Relation",
        'source': "auto-generated"
    })

    added_points = False
    last_valid_frame = None  # 记录最后一个有效帧

    for box in boxes:
        frame = box.get('frame')
        outside = box.get('outside', '0')

        # 检查帧号是否有效
        try:
            frame_num = int(frame)
        except ValueError:
            continue

        # 确保帧号在有效范围内
        if frame_num >= total_frames:
            continue

        # 如果框体标记为"outside"（超出画面），则跳过
        if outside == '1':
            continue

        # 获取边界框坐标
        xtl = float(box.get('xtl'))
        ytl = float(box.get('ytl'))
        xbr = float(box.get('xbr'))
        ybr = float(box.get('ybr'))

        # 确保坐标顺序正确
        left, top = min(xtl, xbr), min(ytl, ybr)
        right, bottom = max(xtl, xbr), max(ytl, ybr)
        width, height = right - left, bottom - top

        # 计算最小间距（基于框体大小）
        min_distance = min(width, height) * 0.3

        # 计算所有候选位置（按优先级顺序）
        candidate_positions = calculate_priority_positions(
            left, top, right, bottom, width, height
        )

        # 尝试所有候选位置
        position_found = False
        for position in candidate_positions:
            rel_x, rel_y = position

            # 检查位置是否有效（不与其他点重叠）
            if position_manager.is_position_valid(frame, rel_x, rel_y, min_distance):
                position_manager.add_point(frame, rel_x, rel_y)
                # 创建点元素
                points_elem = ET.Element('points', {
                    'frame': frame,
                    'keyframe': '1',
                    'outside': '0',  # 默认在画面内
                    'occluded': box.get('occluded', "0"),
                    'points': f"{rel_x:.2f},{rel_y:.2f}",
                    'z_order': "10"  # 确保显示在最上层
                })

                # 添加关系属性
                ET.SubElement(points_elem, 'attribute', {'name': 'predicate'}).text = predicate
                ET.SubElement(points_elem, 'attribute', {'name': 'subject_id'}).text = subject_id
                ET.SubElement(points_elem, 'attribute', {'name': 'object_id'}).text = ''

                relation_track.append(points_elem)
                added_points = True
                position_found = True
                last_valid_frame = frame  # 更新最后一个有效帧
                break  # 找到有效位置后跳出循环

        # 如果找不到有效位置，跳过此帧
        if not position_found:
            continue

    # 添加关系点消亡标记（如果存在有效帧）
    if last_valid_frame is not None:
        try:
            # 确保消亡帧在有效范围内
            outside_frame = int(last_valid_frame) + 1
            if outside_frame >= total_frames:
                outside_frame = total_frames - 1

            # 创建消亡标记点
            outside_elem = ET.Element('points', {
                'frame': str(outside_frame),  # 下一帧标记为消亡
                'keyframe': '1',
                'outside': '1',  # 标记为消亡
                'occluded': "0",
                'points': "0,0",  # 位置设为0,0（不重要）
                'z_order': "0"
            })
            # 添加属性
            ET.SubElement(outside_elem, 'attribute', {'name': 'predicate'}).text = predicate
            ET.SubElement(outside_elem, 'attribute', {'name': 'subject_id'}).text = subject_id
            ET.SubElement(outside_elem, 'attribute', {'name': 'object_id'}).text = ''

            relation_track.append(outside_elem)
        except ValueError:
            pass  # 忽略帧号转换错误

    return relation_track if added_points else None


def create_custom_relation_track(track_id, subj_id, obj_id, predicate, boxes, position_manager, total_frames,
                                 all_tracks):
    """创建自定义关系轨迹（带优先级的位置选择），并确保关系点随主体或客体消亡而消亡"""
    rel_track = ET.Element('track', {
        'id': str(track_id),
        'label': "Relation",
        'source': "custom"
    })

    added_points = False
    last_valid_frame = None  # 记录最后一个有效帧

    # 获取客体轨迹
    obj_track = next((t for t in all_tracks if t.get('id') == obj_id), None)
    if not obj_track:
        return None  # 客体不存在，不创建关系点

    # 创建客体帧状态映射：{frame: outside}
    obj_frame_states = {}
    for box in obj_track.findall('box'):
        frame = box.get('frame')
        outside = box.get('outside', '0')
        obj_frame_states[frame] = outside

    for box in boxes:
        frame = box.get('frame')

        # 检查帧号是否有效
        try:
            frame_num = int(frame)
        except ValueError:
            continue

        # 确保帧号在有效范围内
        if frame_num >= total_frames:
            continue

        # 检查主体是否在画面内
        subject_outside = box.get('outside', '0')
        if subject_outside == '1':
            continue

        # 检查客体是否在画面内
        obj_outside = obj_frame_states.get(frame, '1')  # 默认客体不在画面内
        if obj_outside == '1':
            continue

        # 获取边界框坐标
        xtl = float(box.get('xtl'))
        ytl = float(box.get('ytl'))
        xbr = float(box.get('xbr'))
        ybr = float(box.get('ybr'))

        # 确保坐标顺序正确
        left, top = min(xtl, xbr), min(ytl, ybr)
        right, bottom = max(xtl, xbr), max(ytl, ybr)
        width, height = right - left, bottom - top

        # 计算最小间距（基于框体大小）
        min_distance = min(width, height) * 0.3

        # 计算所有候选位置（按优先级顺序）
        candidate_positions = calculate_priority_positions(
            left, top, right, bottom, width, height
        )

        # 尝试所有候选位置
        position_found = False
        for position in candidate_positions:
            rel_x, rel_y = position

            # 检查位置是否有效（不与其他点重叠）
            if position_manager.is_position_valid(frame, rel_x, rel_y, min_distance):
                position_manager.add_point(frame, rel_x, rel_y)
                # 创建点元素
                pt_elem = ET.Element('points', {
                    'frame': frame,
                    'keyframe': '1',
                    'outside': '0',  # 默认在画面内
                    'occluded': box.get('occluded', "0"),
                    'points': f"{rel_x:.2f},{rel_y:.2f}",
                    'z_order': "5"  # 中等层级
                })

                # 添加属性
                ET.SubElement(pt_elem, 'attribute', {'name': 'predicate'}).text = predicate
                ET.SubElement(pt_elem, 'attribute', {'name': 'subject_id'}).text = subj_id
                ET.SubElement(pt_elem, 'attribute', {'name': 'object_id'}).text = obj_id

                rel_track.append(pt_elem)
                added_points = True
                position_found = True
                last_valid_frame = frame  # 更新最后一个有效帧
                break  # 找到有效位置后跳出循环

        # 如果找不到有效位置，跳过此帧
        if not position_found:
            continue

    # 添加关系点消亡标记（如果存在有效帧）
    if last_valid_frame is not None:
        try:
            # 确保消亡帧在有效范围内
            outside_frame = int(last_valid_frame) + 1
            if outside_frame >= total_frames:
                outside_frame = total_frames - 1

            # 创建消亡标记点
            outside_elem = ET.Element('points', {
                'frame': str(outside_frame),  # 下一帧标记为消亡
                'keyframe': '1',
                'outside': '1',  # 标记为消亡
                'occluded': "0",
                'points': "0,0",  # 位置设为0,0（不重要）
                'z_order': "0"
            })
            # 添加属性
            ET.SubElement(outside_elem, 'attribute', {'name': 'predicate'}).text = predicate
            ET.SubElement(outside_elem, 'attribute', {'name': 'subject_id'}).text = subj_id
            ET.SubElement(outside_elem, 'attribute', {'name': 'object_id'}).text = obj_id

            rel_track.append(outside_elem)
        except ValueError:
            pass  # 忽略帧号转换错误

    return rel_track if added_points else None


def add_custom_relations(root, custom_relations, max_id, position_manager, total_frames=0):
    """添加自定义关系点"""
    added_count = 0
    if not custom_relations:
        return added_count

    # 获取所有轨迹
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
            rel_track = create_custom_relation_track(
                max_id, subj_id, obj_id, pred, boxes, position_manager, total_frames, all_tracks
            )
            if rel_track:
                root.append(rel_track)
                added_count += 1

    return added_count


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

        # 获取总帧数
        total_frames = 0
        meta = root.find('meta')
        if meta is not None:
            task = meta.find('task')
            if task is not None:
                size = task.find('size')
                if size is not None:
                    total_frames = int(size.text)

        # 如果无法获取总帧数，尝试计算最大帧号
        if total_frames == 0:
            max_frame = 0
            for track in root.findall('track'):
                for box in track.findall('box'):
                    frame = int(box.get('frame'))
                    if frame > max_frame:
                        max_frame = frame
            total_frames = max_frame + 1  # 帧号从0开始

        # 计算最大track ID
        track_ids = [int(track.get('id')) for track in root.findall('track')]
        max_id = max(track_ids) if track_ids else -1

        # 创建位置管理器来跟踪每个帧上的关系点位置
        position_manager = PositionManager(root)

        # 添加自动关系点
        processed_count, added_count = add_auto_relations(
            root, rules, config, max_id, position_manager, progress_callback, total_frames
        )

        # 添加自定义关系点
        if custom_relations is not None:
            added_count += add_custom_relations(
                root, custom_relations, max_id, position_manager, total_frames
            )

            # 添加此行：处理完成后清空自定义关系列表
            custom_relations.clear()

        # 保存处理后的XML
        xml_str = ET.tostring(root, encoding='utf-8')
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
        with open(output_path, 'wb') as f:
            f.write(pretty_xml)

        return True, f"处理完成: {processed_count} 个主体，添加 {added_count} 个关系点"

    except Exception as e:
        return False, f"处理错误: {str(e)}"


def add_auto_relations(root, rules, config, max_id, position_manager, progress_callback=None, total_frames=0):
    """添加自动关系点（带智能位置计算）"""
    all_tracks = [t for t in root.findall('track') if t.get('label') != "Relation"]
    total_tracks = len(all_tracks)
    processed = 0
    added_count = 0

    # 修复：正确收集已有关系点的主体ID
    existing_relations = set()
    for track in root.findall('track'):
        if track.get('label') == "Relation":
            for points in track.findall('points'):
                for attr in points.findall('attribute'):
                    if attr.get('name') == 'subject_id' and attr.text:
                        existing_relations.add(attr.text)

    for track in all_tracks:
        track_id = track.get('id')

        # 跳过已经有关系点的主体
        if config.get("skip_existing", True) and track_id in existing_relations:
            processed += 1
            if progress_callback:
                progress = int(processed / total_tracks * 90) + 5
                progress_callback(progress, f"跳过已有关系: {track.get('label')} (ID:{track_id})")
            continue

        label = track.get('label').lower()
        boxes = track.findall('box')

        if not boxes:
            processed += 1
            continue

        max_id += 1
        relation_track = create_relation_track(
            max_id, track_id, boxes, rules, label, position_manager, total_frames
        )
        if relation_track is not None:
            root.append(relation_track)
            added_count += 1

        processed += 1

        if progress_callback:
            progress = int(processed / total_tracks * 90) + 5
            progress_callback(progress, f"添加关系: {label} (ID:{track_id})")

    return processed, added_count



