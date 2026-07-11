# SweePi Raspberry Pi Ansible deployment

This deployment restores a freshly flashed Raspberry Pi running Ubuntu Server
24.04 LTS ARM64 to the production SweePi host state.

Assumptions before running:

- hostname can initially be reached by IP or existing mDNS
- SSH is enabled
- user `sweepi` exists and can use sudo
- Wi-Fi is already configured, or `sweepi_manage_netplan` is enabled with vaulted credentials

## Quick start

```bash
cd deploy/ansible
cp inventory.ini.example inventory.ini
nano inventory.ini

ansible-playbook site.yml --syntax-check
bash scripts/deploy.sh --all
```

After deployment the Pi should be reachable as:

```bash
ssh sweepi@sweepi.local
```

## Roles

The full deployment runs roles in this order:

1. `preflight` validates host, secrets and configuration.
2. `base` upgrades Ubuntu and configures hostname, locale, SSH, mDNS, groups and host directories.
3. `boot_config` enables `/dev/ttyAMA0`, removes serial console use and masks serial getty units.
4. `netplan` optionally installs a bootstrap Wi-Fi profile.
5. `bluetooth` optionally installs BLE Wi-Fi provisioning.
6. `desktop_remote` optionally installs XFCE/XRDP for Remmina.
7. `ros2` installs ROS 2 Jazzy using the official `ros2-apt-source` package.
8. `workspace` checks out the repo, initializes recursive submodules, installs rosdeps and builds.
9. `hardware_access` installs the RPLIDAR udev rule.
10. `services` installs robot/API systemd units.
11. `power_control` installs the top button and `switch_bulb` controller.
12. `backup` optionally installs encrypted Restic backups.

## Important variables

Core defaults:

```yaml
sweepi_user: sweepi
sweepi_hostname: sweepi
sweepi_timezone: Asia/Colombo
sweepi_locale: en_US.UTF-8
sweepi_workspace: /home/sweepi/SweePi
sweepi_reboot_after_deploy: true
```

Host management:

```yaml
sweepi_manage_etc_hosts: true
sweepi_disable_cloud_init_hosts_management: true
sweepi_enable_mdns: true
sweepi_perform_full_upgrade: true
sweepi_apt_autoremove: false
```

`base` creates `/etc/cloud/cloud.cfg.d/99-sweepi-hosts.cfg` with
`manage_etc_hosts: false`; it does not destructively edit the main cloud-init
configuration. `/etc/hosts` is managed with `127.0.0.1 localhost` and
`127.0.1.1 sweepi`.

Hardware:

```yaml
sweepi_base_serial_port: /dev/ttyAMA0
sweepi_base_baud_rate: 115200
sweepi_lidar_serial_port: /dev/rplidar
sweepi_lidar_fallback_serial_port: /dev/ttyUSB0
sweepi_lidar_baud_rate: 460800
sweepi_lidar_frame_id: lidar_link
```

ROS/workspace:

```yaml
sweepi_ros_distro: jazzy
sweepi_install_simulation: false
sweepi_colcon_executor: sequential
sweepi_force_workspace_rebuild: false
sweepi_clean_workspace_before_build: false
```

Simulation packages declared by development packages are skipped on the
production Pi by default:

```yaml
sweepi_rosdep_skip_keys:
  - gazebo
  - gazebo_ros
  - gazebo_ros2_control
  - gz_ros2_control
  - ros_gz
  - ros_gz_sim
  - ros_gz_bridge
```

## Private repository checkout

Public HTTPS checkout is the default:

```yaml
sweepi_repo_auth_method: https
sweepi_repo_url: https://github.com/AkhilaNisal/SweePi.git
sweepi_repo_version: main
```

For a private repository, use a read-only GitHub deploy key and Ansible Vault:

```bash
cd deploy/ansible
cp group_vars/vault.yml.example group_vars/vault.yml
nano group_vars/vault.yml
ansible-vault encrypt group_vars/vault.yml
```

Set:

```yaml
sweepi_repo_auth_method: ssh
sweepi_git_deploy_key_enabled: true
sweepi_git_deploy_key_private: |
  paste the encrypted private key contents here
```

The key is installed as `/home/sweepi/.ssh/id_ed25519_sweepi` with mode `0600`.
GitHub host keys are installed into the `sweepi` user’s `known_hosts`. Do not put
GitHub tokens or passwords in `sweepi_repo_url`.

The checkout initializes recursive submodules. The RPLIDAR source is expected at:

```text
/home/sweepi/SweePi/src/sllidar_ros2
```

## ROS 2 Jazzy installation

The `ros2` role targets Ubuntu 24.04 Noble and ROS 2 Jazzy. It ensures Ubuntu
sources include `universe`, migrates away from the legacy manually managed ROS
APT key/list file, installs the latest official Noble `ros2-apt-source` release
package, then installs ROS and SweePi system dependencies through APT.

System Python dependencies are installed through Ubuntu packages, not `sudo pip`.

## Workspace build

The production Pi uses a memory-safe sequential build:

```bash
colcon build --symlink-install --executor sequential
```

The build runs as `sweepi`, not root. It runs when the repository or submodules
change, when `install/setup.bash` is missing, or when
`sweepi_force_workspace_rebuild` is true. `build`, `install` and `log` are not
deleted unless `sweepi_clean_workspace_before_build` is true.

## Remote desktop through Remmina

Remote desktop is enabled by default:

```yaml
sweepi_enable_remote_desktop: true
sweepi_manage_ufw: false
sweepi_rdp_allow_subnet: "192.168.8.0/24"
```

The role installs XFCE and XRDP, not the full GNOME desktop. It does not switch
the robot to `graphical.target`.

