"""JSON conversion helpers for the SweePi API bridge."""

import json
import math
from urllib.parse import parse_qs, urlparse


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def json_response(handler, status_code, payload):
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.end_headers()
    handler.wfile.write(body)


def parse_json_body(handler):
    raw_length = handler.headers.get('Content-Length', '0')
    try:
        content_length = int(raw_length)
    except ValueError as exc:
        raise ValueError('Invalid Content-Length') from exc

    if content_length <= 0:
        return {}

    body = handler.rfile.read(content_length)
    try:
        data = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError('Invalid JSON body') from exc

    if not isinstance(data, dict):
        raise ValueError('JSON body must be an object')
    return data


def split_path(path):
    parsed = urlparse(path)
    parts = [part for part in parsed.path.split('/') if part]
    query = parse_qs(parsed.query)
    return parts, query


def yaw_to_quaternion(yaw):
    half = yaw / 2.0
    return {
        'x': 0.0,
        'y': 0.0,
        'z': math.sin(half),
        'w': math.cos(half),
    }


def quaternion_to_yaw(orientation):
    x = getattr(orientation, 'x', 0.0)
    y = getattr(orientation, 'y', 0.0)
    z = getattr(orientation, 'z', 0.0)
    w = getattr(orientation, 'w', 1.0)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def pose_to_json(pose_stamped_or_pose, frame='map'):
    pose = getattr(pose_stamped_or_pose, 'pose', pose_stamped_or_pose)
    if hasattr(pose, 'pose'):
        pose = pose.pose
    return {
        'x': float(pose.position.x),
        'y': float(pose.position.y),
        'yaw': float(quaternion_to_yaw(pose.orientation)),
        'frame': frame,
    }


def occupancy_grid_to_json(msg, include_occupancy=True):
    payload = {
        'available': True,
        'frame': msg.header.frame_id or 'map',
        'resolution': float(msg.info.resolution),
        'width': int(msg.info.width),
        'height': int(msg.info.height),
        'origin': {
            'x': float(msg.info.origin.position.x),
            'y': float(msg.info.origin.position.y),
            'yaw': float(quaternion_to_yaw(msg.info.origin.orientation)),
        },
    }
    if include_occupancy:
        payload['occupancy'] = list(msg.data)
    return payload


def path_to_json(msg, stride=1):
    safe_stride = max(1, int(stride))
    points = []
    for pose_stamped in msg.poses[::safe_stride]:
        pose = pose_stamped.pose
        points.append({
            'x': float(pose.position.x),
            'y': float(pose.position.y),
            'yaw': float(quaternion_to_yaw(pose.orientation)),
        })
    return {
        'available': bool(msg.poses),
        'frame': msg.header.frame_id or 'map',
        'points': points,
        'total_points': len(msg.poses),
        'stride': safe_stride,
    }
