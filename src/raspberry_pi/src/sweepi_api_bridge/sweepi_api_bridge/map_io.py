"""Map persistence helpers shared by the bridge."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nav_msgs.msg import OccupancyGrid

from sweepi_api_bridge.runtime_paths import map_metadata_path, maps_root


def _sanitize_map_name(name: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in name)
    return cleaned.strip('_') or 'map'


def save_occupancy_grid(map_msg: OccupancyGrid, name: str) -> dict:
    """Persist the latest occupancy grid under the repo-root runtime/maps folder."""
    if map_msg.info.width <= 0 or map_msg.info.height <= 0:
        raise ValueError('Map dimensions must be positive before saving')

    map_id = _sanitize_map_name(name)
    map_dir = maps_root()
    pgm_path = map_dir / f'{map_id}.pgm'
    yaml_path = map_dir / f'{map_id}.yaml'
    metadata_path = map_metadata_path(map_id)

    width = map_msg.info.width
    height = map_msg.info.height

    image_data = bytearray(width * height)
    for index, cell in enumerate(map_msg.data):
        if cell < 0:
            image_data[index] = 128
        elif cell == 0:
            image_data[index] = 255
        else:
            image_data[index] = 0

    with pgm_path.open('wb') as handle:
        handle.write(b'P5\n')
        handle.write(f'{width} {height}\n'.encode('ascii'))
        handle.write(b'255\n')
        handle.write(image_data)

    with yaml_path.open('w', encoding='utf-8') as handle:
        handle.write(
            '\n'.join(
                [
                    f'image: {pgm_path.name}',
                    f'resolution: {map_msg.info.resolution}',
                    (
                        'origin: '
                        f'[{map_msg.info.origin.position.x}, '
                        f'{map_msg.info.origin.position.y}, 0.0]'
                    ),
                    'negate: 0',
                    'occupied_thresh: 0.65',
                    'free_thresh: 0.196',
                    '',
                    'sweepi_metadata:',
                    f'  saved_at: {datetime.now(timezone.utc).isoformat()}',
                    f'  width: {width}',
                    f'  height: {height}',
                ]
            )
        )

    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(
                {
                    'map_id': map_id,
                    'name': map_id,
                    'rooms': [],
                    'no_go_zones': [],
                    'labels': [],
                },
                indent=2,
            ),
            encoding='utf-8',
        )

    return {
        'map_id': map_id,
        'pgm_path': str(pgm_path),
        'yaml_path': str(yaml_path),
        'metadata_path': str(metadata_path),
    }


def list_saved_maps() -> list[dict]:
    """Return the saved runtime maps catalog."""
    output = []
    for yaml_path in sorted(maps_root().glob('*.yaml')):
        map_id = yaml_path.stem
        metadata = load_map_metadata(map_id)
        output.append(
            {
                'map_id': map_id,
                'yaml_path': str(yaml_path),
                'pgm_path': str(yaml_path.with_suffix('.pgm')),
                'metadata': metadata,
            }
        )
    return output


def load_map_metadata(map_id: str) -> dict:
    metadata_path = map_metadata_path(map_id)
    if not metadata_path.exists():
        return {
            'map_id': map_id,
            'name': map_id,
            'rooms': [],
            'no_go_zones': [],
            'labels': [],
        }
    return json.loads(metadata_path.read_text(encoding='utf-8'))


def save_map_metadata(map_id: str, metadata: dict) -> dict:
    payload = {
        'map_id': map_id,
        'name': metadata.get('name', map_id),
        'rooms': metadata.get('rooms', []),
        'no_go_zones': metadata.get('no_go_zones', []),
        'labels': metadata.get('labels', []),
    }
    path = map_metadata_path(map_id)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload
