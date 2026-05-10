#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEARCH_DIR="$SCRIPT_DIR"
while [ "$SEARCH_DIR" != "/" ] && [ ! -d "$SEARCH_DIR/.git" ]; do
    SEARCH_DIR="$(dirname "$SEARCH_DIR")"
done

if [ ! -d "$SEARCH_DIR/.git" ]; then
    echo -e "${RED}Could not locate the SweePi repository root${NC}"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAP_DIR="$SEARCH_DIR/runtime/raspberry_pi/maps"
mkdir -p "$MAP_DIR"

MAP_NAME="sweepi_map_$TIMESTAMP"

echo -e "${YELLOW}=======================================${NC}"
echo -e "${YELLOW}   SweePi Map Saver${NC}"
echo -e "${YELLOW}=======================================${NC}"
echo -e "Saving map to: ${GREEN}$MAP_DIR/$MAP_NAME${NC}"
echo ""

ros2 run nav2_map_server map_saver_cli -f "$MAP_DIR/$MAP_NAME"

if [ -f "$MAP_DIR/${MAP_NAME}.yaml" ]; then
    echo ""
    echo -e "${GREEN}Map saved successfully${NC}"
    echo -e "${GREEN}  YAML: $MAP_DIR/${MAP_NAME}.yaml${NC}"
    echo -e "${GREEN}  PGM:  $MAP_DIR/${MAP_NAME}.pgm${NC}"
else
    echo ""
    echo -e "${RED}Error saving map${NC}"
    exit 1
fi

echo -e "${YELLOW}=======================================${NC}"
