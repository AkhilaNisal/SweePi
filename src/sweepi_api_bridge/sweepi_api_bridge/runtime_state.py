"""Thread-safe runtime state for the SweePi API bridge."""

from dataclasses import asdict, dataclass, field
import threading
import time


@dataclass
class RuntimeState:
    robot_state: str = 'idle'
    active_task: str = 'none'
    exploration_active: bool = False
    exploration_mode: str = 'unknown'
    cleaning_active: bool = False
    cleaning_paused: bool = False
    active_map_id: str = None
    active_area_name: str = None
    active_task_id: str = None
    active_sections: list = field(default_factory=list)
    active_coverage_map_id: str = None
    cleaning_mode: str = None
    initial_pose_received: bool = False
    initial_pose_source: str = None
    initial_pose: dict = None
    coverage_validated: bool = False
    coverage_path_available: bool = False
    coverage_map_available: bool = False
    live_map_available: bool = False
    last_error: str = None
    warnings: list = field(default_factory=list)
    last_updated_sec: float = field(default_factory=time.time)


class StateStore:
    def __init__(self):
        self._state = RuntimeState()
        self._lock = threading.RLock()

    @property
    def lock(self):
        return self._lock

    def snapshot(self):
        with self._lock:
            return asdict(self._state)

    def update(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._state.last_updated_sec = time.time()
            return asdict(self._state)

    def reset_cleaning(self):
        with self._lock:
            self._state.cleaning_active = False
            self._state.cleaning_paused = False
            self._state.coverage_validated = False
            self._state.coverage_path_available = False
            self._state.coverage_map_available = False
            self._state.cleaning_mode = None
            self._state.active_task_id = None
            self._state.active_sections = []
            self._state.active_coverage_map_id = None
            if self._state.active_task == 'cleaning':
                self._state.active_task = 'none'
                self._state.active_map_id = None
            if self._state.robot_state in (
                'coverage_preparing',
                'waiting_for_initial_pose',
                'coverage_ready',
                'cleaning',
                'paused',
                'returning_home',
            ):
                self._state.robot_state = 'idle'
            self._state.last_updated_sec = time.time()
            return asdict(self._state)

    def reset_exploration(self):
        with self._lock:
            self._state.exploration_active = False
            self._state.exploration_mode = 'stopped'
            if self._state.active_task == 'exploration':
                self._state.active_task = 'none'
                self._state.active_area_name = None
                self._state.active_map_id = None
            if self._state.robot_state == 'exploring':
                self._state.robot_state = 'idle'
            self._state.last_updated_sec = time.time()
            return asdict(self._state)
