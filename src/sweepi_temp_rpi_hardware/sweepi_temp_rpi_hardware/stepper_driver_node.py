#!/usr/bin/env python3

import json
import math
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Int64, String


class DryRunLine:
    def __init__(self, name):
        self.name = name
        self.value = 0

    def set_value(self, value):
        self.value = int(bool(value))

    def release(self):
        pass


class GpiodV1Line:
    def __init__(self, line):
        self.line = line

    def set_value(self, value):
        self.line.set_value(int(bool(value)))

    def release(self):
        self.line.release()


class GpioBundle:
    def __init__(self, chip_name, pins, dry_run, fail_if_unavailable, consumer):
        self.dry_run = dry_run
        self.chip = None
        self.lines = {}

        if dry_run:
            self.lines = {name: DryRunLine(name) for name in pins}
            return

        try:
            import gpiod
        except ImportError as exc:
            message = (
                'python3-libgpiod is not available. Install python3-libgpiod, '
                'or launch with dry_run_gpio:=true on a development machine.'
            )
            if fail_if_unavailable:
                raise RuntimeError(message) from exc
            self.dry_run = True
            self.lines = {name: DryRunLine(name) for name in pins}
            return

        if not hasattr(gpiod, 'Chip') or not hasattr(gpiod.Chip, 'get_line'):
            message = (
                'Unsupported libgpiod Python API. This temporary driver expects '
                'the v1 API with gpiod.Chip(...).get_line(...). Install the '
                'python3-libgpiod package that exposes that API, or use dry_run_gpio:=true.'
            )
            if fail_if_unavailable:
                raise RuntimeError(message)
            self.dry_run = True
            self.lines = {name: DryRunLine(name) for name in pins}
            return

        try:
            self.chip = gpiod.Chip(chip_name)
            for name, pin in pins.items():
                line = self.chip.get_line(int(pin))
                line.request(
                    consumer=consumer,
                    type=gpiod.LINE_REQ_DIR_OUT,
                    default_vals=[0],
                )
                self.lines[name] = GpiodV1Line(line)
        except Exception as exc:
            message = f'Failed to initialize GPIO chip {chip_name}: {exc}'
            if fail_if_unavailable:
                raise RuntimeError(message) from exc
            self.dry_run = True
            self.lines = {name: DryRunLine(name) for name in pins}
            return

    def set_value(self, name, value):
        self.lines[name].set_value(value)

    def close(self):
        for line in self.lines.values():
            try:
                line.release()
            except Exception:
                pass
        if self.chip is not None and hasattr(self.chip, 'close'):
            try:
                self.chip.close()
            except Exception:
                pass


