#!/usr/bin/env python3
"""
Map Loader Module for SweePi Coverage
Handles loading PGM maps and YAML metadata
"""

import os
import yaml
from datetime import datetime

import numpy as np
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Header


class MapLoader:
    """Load and manage maps from disk."""

    def __init__(self, maps_dir=None):
        """
        Initialize map loader.
        
        Args:
            maps_dir: Directory containing maps. Defaults to ~/SweePi/maps/
        """
        if maps_dir is None:
            home = os.path.expanduser('~')
            maps_dir = os.path.join(home, 'SweePi', 'maps')
        
        self.maps_dir = maps_dir
        self._ensure_dir_exists()

    def _ensure_dir_exists(self):
        """Ensure maps directory exists."""
        try:
            os.makedirs(self.maps_dir, exist_ok=True)
        except Exception as e:
            print('Warning: Could not create maps directory: ' + str(e))

    def list_available_maps(self):
        """
        List all available maps in the maps directory.
        Requires both .pgm and .yaml files.
        
        Returns:
            Dict of map names to file paths
        """
        if not os.path.exists(self.maps_dir):
            print('Maps directory does not exist: ' + self.maps_dir)
            return {}
        
        maps = {}
        for file in os.listdir(self.maps_dir):
            if file.endswith('.pgm'):
                map_name = file.replace('.pgm', '')
                pgm_file = os.path.join(self.maps_dir, file)
                yaml_file = os.path.join(self.maps_dir, map_name + '.yaml')
                
                # Both files must exist
                if os.path.exists(yaml_file):
                    maps[map_name] = {
                        'pgm': pgm_file,
                        'yaml': yaml_file
                    }
                    print('Found map: ' + map_name)
                else:
                    print('Missing YAML for: ' + map_name + ' (expected: ' + yaml_file + ')')
        
        return maps

    def get_latest_map(self):
        """Get the most recently created map."""
        maps = self.list_available_maps()
        if not maps:
            return None
        
        latest = max(maps.items(), key=lambda x: os.path.getmtime(x[1]['yaml']))
        return latest[0]

    def load_map(self, map_name):
        """
        Load a specific map.
        
        Args:
            map_name: Name of the map (without extension)
            
        Returns:
            Tuple of (pgm_array, metadata_dict) or (None, None) if not found
        """
        print('Attempting to load map: ' + map_name)
        
        maps = self.list_available_maps()
        print('Available maps: ' + str(list(maps.keys())))
        
        if map_name not in maps:
            print('ERROR: Map not found: ' + map_name)
            return None, None
        
        map_files = maps[map_name]
        print('PGM file: ' + map_files['pgm'])
        print('YAML file: ' + map_files['yaml'])
        
        try:
            pgm_array = self._load_pgm(map_files['pgm'])
            print('PGM loaded successfully: shape=' + str(pgm_array.shape))
        except Exception as e:
            print('ERROR loading PGM: ' + str(e))
            return None, None
        
        try:
            metadata = self._load_yaml(map_files['yaml'])
            print('YAML loaded successfully')
            print('Metadata: ' + str(metadata))
        except Exception as e:
            print('ERROR loading YAML: ' + str(e))
            return None, None
        
        return pgm_array, metadata

    def _load_pgm(self, pgm_file):
        """Load PGM image file."""
        print('Loading PGM file: ' + pgm_file)
        
        if not os.path.exists(pgm_file):
            raise FileNotFoundError('PGM file not found: ' + pgm_file)
        
        with open(pgm_file, 'rb') as f:
            magic = f.readline().decode().strip()
            print('PGM Magic number: ' + magic)
            
            if magic != 'P5':
                raise ValueError('Invalid PGM format. Expected P5, got: ' + magic)
            
            # Skip comments
            while True:
                line = f.readline().decode().strip()
                if not line or not line.startswith('#'):
                    break
            
            # Parse dimensions
            width, height = map(int, line.split())
            print('PGM dimensions: {}x{}'.format(width, height))
            
            # Parse max value
            max_val = int(f.readline().decode().strip())
            print('PGM max value: ' + str(max_val))
            
            # Read image data
            image_data = np.frombuffer(f.read(), dtype=np.uint8)
            image_data = image_data.reshape((height, width))
            print('Image data shape: ' + str(image_data.shape))
        
        # Convert PGM to occupancy grid
        occupancy = np.zeros((height, width), dtype=np.int8)
        
        for y in range(height):
            for x in range(width):
                pixel = image_data[y, x]
                if pixel == 255:
                    occupancy[y, x] = 0  # Free space
                elif pixel == 128:
                    occupancy[y, x] = -1  # Unknown
                else:
                    occupancy[y, x] = 100  # Occupied
        
        print('Occupancy grid created successfully')
        return occupancy

    def _load_yaml(self, yaml_file):
        """Load YAML metadata file."""
        print('Loading YAML file: ' + yaml_file)
        
        if not os.path.exists(yaml_file):
            raise FileNotFoundError('YAML file not found: ' + yaml_file)
        
        with open(yaml_file, 'r') as f:
            metadata = yaml.safe_load(f)
        
        print('YAML content: ' + str(metadata))
        return metadata

    def create_occupancy_grid(self, pgm_array, metadata):
        """
        Convert PGM array to OccupancyGrid message.
        
        Args:
            pgm_array: Numpy array from _load_pgm
            metadata: Dict from _load_yaml
            
        Returns:
            OccupancyGrid message
        """
        height, width = pgm_array.shape
        
        grid = OccupancyGrid()
        grid.header = Header()
        grid.header.frame_id = 'map'
        grid.header.stamp = self._get_ros_time()
        
        grid.info.map_load_time = self._get_ros_time()
        grid.info.resolution = float(metadata.get('resolution', 0.05))
        grid.info.width = width
        grid.info.height = height
        
        origin = metadata.get('origin', [0, 0, 0])
        grid.info.origin.position.x = float(origin[0])
        grid.info.origin.position.y = float(origin[1])
        grid.info.origin.position.z = 0.0
        grid.info.origin.orientation.w = 1.0
        
        grid.data = pgm_array.flatten().tolist()
        
        return grid

    @staticmethod
    def _get_ros_time():
        """Get current time as ROS message."""
        from rclpy.time import Time
        import rclpy
        
        if rclpy.ok():
            return Time(clock_type=1).to_msg()
        else:
            from builtin_interfaces.msg import Time as TimeMsg
            now = datetime.now()
            seconds = int(now.timestamp())
            nanoseconds = int((now.timestamp() - seconds) * 1e9)
            
            time_msg = TimeMsg()
            time_msg.sec = seconds
            time_msg.nanosec = nanoseconds
            return time_msg

    def get_map_info(self, map_name):
        """Get metadata about a map without loading the full data."""
        maps = self.list_available_maps()
        if map_name not in maps:
            return None
        
        metadata = self._load_yaml(maps[map_name]['yaml'])
        return metadata