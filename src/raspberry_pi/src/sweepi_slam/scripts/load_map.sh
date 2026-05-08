#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage: $0 <map_name>${NC}"
    echo ""
    echo -e "${YELLOW}Available maps:${NC}"
    
    MAP_DIR="$HOME/ros2_ws/src/sweepi_slam/maps"
    
    if [ -d "$MAP_DIR" ]; then
        find "$MAP_DIR" -name "*.yaml" | xargs -I {} basename {} .yaml
    else
        echo -e "${RED}No maps directory found${NC}"
    fi
    exit 1
fi

MAP_NAME=$1
MAP_DIR="$HOME/ros2_ws/src/sweepi_slam/maps"
MAP_PATH="$MAP_DIR/$MAP_NAME"

if [ ! -f "$MAP_PATH.yaml" ]; then
    echo -e "${RED}Map not found: $MAP_PATH.yaml${NC}"
    exit 1
fi

echo -e "${GREEN}Loading map: $MAP_NAME${NC}"
echo "Map path: $MAP_PATH"