Remmina settings:

- Protocol: RDP
- Server: `sweepi.local`
- Username: `sweepi`
- XRDP session: Xorg
- Suggested resolution: `1280x720`

UFW is not enabled automatically. If `sweepi_manage_ufw` is true, Ansible allows
TCP 3389 only from `sweepi_rdp_allow_subnet`.

Manual RViz launch over Remmina:

```bash
cd ~/SweePi
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch sweepi_robot_manager master.launch.py \
  launch_api_bridge:=true \
  launch_rviz:=true \
  lidar_serial_port:=/dev/rplidar
```

## Headless production robot service

`sweepi-robot.service` uses the headless form:

```bash
ros2 launch sweepi_robot_manager master.launch.py \
  launch_sim:=false \
  launch_hardware:=true \
  launch_temp_hardware:=false \
  launch_api_bridge:=true \
  launch_rviz:=false \
  use_arm_assist:=false \
  base_serial_port:=/dev/ttyAMA0 \
  lidar_serial_port:=/dev/rplidar
```

Systemd explicitly disables RViz because the service has no graphical session.
The API bridge binds `0.0.0.0:8080`, so the API is available on the local
network when the robot service is running. The standalone
`sweepi-api-bridge.service` conflicts with `sweepi-robot.service` to avoid two
API bridge instances binding port 8080.

Defaults:

```yaml
sweepi_robot_enable_at_boot: false
sweepi_api_bridge_enable_at_boot: false
sweepi_button_start_service: sweepi-robot.service
```

## Button and switch_bulb behavior

The power-control service starts at boot and preserves the current behavior:

1. Pi gets power: `switch_bulb` blinks every 1 second.
2. User activates the top latching switch: `sweepi-robot.service` starts.
3. While ROS/API starts: `switch_bulb` blinks every 0.5 seconds.
4. API health succeeds: `switch_bulb` stays on.
5. User deactivates the switch: robot service stops, LED turns off, Pi powers off.

GPIO variables:

```yaml
sweepi_button_gpio: 17
sweepi_switch_bulb_gpio: 27
sweepi_button_mode: latching
sweepi_button_active_low: true
sweepi_button_bounce_seconds: 0.08
sweepi_led_boot_interval_seconds: 1.0
sweepi_led_starting_interval_seconds: 0.5
```

## UART and RPLIDAR

Boot backups are created once under:

```text
/root/sweepi-boot-backup/
```

The role sets `enable_uart=1`, removes serial console arguments from
`/boot/firmware/cmdline.txt`, and masks:

```text
serial-getty@ttyAMA0.service
serial-getty@serial0.service
```

RPLIDAR udev rule:

```text
source: /home/sweepi/SweePi/src/sllidar_ros2/scripts/rplidar.rules
target: /etc/udev/rules.d/60-rplidar.rules
preferred device: /dev/rplidar
fallback: /dev/ttyUSB0
```

The LiDAR does not have to be connected during provisioning.

## BLE UUIDs

BLE UUIDs are copied from the Flutter app branch
`origin/app-rpi-integration`, file
`src/app/lib/core/provisioning/ble_uuid_constants.dart`. They are not guessed.
Preflight fails if values are placeholders, duplicated, or different from the
current app constants.

## Backups

Backups are disabled by default. To enable:

```yaml
sweepi_enable_backup: true
sweepi_restic_repository: "sftp:backupuser@SERVER:/backups/sweepi"
```

Store `sweepi_restic_password` in encrypted `group_vars/vault.yml`.

## Partial deployments

Examples:

```bash
bash scripts/deploy.sh --all
bash scripts/deploy.sh --only desktop
bash scripts/deploy.sh --only ros2,workspace,hardware
bash scripts/deploy.sh --skip desktop
bash scripts/deploy.sh --skip ros2,workspace
bash scripts/deploy.sh --only services,power --verify
```

Full deployment runs verification by default. Partial deployments skip full
verification unless `--verify` is explicitly provided.

## Verification

`verify.yml` checks hostname, `/etc/hosts`, SSH, Avahi, timezone, locale, groups,
XRDP, ROS, workspace packages, submodules, rosdep, UART configuration, RPLIDAR
udev, service units and API health when a service is running.

Standard verification does not start the robot or motors:

```yaml
sweepi_verify_start_robot_temporarily: false
```

Hardware presence is reported separately. Missing `/dev/rplidar`, `/dev/ttyUSB0`
or `/dev/ttyAMA0` is not treated as a provisioning failure when the udev/boot
configuration is correct.

## Recovery from a failed SD card

1. Flash Ubuntu Server 24.04 LTS ARM64.
2. Configure Wi-Fi or prepare vaulted netplan variables.
3. Enable SSH.
4. Create user `sweepi` with sudo access.
5. From the control machine:

```bash
cd deploy/ansible
cp inventory.ini.example inventory.ini
nano inventory.ini
bash scripts/deploy.sh --all
```

## Rerun after changing one area

- Base/hostname/locale: `bash scripts/deploy.sh --only base --verify`
- UART: `bash scripts/deploy.sh --only boot --verify`
- Desktop/RDP: `bash scripts/deploy.sh --only desktop --verify`
- ROS packages: `bash scripts/deploy.sh --only ros2,workspace,hardware --verify`
- Service templates: `bash scripts/deploy.sh --only services,power --verify`
- Backups: `bash scripts/deploy.sh --only backup --verify`

## Files not to commit

Do not commit:

- `inventory.ini`
- `group_vars/vault.yml`
- private SSH keys
- GitHub tokens
- Wi-Fi passwords
- backup passwords
