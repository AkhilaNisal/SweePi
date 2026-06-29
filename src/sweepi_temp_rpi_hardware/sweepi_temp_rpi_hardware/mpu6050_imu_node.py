#!/usr/bin/env python3

import json
import math
import os
import time

import rclpy
from geometry_msgs.msg import Quaternion
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String
from std_srvs.srv import Trigger

try:
    import yaml
except ImportError:
    yaml = None


PWR_MGMT_1 = 0x6B
SMPLRT_DIV = 0x19
CONFIG = 0x1A
GYRO_CONFIG = 0x1B
ACCEL_CONFIG = 0x1C
INT_ENABLE = 0x38
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43

GRAVITY = 9.80665


def euler_to_quaternion(roll, pitch, yaw):
    q = Quaternion()
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


def diagonal_to_covariance(diagonal):
    covariance = [0.0] * 9
    for index, value in enumerate(diagonal[:3]):
        covariance[index * 3 + index] = float(value)
    return covariance


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class MPU6050:
    def __init__(self, bus_num, address):
        try:
            import smbus2 as smbus_lib
        except ImportError:
            try:
                import smbus as smbus_lib
            except ImportError as exc:
                raise RuntimeError(
                    'No SMBus Python module found. Install python3-smbus or python3-smbus2.'
                ) from exc

        self.bus = smbus_lib.SMBus(bus_num)
        self.address = int(address)
        self.accel_scale = 16384.0
        self.gyro_scale = 131.0
        self.gyro_bias_dps = [0.0, 0.0, 0.0]

    def write_byte(self, register, value):
        self.bus.write_byte_data(self.address, register, value)

    def read_i2c_word(self, register):
        high = self.bus.read_byte_data(self.address, register)
        low = self.bus.read_byte_data(self.address, register + 1)
        value = (high << 8) | low
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        return value

    def initialize(self):
        self.write_byte(PWR_MGMT_1, 0x00)
        time.sleep(0.1)
        self.write_byte(SMPLRT_DIV, 0x07)
        self.write_byte(CONFIG, 0x03)
        self.write_byte(GYRO_CONFIG, 0x00)
        self.write_byte(ACCEL_CONFIG, 0x00)
        self.write_byte(INT_ENABLE, 0x00)

    def read_raw(self):
        ax = self.read_i2c_word(ACCEL_XOUT_H)
        ay = self.read_i2c_word(ACCEL_XOUT_H + 2)
        az = self.read_i2c_word(ACCEL_XOUT_H + 4)
        gx = self.read_i2c_word(GYRO_XOUT_H)
        gy = self.read_i2c_word(GYRO_XOUT_H + 2)
        gz = self.read_i2c_word(GYRO_XOUT_H + 4)
        return ax, ay, az, gx, gy, gz

    def read_scaled(self):
        ax, ay, az, gx, gy, gz = self.read_raw()
        accel_g = [
            ax / self.accel_scale,
            ay / self.accel_scale,
            az / self.accel_scale,
        ]
        gyro_dps = [
            gx / self.gyro_scale - self.gyro_bias_dps[0],
            gy / self.gyro_scale - self.gyro_bias_dps[1],
            gz / self.gyro_scale - self.gyro_bias_dps[2],
        ]
        return accel_g, gyro_dps

    def close(self):
        if hasattr(self.bus, 'close'):
            self.bus.close()


