# SweePi Raspberry Pi BLE Wi-Fi Provisioning Changes

This document records the Raspberry Pi-side changes made during the SweePi mobile app Wi-Fi provisioning debugging session.

The main Raspberry Pi change was made to the BLE Wi-Fi provisioning service so that the app can send Wi-Fi credentials reliably over BLE without Android returning `GATT_UNLIKELY`.

---

## 1. Raspberry Pi file changed

Runtime file on the Raspberry Pi:

```text
/opt/sweepi/ble/sweepi_ble_provisioning.py
```

Service using this file:

```text
sweepi-ble-provisioning.service
```

The service can be monitored with:

```bash
journalctl -u sweepi-ble-provisioning.service -f -o cat
```

---

## 2. Problem before the change

The mobile app successfully discovered the SweePi BLE provisioning service and found the `WIFI_CONFIG` characteristic.

The app log showed:

```text
chr: 7a0b0004-4f2a-4f7a-9b7d-9c7b6f000001
status: GATT_UNLIKELY (14)
BLE write failed. bytes=54
```

This meant:

```text
- BLE connection was working.
- The app found the correct WIFI_CONFIG characteristic.
- The app attempted to write the SSID/password JSON.
- Android rejected the write with GATT_UNLIKELY.
```

The Raspberry Pi journal did not show a useful Wi-Fi config log at first, so the issue was traced to the Raspberry Pi BLE write handler.

---

## 3. Root cause

The `WIFI_CONFIG` BLE write callback was doing the full Wi-Fi connection process directly inside the BLE characteristic setter.

The problematic behavior was:

```python
result = connect_wifi_netplan(ssid, password, country)
```

inside:

```python
@wifi_config.setter
def wifi_config(self, value, options):
    ...
```

`connect_wifi_netplan(...)` is slow because it applies netplan and waits for the Raspberry Pi to connect to Wi-Fi.

A BLE write callback should return quickly. Blocking inside the BLE write callback can cause Android/FlutterBluePlus to fail with:

```text
GATT_UNLIKELY (14)
```

---

## 4. Raspberry Pi implementation change

The `WIFI_CONFIG` setter was changed so that it only receives and validates the Wi-Fi config, updates the BLE status, starts a background worker thread, and returns quickly.

The new flow is:

```text
App writes WIFI_CONFIG over BLE
→ Raspberry Pi parses JSON
→ Raspberry Pi stores selected SSID
→ Raspberry Pi updates status to "connecting"
→ Raspberry Pi starts background worker thread
→ BLE write callback returns quickly
→ background thread runs connect_wifi_netplan(...)
→ background thread updates WIFI_STATUS to connected or failed
```

---

## 5. Added import

The Python file now needs:

```python
import threading
```

---

## 6. Updated WIFI_CONFIG setter

The `wifi_config` setter was changed to this behavior:

```python
@wifi_config.setter
def wifi_config(self, value, options):
    print("[SweePi BLE] WIFI_CONFIG write callback entered", flush=True)

    try:
        raw = bytes(value)
        payload = json.loads(raw.decode("utf-8"))

        ssid = str(payload.get("ssid", "")).strip()
        password = str(payload.get("password", ""))
        country = str(payload.get("country", "LK") or "LK")

        print(
            f"[SweePi BLE] WIFI_CONFIG received ssid={ssid!r} "
            f"password_len={len(password)} country={country}",
            flush=True,
        )
    except Exception as exc:
        print(f"[SweePi BLE] Invalid Wi-Fi config JSON: {exc}", flush=True)
        self.update_status(
            state="failed_unknown",
            message=f"Invalid Wi-Fi config JSON: {exc}",
        )
        return

    self.last_wifi_config = {
        "received": True,
        "ssid": ssid,
    }

    if not ssid:
        self.update_status(
            state="failed_unknown",
            message="SSID is empty",
        )
        return

    self.update_status(
        state="connecting",
        message=f"Connecting to Wi-Fi: {ssid}",
        ssid=ssid,
        ip=get_current_ip(),
    )

    worker = threading.Thread(
        target=self._connect_wifi_config_worker,
        args=(ssid, password, country),
        daemon=True,
    )
    worker.start()
```

Important points:

```text
- The setter logs that the callback was entered.
- The setter parses the JSON safely.
- The setter does not print the Wi-Fi password.
- Only password length is printed.
- The setter updates BLE status to connecting.
- The setter starts a daemon background thread.
- The setter returns without waiting for netplan.
```

---

## 7. Added Wi-Fi worker method

A new worker method was added:

```python
def _connect_wifi_config_worker(self, ssid, password, country):
    try:
        print(f"[SweePi BLE] Starting netplan Wi-Fi connection for {ssid!r}", flush=True)

        result = connect_wifi_netplan(ssid, password, country)

        print(
            f"[SweePi BLE] netplan result ok={result.get('ok')} "
            f"state={result.get('state')} message={result.get('message')}",
            flush=True,
        )

        if result.get("ok"):
            self.update_status(
                state="connected",
                message=result.get("message", "Connected to Wi-Fi"),
                ssid=result.get("ssid", ssid),
                ip=result.get("ip") or get_current_ip(),
                hostname=result.get("hostname") or f"{self.identity['ROBOT_ID']}.local",
            )
        else:
            self.update_status(
                state=result.get("state", "failed_unknown"),
                message=result.get("message", "Wi-Fi connection failed"),
                ssid=get_current_wifi_ssid(),
                ip=get_current_ip(),
                hostname=f"{self.identity['ROBOT_ID']}.local",
            )
    except Exception as exc:
        print(f"[SweePi BLE] Wi-Fi provisioning worker crashed: {exc}", flush=True)
        self.update_status(
            state="failed_unknown",
            message=f"Wi-Fi provisioning crashed: {exc}",
            ssid=get_current_wifi_ssid(),
            ip=get_current_ip(),
            hostname=f"{self.identity['ROBOT_ID']}.local",
        )
```

Important points:

```text
- The worker performs the slow netplan operation.
- The worker updates WIFI_STATUS after the connection attempt.
- If netplan succeeds, status becomes connected.
- If netplan fails, status becomes failed_*.
- If the worker crashes, status becomes failed_unknown.
```

---

## 8. BLE status behavior after the change

The app now expects the Raspberry Pi to report Wi-Fi provisioning states through the `WIFI_STATUS` characteristic.

Expected states include:

```text
idle
scanning
connecting
connected
failed_auth
failed_not_found
failed_timeout
failed_unknown
```

After the app writes credentials, the expected status sequence is:

```text
connecting
→ connected
```

or:

```text
connecting
→ failed_*
```

---

## 9. Verification commands used on Raspberry Pi

After editing the Python file, check Python syntax:

```bash
sudo /opt/sweepi/ble/.venv/bin/python -m py_compile /opt/sweepi/ble/sweepi_ble_provisioning.py
```

Restart the BLE provisioning service:

```bash
sudo systemctl restart sweepi-ble-provisioning.service
```

Follow logs:

```bash
journalctl -u sweepi-ble-provisioning.service -f -o cat
```

Expected BLE startup logs:

```text
[SweePi BLE] Starting BLE Wi-Fi provisioning service
[SweePi BLE] ROBOT_ID=sweepi-dev-001
[SweePi BLE] BLE_NAME=SweePi-Dev-001
[SweePi BLE] SERVICE_UUID=7a0b0001-4f2a-4f7a-9b7d-9c7b6f000001
[SweePi BLE] Advertising started
[SweePi BLE] Ready for app Wi-Fi provisioning
```

Expected logs after pressing Connect in the app:

```text
[SweePi BLE] WIFI_CONFIG write callback entered
[SweePi BLE] WIFI_CONFIG received ssid='...' password_len=... country=LK
[SweePi BLE] Starting netplan Wi-Fi connection for '...'
[SweePi BLE] netplan result ok=True state=connected message=Connected to Wi-Fi
```

---

## 10. Raspberry Pi Wi-Fi verification

Check the Raspberry Pi IP address:

```bash
hostname -I
ip addr show wlan0 | grep "inet "
```

Example result:

```text
172.20.10.6
```

The phone must be connected to the same Wi-Fi/hotspot network as this Raspberry Pi address.

---

## 11. ROS API bridge runtime requirement

This was not a BLE provisioning code change, but it is required for the app to become fully connected after Wi-Fi provisioning.

The app connects to the robot HTTP API after the Raspberry Pi joins Wi-Fi.

Manual command:

```bash
ros2 launch sweepi_api_bridge api_bridge.launch.py
```