class StepperDriverNode(Node):
    def __init__(self):
        super().__init__('sweepi_temp_stepper_driver')

        self.declare_parameter('wheel_radius', 0.0325)
        self.declare_parameter('wheel_separation', 0.20)
        self.declare_parameter('steps_per_rev', 200)
        self.declare_parameter('microsteps', 16)
        self.declare_parameter('max_steps_per_sec', 4000.0)
        self.declare_parameter('accel_steps_per_sec2', 3500.0)
        self.declare_parameter('decel_steps_per_sec2', 15000.0)
        self.declare_parameter('cmd_vel_timeout', 0.2)
        self.declare_parameter('steps_publish_rate_hz', 50.0)
        self.declare_parameter('chip_name', 'gpiochip4')
        self.declare_parameter('left_en_pin', 12)
        self.declare_parameter('left_dir_pin', 5)
        self.declare_parameter('left_step_pin', 6)
        self.declare_parameter('right_en_pin', 22)
        self.declare_parameter('right_dir_pin', 23)
        self.declare_parameter('right_step_pin', 24)
        self.declare_parameter('enable_active_low', True)
        self.declare_parameter('left_dir_inverted', False)
        self.declare_parameter('right_dir_inverted', True)
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('left_steps_topic', '/stepper/left_steps_total')
        self.declare_parameter('right_steps_topic', '/stepper/right_steps_total')
        self.declare_parameter('dry_run_gpio', False)
        self.declare_parameter('fail_if_gpio_unavailable', True)

        self.wheel_radius = float(self.get_parameter('wheel_radius').value)
        self.wheel_separation = float(self.get_parameter('wheel_separation').value)
        self.steps_per_rev = int(self.get_parameter('steps_per_rev').value)
        self.microsteps = int(self.get_parameter('microsteps').value)
        self.max_steps_per_sec = float(self.get_parameter('max_steps_per_sec').value)
        self.accel_steps_per_sec2 = float(self.get_parameter('accel_steps_per_sec2').value)
        self.decel_steps_per_sec2 = float(self.get_parameter('decel_steps_per_sec2').value)
        self.cmd_vel_timeout = float(self.get_parameter('cmd_vel_timeout').value)
        self.steps_publish_rate_hz = float(self.get_parameter('steps_publish_rate_hz').value)
        self.chip_name = str(self.get_parameter('chip_name').value)
        self.enable_active_low = bool(self.get_parameter('enable_active_low').value)
        self.left_dir_inverted = bool(self.get_parameter('left_dir_inverted').value)
        self.right_dir_inverted = bool(self.get_parameter('right_dir_inverted').value)
        self.cmd_vel_topic = str(self.get_parameter('cmd_vel_topic').value)
        self.left_steps_topic = str(self.get_parameter('left_steps_topic').value)
        self.right_steps_topic = str(self.get_parameter('right_steps_topic').value)
        self.dry_run_gpio = bool(self.get_parameter('dry_run_gpio').value)
        self.fail_if_gpio_unavailable = bool(self.get_parameter('fail_if_gpio_unavailable').value)

        self.steps_per_wheel_rev = self.steps_per_rev * self.microsteps
        self.wheel_circumference = 2.0 * math.pi * self.wheel_radius

        pins = {
            'left_en': int(self.get_parameter('left_en_pin').value),
            'left_dir': int(self.get_parameter('left_dir_pin').value),
            'left_step': int(self.get_parameter('left_step_pin').value),
            'right_en': int(self.get_parameter('right_en_pin').value),
            'right_dir': int(self.get_parameter('right_dir_pin').value),
            'right_step': int(self.get_parameter('right_step_pin').value),
        }
        self.gpio = GpioBundle(
            self.chip_name,
            pins,
            self.dry_run_gpio,
            self.fail_if_gpio_unavailable,
            'sweepi_temp_stepper_driver',
        )
        if self.gpio.dry_run and not self.dry_run_gpio:
            self.get_logger().warn(
                'GPIO unavailable and fail_if_gpio_unavailable is false; falling back to dry-run step counts.'
            )
            self.dry_run_gpio = True

        self.lock = threading.Lock()
        self.running = True
        self.target_sps = {'left': 0.0, 'right': 0.0}
        self.current_sps = {'left': 0.0, 'right': 0.0}
        self.step_totals = {'left': 0, 'right': 0}
        self.dry_run_fractional_steps = {'left': 0.0, 'right': 0.0}
        self.last_cmd_time = time.monotonic()
        self.last_dry_run_time = time.monotonic()
        self.last_status = 'starting'

        self._set_step_pin('left', 0)
        self._set_step_pin('right', 0)
        self._enable_drivers(True)

        self.create_subscription(Twist, self.cmd_vel_topic, self.cmd_vel_callback, 10)
        self.left_steps_pub = self.create_publisher(Int64, self.left_steps_topic, 10)
        self.right_steps_pub = self.create_publisher(Int64, self.right_steps_topic, 10)
        self.status_pub = self.create_publisher(String, '/hardware/temp_stepper_status', 10)

        self.create_timer(0.02, self.watchdog_callback)
        self.create_timer(
            1.0 / max(1e-3, self.steps_publish_rate_hz),
            self.publish_step_totals,
        )

        self.threads = []
        if not self.dry_run_gpio:
            self.threads = [
                threading.Thread(target=self.motor_loop, args=('left',), daemon=True),
                threading.Thread(target=self.motor_loop, args=('right',), daemon=True),
            ]
            for thread in self.threads:
                thread.start()

        mode = 'dry-run GPIO simulation' if self.dry_run_gpio else f'GPIO chip {self.chip_name}'
        self.get_logger().info(f'Temporary stepper driver started using {mode}.')

    def cmd_vel_callback(self, msg):
        left_velocity = msg.linear.x - msg.angular.z * self.wheel_separation / 2.0
        right_velocity = msg.linear.x + msg.angular.z * self.wheel_separation / 2.0
        left_sps = self.wheel_velocity_to_steps_per_sec(left_velocity)
        right_sps = self.wheel_velocity_to_steps_per_sec(right_velocity)

        with self.lock:
            self.target_sps['left'] = left_sps
            self.target_sps['right'] = right_sps
            self.last_cmd_time = time.monotonic()
            self.last_status = 'commanded'

    def wheel_velocity_to_steps_per_sec(self, wheel_velocity):
        rev_per_sec = wheel_velocity / self.wheel_circumference
        steps_per_sec = rev_per_sec * self.steps_per_wheel_rev
        return max(-self.max_steps_per_sec, min(self.max_steps_per_sec, steps_per_sec))

    def watchdog_callback(self):
        stale = (time.monotonic() - self.last_cmd_time) > self.cmd_vel_timeout
        if stale:
            with self.lock:
                self.target_sps['left'] = 0.0
                self.target_sps['right'] = 0.0
                self.last_status = 'cmd_vel_stale'

    def publish_step_totals(self):
        if self.dry_run_gpio:
            self._dry_run_update()

        with self.lock:
            left_total = int(self.step_totals['left'])
            right_total = int(self.step_totals['right'])
            target_left = float(self.target_sps['left'])
            target_right = float(self.target_sps['right'])
            current_left = float(self.current_sps['left'])
            current_right = float(self.current_sps['right'])
            age = time.monotonic() - self.last_cmd_time
            status = self.last_status

        left_msg = Int64()
        left_msg.data = left_total
        self.left_steps_pub.publish(left_msg)

        right_msg = Int64()
        right_msg.data = right_total
        self.right_steps_pub.publish(right_msg)

        status_msg = String()
        status_msg.data = json.dumps({
            'status': status,
            'dry_run_gpio': self.dry_run_gpio,
            'cmd_vel_age_sec': round(age, 4),
            'left_steps_total': left_total,
            'right_steps_total': right_total,
            'target_left_steps_per_sec': round(target_left, 3),
            'target_right_steps_per_sec': round(target_right, 3),
            'current_left_steps_per_sec': round(current_left, 3),
            'current_right_steps_per_sec': round(current_right, 3),
        })
        self.status_pub.publish(status_msg)

    def _dry_run_update(self):
        now = time.monotonic()
        dt = max(0.0, now - self.last_dry_run_time)
        self.last_dry_run_time = now

        with self.lock:
            for side in ('left', 'right'):
                self.current_sps[side] = self._limited_speed(
                    self.current_sps[side],
                    self.target_sps[side],
                    dt,
                )
                self.dry_run_fractional_steps[side] += self.current_sps[side] * dt
                whole_steps = math.trunc(self.dry_run_fractional_steps[side])
                if whole_steps:
                    self.step_totals[side] += whole_steps
                    self.dry_run_fractional_steps[side] -= whole_steps

    def motor_loop(self, side):
        last_time = time.monotonic()
        step_pin = f'{side}_step'

        while self.running:
            now = time.monotonic()
            dt = max(0.0, now - last_time)
            last_time = now

            with self.lock:
                sps = self._limited_speed(self.current_sps[side], self.target_sps[side], dt)
                self.current_sps[side] = sps

            abs_sps = abs(sps)
            if abs_sps < 0.5:
                self._set_step_pin(side, 0)
                time.sleep(0.002)
                continue

            self._set_dir_pin(side, sps > 0.0)
            period = 1.0 / abs_sps
            pulse_width = min(0.00005, period * 0.4)

            self.gpio.set_value(step_pin, 1)
            time.sleep(pulse_width)
            self.gpio.set_value(step_pin, 0)

            with self.lock:
                self.step_totals[side] += 1 if sps > 0.0 else -1

            time.sleep(max(0.0, period - pulse_width))

    def _limited_speed(self, current, target, dt):
        if dt <= 0.0:
            return current
        rate_limit = self.accel_steps_per_sec2 if abs(target) > abs(current) else self.decel_steps_per_sec2
        max_delta = rate_limit * dt
        delta = target - current
        if delta > max_delta:
            return current + max_delta
        if delta < -max_delta:
            return current - max_delta
        return target

    def _set_dir_pin(self, side, forward):
        inverted = self.left_dir_inverted if side == 'left' else self.right_dir_inverted
        self.gpio.set_value(f'{side}_dir', bool(forward) ^ bool(inverted))

    def _set_step_pin(self, side, value):
        self.gpio.set_value(f'{side}_step', value)

    def _enable_drivers(self, enable):
        enabled_value = 0 if self.enable_active_low else 1
        disabled_value = 1 - enabled_value
        value = enabled_value if enable else disabled_value
        self.gpio.set_value('left_en', value)
        self.gpio.set_value('right_en', value)

    def destroy_node(self):
        self.running = False
        with self.lock:
            self.target_sps['left'] = 0.0
            self.target_sps['right'] = 0.0
        for thread in self.threads:
            thread.join(timeout=0.5)
        try:
            self._set_step_pin('left', 0)
            self._set_step_pin('right', 0)
            self._enable_drivers(False)
            self.gpio.close()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = StepperDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
