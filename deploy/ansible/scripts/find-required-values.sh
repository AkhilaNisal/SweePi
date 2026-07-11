#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo "BLE UUID candidates from the Flutter application:"
grep -RInE \
  'serviceUuid|wifiConfig|wifiScan|wifiStatus|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' \
  "$REPO_ROOT/src/app/lib" 2>/dev/null || true

cat <<'EOF'

GPIO values cannot be guessed safely.
Enter BCM GPIO numbers, not physical header pin numbers, in:
  deploy/ansible/group_vars/all.yml

Required:
  sweepi_button_gpio
  sweepi_switch_bulb_gpio
EOF