Expected log:

```text
SweePi API bridge listening on http://0.0.0.0:8080/api
```

Check if port `8080` is listening:

```bash
sudo ss -ltnp | grep ':8080' || echo "Nothing listening on 8080"
```

Health check:

```bash
curl -v http://<robot-ip>:8080/api/system/health
```

Example:

```bash
curl -v http://172.20.10.6:8080/api/system/health
```

Expected result:

```text
HTTP/1.0 200 OK
```

Expected JSON includes:

```json
{
  "success": true,
  "message": "API server is healthy.",
  "status": "ok",
  "server": "sweepi_api_bridge"
}
```

If the API bridge is not running, the app can show a socket exception or remain offline even though BLE Wi-Fi provisioning succeeded.

---

## 12. Important networking note

`127.0.0.1` means the current device.

Examples:

```text
127.0.0.1 on the Raspberry Pi means the Raspberry Pi.
127.0.0.1 on the laptop means the laptop.
127.0.0.1 on the phone means the phone.
```

From the phone or laptop, use the Raspberry Pi IP:

```text
http://<robot-ip>:8080/api/system/health
```

Example:

```text
http://172.20.10.6:8080/api/system/health
```

---

## 13. Troubleshooting from this change

### GATT_UNLIKELY

Symptom:

```text
FlutterBluePlusException | writeCharacteristic | android-code: 14 | GATT_UNLIKELY
```

Likely cause:

```text
The Raspberry Pi BLE WIFI_CONFIG write handler is blocking or failing.
```

Fix:

```text
Make sure WIFI_CONFIG does not run connect_wifi_netplan(...) directly inside the BLE callback.
It should start a background thread and return quickly.
```

---

### Nothing listening on 8080

Command:

```bash
sudo ss -ltnp | grep ':8080' || echo "Nothing listening on 8080"
```

Meaning:

```text
The ROS API bridge is not running.
```

Fix:

```bash
ros2 launch sweepi_api_bridge api_bridge.launch.py
```

---

### Connection refused

Meaning:

```text
The IP is reachable, but port 8080 is not accepting connections.
```

Common cause:

```text
The API bridge is not running.
```

---

### Timed out

Meaning:

```text
The phone/laptop cannot reach the Raspberry Pi at that IP.
```

Common causes:

```text
- phone is connected to a different Wi-Fi/hotspot
- wrong robot IP
- hotspot client isolation
- firewall or network isolation
- Raspberry Pi disconnected from Wi-Fi
```

---

## 14. Current limitation

After a Raspberry Pi restart, the BLE provisioning service may start automatically, but the ROS API bridge may not start automatically.

Current manual command:

```bash
ros2 launch sweepi_api_bridge api_bridge.launch.py
```

Recommended next Raspberry Pi improvement:

```text
Create a systemd service for sweepi_api_bridge so the HTTP API starts automatically after boot.
```

---

# App changes summary

The main Raspberry Pi change above required matching app behavior.

The app changes are summarized here only for context.

## App files involved

```text
src/app/lib/features/setup/wifi_setup_screen.dart
src/app/lib/features/setup/wifi_connecting_screen.dart
src/app/lib/core/provisioning/ble_wifi_provisioning_service.dart
src/app/lib/core/provisioning/provisioning_status_model.dart
src/app/lib/core/network/robot_api_client.dart
src/app/lib/core/connection/robot_connection_manager.dart
```

## App-side behavior added or improved

```text
- The Wi-Fi setup screen checks real BLE GATT readiness.
- It shows BLE connected, provisioning service discovered, and WIFI_CONFIG discovered.
- It explains why the Connect button is disabled.
- It can reconnect to SweePi BLE if provisioning is not ready.
- It warns when the target SSID differs from the robot's current SSID.
- It asks for confirmation before continuing with a different SSID.
- The connecting screen polls WIFI_STATUS instead of reading it once.
- API/socket failures are shown as user-friendly Wi-Fi/API bridge troubleshooting messages.
```

## Important app behavior

BLE connection does not mean the robot is online.

The robot is fully online only after:

```text
BLE provisioning succeeds
→ Raspberry Pi joins Wi-Fi
→ phone is on the same Wi-Fi/hotspot
→ ROS API bridge is running
→ /api/system/health succeeds
```
