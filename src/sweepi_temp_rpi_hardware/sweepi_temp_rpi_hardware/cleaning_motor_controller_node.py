#!/usr/bin/env python3
"""Control SweePi vacuum and brush motors from coverage and motion state."""

import json
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sweepi_temp_rpi_hardware.cleaning_motor_gpio import CleaningMotorGpio
from sweepi_temp_rpi_hardware.pwm_ramp import ramp_step

ACTIVE_COVERAGE_STATES = {'EXECUTING', 'SKIPPING_DYNAMIC_OBSTACLE'}
ARM_ACTIVE_STATES = {
    'ARM_PAUSING', 'ARM_TURNING_TO_OBJECT', 'ARM_WAITING_FOR_COMPLETION',
    'ARM_TURNING_TO_PATH', 'ARM_RESUMING',
}


class CleaningMotorController(Node):
    def __init__(self):
        super().__init__('cleaning_motor_controller')
        defaults = {
            'enabled': True, 'gpio_chip_index': 0, 'dry_run_gpio': False,
            'fail_if_gpio_unavailable': True, 'vacuum_pwm_gpio': 18,
            'vacuum_enable_gpio': 17, 'brush_pwm_gpio': 19,
            'brush_1_in1_gpio': 16, 'brush_1_in2_gpio': 20,
            'brush_2_in1_gpio': 21, 'brush_2_in2_gpio': 26,
            'brush_1_reversed': False, 'brush_2_reversed': True,
            'pwm_frequency_hz': 1000.0, 'control_rate_hz': 50.0,
            'status_publish_rate_hz': 2.0, 'vacuum_max_pwm_percent': 10.0,
            'brush_max_pwm_percent': 10.0, 'vacuum_ramp_up_sec': 10.0,
            'brush_ramp_up_sec': 5.0, 'vacuum_ramp_down_sec': 2.0,
            'brush_ramp_down_sec': 1.0, 'coverage_status_topic': '/coverage_execution_status',
            'arm_status_topic': '/coverage_arm_status', 'cmd_vel_topic': '/cmd_vel',
            'hardware_status_topic': '/hardware/cleaning_motors/status',
            'motion_linear_threshold': 0.005, 'motion_angular_threshold': 0.01,
            'motion_timeout_sec': 0.5, 'keep_vacuum_on_during_arm': True,
            'keep_brushes_on_during_arm': False, 'allow_manual_test': False,
            'vacuum_test_pwm_percent': 10.0, 'brush_test_pwm_percent': 10.0,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        p = lambda name: self.get_parameter(name).value
        self.enabled = bool(p('enabled'))
        self.vacuum_max = float(p('vacuum_max_pwm_percent'))
        self.brush_max = float(p('brush_max_pwm_percent'))
        self.vacuum_up = float(p('vacuum_ramp_up_sec'))
        self.brush_up = float(p('brush_ramp_up_sec'))
        self.vacuum_down = float(p('vacuum_ramp_down_sec'))
        self.brush_down = float(p('brush_ramp_down_sec'))
        for name, value in (('vacuum_max_pwm_percent', self.vacuum_max), ('brush_max_pwm_percent', self.brush_max)):
            if not 0.0 <= value <= 100.0:
                raise ValueError(f'{name} must be between 0 and 100')
        pins = {
            'vacuum_pwm': p('vacuum_pwm_gpio'), 'vacuum_enable': p('vacuum_enable_gpio'),
            'brush_pwm': p('brush_pwm_gpio'), 'brush_1_in1': p('brush_1_in1_gpio'),
            'brush_1_in2': p('brush_1_in2_gpio'), 'brush_2_in1': p('brush_2_in1_gpio'),
            'brush_2_in2': p('brush_2_in2_gpio'),
        }
        if len(set(int(v) for v in pins.values())) != len(pins):
            raise ValueError('Cleaning motor GPIO assignments must be unique')
        self.gpio = CleaningMotorGpio(
            pins, float(p('pwm_frequency_hz')), bool(p('dry_run_gpio')),
            bool(p('fail_if_gpio_unavailable')), int(p('gpio_chip_index')),
        )
        self.brush_1_forward = not bool(p('brush_1_reversed'))
        self.brush_2_forward = not bool(p('brush_2_reversed'))
        self.motion_linear_threshold = float(p('motion_linear_threshold'))
        self.motion_angular_threshold = float(p('motion_angular_threshold'))
        self.motion_timeout = float(p('motion_timeout_sec'))
        self.keep_vacuum_arm = bool(p('keep_vacuum_on_during_arm'))
        self.keep_brush_arm = bool(p('keep_brushes_on_during_arm'))
        self.allow_manual_test = bool(p('allow_manual_test'))
        self.vacuum_test = min(float(p('vacuum_test_pwm_percent')), self.vacuum_max)
        self.brush_test = min(float(p('brush_test_pwm_percent')), self.brush_max)
        self.coverage_status = 'IDLE'
        self.arm_status = 'IDLE'
        self.motion_started = False
        self.last_motion_time = 0.0
        self.manual_test = False
        self.estop = False
        self.vacuum_current = 0.0
        self.brush_current = 0.0
        self.vacuum_target = 0.0
        self.brush_target = 0.0
        self.last_update = time.monotonic()
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, str(p('coverage_status_topic')), self._coverage_cb, qos)
        self.create_subscription(String, str(p('arm_status_topic')), self._arm_cb, 10)
        self.create_subscription(Twist, str(p('cmd_vel_topic')), self._cmd_vel_cb, 10)
        self.status_pub = self.create_publisher(String, str(p('hardware_status_topic')), 10)
        self.create_service(Trigger, '/cleaning_motors/emergency_stop', self._estop_cb)
        self.create_service(Trigger, '/cleaning_motors/reset_fault', self._reset_cb)
        self.create_service(Trigger, '/cleaning_motors/start_test', self._start_test_cb)
        self.create_service(Trigger, '/cleaning_motors/stop_test', self._stop_test_cb)
        self.create_timer(1.0 / max(1.0, float(p('control_rate_hz'))), self._control)
        self.create_timer(1.0 / max(0.1, float(p('status_publish_rate_hz'))), self._publish_status)
        self.get_logger().info('Cleaning motor controller ready; motors remain off until EXECUTING and motion begins.')

    def _coverage_cb(self, msg):
        self.coverage_status = msg.data.strip()
        if self.coverage_status not in ACTIVE_COVERAGE_STATES:
            self.motion_started = False

    def _arm_cb(self, msg):
        self.arm_status = msg.data.strip()

    def _cmd_vel_cb(self, msg):
        moving = abs(msg.linear.x) >= self.motion_linear_threshold or abs(msg.angular.z) >= self.motion_angular_threshold
        if moving:
            self.last_motion_time = time.monotonic()
            if self.coverage_status in ACTIVE_COVERAGE_STATES:
                self.motion_started = True

    def _targets(self):
        if not self.enabled or self.estop:
            return 0.0, 0.0
        if self.manual_test:
            return self.vacuum_test, self.brush_test
        arm_active = self.arm_status in ARM_ACTIVE_STATES
        cleaning_motion_active = self.coverage_status in ACTIVE_COVERAGE_STATES and self.motion_started
        if not cleaning_motion_active and not arm_active:
            return 0.0, 0.0
        vacuum = self.vacuum_max if (cleaning_motion_active or (arm_active and self.keep_vacuum_arm)) else 0.0
        brushes = self.brush_max if (cleaning_motion_active and not arm_active) or (arm_active and self.keep_brush_arm) else 0.0
        return vacuum, brushes

    def _control(self):
        now = time.monotonic()
        dt = max(0.0, now - self.last_update)
        self.last_update = now
        self.vacuum_target, self.brush_target = self._targets()
        self.vacuum_current = ramp_step(self.vacuum_current, self.vacuum_target, self.vacuum_max,
                                        self.vacuum_up, self.vacuum_down, dt)
        self.brush_current = ramp_step(self.brush_current, self.brush_target, self.brush_max,
                                       self.brush_up, self.brush_down, dt)
        try:
            self.gpio.set_vacuum_enabled(self.vacuum_current > 0.0 or self.vacuum_target > 0.0)
            self.gpio.set_vacuum_pwm(self.vacuum_current)
            if self.brush_current > 0.0 or self.brush_target > 0.0:
                self.gpio.set_brush_directions(self.brush_1_forward, self.brush_2_forward)
                self.gpio.set_brush_pwm(self.brush_current)
            else:
                self.gpio.stop_brushes()
        except Exception as exc:
            self.estop = True
            self.gpio.all_off()
            self.get_logger().error(f'Cleaning motor GPIO failure: {exc}')

    def _publish_status(self):
        msg = String()
        msg.data = json.dumps({
            'coverage_status': self.coverage_status, 'arm_status': self.arm_status,
            'motion_started': self.motion_started, 'vacuum_target_pwm_percent': round(self.vacuum_target, 3),
            'vacuum_current_pwm_percent': round(self.vacuum_current, 3),
            'brush_target_pwm_percent': round(self.brush_target, 3),
            'brush_current_pwm_percent': round(self.brush_current, 3),
            'max_pwm_percent': {'vacuum': self.vacuum_max, 'brushes': self.brush_max},
            'emergency_stop_latched': self.estop, 'dry_run_gpio': self.gpio.dry_run,
        })
        self.status_pub.publish(msg)

    def _estop_cb(self, _, response):
        self.estop = True
        self.manual_test = False
        self.vacuum_current = self.brush_current = 0.0
        self.gpio.all_off()
        response.success, response.message = True, 'Cleaning motors immediately stopped and latched.'
        return response

    def _reset_cb(self, _, response):
        self.estop = False
        self.motion_started = False
        response.success, response.message = True, 'Fault latch reset; motors remain off until new cleaning motion.'
        return response

    def _start_test_cb(self, _, response):
        if not self.allow_manual_test or self.estop:
            response.success, response.message = False, 'Manual test disabled or emergency stop latched.'
            return response
        self.manual_test = True
        response.success, response.message = True, 'Manual cleaning motor ramp started.'
        return response

    def _stop_test_cb(self, _, response):
        self.manual_test = False
        response.success, response.message = True, 'Manual test stopped.'
        return response

    def destroy_node(self):
        self.gpio.all_off()
        self.gpio.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = CleaningMotorController()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
