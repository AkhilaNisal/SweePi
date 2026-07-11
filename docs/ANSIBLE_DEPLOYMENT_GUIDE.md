# SweePi Raspberry Pi Ansible Deployment Guide

This branch contains the reproducible Raspberry Pi deployment system for **SweePi**.

The purpose of this Ansible setup is to avoid losing Raspberry Pi configuration again when an SD card fails. Instead of manually configuring the Raspberry Pi every time, the required OS-level setup is stored as code and can be reapplied to a new Raspberry Pi.

This deployment is intended to configure:

- Ubuntu host packages
- Raspberry Pi hostname and user environment
- SSH and mDNS
- UART for the STM32/base controller
- Bluetooth/BlueZ Wi-Fi provisioning
- top button behavior
- `switch_bulb` LED behavior
- systemd services
- ROS 2 Jazzy setup, when full deployment is used
- SweePi workspace clone and build, when full deployment is used
- optional encrypted backup support

---

## 1. Why this branch exists

The previous Raspberry Pi SD card failed and some OS-level configuration was lost. The lost configuration included things that were not fully stored in the normal ROS repository, such as:

- button startup behavior
- LED/status bulb behavior
- Bluetooth provisioning service
- systemd service files
- UART/serial configuration
- host package installation
- netplan or network-related configuration
- startup/shutdown behavior

This branch solves that problem by keeping those settings as repeatable deployment code.

The idea is:

```text
Fresh Ubuntu Raspberry Pi
        ↓
SSH access
        ↓
Run Ansible from laptop/WSL
        ↓
Raspberry Pi is configured automatically
```

---

## 2. Repository strategy

This branch is an **orphan branch**.

That means it lives inside the same GitHub repository, but it does not start from the normal `main` branch history.

The normal project branch is used for robot/app code:

```text
main
    ROS 2 packages
    Flutter app branches
    robot source code
```

This branch is used for infrastructure:

```text
infra/ansible-deployment
    Raspberry Pi deployment automation
    systemd services
    button/LED setup
    Bluetooth provisioning
    recovery documentation
```

This makes the Ansible deployment behave like a small standalone deployment repository while still living under the same GitHub project.

---

## 3. What Ansible does

Ansible runs from a control machine and connects to the Raspberry Pi over SSH.

In our workflow:

```text
Windows laptop
    ↓
WSL Ubuntu
    ↓
Ansible
    ↓
Raspberry Pi over SSH
```

The Raspberry Pi does not need Ansible permanently installed. It only needs:

- Ubuntu Server
- SSH enabled
- Python 3
- a user with sudo permission

The Ansible playbook then installs packages, copies scripts, creates service files, enables services, and applies system configuration.

---

## 4. Directory structure

Main deployment directory:

```text
deploy/ansible/
├── ansible.cfg
├── inventory.ini.example
├── requirements.yml
├── site.yml
├── verify.yml
├── group_vars/
│   ├── all.yml
│   └── vault.yml.example
├── roles/
│   ├── preflight/
│   ├── base/
│   ├── boot_config/
│   ├── bluetooth/
│   ├── ros2/
│   ├── workspace/
│   ├── services/
│   ├── power_control/
│   ├── backup/
│   └── netplan/
└── scripts/
    ├── deploy.sh
    ├── install-control-node.sh
    └── find-required-values.sh
```

---

## 5. Important files

### `group_vars/all.yml`

This is the main configuration file.

Edit this file to configure robot-specific values such as:

- Raspberry Pi username
- hostname
- GPIO pins
- BLE UUIDs
- ROS branch
- button behavior
- LED blink timing
- backup settings

Example:

```yaml
sweepi_user: sweepi
sweepi_hostname: sweepi
sweepi_workspace: /home/sweepi/SweePi
```

### `inventory.ini`

This file tells Ansible how to connect to the Raspberry Pi.

It is intentionally ignored by Git because IP addresses can change.

Create it from the example:

```bash
cp inventory.ini.example inventory.ini
```

Example using IP address:

```ini
[sweepi]
sweepi_robot ansible_host=192.168.8.182 ansible_user=sweepi

[sweepi:vars]
ansible_python_interpreter=/usr/bin/python3
```

Example using mDNS:

```ini
[sweepi]
sweepi_robot ansible_host=sweepi.local ansible_user=sweepi

[sweepi:vars]
ansible_python_interpreter=/usr/bin/python3
```

When setting up a new Raspberry Pi, use the IP address first if `sweepi.local` does not resolve.

### `site.yml`

This is the main playbook.

It applies the full Raspberry Pi configuration.

### `verify.yml`

This checks whether important services and files are present after deployment.

### `scripts/deploy.sh`

This is the recommended deployment entry point.

It supports:

- full deployment
- partial deployment using tags
- skipping selected parts
- optional verification

---

## 6. Required Raspberry Pi image setup

When flashing the Raspberry Pi SD card, use:

```text
OS:       Ubuntu Server 24.04 LTS 64-bit
Username: sweepi
Hostname: sweepi
SSH:      enabled
Wi-Fi:    configured
```

The target SSH command is:

```bash
ssh sweepi@sweepi.local
```

If `.local` does not work yet, find the Pi IP and use:

```bash
ssh sweepi@RASPBERRY_PI_IP
```

Example:

```bash
ssh sweepi@192.168.8.182
```

---

## 7. Control machine setup using Windows WSL

Run Ansible from WSL Ubuntu, not from normal Windows CMD or PowerShell.

Open WSL:

```cmd
wsl
```

Install required tools:

```bash
sudo apt update
sudo apt install -y git unzip pipx openssh-client
pipx ensurepath
exec "$SHELL" -l
```

Install Ansible and required collections using the included script:

```bash
cd ~/projects/SweePi
bash deploy/ansible/scripts/install-control-node.sh
```

Check:

```bash
ansible --version
```

---

## 8. SSH setup

First test password SSH:

```bash
ssh sweepi@192.168.8.182
```

Exit:

```bash
exit
```

If WSL has no SSH key yet, create one:

```bash
ssh-keygen -t ed25519 -C "sweepi-ansible"
```

Press Enter for the default path and optionally leave the passphrase empty.

Copy the key to the Pi:

```bash
ssh-copy-id sweepi@192.168.8.182
```

Test passwordless login:

```bash
ssh sweepi@192.168.8.182
```

Exit:

```bash
exit
```

---

## 9. Main configuration values

Open:

```bash
cd ~/projects/SweePi/deploy/ansible
nano group_vars/all.yml
```

### 9.1 User, hostname and workspace

For the current SweePi setup:

```yaml
sweepi_user: sweepi
sweepi_hostname: sweepi
sweepi_workspace: /home/sweepi/SweePi
```

### 9.2 GPIO pins

These must be real **BCM GPIO numbers**, not physical header pin numbers.

```yaml
sweepi_button_gpio: YOUR_BUTTON_BCM_GPIO
sweepi_switch_bulb_gpio: YOUR_LED_BCM_GPIO
```

Do not leave them as:

```yaml
sweepi_button_gpio: -1
sweepi_switch_bulb_gpio: -1
```

### 9.3 BLE values

Known values from the old setup:

```yaml
sweepi_ble_robot_id: sweepi-dev-001
sweepi_ble_name: SweePi-Dev-001
sweepi_ble_service_uuid: "7a0b0001-4f2a-4f7a-9b7d-9c7b6f000001"
```

The app and Raspberry Pi must use the same characteristic UUIDs:

```yaml
sweepi_ble_wifi_config_uuid: "..."
sweepi_ble_wifi_scan_uuid: "..."
sweepi_ble_wifi_status_uuid: "..."
```

Do not leave them as:

```yaml
"CHANGE_ME"
```

### 9.4 Button service target

If the button should start only the API bridge:

```yaml
sweepi_button_start_service: sweepi-api-bridge.service
```

If the button should start the full robot stack:

```yaml
sweepi_button_start_service: sweepi-robot.service
```

