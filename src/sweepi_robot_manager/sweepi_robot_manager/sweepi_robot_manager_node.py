#!/usr/bin/env python3
"""Service-driven task manager for SweePi exploration and coverage."""

import os
import signal
import subprocess
import time
from shutil import which

import rclpy
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.srv import SaveMap
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sweepi_robot_manager_interfaces.srv import StartTask


class SweePiRobotManager(Node):
    """Start, stop, and control SweePi task packages from stable services."""

    def __init__(self):
        super().__init__('sweepi_robot_manager')

        self.declare_parameter('map_topic', '/map')
        self.map_topic = str(self.get_parameter('map_topic').value).strip() or '/map'

        self.active_task = 'idle'
        self.active_map_name = ''
        self.active_process = None
        self.pending_coverage_start = False
        self.pending_coverage_start_deadline = 0.0
        self.last_coverage_start_attempt = 0.0
        self.active_task_start_monotonic = None
        self.active_task_start_wall = ''
        self.coverage_terminal_statuses = (
            'SUCCEEDED',
            'COMPLETED_WITH_SKIPS',
            'FAILED',
            'BLOCKED_DYNAMIC_OBJECT',
        )
        self.coverage_terminal_candidate = ''
        self.coverage_terminal_candidate_time = 0.0
        self.coverage_terminal_grace_sec = 2.0
        self.coverage_terminal_handled = False
        self.latest_coverage_status = ''
        self.latest_coverage_stats = ''
        self.latest_coverage_map_summary = ''
        self.last_coverage_summary = 'No coverage task has completed yet.'
        self.coverage_reset_shutdown_deadline = 0.0
        self.latest_exploration_mode = ''
        self.exploration_stop_candidate_time = 0.0
        self.exploration_stop_grace_sec = 2.0
        self.exploration_stop_handled = False

        self.status_pub = self.create_publisher(
            String,
            '/sweepi_robot_manager/status',
            10,
        )

        string_qos = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.last_coverage_summary_pub = self.create_publisher(
            String,
            '/sweepi_robot_manager/coverage/last_summary',
            string_qos,
        )
        self.coverage_status_sub = self.create_subscription(
            String,
            '/coverage_execution_status',
            self._coverage_status_callback,
            string_qos,
        )
        self.coverage_stats_sub = self.create_subscription(
            String,
            '/coverage_stats',
            self._coverage_stats_callback,
            string_qos,
        )
        self.coverage_map_sub = self.create_subscription(
            OccupancyGrid,
            '/coverage_map',
            self._coverage_map_callback,
            map_qos,
        )
        self.exploration_mode_sub = self.create_subscription(
            String,
            '/exploration/mode',
            self._exploration_mode_callback,
            10,
        )

        self._trigger_clients = {}
        self._save_map_clients = {}

        self.create_service(
            StartTask,
            '/sweepi_robot_manager/start_exploration',
            self._start_exploration_callback,
        )
        self.create_service(
            StartTask,
            '/sweepi_robot_manager/start_coverage',
            self._start_coverage_callback,
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/stop_task',
            self._stop_task_callback,
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/coverage/last_summary',
            self._coverage_last_summary_callback,
        )

        self._create_trigger_service(
            '/sweepi_robot_manager/exploration/start_auto',
            '/switch_to_auto_exploration',
            'Exploration automatic mode requested',
            required_task='exploration',
        )
        self._create_trigger_service(
            '/sweepi_robot_manager/exploration/manual',
            '/switch_to_manual_control',
            'Exploration manual mode requested',
            required_task='exploration',
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/exploration/stop',
            self._exploration_stop_callback,
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/exploration/stop_and_save',
            self._exploration_stop_and_save_callback,
        )

        self._create_trigger_service(
            '/sweepi_robot_manager/coverage/start',
            '/start_coverage_follow_path',
            'Coverage start requested',
            required_task='coverage',
        )
        self._create_trigger_service(
            '/sweepi_robot_manager/coverage/validate',
            '/validate_coverage_follow_path',
            'Coverage path validation requested',
            required_task='coverage',
        )
        self._create_trigger_service(
            '/sweepi_robot_manager/coverage/pause',
            '/pause_coverage_follow_path',
            'Coverage pause requested',
            required_task='coverage',
        )
        self._create_trigger_service(
            '/sweepi_robot_manager/coverage/continue',
            '/continue_coverage_follow_path',
            'Coverage continue requested',
            required_task='coverage',
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/coverage/stop',
            self._coverage_stop_callback,
        )
        self._create_trigger_service(
            '/sweepi_robot_manager/coverage/return_home',
            '/return_home_coverage_follow_path',
            'Coverage return-home requested',
            required_task='coverage',
        )
        self.create_service(
            Trigger,
            '/sweepi_robot_manager/coverage/reset',
            self._coverage_reset_callback,
        )

        self.timer = self.create_timer(1.0, self._timer_callback)
        self._publish_status()
        self._publish_last_coverage_summary()
        self.get_logger().info('SweePi robot manager ready for service commands')

    def _start_exploration_callback(self, request, response):
        map_name = self._clean_map_name(request.map_name)
        if not map_name:
            response.success = False
            response.message = 'map_name is required to start exploration'
            return response

        mode = str(request.mode or 'auto').strip().lower()
        if mode not in ('auto', 'manual', 'stopped'):
            response.success = False
            response.message = 'Exploration mode must be auto, manual, or stopped'
            return response

        return self._start_task(
            task='exploration',
            map_name=map_name,
            response=response,
            command=[
                'ros2',
                'launch',
                'sweepi_robot_manager',
                'exploration_task.launch.py',
                'map_name:=%s' % map_name,
                'start_mode:=%s' % mode,
                'use_sim_time:=%s' % self._use_sim_time_value(),
            ],
            initial_mode=mode,
        )

    def _start_coverage_callback(self, request, response):
        map_name = self._clean_map_name(request.map_name)
        if not map_name:
            response.success = False
            response.message = 'map_name is required to start coverage'
            return response

        map_yaml = self._coverage_map_path(map_name)
        if not os.path.exists(map_yaml):
            response.success = False
            response.message = 'Coverage map does not exist: %s' % map_yaml
            return response

        return self._start_task(
            task='coverage',
            map_name=map_name,
            response=response,
            command=[
                'ros2',
                'launch',
                'sweepi_robot_manager',
                'coverage_task.launch.py',
                'map_name:=%s' % map_name,
                'auto_start:=false',
                'use_sim_time:=%s' % self._use_sim_time_value(),
            ],
            transition_from_task='exploration',
            start_coverage_when_ready=bool(request.auto_start),
        )

    def _start_task(
        self,
        task,
        map_name,
        response,
        command,
        transition_from_task=None,
        start_coverage_when_ready=False,
        initial_mode='',
    ):
        self._refresh_active_process()
        if self.active_process is not None:
            if self.active_task == transition_from_task:
                self.get_logger().info(
                    'Stopping active %s launch before starting %s'
                    % (self.active_task, task)
                )
                self._stop_active_task()
                self._refresh_active_process()

        if self.active_process is not None:
            response.success = False
            response.message = (
                '%s is already active. Call /sweepi_robot_manager/stop_task first.'
                % self.active_task
            )
            return response

        ros2_executable = which('ros2')
        if ros2_executable is None:
            response.success = False
            response.message = 'ros2 executable was not found in PATH'
            return response

        command[0] = ros2_executable

        try:
            self.active_process = subprocess.Popen(
                command,
                preexec_fn=os.setsid,
            )
        except OSError as exc:
            self.active_process = None
            self.active_task = 'idle'
            self.active_map_name = ''
            self.active_task_start_monotonic = None
            self.active_task_start_wall = ''
            self.pending_coverage_start = False
            self.pending_coverage_start_deadline = 0.0
            self.last_coverage_start_attempt = 0.0
            response.success = False
            response.message = 'Failed to start %s: %s' % (task, exc)
            return response

        self.active_task = task
        self.active_map_name = map_name
        self.active_task_start_monotonic = time.monotonic()
        self.active_task_start_wall = time.strftime('%Y-%m-%d %H:%M:%S')
        if task == 'coverage':
            self._reset_active_coverage_tracking()
        elif task == 'exploration':
            self._reset_active_exploration_tracking(initial_mode)
        if start_coverage_when_ready:
            self._schedule_coverage_start()
        response.success = True
        if start_coverage_when_ready:
            response.message = (
                'Started coverage with map_name=%s. Waiting for path, initial '
                'pose, and Nav2 costmaps before beginning motion.'
                % map_name
            )
        elif task == 'coverage':
            response.message = (
                'Started coverage with map_name=%s. Set the initial pose, then '
                'call /sweepi_robot_manager/coverage/validate and '
                '/sweepi_robot_manager/coverage/start.'
                % map_name
            )
        else:
            response.message = (
                'Started %s with map_name=%s. Use manager services for task controls.'
                % (task, map_name)
            )
        self.get_logger().info('%s launch started: %s' % (task, ' '.join(command)))
        self._publish_status()
        return response

    def _stop_task_callback(self, request, response):
        del request
        stopped_task = self.active_task
        stopped = self._stop_active_task()
        response.success = True
        if stopped:
            response.message = 'Stopped active task: %s' % stopped_task
        else:
            response.message = 'No active task to stop'
        return response

    def _stop_active_task(self):
        self._refresh_active_process()
        if self.active_process is None:
            self.active_task = 'idle'
            self.active_map_name = ''
            self.active_task_start_monotonic = None
            self.active_task_start_wall = ''
            self._publish_status()
            return False

        process = self.active_process
        task = self.active_task
        pgid = self._process_group_id(process)
        self.get_logger().info('Stopping active %s launch' % task)

        try:
            self._signal_process_tree(process, pgid, signal.SIGINT)
            process.wait(timeout=8.0)
        except subprocess.TimeoutExpired:
            self.get_logger().warn(
                '%s launch did not exit after SIGINT; sending SIGTERM' % task
            )
            self._signal_process_tree(process, pgid, signal.SIGTERM)
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.get_logger().error(
                    '%s launch did not exit after SIGTERM; sending SIGKILL' % task
                )
                self._signal_process_tree(process, pgid, signal.SIGKILL)
                process.wait(timeout=3.0)
        except ProcessLookupError:
            pass

        if pgid is not None and not self._wait_process_group_exit(pgid, 3.0):
            self.get_logger().warn(
                '%s child processes still exist after SIGINT; sending SIGTERM'
                % task
            )
            self._signal_process_tree(process, pgid, signal.SIGTERM)
            if not self._wait_process_group_exit(pgid, 3.0):
                self.get_logger().warn(
                    '%s child processes still exist after SIGTERM; sending SIGKILL'
                    % task
                )
                self._signal_process_tree(process, pgid, signal.SIGKILL)
                self._wait_process_group_exit(pgid, 2.0)

        self.active_process = None
        self.active_task = 'idle'
        self.active_map_name = ''
        self.active_task_start_monotonic = None
        self.active_task_start_wall = ''
        self.pending_coverage_start = False
        self.pending_coverage_start_deadline = 0.0
        self.last_coverage_start_attempt = 0.0
        self.coverage_reset_shutdown_deadline = 0.0
        self._publish_status()
        return True

    def _process_group_id(self, process):
        try:
            return os.getpgid(process.pid)
        except ProcessLookupError:
            return None

    def _signal_process_tree(self, process, pgid, sig):
        if pgid is not None:
            os.killpg(pgid, sig)
            return
        process.send_signal(sig)

    def _process_group_exists(self, pgid):
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _wait_process_group_exit(self, pgid, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if not self._process_group_exists(pgid):
                return True
            time.sleep(0.1)
        return not self._process_group_exists(pgid)

    def _schedule_coverage_start(self):
        self.pending_coverage_start = True
        self.pending_coverage_start_deadline = time.monotonic() + 180.0
        self.last_coverage_start_attempt = 0.0

    def _create_trigger_service(
        self,
        manager_service,
        target_service,
        success_text,
        required_task,
    ):
        self._trigger_clients[target_service] = self.create_client(
            Trigger,
            target_service,
        )

        def callback(request, response):
            del request
            if not self._task_is_active(required_task):
                response.success = False
                response.message = '%s is not active' % required_task
                return response
            return self._forward_trigger(
                target_service,
                success_text,
                response,
            )

        self.create_service(Trigger, manager_service, callback)

    def _forward_trigger(self, target_service, success_text, response):
        client = self._trigger_clients[target_service]
        if not client.wait_for_service(timeout_sec=1.0):
            response.success = False
            response.message = 'Target service unavailable: %s' % target_service
            return response

        future = client.call_async(Trigger.Request())
        future.add_done_callback(
            lambda done_future, service=target_service: self._log_trigger_result(
                service,
                done_future,
            )
        )
        response.success = True
        response.message = success_text
        return response

    def _coverage_reset_callback(self, request, response):
        del request
        if not self._task_is_active('coverage'):
            response.success = False
            response.message = 'coverage is not active'
            return response

        unavailable = self._request_coverage_reset_services(timeout_sec=0.5)

        if unavailable:
            response.success = False
            response.message = (
                'Coverage reset partially requested; unavailable services: %s'
                % ', '.join(unavailable)
            )
            return response

        self._reset_active_coverage_tracking()
        self.coverage_reset_shutdown_deadline = time.monotonic() + 1.0
        response.success = True
        response.message = (
            'Coverage reset requested; coverage map, planner path, and FollowPath '
            'cache will be cleared. Manager will return to idle; start coverage '
            'again from /start_coverage.'
        )
        return response

    def _coverage_stop_callback(self, request, response):
        del request
        if not self._task_is_active('coverage'):
            response.success = False
            response.message = 'coverage is not active'
            return response

        target_service = '/stop_coverage_follow_path'
        client = self._trigger_clients.get(target_service)
        if client is None:
            client = self.create_client(Trigger, target_service)
            self._trigger_clients[target_service] = client

        if client.wait_for_service(timeout_sec=1.0):
            future = client.call_async(Trigger.Request())
            future.add_done_callback(self._coverage_stop_done)
        else:
            self.get_logger().warn(
                'Target service unavailable: %s; closing coverage launch anyway'
                % target_service
            )
            self.coverage_reset_shutdown_deadline = time.monotonic() + 0.5

        response.success = True
        response.message = (
            'Coverage stop requested. Manager will close the coverage launch '
            'stack and return to idle.'
        )
        return response

    def _coverage_stop_done(self, future):
        self._log_trigger_result('/stop_coverage_follow_path', future)
        if self.active_task == 'coverage':
            self.coverage_reset_shutdown_deadline = time.monotonic() + 0.5

    def _exploration_stop_callback(self, request, response):
        del request
        if not self._task_is_active('exploration'):
            response.success = False
            response.message = 'exploration is not active'
            return response

        target_service = '/stop_exploration'
        client = self._trigger_clients.get(target_service)
        if client is None:
            client = self.create_client(Trigger, target_service)
            self._trigger_clients[target_service] = client

        if not client.wait_for_service(timeout_sec=1.0):
            response.success = False
            response.message = 'Target service unavailable: %s' % target_service
            return response

        future = client.call_async(Trigger.Request())
        future.add_done_callback(self._exploration_stop_done)
        response.success = True
        response.message = (
            'Exploration stop requested. Manager will close the exploration '
            'launch stack and return to idle.'
        )
        return response

    def _exploration_stop_done(self, future):
        try:
            result = future.result()
        except Exception as exc:
            self.get_logger().error('/stop_exploration failed: %s' % exc)
        else:
            level = self.get_logger().info if result.success else self.get_logger().warn
            level('/stop_exploration result: %s' % result.message)

        if self.active_task == 'exploration':
            self.get_logger().info(
                'Exploration stopped. Returning manager to idle.'
            )
            self._stop_active_task()

    def _exploration_stop_and_save_callback(self, request, response):
        del request
        if not self._task_is_active('exploration'):
            response.success = False
            response.message = 'exploration is not active'
            return response

        if not self.active_map_name:
            response.success = False
            response.message = 'active exploration map_name is missing'
            return response

        target_service = '/stop_exploration_and_save'
        client = self._save_map_clients.get(target_service)
        if client is None:
            client = self.create_client(SaveMap, target_service)
            self._save_map_clients[target_service] = client

        if not client.wait_for_service(timeout_sec=1.0):
            response.success = False
            response.message = 'Target service unavailable: %s' % target_service
            return response

        save_request = SaveMap.Request()
        save_request.map_topic = self.map_topic
        save_request.map_url = self.active_map_name
        save_request.image_format = 'pgm'
        save_request.map_mode = 'trinary'
        save_request.free_thresh = 0.196
        save_request.occupied_thresh = 0.65

        future = client.call_async(save_request)
        future.add_done_callback(self._exploration_stop_and_save_done)
        response.success = True
        response.message = (
            'Exploration stop-and-save requested for map_name=%s. Manager will '
            'close the exploration launch stack and return to idle.'
            % self.active_map_name
        )
        return response

    def _exploration_stop_and_save_done(self, future):
        self._log_save_map_result(future)
        if self.active_task == 'exploration':
            self.get_logger().info(
                'Exploration stop-and-save finished. Returning manager to idle.'
            )
            self._stop_active_task()

    def _coverage_last_summary_callback(self, request, response):
        del request
        response.success = bool(self.last_coverage_summary)
        response.message = self.last_coverage_summary
        return response

    def _coverage_status_callback(self, msg):
        status = str(msg.data or '').strip()
        if not status:
            return

        self.latest_coverage_status = status
        if self.active_task != 'coverage':
            return

        if status in self.coverage_terminal_statuses:
            if self.coverage_terminal_candidate != status:
                self.coverage_terminal_candidate = status
                self.coverage_terminal_candidate_time = time.monotonic()
            return

        self.coverage_terminal_candidate = ''
        self.coverage_terminal_candidate_time = 0.0

    def _coverage_stats_callback(self, msg):
        data = str(msg.data or '').strip()
        if data:
            self.latest_coverage_stats = data

    def _coverage_map_callback(self, msg):
        covered_cells = 0
        uncovered_cells = 0
        for cell_value in msg.data:
            if cell_value == 100:
                covered_cells += 1
            elif cell_value == 50:
                uncovered_cells += 1

        coverable_cells = covered_cells + uncovered_cells
        percentage = 0.0
        if coverable_cells > 0:
            percentage = (covered_cells / coverable_cells) * 100.0

        self.latest_coverage_map_summary = (
            'coverage_map frame=%s size=%dx%d resolution=%.3f '
            'covered_cells=%d uncovered_cells=%d coverable_cells=%d '
            'percentage=%.1f'
            % (
                msg.header.frame_id or 'map',
                msg.info.width,
                msg.info.height,
                msg.info.resolution,
                covered_cells,
                uncovered_cells,
                coverable_cells,
                percentage,
            )
        )

    def _exploration_mode_callback(self, msg):
        mode = str(msg.data or '').strip().lower()
        if not mode:
            return

        previous_mode = self.latest_exploration_mode
        self.latest_exploration_mode = mode
        if self.active_task != 'exploration' or self.exploration_stop_handled:
            return

        if mode == 'stopped' and previous_mode in ('auto', 'manual'):
            self.exploration_stop_candidate_time = time.monotonic()
            self.get_logger().info(
                'Exploration reported stopped. Waiting briefly before '
                'returning manager to idle.'
            )

    def _reset_active_coverage_tracking(self):
        self.coverage_terminal_candidate = ''
        self.coverage_terminal_candidate_time = 0.0
        self.coverage_terminal_handled = False
        self.latest_coverage_status = ''
        self.latest_coverage_stats = ''
        self.latest_coverage_map_summary = ''

    def _request_coverage_reset_services(self, timeout_sec=0.2):
        targets = (
            '/reset_coverage_tracker',
            '/reset_coverage_planner',
            '/reset_coverage_follow_path',
        )
        unavailable = []
        for target_service in targets:
            client = self._trigger_clients.get(target_service)
            if client is None:
                client = self.create_client(Trigger, target_service)
                self._trigger_clients[target_service] = client

            if not client.wait_for_service(timeout_sec=timeout_sec):
                unavailable.append(target_service)
                continue

            future = client.call_async(Trigger.Request())
            future.add_done_callback(
                lambda done_future, service=target_service: (
                    self._log_trigger_result(service, done_future)
                )
            )
        return unavailable

    def _reset_active_exploration_tracking(self, initial_mode=''):
        self.latest_exploration_mode = str(initial_mode or '').strip().lower()
        self.exploration_stop_candidate_time = 0.0
        self.exploration_stop_handled = False

    def _finalize_completed_coverage_if_ready(self):
        if self.active_task != 'coverage' or self.active_process is None:
            return
        if self.coverage_terminal_handled:
            return
        if not self.coverage_terminal_candidate:
            return

        elapsed = time.monotonic() - self.coverage_terminal_candidate_time
        if elapsed < self.coverage_terminal_grace_sec:
            return

        final_status = self.coverage_terminal_candidate
        self._record_coverage_summary(final_status, publish=True)
        self.coverage_terminal_handled = True
        self.get_logger().info(
            'Coverage finished with status=%s. Clearing coverage visuals before '
            'returning manager to idle.'
            % final_status
        )
        unavailable = self._request_coverage_reset_services(timeout_sec=0.2)
        if unavailable:
            self.get_logger().warn(
                'Coverage finished, but reset services were unavailable: %s'
                % ', '.join(unavailable)
            )
        self.coverage_reset_shutdown_deadline = time.monotonic() + 1.0

    def _finalize_completed_exploration_if_ready(self):
        if self.active_task != 'exploration' or self.active_process is None:
            return
        if self.exploration_stop_handled:
            return
        if self.exploration_stop_candidate_time <= 0.0:
            return

        elapsed = time.monotonic() - self.exploration_stop_candidate_time
        if elapsed < self.exploration_stop_grace_sec:
            return

        self.exploration_stop_handled = True
        self.get_logger().info(
            'Exploration finished or stopped. Returning manager to idle.'
        )
        self._stop_active_task()

    def _record_coverage_summary(self, final_status, publish=False):
        elapsed_sec = 0.0
        if self.active_task_start_monotonic is not None:
            elapsed_sec = time.monotonic() - self.active_task_start_monotonic

        finished_wall = time.strftime('%Y-%m-%d %H:%M:%S')
        fields = [
            'task=coverage',
            'status=%s' % final_status,
            'map_name=%s' % (self.active_map_name or '(unset)'),
            'started_at=%s' % (self.active_task_start_wall or '(unknown)'),
            'finished_at=%s' % finished_wall,
            'duration_sec=%.1f' % elapsed_sec,
        ]
        if self.latest_coverage_stats:
            fields.append('stats="%s"' % self.latest_coverage_stats)
        if self.latest_coverage_map_summary:
            fields.append('map="%s"' % self.latest_coverage_map_summary)

        self.last_coverage_summary = ' '.join(fields)
        self.get_logger().info(
            'Last coverage summary: %s' % self.last_coverage_summary
        )
        if publish:
            self._publish_last_coverage_summary()

    def _publish_last_coverage_summary(self):
        if not rclpy.ok():
            return
        msg = String()
        msg.data = self.last_coverage_summary
        try:
            self.last_coverage_summary_pub.publish(msg)
        except Exception:
            pass

    def _task_is_active(self, task):
        self._refresh_active_process()
        return self.active_task == task and self.active_process is not None

    def _refresh_active_process(self):
        if self.active_process is None:
            return
        return_code = self.active_process.poll()
        if return_code is None:
            return
        self.get_logger().info(
            '%s launch exited with code %s' % (self.active_task, return_code)
        )
        if self.active_task == 'coverage' and not self.coverage_terminal_handled:
            self._record_coverage_summary(
                'LAUNCH_EXITED_%s' % return_code,
                publish=True,
            )
        self.active_process = None
        self.active_task = 'idle'
        self.active_map_name = ''
        self.active_task_start_monotonic = None
        self.active_task_start_wall = ''
        self.pending_coverage_start = False
        self.pending_coverage_start_deadline = 0.0
        self.last_coverage_start_attempt = 0.0
        self.coverage_reset_shutdown_deadline = 0.0
        self._publish_status()

    def _timer_callback(self):
        self._refresh_active_process()
        self._tick_pending_coverage_start()
        self._tick_pending_coverage_reset_shutdown()
        self._finalize_completed_coverage_if_ready()
        self._finalize_completed_exploration_if_ready()
        self._publish_status()

    def _tick_pending_coverage_reset_shutdown(self):
        if self.coverage_reset_shutdown_deadline <= 0.0:
            return
        if time.monotonic() < self.coverage_reset_shutdown_deadline:
            return

        self.coverage_reset_shutdown_deadline = 0.0
        if self.active_task == 'coverage' and self.active_process is not None:
            self.get_logger().info(
                'Closing coverage launch and returning idle.'
            )
            self._stop_active_task()

    def _tick_pending_coverage_start(self):
        if not self.pending_coverage_start:
            return
        if not self._task_is_active('coverage'):
            self.pending_coverage_start = False
            return

        now = time.monotonic()
        if now > self.pending_coverage_start_deadline:
            self.pending_coverage_start = False
            self.get_logger().warn(
                'Timed out waiting to start coverage. Set the initial pose and '
                'call /sweepi_robot_manager/coverage/start to try again.'
            )
            return
        if now - self.last_coverage_start_attempt < 2.0:
            return

        self.last_coverage_start_attempt = now
        client = self._trigger_clients.get('/start_coverage_follow_path')
        if client is None:
            return
        if not client.wait_for_service(timeout_sec=0.1):
            self.get_logger().info(
                'Waiting for /start_coverage_follow_path service...',
                throttle_duration_sec=5.0,
            )
            return

        future = client.call_async(Trigger.Request())
        future.add_done_callback(self._coverage_auto_start_result)

    def _coverage_auto_start_result(self, future):
        try:
            result = future.result()
        except Exception as exc:
            self.get_logger().warn('Coverage start attempt failed: %s' % exc)
            return

        if result.success:
            self.pending_coverage_start = False
            self.get_logger().info(
                'Coverage motion started: %s' % result.message
            )
            return

        self.get_logger().info(
            'Coverage not ready yet: %s' % result.message,
            throttle_duration_sec=5.0,
        )

    def _log_trigger_result(self, service, future):
        try:
            result = future.result()
        except Exception as exc:
            self.get_logger().error('%s failed: %s' % (service, exc))
            return
        level = self.get_logger().info if result.success else self.get_logger().warn
        level('%s result: %s' % (service, result.message))

    def _log_save_map_result(self, future):
        try:
            result = future.result()
        except Exception as exc:
            self.get_logger().error('/stop_exploration_and_save failed: %s' % exc)
            return
        if result.result:
            self.get_logger().info('/stop_exploration_and_save completed')
        else:
            self.get_logger().warn('/stop_exploration_and_save failed')

    def _publish_status(self):
        if not rclpy.ok():
            return

        msg = String()
        msg.data = (
            'task=%s map_name=%s latest_coverage_status=%s '
            'latest_exploration_mode=%s'
        ) % (
            self.active_task,
            self.active_map_name or '(unset)',
            self.latest_coverage_status or '(none)',
            self.latest_exploration_mode or '(none)',
        )
        try:
            self.status_pub.publish(msg)
        except Exception:
            pass

    def _clean_map_name(self, value):
        return str(value or '').strip()

    def _coverage_map_path(self, map_name):
        name = os.path.basename(str(map_name).strip())
        if name.endswith('.yaml'):
            name = name[:-5]
        return os.path.join(os.path.expanduser('~'), 'SweePi', 'maps', name + '.yaml')

    def _use_sim_time_value(self):
        try:
            return self.get_parameter('use_sim_time').value and 'true' or 'false'
        except Exception:
            return 'false'

    def _bool_arg(self, value):
        return 'true' if bool(value) else 'false'


def main(args=None):
    rclpy.init(args=args)
    node = SweePiRobotManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop_active_task()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
