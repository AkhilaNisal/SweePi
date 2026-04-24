"""Small helpers for occupancy-grid coverage tracking."""

import math


def world_to_map(world_x, world_y, map_info):
    """Convert world coordinates to integer map-cell coordinates."""
    if map_info.resolution <= 0.0:
        raise ValueError("Map resolution must be positive")

    map_x = math.floor(
        (world_x - map_info.origin.position.x) / map_info.resolution
    )
    map_y = math.floor(
        (world_y - map_info.origin.position.y) / map_info.resolution
    )
    return int(map_x), int(map_y)


def map_to_flat_index(map_x, map_y, width):
    """Convert map-cell coordinates to a flat occupancy-grid array index."""
    return map_y * width + map_x


def in_bounds(map_x, map_y, width, height):
    """Return True when map-cell coordinates are inside the grid."""
    return 0 <= map_x < width and 0 <= map_y < height


def meters_to_cell_radius(radius_m, resolution):
    """Convert a metric radius to the number of grid cells it spans."""
    if resolution <= 0.0:
        raise ValueError("Map resolution must be positive")
    return max(0, int(math.ceil(radius_m / resolution)))
