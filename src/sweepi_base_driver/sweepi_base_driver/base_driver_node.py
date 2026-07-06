import json
import math
import time
from dataclasses import dataclass
from typing import List, Optional

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String

try:
    import serial
except ImportError:  # pragma: no cover - reported at runtime on the robot.
    serial = None


@dataclass
class FeedbackPacket:
    seq: int
    stm_time_us: int
    delta_left_ticks: int
    delta_right_ticks: int
    gyro: List[float]
    accel: List[float]
    battery_voltage: float
    fault: int
    status: str


def yaw_to_quaternion(yaw: float):
    half_yaw = yaw * 0.5
    return 0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw)


def diagonal_covariance(diagonal: List[float], size: int) -> List[float]:
    covariance = [0.0] * (size * size)
    for index, value in enumerate(diagonal[:size]):
        covariance[index * size + index] = float(value)
    return covariance


def xor_checksum(payload: str) -> str:
    value = 0
    for char in payload.encode('ascii', errors='ignore'):
        value ^= char
    return f'{value:02X}'


class BaseDriverNode(Node):
    def __init__(self):
        super().__init__('base_driver_node')

        self.serial_port = self.declare_parameter('serial_port', '/dev/ttyAMA0').value
        self.baud_rate = int(self.declare_parameter('baud_rate', 115200).value)
        self.serial_timeout = float(self.declare_parameter('serial_timeout', 0.02).value)
        self.reconnect_period = float(self.declare_parameter('reconnect_period', 1.0).value)

        self.wheel_radius = float(self.declare_parameter('wheel_radius', 0.0615).value)
        self.wheel_separation = float(self.declare_parameter('wheel_separation', 0.29).value)
        self.ticks_per_revolution = float(
            self.declare_parameter('ticks_per_revolution', 7392.0).value
        )
        self.left_encoder_sign = float(self.declare_parameter('left_encoder_sign', 1.0).value)
        self.right_encoder_sign = float(self.declare_parameter('right_encoder_sign', 1.0).value)
        self.left_motor_command_sign = float(
            self.declare_parameter('left_motor_command_sign', 1.0).value
        )
        self.right_motor_command_sign = float(
            self.declare_parameter('right_motor_command_sign', 1.0).value
        )

        self.command_rate_hz = float(self.declare_parameter('command_rate_hz', 50.0).value)
        self.feedback_poll_rate_hz = float(
            self.declare_parameter('feedback_poll_rate_hz', 100.0).value
        )
        self.cmd_vel_timeout = float(self.declare_parameter('cmd_vel_timeout', 0.5).value)
        self.motor_enable = bool(self.declare_parameter('motor_enable', True).value)
        self.suction_enable = bool(self.declare_parameter('suction_enable', False).value)
        self.brush_enable = bool(self.declare_parameter('brush_enable', False).value)
        self.command_mode = str(self.declare_parameter('command_mode', 'NORMAL').value)
        self.use_checksum = bool(self.declare_parameter('use_checksum', False).value)

        cmd_vel_topic = self.declare_parameter('cmd_vel_topic', '/cmd_vel').value
        wheel_odom_topic = self.declare_parameter('wheel_odom_topic', '/wheel/odom').value
        imu_topic = self.declare_parameter('imu_topic', '/imu/data').value
        status_topic = self.declare_parameter('status_topic', '/hardware/status').value
        self.odom_frame_id = self.declare_parameter('odom_frame_id', 'odom').value
        self.base_frame_id = self.declare_parameter('base_frame_id', 'base_footprint').value
        self.imu_frame_id = self.declare_parameter('imu_frame_id', 'imu_link').value

        self.gyro_units = str(self.declare_parameter('gyro_units', 'rad_s').value)
        self.accel_units = str(self.declare_parameter('accel_units', 'm_s2').value)
        self.imu_angular_velocity_signs = list(
            self.declare_parameter(
                'imu_angular_velocity_signs', [1.0, 1.0, 1.0]
            ).value
        )
        self.imu_linear_acceleration_signs = list(
            self.declare_parameter(
                'imu_linear_acceleration_signs', [1.0, 1.0, 1.0]
            ).value
        )

        pose_cov_diag = list(
            self.declare_parameter(
                'wheel_odom_pose_covariance_diagonal',
                [0.02, 0.02, 99999.0, 99999.0, 99999.0, 0.05],
            ).value
        )
        twist_cov_diag = list(
            self.declare_parameter(
                'wheel_odom_twist_covariance_diagonal',
                [0.02, 99999.0, 99999.0, 99999.0, 99999.0, 0.05],
            ).value
        )
        imu_angular_cov_diag = list(
            self.declare_parameter(
                'imu_angular_velocity_covariance_diagonal', [0.05, 0.05, 0.02]
            ).value
        )
        imu_linear_cov_diag = list(
            self.declare_parameter(
                'imu_linear_acceleration_covariance_diagonal', [0.2, 0.2, 0.2]
            ).value
        )

        self.pose_covariance = diagonal_covariance(pose_cov_diag, 6)
        self.twist_covariance = diagonal_covariance(twist_cov_diag, 6)
        self.imu_angular_covariance = diagonal_covariance(imu_angular_cov_diag, 3)
        self.imu_linear_covariance = diagonal_covariance(imu_linear_cov_diag, 3)

        self.cmd_subscription = self.create_subscription(
            Twist, cmd_vel_topic, self.cmd_vel_callback, 10
        )
        self.odom_publisher = self.create_publisher(Odometry, wheel_odom_topic, 10)
        self.imu_publisher = self.create_publisher(Imu, imu_topic, 10)
        self.status_publisher = self.create_publisher(String, status_topic, 10)

        self.serial_handle = None
        self.last_reconnect_attempt = 0.0
        self.command_seq = 0
        self.last_cmd_vel = Twist()
        self.last_cmd_vel_time = self.get_clock().now()
        self.last_feedback_wall_time: Optional[float] = None
        self.last_feedback_seq: Optional[int] = None
        self.last_stm_time_us: Optional[int] = None
        self.dropped_feedback_packets = 0
        self.battery_voltage: Optional[float] = None
        self.fault = 0
        self.hardware_status = 'NO_FEEDBACK'

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.meters_per_tick = (
            2.0 * math.pi * self.wheel_radius / self.ticks_per_revolution
        )

        self.feedback_timer = self.create_timer(
            1.0 / max(self.feedback_poll_rate_hz, 1.0), self.poll_feedback
        )
        self.command_timer = self.create_timer(
            1.0 / max(self.command_rate_hz, 1.0), self.send_command
        )
        self.status_timer = self.create_timer(1.0, self.publish_status)

        self.get_logger().info(
            f'SweePi base driver starting on {self.serial_port} at {self.baud_rate} baud'
        )
        self.log_startup_parameters()
        self.connect_serial()

    def log_startup_parameters(self):
        self.get_logger().info(
            'Base driver parameters: '
            f'serial_port={self.serial_port}, '
            f'baud_rate={self.baud_rate}, '
            f'wheel_radius={self.wheel_radius}, '
            f'wheel_separation={self.wheel_separation}, '
            f'ticks_per_revolution={self.ticks_per_revolution}, '
            f'left_encoder_sign={self.left_encoder_sign}, '
            f'right_encoder_sign={self.right_encoder_sign}, '
            f'left_motor_command_sign={self.left_motor_command_sign}, '
            f'right_motor_command_sign={self.right_motor_command_sign}, '
            f'command_rate_hz={self.command_rate_hz}, '
            f'feedback_poll_rate_hz={self.feedback_poll_rate_hz}, '
            f'cmd_vel_timeout={self.cmd_vel_timeout}, '
            f'gyro_units={self.gyro_units}, '
            f'accel_units={self.accel_units}'
        )

    def connect_serial(self):
        if serial is None:
            self.get_logger().error(
                'python3-serial is not available; install the python3-serial package.'
            )
            return

        now = time.monotonic()
        if now - self.last_reconnect_attempt < self.reconnect_period:
            return
        self.last_reconnect_attempt = now

        try:
            self.serial_handle = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=self.serial_timeout,
                write_timeout=self.serial_timeout,
            )
            self.get_logger().info(f'Connected to STM32 on {self.serial_port}')
        except serial.SerialException as exc:
            self.serial_handle = None
            self.get_logger().warn(f'Waiting for STM32 serial port: {exc}')

    def close_serial(self):
        if self.serial_handle is None:
            return
        try:
            self.serial_handle.close()
        except serial.SerialException:
            pass
        self.serial_handle = None

    def cmd_vel_callback(self, msg: Twist):
        self.last_cmd_vel = msg
        self.last_cmd_vel_time = self.get_clock().now()

    def send_command(self):
        if self.serial_handle is None or not self.serial_handle.is_open:
            self.connect_serial()
            return

        now = self.get_clock().now()
        cmd_age = (now - self.last_cmd_vel_time).nanoseconds / 1e9
        cmd_is_fresh = cmd_age <= self.cmd_vel_timeout

        linear_x = self.last_cmd_vel.linear.x if cmd_is_fresh else 0.0
        angular_z = self.last_cmd_vel.angular.z if cmd_is_fresh else 0.0
        left_velocity = (
            linear_x - angular_z * self.wheel_separation * 0.5
        ) * self.left_motor_command_sign
        right_velocity = (
            linear_x + angular_z * self.wheel_separation * 0.5
        ) * self.right_motor_command_sign
        mode = self.command_mode if cmd_is_fresh else 'STOP'
        motor_enable = self.motor_enable and cmd_is_fresh

        self.command_seq = (self.command_seq + 1) % 1000000
        time_ms = int(time.monotonic() * 1000.0)
        fields = [
            'CMD',
            str(self.command_seq),
            str(time_ms),
            f'{left_velocity:.4f}',
            f'{right_velocity:.4f}',
            '1' if motor_enable else '0',
            '1' if self.suction_enable else '0',
            '1' if self.brush_enable else '0',
            mode,
        ]
        payload = ','.join(fields)
        if self.use_checksum:
            payload = f'{payload},{xor_checksum(payload)}'
        line = f'{payload}\n'

        try:
            self.serial_handle.write(line.encode('ascii'))
        except serial.SerialException as exc:
            self.get_logger().error(f'Serial write failed: {exc}')
            self.close_serial()

    def poll_feedback(self):
        if self.serial_handle is None or not self.serial_handle.is_open:
            self.connect_serial()
            return

        lines_read = 0
        while lines_read < 20:
            try:
                if self.serial_handle.in_waiting == 0:
                    break
                raw_line = self.serial_handle.readline()
            except serial.SerialException as exc:
                self.get_logger().error(f'Serial read failed: {exc}')
                self.close_serial()
                return

            if not raw_line:
                break
            lines_read += 1
            line = raw_line.decode('ascii', errors='replace').strip()
            if not line:
                continue
            self.handle_serial_line(line)

    def handle_serial_line(self, line: str):
        fields = line.split(',')
        packet_type = fields[0] if fields else ''

        if packet_type == 'FB':
            packet = self.parse_feedback(fields, line)
            if packet is not None:
                self.handle_feedback(packet)
        elif packet_type == 'ACK':
            self.get_logger().debug(f'STM32 ACK: {line}')
        elif packet_type == 'PONG':
            self.get_logger().debug(f'STM32 PONG: {line}')
        else:
            self.get_logger().warn(f'Ignoring unknown STM32 packet: {line}')

    def parse_feedback(self, fields: List[str], line: str) -> Optional[FeedbackPacket]:
        if len(fields) < 14:
            self.get_logger().warn(f'Ignoring short feedback packet: {line}')
            return None

        if self.use_checksum:
            payload = ','.join(fields[:-1])
            expected = xor_checksum(payload)
            received = fields[-1].upper()
            if expected != received:
                self.get_logger().warn(
                    f'Ignoring feedback packet with bad checksum: expected {expected}, got {received}'
                )
                return None

        try:
            return FeedbackPacket(
                seq=int(fields[1]),
                stm_time_us=int(fields[2]),
                delta_left_ticks=int(fields[3]),
                delta_right_ticks=int(fields[4]),
                gyro=[float(fields[5]), float(fields[6]), float(fields[7])],
                accel=[float(fields[8]), float(fields[9]), float(fields[10])],
                battery_voltage=float(fields[11]),
                fault=int(fields[12]),
                status=fields[13],
            )
        except ValueError as exc:
            self.get_logger().warn(f'Ignoring invalid feedback packet: {exc}: {line}')
            return None

    def handle_feedback(self, packet: FeedbackPacket):
        if self.last_feedback_seq is not None:
            expected_seq = (self.last_feedback_seq + 1) % 1000000
            if packet.seq != expected_seq:
                self.dropped_feedback_packets += 1
                self.get_logger().warn(
                    f'Feedback sequence jump: expected {expected_seq}, got {packet.seq}'
                )
        self.last_feedback_seq = packet.seq

        dt = self.calculate_dt(packet.stm_time_us)
        if dt <= 0.0:
            self.get_logger().warn('Ignoring feedback with non-positive STM32 dt')
            return

        self.last_feedback_wall_time = time.monotonic()
        self.battery_voltage = packet.battery_voltage
        self.fault = packet.fault
        self.hardware_status = packet.status

        left_distance = (
            packet.delta_left_ticks * self.left_encoder_sign * self.meters_per_tick
        )
        right_distance = (
            packet.delta_right_ticks * self.right_encoder_sign * self.meters_per_tick
        )
        delta_s = (right_distance + left_distance) * 0.5
        delta_theta = (right_distance - left_distance) / self.wheel_separation

        self.x += delta_s * math.cos(self.yaw + delta_theta * 0.5)
        self.y += delta_s * math.sin(self.yaw + delta_theta * 0.5)
        self.yaw = math.atan2(
            math.sin(self.yaw + delta_theta), math.cos(self.yaw + delta_theta)
        )

        linear_velocity = delta_s / dt
        angular_velocity = delta_theta / dt
        stamp = self.get_clock().now().to_msg()

        self.publish_wheel_odom(stamp, linear_velocity, angular_velocity)
        self.publish_imu(stamp, packet)

    def calculate_dt(self, stm_time_us: int) -> float:
        if self.last_stm_time_us is None:
            self.last_stm_time_us = stm_time_us
            return 1.0 / max(self.feedback_poll_rate_hz, 1.0)

        dt = (stm_time_us - self.last_stm_time_us) / 1e6
        self.last_stm_time_us = stm_time_us
        return dt

    def publish_wheel_odom(self, stamp, linear_velocity: float, angular_velocity: float):
        msg = Odometry()
        msg.header.stamp = stamp
        msg.header.frame_id = self.odom_frame_id
        msg.child_frame_id = self.base_frame_id
        msg.pose.pose.position.x = self.x
        msg.pose.pose.position.y = self.y
        msg.pose.pose.position.z = 0.0
        qx, qy, qz, qw = yaw_to_quaternion(self.yaw)
        msg.pose.pose.orientation.x = qx
        msg.pose.pose.orientation.y = qy
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        msg.twist.twist.linear.x = linear_velocity
        msg.twist.twist.angular.z = angular_velocity
        msg.pose.covariance = self.pose_covariance
        msg.twist.covariance = self.twist_covariance
        self.odom_publisher.publish(msg)

    def publish_imu(self, stamp, packet: FeedbackPacket):
        gyro = self.convert_gyro(packet.gyro)
        accel = self.convert_accel(packet.accel)

        msg = Imu()
        msg.header.stamp = stamp
        msg.header.frame_id = self.imu_frame_id
        msg.orientation.w = 1.0
        msg.orientation_covariance[0] = -1.0
        msg.angular_velocity.x = gyro[0]
        msg.angular_velocity.y = gyro[1]
        msg.angular_velocity.z = gyro[2]
        msg.linear_acceleration.x = accel[0]
        msg.linear_acceleration.y = accel[1]
        msg.linear_acceleration.z = accel[2]
        msg.angular_velocity_covariance = self.imu_angular_covariance
        msg.linear_acceleration_covariance = self.imu_linear_covariance
        self.imu_publisher.publish(msg)

    def convert_gyro(self, gyro: List[float]) -> List[float]:
        values = list(gyro)
        if self.gyro_units in ('deg_s', 'degrees_s', 'degree_s'):
            values = [value * math.pi / 180.0 for value in values]
        return [
            values[index] * float(self.imu_angular_velocity_signs[index])
            for index in range(3)
        ]

    def convert_accel(self, accel: List[float]) -> List[float]:
        values = list(accel)
        if self.accel_units in ('g', 'gravity'):
            values = [value * 9.80665 for value in values]
        return [
            values[index] * float(self.imu_linear_acceleration_signs[index])
            for index in range(3)
        ]

    def publish_status(self):
        feedback_age = None
        if self.last_feedback_wall_time is not None:
            feedback_age = time.monotonic() - self.last_feedback_wall_time

        msg = String()
        msg.data = json.dumps(
            {
                'connected': self.serial_handle is not None and self.serial_handle.is_open,
                'serial_port': self.serial_port,
                'battery_voltage': self.battery_voltage,
                'fault': self.fault,
                'status': self.hardware_status,
                'feedback_age_sec': feedback_age,
                'dropped_feedback_packets': self.dropped_feedback_packets,
            },
            sort_keys=True,
        )
        self.status_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = BaseDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_serial()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
