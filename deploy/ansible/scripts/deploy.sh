#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f inventory.ini ]]; then
  echo "inventory.ini is missing."
  echo "Run: cp inventory.ini.example inventory.ini"
  exit 1
fi

ansible-playbook site.yml --ask-become-pass "$@"
ansible-playbook verify.yml --ask-become-pass
