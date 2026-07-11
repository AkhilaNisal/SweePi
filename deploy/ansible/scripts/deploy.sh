#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f inventory.ini ]]; then
  echo "inventory.ini is missing."
  echo "Run: cp inventory.ini.example inventory.ini"
  exit 1
fi

MODE="all"
TAGS=""
SKIP_TAGS=""
RUN_VERIFY="true"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      MODE="all"
      RUN_VERIFY="true"
      shift
      ;;

    --only)
      MODE="only"
      TAGS="${2:-}"
      RUN_VERIFY="false"
      if [[ -z "$TAGS" ]]; then
        echo "Usage: bash scripts/deploy.sh --only bluetooth,power"
        exit 1
      fi
      shift 2
      ;;

    --skip)
      MODE="skip"
      SKIP_TAGS="${2:-}"
      RUN_VERIFY="false"
      if [[ -z "$SKIP_TAGS" ]]; then
        echo "Usage: bash scripts/deploy.sh --skip ros2,workspace"
        exit 1
      fi
      shift 2
      ;;

    --verify)
      RUN_VERIFY="true"
      shift
      ;;

    --no-verify)
      RUN_VERIFY="false"
      shift
      ;;

    -h|--help)
      echo "Usage:"
      echo "  bash scripts/deploy.sh"
      echo "  bash scripts/deploy.sh --all"
      echo "  bash scripts/deploy.sh --only desktop"
      echo "  bash scripts/deploy.sh --only ros2,workspace,hardware"
      echo "  bash scripts/deploy.sh --skip ros2,workspace"
      echo "  bash scripts/deploy.sh --skip desktop"
      echo "  bash scripts/deploy.sh --only services,power --verify"
      echo
      echo "Common tags:"
      echo "  preflight base boot uart network netplan bluetooth ble desktop rdp"
      echo "  ros2 workspace build hardware serial lidar udev services systemd"
      echo "  power gpio button led backup"
      exit 0
      ;;

    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

PLAYBOOK_ARGS=()

if [[ "$MODE" == "only" ]]; then
  PLAYBOOK_ARGS+=(--tags "$TAGS")
elif [[ "$MODE" == "skip" ]]; then
  PLAYBOOK_ARGS+=(--skip-tags "$SKIP_TAGS")
fi

echo "Running SweePi deployment mode: $MODE"

if [[ "$MODE" == "only" ]]; then
  echo "Only tags: $TAGS"
fi

if [[ "$MODE" == "skip" ]]; then
  echo "Skipping tags: $SKIP_TAGS"
fi

ansible-playbook site.yml \
  --ask-become-pass \
  "${PLAYBOOK_ARGS[@]}" \
  "${EXTRA_ARGS[@]}"

if [[ "$RUN_VERIFY" == "true" ]]; then
  echo "Running full verification..."
  ansible-playbook verify.yml --ask-become-pass
else
  echo "Skipping full verification for partial deployment."
fi