For the real robot, this is normally preferred:

```yaml
sweepi_button_start_service: sweepi-robot.service
```

### 9.5 Backup settings

Backup is disabled by default:

```yaml
sweepi_enable_backup: false
```

Therefore these placeholders can remain for now:

```yaml
sweepi_restic_repository: "CHANGE_ME"
sweepi_restic_password: "CHANGE_ME_USE_ANSIBLE_VAULT"
```

When backup is enabled later, these must be configured using Ansible Vault.

---

## 10. Quick configuration check

Before deployment, run:

```bash
cd ~/projects/SweePi/deploy/ansible
grep -nE "CHANGE_ME|-1|thunderbot" group_vars/all.yml
```

Expected:

- no `-1`
- no `thunderbot`
- no BLE `CHANGE_ME`

It is okay if the only remaining `CHANGE_ME` values are Restic backup values while:

```yaml
sweepi_enable_backup: false
```

---

## 11. Ansible connection test

From:

```bash
cd ~/projects/SweePi/deploy/ansible
```

Test without sudo:

```bash
ansible sweepi -m ping -e ansible_become=false
```

Expected:

```text
sweepi_robot | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

Test with sudo:

```bash
ansible sweepi -m ping --ask-become-pass
```

or:

```bash
ansible sweepi -m ping -K
```

Enter the Raspberry Pi `sweepi` password.

Expected:

```text
sweepi_robot | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

---

## 12. Syntax check

Run:

```bash
ansible-playbook site.yml --syntax-check
ansible-playbook verify.yml --syntax-check
```

Warnings about deprecation are not fatal. If the output ends with:

```text
playbook: site.yml
playbook: verify.yml
```

the syntax check passed.

---

## 13. Full deployment from scratch

For a fresh Raspberry Pi where Ansible should configure everything:

```bash
cd ~/projects/SweePi/deploy/ansible
bash scripts/deploy.sh
```

or:

```bash
bash scripts/deploy.sh --all
```

This applies all roles:

```text
preflight
base
boot_config
netplan, if enabled
bluetooth
ros2
workspace
services
power_control
backup, if enabled
```

Use this mode for a new clean Raspberry Pi.

---

## 14. Partial deployment

Partial deployment is useful when the Raspberry Pi already has some components installed manually.

### 14.1 Deploy only Bluetooth and button/LED

```bash
bash scripts/deploy.sh --only bluetooth,power
```

This applies only:

```text
Bluetooth provisioning
Top button logic
switch_bulb LED logic
```

### 14.2 Deploy only Bluetooth

```bash
bash scripts/deploy.sh --only bluetooth
```

### 14.3 Deploy only button and switch_bulb

```bash
bash scripts/deploy.sh --only power
```

### 14.4 Deploy everything except ROS and workspace

```bash
bash scripts/deploy.sh --skip ros2,workspace
```

This is useful if ROS was installed manually but you still want host services and power/BLE setup.

---

## 15. What each role does

### `preflight`

Checks whether the target is suitable.

It validates:

- Ubuntu version
- 64-bit ARM architecture
- target user exists
- GPIO values are configured
- BLE UUIDs are valid
- backup values are configured when backup is enabled

### `base`

Configures basic host setup.

It installs common packages and creates directories:

```text
/opt/sweepi
/opt/sweepi/ble
/opt/sweepi/power
/etc/sweepi
/var/lib/sweepi
/var/lib/sweepi/maps
/var/lib/sweepi/calibration
/var/log/sweepi
```

It also configures:

- hostname
- timezone
- SSH
- mDNS through `avahi-daemon`
- user hardware groups

### `boot_config`

Configures Raspberry Pi boot-level serial settings.

It enables:

```text
enable_uart=1
```

It disables serial console/getty usage so the STM32/base serial link can use:

```text
/dev/ttyAMA0
```

### `bluetooth`

Installs and configures BlueZ BLE Wi-Fi provisioning.

It installs:

```text
sweepi-ble-provisioning.service
```

