#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y pipx openssh-client
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"

if ! command -v ansible-playbook >/dev/null 2>&1; then
  pipx install --include-deps ansible
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"
ansible-galaxy collection install -r requirements.yml
ansible --version
