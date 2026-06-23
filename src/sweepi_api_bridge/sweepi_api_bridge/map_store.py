"""Saved map metadata and occupancy helpers for SweePi maps."""

import json
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
        payload = {
            'map_id': clean_id,
            'name': meta.get('name') or clean_id,
            'available': self.exists(clean_id),
            'resolution': yaml_data.get('resolution'),
            'origin': yaml_data.get('origin'),
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
            'origin': {
                'x': float(origin[0]) if len(origin) > 0 else 0.0,
                'y': float(origin[1]) if len(origin) > 1 else 0.0,
                'yaw': float(origin[2]) if len(origin) > 2 else 0.0,
            },
            'occupancy': occupancy,
        }

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

    def _now_string(self):
        from datetime import datetime

        return datetime.now().isoformat(timespec='seconds')