The service reads:

```text
/etc/sweepi/ble.env
```

and installs the provisioning Python script at:

```text
/opt/sweepi/ble/sweepi_ble_provisioning.py
```

This allows the mobile app to send Wi-Fi credentials over BLE.

### `ros2`

Installs ROS 2 Jazzy and required ROS packages.

This is used for fresh setup.

If ROS is already installed manually and APT sources conflict, use partial deployment or fix the duplicate ROS APT source on that Pi.

### `workspace`

Clones the SweePi repository and builds it with `colcon`.

Main variables:

```yaml
sweepi_repo_url: https://github.com/AkhilaNisal/SweePi.git
sweepi_repo_version: main
sweepi_workspace: /home/sweepi/SweePi
```

### `services`

Installs systemd services for the ROS API and full robot stack.

Installed services:

```text
sweepi-api-bridge.service
sweepi-robot.service
```

The complete robot service launches:

```bash
ros2 launch sweepi_robot_manager master.launch.py \
  launch_sim:=false \
  launch_hardware:=true \
  launch_base:=true \
  launch_ekf:=true \
  launch_robot_description:=true \
  launch_lidar:=true \
  launch_api_bridge:=true
```

### `power_control`

Installs the top button and `switch_bulb` service.

Installed service:

```text
sweepi-power-control.service
```

Installed script:

```text
/opt/sweepi/power/sweepi_power_control.py
```

Installed environment file:

```text
/etc/sweepi/power.env
```

### `backup`

Optional Restic backup setup.

Disabled by default.

It can later be used to back up:

```text
/etc
/opt/sweepi
/var/lib/sweepi
/boot/firmware
/home/sweepi/SweePi
```

### `netplan`

Optional Wi-Fi/netplan management.

Disabled by default to avoid accidentally disconnecting the Pi.

---

## 16. Button and switch_bulb behavior

The power control role implements this behavior:

```text
Pi receives power
    switch_bulb blinks every 1 second

Top button/switch becomes active
    configured SweePi service starts
    switch_bulb blinks every 0.5 seconds

API health endpoint becomes ready
    switch_bulb remains continuously ON

Top button/switch becomes inactive
    configured SweePi service stops
    switch_bulb turns OFF
    Raspberry Pi performs graceful poweroff
```

Important variables:

```yaml
sweepi_button_mode: latching
sweepi_button_active_low: true
sweepi_button_bounce_seconds: 0.08

sweepi_led_boot_interval_seconds: 1.0
sweepi_led_starting_interval_seconds: 0.5

sweepi_button_start_service: sweepi-robot.service
sweepi_api_health_url: http://127.0.0.1:8080/api/system/health
sweepi_api_health_timeout_seconds: 120
```

For a momentary button:

```yaml
sweepi_button_mode: momentary
```

For a latching switch:

```yaml
sweepi_button_mode: latching
```

---

## 17. Installed systemd services

After deployment, check services on the Raspberry Pi:

```bash
sudo systemctl status sweepi-ble-provisioning.service
sudo systemctl status sweepi-power-control.service
sudo systemctl status sweepi-api-bridge.service
sudo systemctl status sweepi-robot.service
```

View logs:

```bash
sudo journalctl -u sweepi-ble-provisioning.service -n 80 --no-pager
sudo journalctl -u sweepi-power-control.service -n 80 --no-pager
sudo journalctl -u sweepi-api-bridge.service -n 80 --no-pager
sudo journalctl -u sweepi-robot.service -n 80 --no-pager
```

Follow live logs:

```bash
sudo journalctl -u sweepi-power-control.service -f
```

---

## 18. After deployment verification

Run from WSL:

```bash
cd ~/projects/SweePi/deploy/ansible
ansible-playbook verify.yml --ask-become-pass
```

Manual checks on the Pi:

```bash
hostname
whoami
ls -la /opt/sweepi
ls -la /etc/sweepi
ls -la /var/lib/sweepi
```

Check UART:

```bash
ls -l /dev/ttyAMA0
```

