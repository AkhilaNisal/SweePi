#!/usr/bin/env python3
"""Broadcast odom -> base TF from /odom after Gazebo sim time is stable."""

import time

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from tf2_ros import TransformBroadcaster


class OdomTfBroadcaster(Node):
    def __init__(self):
        super().__init__('odom_tf_broadcaster')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('clock_topic', '/clock')
        self.declare_parameter('default_parent_frame', 'odom')
        self.declare_parameter('default_child_frame', 'base_footprint')
        self.declare_parameter('max_future_odom_sec', 0.50)
        self.declare_parameter('max_past_odom_sec', 2.0)
        self.declare_parameter('startup_clock_settle_sec', 8.0)
        self.declare_parameter('max_odom_stamp_jump_sec', 5.0)

        self.odom_topic = str(self.get_parameter('odom_topic').value)
        self.clock_topic = str(self.get_parameter('clock_topic').value)
        self.default_parent_frame = str(
            self.get_parameter('default_parent_frame').value
        )
        self.default_child_frame = str(
            self.get_parameter('default_child_frame').value
        )
        self.max_future_odom_ns = int(
            float(self.get_parameter('max_future_odom_sec').value) * 1e9
        )
        self.max_past_odom_ns = int(
            float(self.get_parameter('max_past_odom_sec').value) * 1e9
        )
        self.startup_clock_settle_sec = float(
            self.get_parameter('startup_clock_settle_sec').value
        )
        self.max_odom_stamp_jump_ns = int(
            float(self.get_parameter('max_odom_stamp_jump_sec').value) * 1e9
        )
        self.last_stamp_ns = None
        self.latest_clock_ns = None
        self.first_clock_wall_time = None
        self.last_clock_jump_wall_time = None
        self.clock_settled_announced = False
        self.initial_epoch_locked = False
        self.tf_broadcaster = TransformBroadcaster(self)
        self.clock_sub = self.create_subscription(
            Clock,
            self.clock_topic,
            self.clock_callback,
            10,
        )
        self.odom_sub = self.create_subscription(
            Odometry,
            self.odom_topic,
            self.odom_callback,
            50,
        )
        self.get_logger().info(
            'Broadcasting TF from %s using odometry topic %s; waiting for %s '
            'to settle for %.1fs and dropping odom more than %.2fs ahead of '
            'or %.2fs behind sim time'
            % (
                self.default_child_frame,
                self.odom_topic,
                self.clock_topic,
                self.startup_clock_settle_sec,
                self.max_future_odom_ns / 1e9,
                self.max_past_odom_ns / 1e9,
            )
        )

    def clock_callback(self, msg):
        clock_ns = msg.clock.sec * 1000000000 + msg.clock.nanosec
        wall_now = time.monotonic()
        if self.first_clock_wall_time is None:
            self.first_clock_wall_time = wall_now
            self.last_clock_jump_wall_time = wall_now
        if self.latest_clock_ns is not None and clock_ns < self.latest_clock_ns:
            self.get_logger().warn(
                'Simulation clock jumped backward from %.9f to %.9f; resetting '
                'odom TF timestamp filter'
                % (self.latest_clock_ns / 1e9, clock_ns / 1e9),
                throttle_duration_sec=2.0,
            )
            self.last_stamp_ns = None
            self.initial_epoch_locked = False
            self.last_clock_jump_wall_time = wall_now
            self.clock_settled_announced = False
        self.latest_clock_ns = clock_ns

    def odom_callback(self, msg):
        stamp_ns = msg.header.stamp.sec * 1000000000 + msg.header.stamp.nanosec
        if self.latest_clock_ns is None:
            self.get_logger().info(
                'Waiting for /clock before publishing odom TF',
                throttle_duration_sec=2.0,
            )
            return
        if not self.is_clock_settled():
            self.get_logger().info(
                'Waiting for %s to settle before publishing odom TF'
                % self.clock_topic,
                throttle_duration_sec=2.0,
            )
            return
        if not self.clock_settled_announced:
            self.get_logger().info(
                '%s is stable; publishing odom TF from %s'
                % (self.clock_topic, self.odom_topic)
            )
            self.clock_settled_announced = True
        if stamp_ns > self.latest_clock_ns + self.max_future_odom_ns:
            self.get_logger().warn(
                'Ignoring future /odom timestamp %.9f while /clock is %.9f'
                % (stamp_ns / 1e9, self.latest_clock_ns / 1e9),
                throttle_duration_sec=2.0,
            )
            return
        if stamp_ns < self.latest_clock_ns - self.max_past_odom_ns:
            self.get_logger().warn(
                'Ignoring stale /odom timestamp %.9f while /clock is %.9f'
                % (stamp_ns / 1e9, self.latest_clock_ns / 1e9),
                throttle_duration_sec=2.0,
            )
            return
        if not self.initial_epoch_locked:
            self.initial_epoch_locked = True
            self.get_logger().info(
                'Locked odom TF epoch at %.9fs' % (stamp_ns / 1e9)
            )
        if (
            self.last_stamp_ns is not None
            and stamp_ns - self.last_stamp_ns > self.max_odom_stamp_jump_ns
        ):
            self.get_logger().warn(
                'Ignoring implausible /odom timestamp jump from %.9f to %.9f'
                % (self.last_stamp_ns / 1e9, stamp_ns / 1e9),
                throttle_duration_sec=2.0,
            )
            return
        if self.last_stamp_ns is not None and stamp_ns <= self.last_stamp_ns:
            self.get_logger().warn(
                'Ignoring non-monotonic /odom timestamp %.9f; last was %.9f'
                % (stamp_ns / 1e9, self.last_stamp_ns / 1e9),
                throttle_duration_sec=5.0,
            )
            return
        self.last_stamp_ns = stamp_ns

        transform = TransformStamped()
        transform.header.stamp = msg.header.stamp
        transform.header.frame_id = msg.header.frame_id or self.default_parent_frame
        transform.child_frame_id = msg.child_frame_id or self.default_child_frame
        transform.transform.translation.x = msg.pose.pose.position.x
        transform.transform.translation.y = msg.pose.pose.position.y
        transform.transform.translation.z = msg.pose.pose.position.z
        transform.transform.rotation = msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(transform)

    def is_clock_settled(self):
        if self.first_clock_wall_time is None:
            return False
        last_unstable_time = self.last_clock_jump_wall_time or self.first_clock_wall_time
        return time.monotonic() - last_unstable_time >= self.startup_clock_settle_sec


def main(args=None):
    rclpy.init(args=args)
    node = OdomTfBroadcaster()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
