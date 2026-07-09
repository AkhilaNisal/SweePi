# SweePi Mobile App Wi-Fi Provisioning and API Bridge Setup

## Preconditions

- Raspberry Pi BLE provisioning service is running.
- Phone Bluetooth is enabled.
- Phone and robot must end up on the same Wi-Fi or hotspot.
- ROS 2 environment is available on the Raspberry Pi.

## BLE Wi-Fi Setup Flow

1. The app discovers SweePi over BLE.
2. The app connects to the SweePi BLE GATT service.
3. The app scans available Wi-Fi networks.
4. The user selects or manually enters an SSID and password.
5. The app sends credentials over the `WIFI_CONFIG` characteristic.
6. The Raspberry Pi joins Wi-Fi.
7. The app connects to the SweePi API over Wi-Fi.

If SweePi reports that it is currently connected to a different SSID than the
one selected in the app, the app warns before continuing. This does not block
setup, but after provisioning the phone must also be connected to the selected
SSID or the app may not find SweePi over Wi-Fi.

## API Bridge Requirement

Start the ROS API bridge manually on the Raspberry Pi:

```bash
ros2 launch sweepi_api_bridge api_bridge.launch.py
```

Expected log:

```text
SweePi API bridge listening on http://0.0.0.0:8080/api
```

Health check:

```bash
curl http://<robot-ip>:8080/api/system/health
```

The mobile app uses this endpoint to confirm that the robot API is reachable:

```text
http://<robot-ip>:8080/api/system/health
```

## Troubleshooting

- "Nothing listening on 8080" means the API bridge is not running.
- "Connection refused" means the IP is reachable but the API server is not accepting connections.
- "Timed out" usually means wrong network, wrong IP, hotspot isolation, or firewall.
- "GATT_UNLIKELY" means BLE write handler problem; the `WIFI_CONFIG` handler must return quickly and should not block while running netplan.
- `127.0.0.1` means the current device, not always the robot.
- If the app still tries an old robot IP, rediscover SweePi or clear the selected robot from the app before trying again.

## Useful Commands

```bash
hostname -I
ip addr show wlan0 | grep "inet "
sudo ss -ltnp | grep ':8080' || echo "Nothing listening on 8080"
curl -v http://<robot-ip>:8080/api/system/health
journalctl -u sweepi-ble-provisioning.service -f -o cat
```
