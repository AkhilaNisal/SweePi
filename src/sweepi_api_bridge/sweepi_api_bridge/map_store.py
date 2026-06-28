"""Saved map metadata and occupancy helpers for SweePi maps."""

from datetime import datetime, timezone
import json
import math
import os
import re


def sanitize_map_id(value, fallback='map'):
    text = str(value or '').strip().lower()
    text = re.sub(r'[^a-z0-9_-]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_-')
    return text or fallback


class MapStore:
    def __init__(self, maps_dir=None):
        self.maps_dir = os.path.expanduser(maps_dir or '~/SweePi/maps')

    def map_yaml_path(self, map_id):
        return os.path.join(self.maps_dir, '%s.yaml' % sanitize_map_id(map_id))

    def map_image_path(self, map_id, yaml_data=None):
        if yaml_data and yaml_data.get('image'):
            image = str(yaml_data['image'])
            if os.path.isabs(image):
                return image
            return os.path.join(self.maps_dir, image)
        return os.path.join(self.maps_dir, '%s.pgm' % sanitize_map_id(map_id))

    def meta_path(self, map_id):
        return os.path.join(self.maps_dir, '%s.meta.json' % sanitize_map_id(map_id))

    def exists(self, map_id):
        return os.path.exists(self.map_yaml_path(map_id))

    def list_maps(self):
        if not os.path.isdir(self.maps_dir):
            return []
        maps = []
        for name in sorted(os.listdir(self.maps_dir)):
            if not name.endswith('.yaml'):
                continue
            map_id = name[:-5]
            maps.append(self.metadata(map_id))
        return maps

    def metadata(self, map_id):
        clean_id = sanitize_map_id(map_id)
        yaml_data = self.read_yaml(clean_id)
        meta = self.read_meta(clean_id)
        image = self._read_pgm(self.map_image_path(clean_id, yaml_data))
        origin = self._origin_to_dict(yaml_data.get('origin', [0.0, 0.0, 0.0]))
        payload = {
            'map_id': clean_id,
            'name': meta.get('name') or clean_id,
            'available': self.exists(clean_id),
            'resolution': yaml_data.get('resolution'),
            'origin': origin,
            'width': image['width'] if image else None,
            'height': image['height'] if image else None,
            'sections': meta.get('sections', []),
            'no_go_zones': meta.get('no_go_zones', []),
            'created_at': meta.get('created_at'),
            'updated_at': meta.get('updated_at'),
        }
        return payload

    def read_meta(self, map_id):
        path = self.meta_path(map_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def update_metadata(self, map_id, name=None, sections=None, no_go_zones=None):
        clean_id = sanitize_map_id(map_id)
        meta = self.read_meta(clean_id)
        meta['map_id'] = clean_id
        if name is not None:
            meta['name'] = str(name).strip() or clean_id
        else:
            meta['name'] = meta.get('name') or clean_id
        if sections is not None:
            meta['sections'] = sections
        else:
            meta.setdefault('sections', [])
        if no_go_zones is not None:
            meta['no_go_zones'] = no_go_zones
        else:
            meta.setdefault('no_go_zones', [])
        meta['updated_at'] = self._now_string()
        if not meta.get('created_at'):
            meta['created_at'] = meta['updated_at']
        os.makedirs(self.maps_dir, exist_ok=True)
        with open(self.meta_path(clean_id), 'w', encoding='utf-8') as handle:
            json.dump(meta, handle, indent=2, sort_keys=True)
        return self.metadata(clean_id)

    def write_sections(self, map_id, sections, no_go_zones):
        clean_id = sanitize_map_id(map_id)
        meta = self.read_meta(clean_id)
        meta['map_id'] = clean_id
        meta['name'] = meta.get('name') or clean_id
        meta['sections'] = sections
        meta['no_go_zones'] = no_go_zones
        meta['updated_at'] = self._now_string()
        if not meta.get('created_at'):
            meta['created_at'] = meta['updated_at']
        os.makedirs(self.maps_dir, exist_ok=True)
        with open(self.meta_path(clean_id), 'w', encoding='utf-8') as handle:
            json.dump(meta, handle, indent=2, sort_keys=True)
        return meta

    def write_processed_map(self, output_map_id, processed_map, meta_extra=None):
        clean_id = sanitize_map_id(output_map_id)
        width = int(processed_map['width'])
        height = int(processed_map['height'])
        resolution = float(processed_map['resolution'])
        origin = processed_map['origin']
        occupancy = [int(value) for value in processed_map['occupancy']]
        if width <= 0 or height <= 0 or len(occupancy) != width * height:
            raise ValueError('processed_map occupancy size does not match width*height')

        os.makedirs(self.maps_dir, exist_ok=True)
        self._write_occupancy_as_map(
            clean_id,
            width,
            height,
            resolution,
            self._origin_to_dict(origin),
            occupancy,
        )
        meta = self.ensure_meta(clean_id, meta_extra or {})
        return {'map_id': clean_id, 'metadata': meta}

    def write_section_map(self, base_map_id, output_map_id, sections, meta_extra=None):
        source = self.read_map(base_map_id)
        if not source.get('available'):
            raise ValueError('base map not found')

        width = int(source['width'])
        height = int(source['height'])
        resolution = float(source['resolution'])
        origin = source['origin']
        source_occupancy = list(source['occupancy'])
        masked = []
        for index, cell in enumerate(source_occupancy):
            x_index = index % width
            y_index = index // width
            world_x = origin['x'] + (x_index + 0.5) * resolution
            world_y = origin['y'] + (y_index + 0.5) * resolution
            if cell == 0 and self._point_in_sections(world_x, world_y, sections):
                masked.append(0)
            elif cell == -1:
                masked.append(-1)
            else:
                masked.append(100)

        os.makedirs(self.maps_dir, exist_ok=True)
        self._write_occupancy_as_map(
            output_map_id,
            width,
            height,
            resolution,
            origin,
            masked,
        )
        meta = self.ensure_meta(output_map_id, meta_extra or {})
        return {'map_id': sanitize_map_id(output_map_id), 'metadata': meta}

    def ensure_meta(self, map_id, extra=None):
        clean_id = sanitize_map_id(map_id)
        meta = self.read_meta(clean_id)
        meta.setdefault('map_id', clean_id)
        meta.setdefault('name', clean_id)
        meta.setdefault('created_at', self._now_string())
        meta['updated_at'] = self._now_string()
        if extra:
            meta.update(extra)
        os.makedirs(self.maps_dir, exist_ok=True)
        with open(self.meta_path(clean_id), 'w', encoding='utf-8') as handle:
            json.dump(meta, handle, indent=2, sort_keys=True)
        return meta

    def read_map(self, map_id):
        clean_id = sanitize_map_id(map_id)
        yaml_data = self.read_yaml(clean_id)
        if not yaml_data:
            return {'available': False, 'map_id': clean_id, 'message': 'Map not found'}

        image_path = self.map_image_path(clean_id, yaml_data)
        image = self._read_pgm(image_path)
        if image is None:
            return {
                'available': False,
                'map_id': clean_id,
                'metadata': self.metadata(clean_id),
                'message': 'Map image could not be read',
            }

        resolution = float(yaml_data.get('resolution', 0.05))
        origin = yaml_data.get('origin', [0.0, 0.0, 0.0])
        negate = int(yaml_data.get('negate', 0))
        occupied_thresh = float(yaml_data.get('occupied_thresh', 0.65))
        free_thresh = float(yaml_data.get('free_thresh', 0.196))
        occupancy = []
        for pixel in image['pixels']:
            value = 255 - pixel if negate else pixel
            occ = (255 - value) / 255.0
            if occ > occupied_thresh:
                occupancy.append(100)
            elif occ < free_thresh:
                occupancy.append(0)
            else:
                occupancy.append(-1)

        return {
            'available': True,
            'map_id': clean_id,
            'metadata': self.metadata(clean_id),
            'resolution': resolution,
            'width': image['width'],
            'height': image['height'],
            'origin': self._origin_to_dict(origin),
            'occupancy': occupancy,
        }

    def check_pose(self, map_id, x, y, allow_unknown=False, occupied_threshold=50):
        """Validate a world-frame pose against a saved occupancy map."""
        clean_id = sanitize_map_id(map_id)
        saved_map = self.read_map(clean_id)
        if not saved_map.get('available'):
            return {
                'ok': False,
                'code': 'MAP_NOT_FOUND',
                'message': saved_map.get('message', 'Map not found'),
                'map_id': clean_id,
            }

        width = int(saved_map.get('width') or 0)
        height = int(saved_map.get('height') or 0)
        resolution = float(saved_map.get('resolution') or 0.0)
        occupancy = saved_map.get('occupancy') or []
        if width <= 0 or height <= 0 or resolution <= 0.0:
            return {
                'ok': False,
                'code': 'MAP_INVALID',
                'message': 'Map metadata is invalid.',
                'map_id': clean_id,
            }

        origin = self._origin_to_dict(saved_map.get('origin'))
        dx = float(x) - origin['x']
        dy = float(y) - origin['y']
        yaw = origin.get('yaw', 0.0)
        cos_yaw = math.cos(-yaw)
        sin_yaw = math.sin(-yaw)
        local_x = (dx * cos_yaw) - (dy * sin_yaw)
        local_y = (dx * sin_yaw) + (dy * cos_yaw)
        cell_x = int(math.floor(local_x / resolution))
        cell_y = int(math.floor(local_y / resolution))

        cell_info = {
            'x': cell_x,
            'y': cell_y,
            'width': width,
            'height': height,
            'resolution': resolution,
        }
        if cell_x < 0 or cell_y < 0 or cell_x >= width or cell_y >= height:
            return {
                'ok': False,
                'code': 'INITIAL_POSE_OUTSIDE_MAP',
                'message': 'Initial pose is outside the map bounds.',
                'map_id': clean_id,
                'cell': cell_info,
            }

        index = (cell_y * width) + cell_x
        value = int(occupancy[index]) if 0 <= index < len(occupancy) else 100
        result = {
            'ok': True,
            'code': 'OK',
            'message': 'Initial pose is in a free map cell.',
            'map_id': clean_id,
            'cell': dict(cell_info, index=index),
            'occupancy': value,
        }
        if value < 0 and not allow_unknown:
            result.update({
                'ok': False,
                'code': 'INITIAL_POSE_UNKNOWN',
                'message': 'Initial pose is in an unknown map cell.',
            })
        elif value >= int(occupied_threshold):
            result.update({
                'ok': False,
                'code': 'INITIAL_POSE_OCCUPIED',
                'message': 'Initial pose is in an occupied map cell.',
            })
        return result

    def read_yaml(self, map_id):
        path = self.map_yaml_path(map_id)
        if not os.path.exists(path):
            return {}
        data = {}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                for raw_line in handle:
                    line = raw_line.split('#', 1)[0].strip()
                    if not line or ':' not in line:
                        continue
                    key, value = line.split(':', 1)
                    data[key.strip()] = self._parse_yaml_scalar(value.strip())
        except OSError:
            return {}
        return data

    def _parse_yaml_scalar(self, value):
        if value.startswith('[') and value.endswith(']'):
            parts = [part.strip() for part in value[1:-1].split(',')]
            parsed = []
            for part in parts:
                try:
                    parsed.append(float(part))
                except ValueError:
                    parsed.append(part.strip('"\''))
            return parsed
        stripped = value.strip('"\'')
        try:
            if any(char in stripped for char in ('.', 'e', 'E')):
                return float(stripped)
            return int(stripped)
        except ValueError:
            return stripped

    def _read_pgm(self, path):
        try:
            with open(path, 'rb') as handle:
                magic = self._read_token(handle)
                if magic not in (b'P2', b'P5'):
                    return None
                width = int(self._read_token(handle))
                height = int(self._read_token(handle))
                max_value = int(self._read_token(handle))
                if width <= 0 or height <= 0 or max_value <= 0:
                    return None
                if magic == b'P5':
                    raw = handle.read(width * height)
                    pixels = [int((byte / max_value) * 255) for byte in raw]
                else:
                    pixels = [
                        int((int(self._read_token(handle)) / max_value) * 255)
                        for _ in range(width * height)
                    ]
        except (OSError, ValueError):
            return None
        return {'width': width, 'height': height, 'pixels': pixels}

    def _read_token(self, handle):
        token = bytearray()
        while True:
            char = handle.read(1)
            if not char:
                return bytes(token)
            if char == b'#':
                handle.readline()
                continue
            if char.isspace():
                if token:
                    return bytes(token)
                continue
            token.extend(char)

    def _origin_to_dict(self, origin):
        if isinstance(origin, dict):
            return {
                'x': float(origin.get('x', 0.0)),
                'y': float(origin.get('y', 0.0)),
                'yaw': float(origin.get('yaw', 0.0)),
            }
        values = origin if isinstance(origin, (list, tuple)) else []
        return {
            'x': float(values[0]) if len(values) > 0 else 0.0,
            'y': float(values[1]) if len(values) > 1 else 0.0,
            'yaw': float(values[2]) if len(values) > 2 else 0.0,
        }

    def _point_in_sections(self, x, y, sections):
        for section in sections:
            bounds = section.get('bounds', {})
            min_x = float(bounds.get('x', 0.0))
            min_y = float(bounds.get('y', 0.0))
            max_x = min_x + float(bounds.get('width', 0.0))
            max_y = min_y + float(bounds.get('height', 0.0))
            if min_x <= x <= max_x and min_y <= y <= max_y:
                return True
        return False

    def _write_occupancy_as_map(
        self,
        map_id,
        width,
        height,
        resolution,
        origin,
        occupancy,
    ):
        clean_id = sanitize_map_id(map_id)
        pgm_name = clean_id + '.pgm'
        yaml_name = clean_id + '.yaml'
        pgm_path = os.path.join(self.maps_dir, pgm_name)
        yaml_path = os.path.join(self.maps_dir, yaml_name)
        with open(pgm_path, 'wb') as handle:
            handle.write(('P5\n%d %d\n255\n' % (width, height)).encode('ascii'))
            pixels = bytearray()
            for cell in occupancy:
                if cell < 0:
                    pixels.append(205)
                elif cell >= 50:
                    pixels.append(0)
                else:
                    pixels.append(254)
            handle.write(bytes(pixels))

        yaw = float(origin.get('yaw', 0.0))
        if not math.isfinite(yaw):
            yaw = 0.0
        yaml_text = (
            'image: %s\n'
            'mode: trinary\n'
            'resolution: %.12g\n'
            'origin: [%.12g, %.12g, %.12g]\n'
            'negate: 0\n'
            'occupied_thresh: 0.65\n'
            'free_thresh: 0.196\n'
        ) % (
            pgm_name,
            float(resolution),
            float(origin.get('x', 0.0)),
            float(origin.get('y', 0.0)),
            yaw,
        )
        with open(yaml_path, 'w', encoding='utf-8') as handle:
            handle.write(yaml_text)

    def _now_string(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            '+00:00',
            'Z',
        )
