#!/usr/bin/env python3
import math
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from action_msgs.msg import GoalStatusArray

try:
    from sweepi_interfaces.msg import HardwareStatus
except Exception:
    HardwareStatus = None

TOPICS = ['/cmd_vel_nav', '/cmd_vel_smoothed', '/cmd_vel']

class Monitor(Node):
    def __init__(self, duration):
        super().__init__('coverage_motion_chain_monitor')
        self.start = time.monotonic()
        self.duration = duration
        self.vel = {t: {'count': 0, 'nonzero': 0, 'max_lin': 0.0, 'max_ang': 0.0, 'first_nonzero': None, 'last': None} for t in TOPICS}
        self.odom_first = None
        self.odom_last = None
        self.hw_count = 0
        self.hw_faults = []
        self.exec = []
        self.action = []
        for topic in TOPICS:
            self.create_subscription(Twist, topic, self._vel_cb(topic), 10)
        self.create_subscription(Odometry, '/wheel/odom', self._odom_cb, 10)
        self.create_subscription(String, '/coverage_execution_status', self._exec_cb, 10)
        self.create_subscription(GoalStatusArray, '/follow_path/_action/status', self._action_cb, 10)
        if HardwareStatus is not None:
            self.create_subscription(HardwareStatus, '/hardware/status', self._hw_cb, 10)
        self.timer = self.create_timer(1.0, self._tick)

    def _vel_cb(self, topic):
        def cb(msg):
            now = time.monotonic() - self.start
            lin = float(msg.linear.x)
            ang = float(msg.angular.z)
            rec = self.vel[topic]
            rec['count'] += 1
            rec['max_lin'] = max(rec['max_lin'], abs(lin))
            rec['max_ang'] = max(rec['max_ang'], abs(ang))
            rec['last'] = (now, lin, ang)
            if abs(lin) > 1e-4 or abs(ang) > 1e-4:
                rec['nonzero'] += 1
                if rec['first_nonzero'] is None:
                    rec['first_nonzero'] = (now, lin, ang)
        return cb

    def _odom_cb(self, msg):
        pose = msg.pose.pose.position
        yaw = 0.0
        sample = (time.monotonic() - self.start, float(pose.x), float(pose.y), yaw)
        if self.odom_first is None:
            self.odom_first = sample
        self.odom_last = sample

    def _hw_cb(self, msg):
        self.hw_count += 1
        fault = getattr(msg, 'fault', 0)
        if fault:
            self.hw_faults.append((time.monotonic() - self.start, fault, str(msg)))

    def _exec_cb(self, msg):
        value = msg.data
        if not self.exec or self.exec[-1][1] != value:
            self.exec.append((time.monotonic() - self.start, value))

    def _action_cb(self, msg):
        statuses = [(s.goal_info.goal_id.uuid, s.status) for s in msg.status_list]
        condensed = [s.status for s in msg.status_list]
        if not self.action or self.action[-1][1] != condensed:
            self.action.append((time.monotonic() - self.start, condensed))

    def _tick(self):
        elapsed = time.monotonic() - self.start
        if elapsed >= self.duration:
            self.report()
            rclpy.shutdown()

    def report(self):
        print('MOTION_CHAIN_MONITOR duration=%.1f' % (time.monotonic() - self.start), flush=True)
        for topic, rec in self.vel.items():
            print('%s count=%d nonzero=%d max_lin=%.4f max_ang=%.4f first_nonzero=%s last=%s' % (
                topic, rec['count'], rec['nonzero'], rec['max_lin'], rec['max_ang'], rec['first_nonzero'], rec['last']), flush=True)
        if self.odom_first and self.odom_last:
            dx = self.odom_last[1] - self.odom_first[1]
            dy = self.odom_last[2] - self.odom_first[2]
            print('/wheel/odom first=%s last=%s delta_xy=%.4f' % (self.odom_first, self.odom_last, math.hypot(dx, dy)), flush=True)
        print('/hardware/status count=%d faults=%s' % (self.hw_count, self.hw_faults[:3]), flush=True)
        print('/coverage_execution_status transitions=%s' % (self.exec,), flush=True)
        print('/follow_path action status transitions=%s' % (self.action,), flush=True)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=30.0)
    args = parser.parse_args()
    rclpy.init()
    node = Monitor(args.duration)
    rclpy.spin(node)

if __name__ == '__main__':
    main()
