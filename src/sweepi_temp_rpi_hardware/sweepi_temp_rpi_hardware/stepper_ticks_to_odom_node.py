#!/usr/bin/env python3

import json
import math
import threading
import time

import rclpy
from geometry_msgs.msg import Quaternion
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Int64, String
from std_srvs.srv import Trigger


def yaw_to_quaternion(yaw):
    q = Quaternion()
    q.z = math.sin(yaw * 0.5)
    q.w = math.cos(yaw * 0.5)
    return q


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def diagonal_to_covariance(diagonal):
    covariance = [0.0] * 36
    for index, value in enumerate(diagonal[:6]):
        covariance[index * 6 + index] = float(value)
    return covariance


class StepperTicksToOdomNode(Node):
    def __init__(self):
        super().__init__('sweepi_temp_stepper_odom')

        self.declare_parameter('wheel_radius', 0.0325)
        self.declare_parameter('wheel_separation', 0.20)
        self.declare_parameter('steps_per_rev', 200)
        self.declare_parameter('microsteps', 16)
        self.declare_parameter('left_step_sign', 1.0)
        self.declare_parameter('right_step_sign', 1.0)
        self.declare_parameter('publish_rate_hz', 50.0)
        self.declare_parameter('odom_frame_id', 'odom')
        self.declare_parameter('base_frame_id', 'base_footprint')
        self.declare_parameter('wheel_odom_topic', '/wheel/odom')
        self.declare_parameter('left_steps_topic', '/stepper/left_steps_total')
        self.declare_parameter('right_steps_topic', '/stepper/right_steps_total')
        self.declare_parameter(
            'wheel_odom_pose_covariance_diagonal',
            [0.05, 0.05, 99999.0, 99999.0, 99999.0, 0.10],
        )
        self.declare_parameter(
            'wheel_odom_twist_covariance_diagonal',
            [0.05, 99999.0, 99999.0, 99999.0, 99999.0, 0.10],
        )

        self.wheel_radius = float(self.get_parameter('wheel_radius').value)
        self.wheel_separation = float(self.get_parameter('wheel_separation').value)
        self.steps_per_rev = int(self.get_parameter('steps_per_rev').value)
        self.microsteps = int(self.get_parameter('microsteps').value)
        self.left_step_sign = float(self.get_parameter('left_step_sign').value)
        self.right_step_sign = float(self.get_parameter('right_step_sign').value)
        self.publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        self.odom_frame_id = str(self.get_parameter('odom_frame_id').value)
        self.base_frame_id = str(self.get_parameter('base_frame_id').value)
        self.wheel_odom_topic = str(self.get_parameter('wheel_odom_topic').value)
        self.left_steps_topic = str(self.get_parameter('left_steps_topic').value)
        self.right_steps_topic = str(self.get_parameter('right_steps_topic').value)
        self.pose_covariance = diagonal_to_covariance(
            list(self.get_parameter('wheel_odom_pose_covariance_diagonal').value)
        )
        self.twist_covariance = diagonal_to_covariance(
            list(self.get_parameter('wheel_odom_twist_covariance_diagonal').value)
        )

        steps_per_wheel_rev = self.steps_per_rev * self.microsteps
        self.meters_per_step = 2.0 * math.pi * self.wheel_radius / float(steps_per_wheel_rev)

        self.lock = threading.Lock()
        self.latest_left_steps = None
        self.latest_right_steps = None
        self.prev_left_steps = None
        self.prev_right_steps = None
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.last_update_time = time.monotonic()
        self.last_status = 'waiting_for_step_counts'

        self.create_subscription(Int64, self.left_steps_topic, self.left_steps_callback, 10)
        self.create_subscription(Int64, self.right_steps_topic, self.right_steps_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, self.wheel_odom_topic, 10)
        self.status_pub = self.create_publisher(String, '/hardware/temp_odom_status', 10)
        self.create_service(Trigger, '/wheel_odom/reset', self.reset_callback)
        self.create_timer(1.0 / max(1e-3, self.publish_rate_hz), self.update)

        self.get_logger().info('Temporary stepper wheel odometry started. No TF will be published.')

    def left_steps_callback(self, msg):
        with self.lock:
            self.latest_left_steps = int(msg.data)

    def right_steps_callback(self, msg):
        with self.lock:
            self.latest_right_steps = int(msg.data)

    def reset_callback(self, request, response):
        del request
        with self.lock:
            self.x = 0.0
            self.y = 0.0
            self.yaw = 0.0
            self.prev_left_steps = self.latest_left_steps
            self.prev_right_steps = self.latest_right_steps
            self.last_update_time = time.monotonic()
            self.last_status = 'reset'
        response.success = True
        response.message = 'Wheel odometry reset to zero using current step totals as baseline.'
        return response

    def update(self):
        now = time.monotonic()
        with self.lock:
            if self.latest_left_steps is None or self.latest_right_steps is None:
                self._publish_status_locked('waiting_for_step_counts', now)
                return

            if self.prev_left_steps is None or self.prev_right_steps is None:
                self.prev_left_steps = self.latest_left_steps
                self.prev_right_steps = self.latest_right_steps
                self.last_update_time = now
                self._publish_status_locked('baseline_set', now)
                return

            dt = now - self.last_update_time
            if dt <= 0.0:
                return

            delta_left_steps = self.latest_left_steps - self.prev_left_steps
            delta_right_steps = self.latest_right_steps - self.prev_right_steps
            self.prev_left_steps = self.latest_left_steps
            self.prev_right_steps = self.latest_right_steps
            self.last_update_time = now

            left_distance = delta_left_steps * self.left_step_sign * self.meters_per_step
            right_distance = delta_right_steps * self.right_step_sign * self.meters_per_step
            delta_s = (right_distance + left_distance) / 2.0
            delta_theta = (right_distance - left_distance) / self.wheel_separation

            self.x += delta_s * math.cos(self.yaw + delta_theta / 2.0)
            self.y += delta_s * math.sin(self.yaw + delta_theta / 2.0)
            self.yaw = normalize_angle(self.yaw + delta_theta)

            linear_velocity = delta_s / dt
            angular_velocity = delta_theta / dt
            x = self.x
            y = self.y
            yaw = self.yaw
            self.last_status = 'publishing'
            left_total = self.latest_left_steps
            right_total = self.latest_right_steps

        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = self.odom_frame_id
        odom.child_frame_id = self.base_frame_id
        odom.pose.pose.position.x = x
        odom.pose.pose.position.y = y
        odom.pose.pose.orientation = yaw_to_quaternion(yaw)
        odom.pose.covariance = self.pose_covariance
        odom.twist.twist.linear.x = linear_velocity
        odom.twist.twist.angular.z = angular_velocity
        odom.twist.covariance = self.twist_covariance
        self.odom_pub.publish(odom)

        status_msg = String()
        status_msg.data = json.dumps({
            'status': 'publishing',
            'x': round(x, 4),
            'y': round(y, 4),
            'yaw': round(yaw, 4),
            'left_steps_total': left_total,
            'right_steps_total': right_total,
            'linear_velocity': round(linear_velocity, 4),
            'angular_velocity': round(angular_velocity, 4),
        })
        self.status_pub.publish(status_msg)

    def _publish_status_locked(self, status, now):
        self.last_status = status
        msg = String()
        msg.data = json.dumps({
            'status': status,
            'left_steps_total': self.latest_left_steps,
            'right_steps_total': self.latest_right_steps,
            'age_since_update_sec': round(now - self.last_update_time, 4),
        })
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = StepperTicksToOdomNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
