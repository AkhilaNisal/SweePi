# SweePi complete Raspberry Pi deployment

This is the actual host implementation, not a preliminary setup phase. One
playbook installs and configures:

- Ubuntu host packages, hostname, timezone, users and groups
- UART on `/dev/ttyAMA0` and disabled serial console
- BlueZ BLE Wi-Fi provisioning and its systemd service
- ROS 2 Jazzy, rosdep dependencies and the SweePi workspace build
- API bridge and complete robot systemd units
- top button and `switch_bulb` GPIO behavior
- optional managed netplan
- optional encrypted Restic backups

## Values that must be entered

Open:

```bash
nano deploy/ansible/group_vars/all.yml
```

Set the two BCM GPIO numbers:

```yaml
sweepi_button_gpio: 17
sweepi_switch_bulb_gpio: 27
```

The numbers above are only examples. Use the pins wired on the robot.

Set the four UUIDs to exactly match the Flutter application:

```yaml
sweepi_ble_service_uuid: "..."
sweepi_ble_wifi_config_uuid: "..."
sweepi_ble_wifi_scan_uuid: "..."
sweepi_ble_wifi_status_uuid: "..."
```

Search the application automatically:

```bash
bash deploy/ansible/scripts/find-required-values.sh
```

## Deploy from the Ubuntu laptop

```bash
cd ~/SweePi
git switch -c infra/ansible-deployment

bash deploy/ansible/scripts/install-control-node.sh

cd deploy/ansible
cp inventory.ini.example inventory.ini
nano inventory.ini

ssh-copy-id thunderbot@RASPBERRY_PI_IP

bash scripts/deploy.sh
```

The first run installs ROS and builds the workspace, so it can take time. The
playbook reboots automatically when UART or package updates require it.

## Start and inspect services

```bash
sudo systemctl start sweepi-api-bridge.service
sudo systemctl status sweepi-api-bridge.service

sudo systemctl start sweepi-robot.service
sudo systemctl status sweepi-robot.service

sudo systemctl status sweepi-ble-provisioning.service
sudo systemctl status sweepi-power-control.service
```

Do not start both `sweepi-api-bridge.service` and `sweepi-robot.service` when the
master launch is configured to include the API bridge.

## Button behavior

Default `latching` behavior:

1. Pi gets power: `switch_bulb` blinks every 1 second.
2. Top switch becomes active: configured ROS service starts.
3. While starting: bulb blinks every 0.5 seconds.
4. Health endpoint succeeds: bulb stays on.
5. Top switch becomes inactive: service stops, bulb turns off, Pi powers off.

Change this line to start the complete robot stack:

```yaml
sweepi_button_start_service: sweepi-robot.service
```

## Enable encrypted backups

Create and encrypt the vault file:

```bash
cd deploy/ansible
cp group_vars/vault.yml.example group_vars/vault.yml
nano group_vars/vault.yml
ansible-vault encrypt group_vars/vault.yml
```

Set in `group_vars/all.yml`:

```yaml
sweepi_enable_backup: true
sweepi_restic_repository: "sftp:backupuser@SERVER:/backups/sweepi"
```

Deploy with:

```bash
ansible-playbook site.yml --ask-become-pass --ask-vault-pass
```

## Commit the infrastructure

```bash
git add deploy/ansible
git commit -m "Add reproducible Raspberry Pi Ansible deployment"
git push -u origin infra/ansible-deployment
```

Do not commit `inventory.ini`, `vault.yml`, private keys or plain-text
passwords.