class MPU6050ImuNode(Node):
    def __init__(self):
        super().__init__('sweepi_temp_mpu6050')

        self.declare_parameter('i2c_bus', 1)
        self.declare_parameter('i2c_address', 0x68)
        self.declare_parameter('frame_id', 'imu_link')
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('publish_rate_hz', 50.0)
        self.declare_parameter('calibrate_on_startup', True)
        self.declare_parameter('gyro_calibration_samples', 1000)
        self.declare_parameter('gyro_calibration_delay_sec', 0.002)
        self.declare_parameter('calibration_file', '~/.ros/sweepi_mpu6050_calibration.yaml')
        self.declare_parameter('save_calibration', True)
        self.declare_parameter('load_calibration_if_available', True)
        self.declare_parameter('publish_orientation', False)
        self.declare_parameter('enable_light_low_pass_filter', True)
        self.declare_parameter('low_pass_alpha', 0.7)
        self.declare_parameter('gyro_units_output', 'rad_s')
        self.declare_parameter('accel_units_output', 'm_s2')
        self.declare_parameter('angular_velocity_signs', [1.0, 1.0, 1.0])
        self.declare_parameter('linear_acceleration_signs', [1.0, 1.0, 1.0])
        self.declare_parameter('enable_stationary_bias_adaptation', True)
        self.declare_parameter('stationary_gyro_threshold_dps', 0.8)
        self.declare_parameter('stationary_accel_threshold_g', 0.08)
        self.declare_parameter('yaw_bias_adapt_alpha', 0.001)
        self.declare_parameter('zero_gyro_when_stationary', True)
        self.declare_parameter('angular_velocity_covariance_diagonal', [0.05, 0.05, 0.02])
        self.declare_parameter('linear_acceleration_covariance_diagonal', [0.30, 0.30, 0.30])
        self.declare_parameter('orientation_covariance_diagonal', [99999.0, 99999.0, 99999.0])

        self.i2c_bus = int(self.get_parameter('i2c_bus').value)
        self.i2c_address = int(self.get_parameter('i2c_address').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.imu_topic = str(self.get_parameter('imu_topic').value)
        self.publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        self.calibrate_on_startup = bool(self.get_parameter('calibrate_on_startup').value)
        self.gyro_calibration_samples = int(self.get_parameter('gyro_calibration_samples').value)
        self.gyro_calibration_delay_sec = float(
            self.get_parameter('gyro_calibration_delay_sec').value
        )
        self.calibration_file = os.path.expanduser(str(self.get_parameter('calibration_file').value))
        self.save_calibration = bool(self.get_parameter('save_calibration').value)
        self.load_calibration_if_available = bool(
            self.get_parameter('load_calibration_if_available').value
        )
        self.publish_orientation = bool(self.get_parameter('publish_orientation').value)
        self.enable_light_low_pass_filter = bool(
            self.get_parameter('enable_light_low_pass_filter').value
        )
        self.low_pass_alpha = float(self.get_parameter('low_pass_alpha').value)
        self.angular_velocity_signs = [
            float(value) for value in self.get_parameter('angular_velocity_signs').value
        ]
        self.linear_acceleration_signs = [
            float(value) for value in self.get_parameter('linear_acceleration_signs').value
        ]
        self.enable_stationary_bias_adaptation = bool(
            self.get_parameter('enable_stationary_bias_adaptation').value
        )
        self.stationary_gyro_threshold_dps = float(
            self.get_parameter('stationary_gyro_threshold_dps').value
        )
        self.stationary_accel_threshold_g = float(
            self.get_parameter('stationary_accel_threshold_g').value
        )
        self.yaw_bias_adapt_alpha = float(self.get_parameter('yaw_bias_adapt_alpha').value)
        self.zero_gyro_when_stationary = bool(self.get_parameter('zero_gyro_when_stationary').value)
        self.angular_velocity_covariance = diagonal_to_covariance(
            list(self.get_parameter('angular_velocity_covariance_diagonal').value)
        )
        self.linear_acceleration_covariance = diagonal_to_covariance(
            list(self.get_parameter('linear_acceleration_covariance_diagonal').value)
        )
        self.orientation_covariance = diagonal_to_covariance(
            list(self.get_parameter('orientation_covariance_diagonal').value)
        )

        self.imu_pub = self.create_publisher(Imu, self.imu_topic, 10)
        self.calibration_status_pub = self.create_publisher(String, '/imu/calibration_status', 10)
        self.hardware_status_pub = self.create_publisher(String, '/hardware/temp_imu_status', 10)
        self.create_service(Trigger, '/imu/calibrate_gyro', self.calibrate_service_callback)

        self.filtered_accel_g = None
        self.filtered_gyro_dps = None
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.last_time = time.monotonic()
        self.read_failure_count = 0
        self.last_warning_time = 0.0

        self.mpu = MPU6050(self.i2c_bus, self.i2c_address)
        self.mpu.initialize()
        time.sleep(0.1)
        self._initialize_calibration()

        self.create_timer(1.0 / max(1e-3, self.publish_rate_hz), self.update)
        self.get_logger().info(
            f'MPU6050 IMU node publishing {self.imu_topic}; orientation publishing is '
            f'{"enabled" if self.publish_orientation else "disabled"}.'
        )

    def _initialize_calibration(self):
        if self.load_calibration_if_available and self._load_calibration():
            self._publish_calibration_status('loaded', self.mpu.gyro_bias_dps)
            return

        if self.calibrate_on_startup:
            self.get_logger().info('Keep the robot still: calibrating MPU6050 gyro bias.')
            bias = self._collect_gyro_bias()
            self.mpu.gyro_bias_dps = bias
            if self.save_calibration:
                self._save_calibration(bias)
            self._publish_calibration_status('startup_calibrated', bias)
            return

        self.get_logger().warn('No MPU6050 calibration loaded; using zero gyro bias.')
        self._publish_calibration_status('zero_bias', self.mpu.gyro_bias_dps)

    def calibrate_service_callback(self, request, response):
        del request
        try:
            self.get_logger().info('Manual gyro calibration requested. Keep the robot still.')
            bias = self._collect_gyro_bias()
            self.mpu.gyro_bias_dps = bias
            if self.save_calibration:
                self._save_calibration(bias)
            self._publish_calibration_status('manual_calibrated', bias)
            response.success = True
            response.message = (
                f'Gyro bias dps: x={bias[0]:.5f}, y={bias[1]:.5f}, z={bias[2]:.5f}'
            )
        except Exception as exc:
            response.success = False
            response.message = f'Gyro calibration failed: {exc}'
            self._publish_calibration_status('calibration_failed', self.mpu.gyro_bias_dps, str(exc))
        return response

    def _collect_gyro_bias(self):
        sums = [0.0, 0.0, 0.0]
        samples = max(1, self.gyro_calibration_samples)
        for _ in range(samples):
            _, _, _, gx, gy, gz = self.mpu.read_raw()
            sums[0] += gx / self.mpu.gyro_scale
            sums[1] += gy / self.mpu.gyro_scale
            sums[2] += gz / self.mpu.gyro_scale
            time.sleep(max(0.0, self.gyro_calibration_delay_sec))
        return [value / samples for value in sums]

    def _load_calibration(self):
        if not os.path.exists(self.calibration_file):
            return False
        try:
            with open(self.calibration_file, 'r', encoding='utf-8') as stream:
                if yaml is not None:
                    data = yaml.safe_load(stream) or {}
                else:
                    data = self._read_simple_yaml(stream.read())
            bias = data.get('gyro_bias_dps')
            if bias is None:
                bias = [
                    data.get('gyro_bias_x_dps', 0.0),
                    data.get('gyro_bias_y_dps', 0.0),
                    data.get('gyro_bias_z_dps', 0.0),
                ]
            self.mpu.gyro_bias_dps = [float(value) for value in bias[:3]]
            return True
        except Exception as exc:
            self.get_logger().warn(f'Could not load MPU6050 calibration file: {exc}')
            return False

    def _save_calibration(self, bias):
        try:
            os.makedirs(os.path.dirname(self.calibration_file), exist_ok=True)
            data = {
                'gyro_bias_dps': [float(value) for value in bias],
                'i2c_address': int(self.i2c_address),
                'updated_unix_time': time.time(),
            }
            with open(self.calibration_file, 'w', encoding='utf-8') as stream:
                if yaml is not None:
                    yaml.safe_dump(data, stream, default_flow_style=False)
                else:
                    stream.write(f"gyro_bias_dps: [{bias[0]}, {bias[1]}, {bias[2]}]\n")
                    stream.write(f"i2c_address: {self.i2c_address}\n")
                    stream.write(f"updated_unix_time: {time.time()}\n")
        except Exception as exc:
            self.get_logger().warn(f'Could not save MPU6050 calibration file: {exc}')

    def _read_simple_yaml(self, text):
        data = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or ':' not in line:
                continue
            key, value = line.split(':', 1)
            value = value.strip()
            if value.startswith('[') and value.endswith(']'):
                data[key.strip()] = [
                    float(item.strip()) for item in value[1:-1].split(',') if item.strip()
                ]
            else:
                try:
                    data[key.strip()] = float(value)
                except ValueError:
                    data[key.strip()] = value
        return data

    def update(self):
        now = time.monotonic()
        dt = now - self.last_time
        self.last_time = now
        if dt <= 0.0 or dt > 1.0:
            dt = 1.0 / max(1e-3, self.publish_rate_hz)

        try:
            accel_g, gyro_dps = self.mpu.read_scaled()
        except Exception as exc:
            self.read_failure_count += 1
            self._publish_hardware_status('read_failed', str(exc))
            if now - self.last_warning_time > 2.0:
                self.get_logger().warn(f'MPU6050 read failed: {exc}')
                self.last_warning_time = now
            return

        if self.enable_light_low_pass_filter:
            accel_g = self._filter_vector('accel', accel_g)
            gyro_dps = self._filter_vector('gyro', gyro_dps)

        accel_mag = math.sqrt(sum(value * value for value in accel_g))
        gyro_stationary = all(abs(value) < self.stationary_gyro_threshold_dps for value in gyro_dps)
        accel_stationary = abs(accel_mag - 1.0) < self.stationary_accel_threshold_g
        is_stationary = gyro_stationary and accel_stationary

        if self.enable_stationary_bias_adaptation and is_stationary:
            self.mpu.gyro_bias_dps[2] += self.yaw_bias_adapt_alpha * gyro_dps[2]
            gyro_dps[2] *= (1.0 - self.yaw_bias_adapt_alpha)
            if self.zero_gyro_when_stationary:
                gyro_dps = [0.0, 0.0, 0.0]

        signed_gyro_dps = [
            gyro_dps[index] * self.angular_velocity_signs[index] for index in range(3)
        ]
        signed_accel_g = [
            accel_g[index] * self.linear_acceleration_signs[index] for index in range(3)
        ]

        imu_msg = Imu()
        imu_msg.header.stamp = self.get_clock().now().to_msg()
        imu_msg.header.frame_id = self.frame_id

        if self.publish_orientation:
            self._update_orientation(signed_accel_g, signed_gyro_dps, dt)
            imu_msg.orientation = euler_to_quaternion(self.roll, self.pitch, self.yaw)
            imu_msg.orientation_covariance = self.orientation_covariance
        else:
            imu_msg.orientation.w = 1.0
            imu_msg.orientation_covariance[0] = -1.0

        imu_msg.angular_velocity.x = math.radians(signed_gyro_dps[0])
        imu_msg.angular_velocity.y = math.radians(signed_gyro_dps[1])
        imu_msg.angular_velocity.z = math.radians(signed_gyro_dps[2])
        imu_msg.angular_velocity_covariance = self.angular_velocity_covariance

        imu_msg.linear_acceleration.x = signed_accel_g[0] * GRAVITY
        imu_msg.linear_acceleration.y = signed_accel_g[1] * GRAVITY
        imu_msg.linear_acceleration.z = signed_accel_g[2] * GRAVITY
        imu_msg.linear_acceleration_covariance = self.linear_acceleration_covariance
        self.imu_pub.publish(imu_msg)

        self._publish_hardware_status('publishing', None, is_stationary, signed_gyro_dps, signed_accel_g)

    def _filter_vector(self, kind, vector):
        previous = self.filtered_accel_g if kind == 'accel' else self.filtered_gyro_dps
        if previous is None:
            filtered = list(vector)
        else:
            alpha = max(0.0, min(1.0, self.low_pass_alpha))
            filtered = [
                alpha * vector[index] + (1.0 - alpha) * previous[index] for index in range(3)
            ]
        if kind == 'accel':
            self.filtered_accel_g = filtered
        else:
            self.filtered_gyro_dps = filtered
        return filtered

    def _update_orientation(self, accel_g, gyro_dps, dt):
        roll_acc = math.atan2(accel_g[1], accel_g[2])
        pitch_acc = math.atan2(-accel_g[0], math.sqrt(accel_g[1] ** 2 + accel_g[2] ** 2))
        alpha = 0.98
        self.roll = alpha * (self.roll + math.radians(gyro_dps[0]) * dt) + (1.0 - alpha) * roll_acc
        self.pitch = (
            alpha * (self.pitch + math.radians(gyro_dps[1]) * dt) + (1.0 - alpha) * pitch_acc
        )
        self.yaw = normalize_angle(self.yaw + math.radians(gyro_dps[2]) * dt)

    def _publish_calibration_status(self, status, bias, error=None):
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'gyro_bias_dps': [round(float(value), 6) for value in bias],
            'calibration_file': self.calibration_file,
            'error': error,
        })
        self.calibration_status_pub.publish(msg)

    def _publish_hardware_status(
        self,
        status,
        error=None,
        stationary=None,
        gyro_dps=None,
        accel_g=None,
    ):
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'frame_id': self.frame_id,
            'imu_topic': self.imu_topic,
            'read_failure_count': self.read_failure_count,
            'stationary': stationary,
            'gyro_dps': None if gyro_dps is None else [round(value, 5) for value in gyro_dps],
            'accel_g': None if accel_g is None else [round(value, 5) for value in accel_g],
            'orientation_published': self.publish_orientation,
            'error': error,
        })
        self.hardware_status_pub.publish(msg)

    def destroy_node(self):
        try:
            self.mpu.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MPU6050ImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