Check mDNS:

```bash
ssh sweepi@sweepi.local
```

If `.local` does not work from WSL, use IP address in `inventory.ini`. Windows and WSL sometimes behave differently with `.local` name resolution.

---

## 19. Known issue: `/boot/firmware` backup filename

The Raspberry Pi boot partition is usually FAT-based. FAT does not allow some characters that Ansible may put in automatic backup filenames, such as `:`.

If an Ansible task fails while backing up:

```text
/boot/firmware/cmdline.txt
```

with an invalid filename error, use manual safe backups instead and avoid Ansible timestamped backup files on `/boot/firmware`.

Manual backup command:

```bash
ansible sweepi -b -K -m shell -a '
mkdir -p /root/sweepi-boot-backup &&
cp -a /boot/firmware/config.txt /root/sweepi-boot-backup/config.txt.before-ansible &&
cp -a /boot/firmware/cmdline.txt /root/sweepi-boot-backup/cmdline.txt.before-ansible
'
```

---

## 20. Known issue: ROS APT source conflict

If ROS was already installed manually, APT may contain two ROS source definitions with different `Signed-By` values.

Error example:

```text
Conflicting values set for option Signed-By regarding source http://packages.ros.org/ros2/ubuntu
```

For future fresh installs, the full Ansible deployment should manage ROS from scratch.

For a current Pi that already has ROS manually installed, either:

1. fix the duplicate ROS APT source once, or
2. use partial deployment:

```bash
bash scripts/deploy.sh --only bluetooth,power
```

or:

```bash
bash scripts/deploy.sh --skip ros2,workspace
```

Do not permanently remove ROS installation logic from this branch, because the main purpose of this branch is full fresh deployment.

---

## 21. Commit workflow

After editing the deployment files:

```bash
cd ~/projects/SweePi
git status
git add deploy/ansible
git commit -m "Update Raspberry Pi Ansible deployment"
git push
```

Do not commit:

```text
deploy/ansible/inventory.ini
deploy/ansible/group_vars/vault.yml
private SSH keys
plain-text passwords
```

These are excluded or should remain local.

---

## 22. Recommended recovery process after future SD failure

When another SD card fails:

1. Flash Ubuntu Server 24.04 LTS 64-bit.
2. Set:
   - username: `sweepi`
   - hostname: `sweepi`
   - SSH enabled
   - Wi-Fi connected
3. Boot the Pi.
4. Find the IP:
   ```bash
   hostname -I
   ```
5. From WSL:
   ```bash
   ssh-copy-id sweepi@RASPBERRY_PI_IP
   ```
6. Configure:
   ```bash
   deploy/ansible/inventory.ini
   ```
7. Run:
   ```bash
   cd ~/projects/SweePi/deploy/ansible
   bash scripts/deploy.sh --all
   ```
8. Verify services:
   ```bash
   ansible-playbook verify.yml --ask-become-pass
   ```

This should restore the host setup without manually repeating all Raspberry Pi configuration steps.

---

## 23. Practical command summary

### Full fresh deployment

```bash
cd ~/projects/SweePi/deploy/ansible
bash scripts/deploy.sh --all
```

### Only Bluetooth and button/LED

```bash
bash scripts/deploy.sh --only bluetooth,power
```

### Everything except ROS and workspace

```bash
bash scripts/deploy.sh --skip ros2,workspace
```

### Check connection

```bash
ansible sweepi -m ping -e ansible_become=false
ansible sweepi -m ping -K
```

### Syntax check

```bash
ansible-playbook site.yml --syntax-check
ansible-playbook verify.yml --syntax-check
```

### Verify deployment

```bash
ansible-playbook verify.yml --ask-become-pass
```

---

## 24. Final rule

Any permanent Raspberry Pi change should be stored in one of these places:

```text
Ansible task
Ansible template
group_vars/all.yml variable
encrypted vault file
documented recovery command
```

Do not make important Raspberry Pi changes only by hand. If a change is important enough to keep, it should be reproducible through this Ansible branch.
