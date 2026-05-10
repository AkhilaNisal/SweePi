"""Runtime paths rooted at the repository root."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward until the repository root is found."""
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / '.git').exists():
            return candidate
    for candidate in [current, *current.parents]:
        if (candidate / 'src' / 'raspberry_pi' / 'src').exists():
            return candidate
    raise RuntimeError('Could not resolve the SweePi repository root')


def runtime_root(start: Path | None = None) -> Path:
    root = find_repo_root(start)
    path = root / 'runtime' / 'raspberry_pi'
    path.mkdir(parents=True, exist_ok=True)
    return path


def maps_root(start: Path | None = None) -> Path:
    path = runtime_root(start) / 'maps'
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_root(start: Path | None = None) -> Path:
    path = runtime_root(start) / 'data'
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_root(start: Path | None = None) -> Path:
    path = runtime_root(start) / 'logs'
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path(start: Path | None = None) -> Path:
    return data_root(start) / 'bridge.sqlite3'


def active_map_file(start: Path | None = None) -> Path:
    return data_root(start) / 'active_map.json'


def map_metadata_path(map_id: str, start: Path | None = None) -> Path:
    return maps_root(start) / f'{map_id}.meta.json'
