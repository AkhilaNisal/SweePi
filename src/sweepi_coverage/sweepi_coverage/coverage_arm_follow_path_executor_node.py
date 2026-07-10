#!/usr/bin/env python3
"""FollowPath coverage executor with optional rear-mounted arm assistance."""

import copy
import math
import time
import uuid

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import Spin
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import LaserScan, Range
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sweepi_coverage.coverage_follow_path_executor_node import (
    CoverageFollowPathExecutorNode,
)


class CoverageArmFollowPathExecutorNode(CoverageFollowPathExecutorNode):
    """Use a rear arm for confirmed obstacles when the front ToF is clear."""

    ARM_IDLE = 'IDLE'
    ARM_PAUSING = 'ARM_PAUSING'
    ARM_TURNING_TO_OBJECT = 'ARM_TURNING_TO_OBJECT'
    ARM_WAITING_FOR_COMPLETION = 'ARM_WAITING_FOR_COMPLETION'
    ARM_TURNING_TO_PATH = 'ARM_TURNING_TO_PATH'
    ARM_RESUMING = 'ARM_RESUMING'
    ARM_FAILED = 'ARM_FAILED'

    def __init__(self):
        super().__init__()
        self._declare_arm_parameters()
        self._load_arm_parameters()

        self.arm_state = self.ARM_IDLE
        self.arm_active = False
        self.arm_report = None
        self.arm_failure_context = None
        self.arm_candidate_position = None
        self.arm_candidate_signature = None
        self.arm_handled_positions = []
        self.arm_handled_objects = []
        self.arm_completion_received = False
        self.arm_replan_waiting_for_path = False
        self.arm_resume_suppress_until_monotonic = 0.0
        self.arm_resume_ignore_handled_costmap = False
        self.arm_command_id = None
        self.arm_started_acknowledged = False
        self.arm_deadline_monotonic = 0.0
        self.arm_start_ack_deadline_monotonic = 0.0
        self.arm_pause_deadline_monotonic = 0.0
        self.arm_spin_goal_handle = None
        self.arm_spin_request_id = 0
        self.arm_inflated_detection_candidate = None
        self.latest_front_tof = None
        self.latest_front_tof_monotonic = 0.0
        self.front_tof_free_readings = 0
        self.latest_front_lidar = None
        self.latest_front_lidar_monotonic = 0.0
        self.latest_front_lidar_min_range = float('inf')
        self.latest_front_lidar_min_angle = float('inf')
        self.front_lidar_object_readings = 0

        self.arm_spin_client = ActionClient(self, Spin, self.arm_spin_action_name)
        self.front_tof_sub = self.create_subscription(
            Range, self.front_tof_topic, self._front_tof_callback, 10
        )
        self.front_lidar_sub = self.create_subscription(
            LaserScan, self.front_lidar_topic, self._front_lidar_callback, 10
        )
        self.arm_command_pub = self.create_publisher(
            String, self.arm_command_topic, 10
        )
        self.arm_status_sub = self.create_subscription(
            String, self.arm_status_topic, self._arm_status_callback, 10
        )
        self.coverage_arm_status_pub = self.create_publisher(
            String, self.coverage_arm_status_topic, 10
        )
        self.arm_replan_planner_client = self.create_client(
            Trigger, self.arm_replan_planner_service
        )
        self.arm_manual_complete_service = self.create_service(
            Trigger,
            '/coverage_arm/manual_complete',
            self._manual_complete_callback,
        )
        self.arm_timer = self.create_timer(0.1, self._arm_timer_callback)
        self._publish_arm_status(
            'IDLE use_robot_arm=%s inflated_promotion=true '
            'front_lidar_threshold_m=%.2f front_tof_clear_threshold_m=%.2f'
            % (
                str(self.use_robot_arm).lower(),
                self.front_lidar_object_threshold_m,
                self.tof_free_space_threshold_m,
            )
        )

    def _declare_arm_parameters(self):
        defaults = {
            'use_robot_arm': False,
            'front_tof_topic': '/tof/front/range',
            'tof_free_space_threshold_m': 0.50,
            'tof_message_timeout_sec': 0.5,
            'tof_required_free_readings': 5,
            'front_lidar_topic': '/scan',
            'front_lidar_object_threshold_m': 0.50,
            'front_lidar_sector_half_angle_rad': 0.35,
            'front_lidar_object_max_angle_rad': 0.25,
            'front_lidar_message_timeout_sec': 0.5,
            'front_lidar_required_object_readings': 5,
            'arm_command_topic': '/sweepi_arm/command',
            'arm_status_topic': '/sweepi_arm/status',
            'coverage_arm_status_topic': '/coverage_arm_status',
            'arm_spin_action_name': '/spin',
            'arm_turn_angle_rad': math.pi,
            'arm_spin_timeout_sec': 15.0,
            'arm_start_ack_timeout_sec': 3.0,
            'arm_completion_timeout_sec': 60.0,
            'arm_handled_object_radius_m': 0.50,
            'arm_resume_handled_costmap_radius_m': 0.75,
            'arm_handled_path_index_margin': 10,
            'arm_static_obstacle_reject_radius_m': 0.45,
            'arm_mark_failed_object_handled': True,
            'arm_resume_on_failure': True,
            'arm_replan_after_completion': True,
            'arm_replan_on_resume_failure': True,
            'arm_replan_max_tolerated_blocked_costmap_samples': 75,
            'arm_replan_max_tolerated_blocked_costmap_ratio': 0.05,
            'arm_replan_max_tolerated_blocked_cost': 99,
            'arm_replan_planner_service': '/replan_coverage_planner',
            'arm_fallback_to_dynamic_bypass': False,
            'arm_resume_suppress_detection_sec': 3.0,
        }
        for name, value in defaults.items():
            self._declare_parameter_if_needed(name, value)

    def _load_arm_parameters(self):
        self.use_robot_arm = self._bool_param('use_robot_arm')
        self.front_tof_topic = self._string_param('front_tof_topic')
        self.tof_free_space_threshold_m = max(
            0.0, self._double_param('tof_free_space_threshold_m')
        )
        self.tof_message_timeout_sec = max(
            0.0, self._double_param('tof_message_timeout_sec')
        )
        self.tof_required_free_readings = max(
            1, self._int_param('tof_required_free_readings')
        )
        self.front_lidar_topic = self._string_param('front_lidar_topic')
        self.front_lidar_object_threshold_m = max(
            0.0, self._double_param('front_lidar_object_threshold_m')
        )
        self.front_lidar_sector_half_angle_rad = max(
            0.0, self._double_param('front_lidar_sector_half_angle_rad')
        )
        self.front_lidar_object_max_angle_rad = max(
            0.0,
            min(
                self.front_lidar_sector_half_angle_rad,
                self._double_param('front_lidar_object_max_angle_rad'),
            ),
        )
        self.front_lidar_message_timeout_sec = max(
            0.0, self._double_param('front_lidar_message_timeout_sec')
        )
        self.front_lidar_required_object_readings = max(
            1, self._int_param('front_lidar_required_object_readings')
        )
        self.arm_command_topic = self._string_param('arm_command_topic')
        self.arm_status_topic = self._string_param('arm_status_topic')
        self.coverage_arm_status_topic = self._string_param(
            'coverage_arm_status_topic'
        )
        self.arm_spin_action_name = self._string_param('arm_spin_action_name')
        self.arm_turn_angle_rad = self._double_param('arm_turn_angle_rad')
        self.arm_spin_timeout_sec = max(
            0.1, self._double_param('arm_spin_timeout_sec')
        )
        self.arm_start_ack_timeout_sec = max(
            0.1, self._double_param('arm_start_ack_timeout_sec')
        )
        self.arm_completion_timeout_sec = max(
            0.1, self._double_param('arm_completion_timeout_sec')
        )
        self.arm_resume_suppress_detection_sec = max(
            0.0, self._double_param('arm_resume_suppress_detection_sec')
        )
        self.arm_handled_object_radius_m = max(
            0.0, self._double_param('arm_handled_object_radius_m')
        )
        self.arm_resume_handled_costmap_radius_m = max(
            self.arm_handled_object_radius_m,
            self._double_param('arm_resume_handled_costmap_radius_m'),
        )
        self.arm_handled_path_index_margin = max(
            0, self._int_param('arm_handled_path_index_margin')
        )
        self.arm_static_obstacle_reject_radius_m = max(
            0.0, self._double_param('arm_static_obstacle_reject_radius_m')
        )
        self.arm_mark_failed_object_handled = self._bool_param(
            'arm_mark_failed_object_handled'
        )
        self.arm_resume_on_failure = self._bool_param('arm_resume_on_failure')
        self.arm_replan_after_completion = self._bool_param(
            'arm_replan_after_completion'
        )
        self.arm_replan_on_resume_failure = self._bool_param(
            'arm_replan_on_resume_failure'
        )
        self.arm_replan_max_tolerated_blocked_costmap_samples = max(
            0, self._int_param('arm_replan_max_tolerated_blocked_costmap_samples')
        )
        self.arm_replan_max_tolerated_blocked_costmap_ratio = max(
            0.0,
            self._double_param('arm_replan_max_tolerated_blocked_costmap_ratio'),
        )
        self.arm_replan_max_tolerated_blocked_cost = max(
            self.max_tolerated_blocked_cost,
            self._int_param('arm_replan_max_tolerated_blocked_cost'),
        )
        self.arm_replan_planner_service = self._string_param(
            'arm_replan_planner_service'
        )
        self.arm_fallback_to_dynamic_bypass = self._bool_param(
            'arm_fallback_to_dynamic_bypass'
        )

    def _front_tof_callback(self, msg):
        self.latest_front_tof = msg
        self.latest_front_tof_monotonic = time.monotonic()
        if self._tof_reading_is_free(msg):
            self.front_tof_free_readings += 1
        else:
            self.front_tof_free_readings = 0

    def _front_lidar_callback(self, msg):
        self.latest_front_lidar = msg
        self.latest_front_lidar_monotonic = time.monotonic()
        (
            self.latest_front_lidar_min_range,
            self.latest_front_lidar_min_angle,
        ) = self._front_lidar_min_range_and_angle(msg)
        if self._front_lidar_reading_has_object(msg):
            self.front_lidar_object_readings += 1
        else:
            self.front_lidar_object_readings = 0

    def _tof_reading_is_free(self, msg):
        value = float(msg.range)
        if math.isnan(value) or value == float('-inf') or value < 0.0:
            return False
        # sensor_msgs/Range defines +Inf as a valid out-of-range reading.
        # For a front clearance sensor that is free space, not invalid data.
        if value == float('inf'):
            return True
        if math.isfinite(msg.min_range) and value < msg.min_range:
            return False
        if (
            math.isfinite(msg.max_range)
            and msg.max_range > 0.0
            and value > msg.max_range
        ):
            return False
        return value >= self.tof_free_space_threshold_m

    def _front_tof_is_fresh_and_free(self):
        return self._front_tof_status()['free']

    def _front_tof_status(self):
        if self.latest_front_tof is None:
            return {
                'free': False,
                'reason': 'tof_missing',
                'range': float('nan'),
                'age_sec': float('inf'),
            }

        age_sec = time.monotonic() - self.latest_front_tof_monotonic
        value = float(self.latest_front_tof.range)
        reading_free = self._tof_reading_is_free(self.latest_front_tof)
        if age_sec > self.tof_message_timeout_sec:
            reason = 'tof_stale'
            free = False
        elif not reading_free:
            reason = 'tof_blocked_or_invalid'
            free = False
        elif self.front_tof_free_readings < self.tof_required_free_readings:
            reason = 'tof_waiting_for_consecutive_free_readings'
            free = False
        else:
            reason = 'tof_free'
            free = True
        return {
            'free': free,
            'reason': reason,
            'range': value,
            'age_sec': age_sec,
        }

    def _front_lidar_min_range(self, msg):
        return self._front_lidar_min_range_and_angle(msg)[0]

    def _front_lidar_min_range_and_angle(self, msg):
        if msg is None or not msg.ranges:
            return float('inf'), float('inf')

        min_range = float('inf')
        min_angle = float('inf')
        angle = float(msg.angle_min)
        angle_increment = float(msg.angle_increment)
        for value in msg.ranges:
            normalized_angle = math.atan2(math.sin(angle), math.cos(angle))
            if abs(normalized_angle) <= self.front_lidar_sector_half_angle_rad:
                distance = float(value)
                if self._lidar_range_is_valid(msg, distance):
                    if distance < min_range:
                        min_range = distance
                        min_angle = normalized_angle
            angle += angle_increment
        return min_range, min_angle

    def _lidar_range_is_valid(self, msg, distance):
        if not math.isfinite(distance):
            return False
        if distance < 0.0:
            return False
        if math.isfinite(msg.range_min) and distance < msg.range_min:
            return False
        if (
            math.isfinite(msg.range_max)
            and msg.range_max > 0.0
            and distance > msg.range_max
        ):
            return False
        return True

    def _front_lidar_reading_has_object(self, msg):
        min_range, min_angle = self._front_lidar_min_range_and_angle(msg)
        return (
            min_range <= self.front_lidar_object_threshold_m
            and abs(min_angle) <= self.front_lidar_object_max_angle_rad
        )

    def _front_lidar_has_fresh_object(self):
        return self._front_lidar_status()['object_detected']

    def _front_lidar_status(self):
        if self.latest_front_lidar is None:
            return {
                'object_detected': False,
                'reason': 'front_lidar_missing',
                'min_range': float('inf'),
                'age_sec': float('inf'),
            }

        age_sec = time.monotonic() - self.latest_front_lidar_monotonic
        min_range = self.latest_front_lidar_min_range
        min_angle = self.latest_front_lidar_min_angle
        reading_has_object = min_range <= self.front_lidar_object_threshold_m
        if age_sec > self.front_lidar_message_timeout_sec:
            reason = 'front_lidar_stale'
            object_detected = False
        elif not reading_has_object:
            reason = 'front_lidar_no_object_within_threshold'
            object_detected = False
        elif abs(min_angle) > self.front_lidar_object_max_angle_rad:
            reason = 'front_lidar_object_not_centered'
            object_detected = False
        elif (
            self.front_lidar_object_readings
            < self.front_lidar_required_object_readings
        ):
            reason = 'front_lidar_waiting_for_consecutive_object_readings'
            object_detected = False
        else:
            reason = 'front_lidar_object_detected'
            object_detected = True
        return {
            'object_detected': object_detected,
            'reason': reason,
            'min_range': min_range,
            'min_angle': min_angle,
            'age_sec': age_sec,
        }

    def _candidate_object_position(self, report):
        poses = report.get('dynamic_only_blocked_poses', [])
        if not poses:
            return None
        finite_points = [
            (pose.pose.position.x, pose.pose.position.y)
            for pose in poses
            if math.isfinite(pose.pose.position.x)
            and math.isfinite(pose.pose.position.y)
        ]
        if not finite_points:
            return None
        frame = (
            report.get('path_frame')
            or poses[0].header.frame_id
            or self.global_frame
        )
        return (
            frame,
            sum(point[0] for point in finite_points) / len(finite_points),
            sum(point[1] for point in finite_points) / len(finite_points),
        )

    def _candidate_object_signature(self, report):
        candidate = self._candidate_object_position(report)
        if candidate is None:
            return None
        nearest_index = int(report.get('nearest_index', -1))
        blocked_start_index = int(
            report.get('blocked_start_index', nearest_index)
        )
        blocked_end_index = int(report.get('blocked_end_index', nearest_index))
        if blocked_start_index < 0:
            blocked_start_index = nearest_index
        if blocked_end_index < 0:
            blocked_end_index = blocked_start_index
        if blocked_start_index > blocked_end_index:
            blocked_start_index, blocked_end_index = (
                blocked_end_index,
                blocked_start_index,
            )
        return {
            'frame': candidate[0],
            'x': candidate[1],
            'y': candidate[2],
            'nearest_index': nearest_index,
            'blocked_start_index': blocked_start_index,
            'blocked_end_index': blocked_end_index,
        }

    def _object_was_handled(self, candidate, report=None):
        if candidate is None:
            return False
        return self._handled_object_match_reason(candidate, report) is not None

    def _handled_object_match_reason(self, candidate, report=None):
        frame, x_value, y_value = candidate
        radius_sq = self.arm_handled_object_radius_m ** 2
        for old_frame, old_x, old_y in self.arm_handled_positions:
            if (
                old_frame == frame
                and (x_value - old_x) ** 2 + (y_value - old_y) ** 2
                <= radius_sq
            ):
                return 'position_radius'

        signature = self._candidate_object_signature(report) if report else None
        if signature is None:
            return None

        margin = self.arm_handled_path_index_margin
        for handled in getattr(self, 'arm_handled_objects', []):
            if handled.get('frame') != signature['frame']:
                continue
            dx = signature['x'] - handled.get('x', float('inf'))
            dy = signature['y'] - handled.get('y', float('inf'))
            if dx * dx + dy * dy <= radius_sq:
                return 'signature_radius'

            old_start = int(handled.get('blocked_start_index', -1))
            old_end = int(handled.get('blocked_end_index', old_start))
            new_start = signature['blocked_start_index']
            new_end = signature['blocked_end_index']
            intervals_overlap = (
                new_start <= old_end + margin
                and new_end >= old_start - margin
            )
            if intervals_overlap:
                return 'path_index_overlap'
        return None

    def _should_use_arm(self, report):
        candidate = self._candidate_object_position(report)
        return (
            self.use_robot_arm
            and not self.arm_active
            and candidate is not None
            and not self._object_was_handled(candidate, report)
            and self._arm_static_obstacle_reject_reason(report) is None
            and self._front_lidar_has_fresh_object()
            and self._front_tof_is_fresh_and_free()
        )

    def _arm_static_obstacle_reject_reason(self, report, path=None):
        if self.arm_static_obstacle_reject_radius_m <= 0.0:
            return None
        candidate = self._candidate_object_position(report)
        pose = PoseStamped()
        if candidate is not None:
            pose.header.frame_id = candidate[0] or self.global_frame
            pose.pose.position.x = candidate[1]
            pose.pose.position.y = candidate[2]
        elif path is not None and getattr(path, 'poses', None):
            nearest_index = max(
                0,
                min(int(report.get('nearest_index', 0)), len(path.poses) - 1),
            )
            pose = copy.deepcopy(path.poses[nearest_index])
        else:
            return None
        pose.pose.orientation.w = 1.0
        static_info = self._nearest_static_obstacle_distance(
            pose,
            self.arm_static_obstacle_reject_radius_m,
        )
        if not static_info.get('valid', False):
            return None
        distance = static_info.get('distance_m', float('inf'))
        if math.isfinite(distance):
            return 'candidate_near_static_obstacle_%.3fm' % distance
        return None

    def _detect_dynamic_blocked_interval(self, path, force_confirm=False):
        report = super()._detect_dynamic_blocked_interval(path, force_confirm)
        reason = self._arm_inflated_promotion_block_reason(report, path)
        if reason is not None:
            self.arm_inflated_detection_candidate = None
            self._log_arm_inflated_promotion_rejection(report, reason)
            return report
        return self._promote_inflated_rejection_for_arm(
            report,
            path,
            force_confirm,
        )

    def _arm_can_promote_inflated_rejection(self, report, path):
        return self._arm_inflated_promotion_block_reason(report, path) is None

    def _arm_inflated_promotion_block_reason(self, report, path):
        if report is None or report.get('blocked'):
            return 'no_inflated_rejection_report'
        if not self.use_robot_arm or self.arm_active:
            return (
                'arm_disabled'
                if not self.use_robot_arm
                else 'arm_already_active'
            )
        if time.monotonic() < self.arm_resume_suppress_until_monotonic:
            return 'arm_resume_suppress_window_active'
        if report.get('reason') != 'inflated_or_non_lethal_local_cost':
            return 'report_reason_%s' % report.get('reason', 'unknown')
        if report.get('inflated_ignored_count', 0) <= 0:
            return 'no_inflated_cells'
        if path is None or not getattr(path, 'poses', None):
            return 'path_unavailable'
        lidar_status = self._front_lidar_status()
        if not lidar_status['object_detected']:
            return lidar_status['reason']
        tof_status = self._front_tof_status()
        if not tof_status['free']:
            return tof_status['reason']
        static_reason = self._arm_static_obstacle_reject_reason(report, path)
        if static_reason is not None:
            return static_reason
        return None

    def _log_arm_inflated_promotion_rejection(self, report, reason):
        if report is None:
            return
        if (
            report.get('reason') != 'inflated_or_non_lethal_local_cost'
            and report.get('inflated_ignored_count', 0) <= 0
        ):
            return
        tof_status = self._front_tof_status()
        lidar_status = self._front_lidar_status()
        text = (
            '[ARM_DETECT] rejected inflated local cost promotion: '
            'reason=%s use_robot_arm=%s arm_active=%s tof_topic=%s '
            'tof_range=%.3f tof_age_sec=%.3f free_readings=%d/%d '
            'lidar_topic=%s lidar_min_range=%.3f lidar_angle=%.3f '
            'lidar_age_sec=%.3f lidar_object_readings=%d/%d '
            'report_reason=%s cost=%d'
            % (
                reason,
                str(self.use_robot_arm).lower(),
                str(self.arm_active).lower(),
                self.front_tof_topic,
                float(tof_status['range']),
                float(tof_status['age_sec']),
                self.front_tof_free_readings,
                self.tof_required_free_readings,
                self.front_lidar_topic,
                float(lidar_status['min_range']),
                float(lidar_status.get('min_angle', float('inf'))),
                float(lidar_status['age_sec']),
                self.front_lidar_object_readings,
                self.front_lidar_required_object_readings,
                report.get('reason', 'unknown'),
                int(report.get('max_ignored_inflated_cost', 0)),
            )
        )
        self.get_logger().warn(text, throttle_duration_sec=1.0)
        self._publish_dynamic_skip_status(text)

    def _promote_inflated_rejection_for_arm(self, report, path, force_confirm):
        promoted = copy.deepcopy(report)
        nearest_index = max(
            0,
            min(int(promoted.get('nearest_index', 0)), len(path.poses) - 1),
        )
        promoted['blocked_start_index'] = nearest_index
        promoted['blocked_end_index'] = nearest_index
        promoted['dynamic_only_blocked_poses'] = [
            copy.deepcopy(path.poses[nearest_index])
        ]
        promoted['dynamic_only_blocked_count'] = 1
        promoted['blocked_path_length_m'] = 0.0
        promoted['arm_assist_inflated_candidate'] = True

        candidate_position = self._candidate_object_position(promoted)
        handled_reason = self._handled_object_match_reason(
            candidate_position,
            promoted,
        )
        if handled_reason is not None:
            promoted['blocked'] = False
            promoted['reason'] = 'arm_assist_object_already_handled'
            text = (
                '[ARM_DETECT] rejected inflated local cost promotion: '
                'reason=object_already_handled match=%s nearest_index=%d'
                % (handled_reason, nearest_index)
            )
            self.get_logger().info(text, throttle_duration_sec=1.0)
            self._publish_dynamic_skip_status(text)
            return promoted

        now = time.monotonic()
        candidate = self.arm_inflated_detection_candidate
        index_margin = max(1, getattr(self, 'dynamic_resume_ignore_index_margin', 1))
        candidate_changed = (
            candidate is None
            or abs(nearest_index - candidate.get('nearest_index', -1)) > index_margin
        )
        if (
            not candidate_changed
            and getattr(self, 'dynamic_detection_hysteresis_sec', 0.0) > 0.0
            and now - candidate.get('last_seen_time', 0.0)
            > self.dynamic_detection_hysteresis_sec
        ):
            candidate_changed = True

        if candidate_changed:
            candidate = {
                'first_seen_time': now,
                'last_seen_time': now,
                'count': 0,
                'nearest_index': nearest_index,
                'max_cost': int(promoted.get('max_ignored_inflated_cost', 0)),
            }

        candidate['last_seen_time'] = now
        candidate['count'] = candidate.get('count', 0) + 1
        candidate['nearest_index'] = nearest_index
        candidate['max_cost'] = max(
            candidate.get('max_cost', 0),
            int(promoted.get('max_ignored_inflated_cost', 0)),
        )
        self.arm_inflated_detection_candidate = candidate
        consecutive_count = candidate['count']
        required_consecutive = (
            1 if force_confirm else self.dynamic_required_consecutive_detections
        )
        promoted['consecutive_count'] = consecutive_count

        if consecutive_count < required_consecutive:
            promoted['blocked'] = False
            promoted['reason'] = 'arm_assist_inflated_candidate_pending'
            text = (
                '[ARM_DETECT] inflated local cost candidate with free ToF '
                'seen count=%d/%d nearest_index=%d cost=%d'
                % (
                    consecutive_count,
                    required_consecutive,
                    nearest_index,
                    int(promoted.get('max_ignored_inflated_cost', 0)),
                )
            )
            self.get_logger().info(text, throttle_duration_sec=1.0)
            self._publish_dynamic_skip_status(text)
            return promoted

        promoted['blocked'] = True
        promoted['reason'] = 'arm_assist_inflated_local_cost_with_free_tof'
        tof_status = self._front_tof_status()
        lidar_status = self._front_lidar_status()
        text = (
            '[ARM_DETECT] promoting inflated local cost to arm candidate '
            'nearest_index=%d cost=%d front_lidar_min_range=%.3f '
            'front_lidar_angle=%.3f front_tof_range=%.3f '
            'samples_lidar=%d/%d samples_tof=%d/%d'
            % (
                nearest_index,
                int(promoted.get('max_ignored_inflated_cost', 0)),
                float(lidar_status['min_range']),
                float(lidar_status.get('min_angle', float('inf'))),
                float(tof_status['range']),
                self.front_lidar_object_readings,
                self.front_lidar_required_object_readings,
                self.front_tof_free_readings,
                self.tof_required_free_readings,
            )
        )
        self.get_logger().warn(text)
        self._publish_dynamic_skip_status(text)
        return promoted

    def _start_dynamic_skip(self, report):
        if not self._should_use_arm(report):
            return super()._start_dynamic_skip(report)
        return self._start_arm_operation(report, None)

    def _start_dynamic_skip_after_failure(self, report, error_code, error_label):
        if not self._should_use_arm(report):
            return super()._start_dynamic_skip_after_failure(
                report, error_code, error_label
            )
        return self._start_arm_operation(report, (error_code, error_label))

    def _start_arm_operation(self, report, failure_context):
        candidate = self._candidate_object_position(report)
        tof_range = (
            float(self.latest_front_tof.range)
            if self.latest_front_tof is not None
            else float('nan')
        )
        lidar_status = self._front_lidar_status()
        self.get_logger().warn(
            '[ARM_TRIGGER] decision=TRIGGER_ARM frame=%s object_x=%.3f '
            'object_y=%.3f front_lidar=%.3f lidar_angle=%.3f '
            'lidar_readings=%d/%d front_tof=%.3f free_readings=%d/%d. Pausing '
            'FollowPath before rotating to the rear-mounted arm.'
            % (
                candidate[0],
                candidate[1],
                candidate[2],
                float(lidar_status['min_range']),
                float(lidar_status.get('min_angle', float('inf'))),
                self.front_lidar_object_readings,
                self.front_lidar_required_object_readings,
                tof_range,
                self.front_tof_free_readings,
                self.tof_required_free_readings,
            )
        )
        if not self._snapshot_pause_resume_path():
            self._publish_arm_status('ARM_FAILED reason=pause_snapshot_failed')
            return self._fallback_to_dynamic_bypass(report, failure_context)

        self.arm_active = True
        self.arm_state = self.ARM_PAUSING
        self.arm_report = copy.deepcopy(report)
        self.arm_failure_context = failure_context
        self.arm_candidate_position = self._candidate_object_position(report)
        self.arm_candidate_signature = self._candidate_object_signature(report)
        self.coverage_pause_requested = True
        self.coverage_stopped = False
        self._abort_dynamic_work_for_control_request('pause')
        self._request_cancel_active_motion('pause')
        self._publish_zero_velocity()
        self._set_status(self.ARM_PAUSING)
        self.arm_pause_deadline_monotonic = (
            time.monotonic() + self.arm_spin_timeout_sec
        )
        self._publish_arm_status('ARM_PAUSING reason=dynamic_local_only_obstacle')
        return True

    def _arm_timer_callback(self):
        if not self.arm_active:
            return
        now = time.monotonic()
        if self.arm_state == self.ARM_PAUSING:
            self._publish_zero_velocity()
            if not self.goal_in_flight and self.current_goal_handle is None:
                self._start_spin(self.arm_turn_angle_rad, returning=False)
            elif now >= self.arm_pause_deadline_monotonic:
                self._fail_arm_operation('follow_path_stop_timeout', restore=False)
        elif self.arm_state in (
            self.ARM_TURNING_TO_OBJECT,
            self.ARM_TURNING_TO_PATH,
        ) and now >= self.arm_deadline_monotonic:
            if self.arm_spin_goal_handle is not None:
                self.arm_spin_goal_handle.cancel_goal_async()
            self._spin_failed('spin_timeout')
        elif self.arm_state == self.ARM_WAITING_FOR_COMPLETION:
            if (
                not self.arm_started_acknowledged
                and self.arm_start_ack_deadline_monotonic > 0.0
                and now >= self.arm_start_ack_deadline_monotonic
            ):
                self.arm_start_ack_deadline_monotonic = 0.0
                self._publish_arm_status(
                    'ARM_WAITING_FOR_COMPLETION command_id=%s '
                    'awaiting=COMPLETED start_ack=missing'
                    % self.arm_command_id
                )
            if now >= self.arm_deadline_monotonic:
                self._fail_arm_operation('arm_completion_timeout', restore=True)

    def _start_spin(self, angle, returning):
        self.arm_state = (
            self.ARM_TURNING_TO_PATH if returning else self.ARM_TURNING_TO_OBJECT
        )
        self._set_status(self.arm_state)
        self._publish_zero_velocity()
        if not self.arm_spin_client.server_is_ready():
            self._spin_failed('spin_action_unavailable')
            return
        goal = Spin.Goal()
        goal.target_yaw = float(angle)
        goal.time_allowance = Duration(seconds=self.arm_spin_timeout_sec).to_msg()
        if hasattr(goal, 'disable_collision_checks'):
            goal.disable_collision_checks = False
        self.arm_spin_request_id += 1
        request_id = self.arm_spin_request_id
        self.arm_deadline_monotonic = time.monotonic() + self.arm_spin_timeout_sec
        self._publish_arm_status('%s angle_rad=%.6f' % (self.arm_state, angle))
        future = self.arm_spin_client.send_goal_async(goal)
        future.add_done_callback(
            lambda done, rid=request_id, is_return=returning: (
                self._spin_goal_response(done, rid, is_return)
            )
        )

    def _spin_goal_response(self, future, request_id, returning):
        if request_id != self.arm_spin_request_id or not self.arm_active:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._spin_failed('spin_goal_exception:%s' % exc)
            return
        if not goal_handle.accepted:
            self._spin_failed('spin_goal_rejected')
            return
        self.arm_spin_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda done, rid=request_id, is_return=returning: (
                self._spin_result(done, rid, is_return)
            )
        )

    def _spin_result(self, future, request_id, returning):
        if request_id != self.arm_spin_request_id or not self.arm_active:
            return
        self.arm_spin_goal_handle = None
        try:
            wrapped = future.result()
        except Exception as exc:
            self._spin_failed('spin_result_exception:%s' % exc)
            return
        if wrapped.status != GoalStatus.STATUS_SUCCEEDED:
            self._spin_failed('spin_status_%d' % wrapped.status)
            return
        if returning:
            if self.arm_replan_after_completion and self.arm_completion_received:
                self._request_arm_replan_after_completion()
            else:
                self._resume_after_arm()
        else:
            self._send_arm_start_command()

    def _spin_failed(self, reason):
        returning = self.arm_state == self.ARM_TURNING_TO_PATH
        if returning:
            self._publish_arm_status('ARM_FAILED reason=return_%s' % reason)
            self._resume_after_arm()
        else:
            # A failed Spin may still have moved partway. Request the inverse
            # turn before resuming; if Spin itself is unavailable, the return
            # attempt fails asynchronously into the safe-resume path.
            self._fail_arm_operation(reason, restore=True)

    def _send_arm_start_command(self):
        self.arm_state = self.ARM_WAITING_FOR_COMPLETION
        self._set_status(self.ARM_WAITING_FOR_COMPLETION)
        self.arm_command_id = uuid.uuid4().hex
        self.arm_started_acknowledged = False
        now = time.monotonic()
        self.arm_start_ack_deadline_monotonic = now + self.arm_start_ack_timeout_sec
        self.arm_deadline_monotonic = now + self.arm_completion_timeout_sec
        message = String()
        message.data = 'START:%s' % self.arm_command_id
        self.arm_command_pub.publish(message)
        self.get_logger().warn(
            '[ARM_WAIT] command=%s published on %s. Coverage is paused; '
            'waiting asynchronously for COMPLETED:%s on %s.'
            % (
                message.data,
                self.arm_command_topic,
                self.arm_command_id,
                self.arm_status_topic,
            )
        )
        self._publish_arm_status(
            'ARM_WAITING_FOR_COMPLETION command_id=%s awaiting=COMPLETED'
            % self.arm_command_id
        )

    def _arm_status_callback(self, msg):
        parts = msg.data.strip().split(':', 1)
        if len(parts) != 2:
            if self.arm_state == self.ARM_WAITING_FOR_COMPLETION:
                self.get_logger().warn(
                    '[ARM_WAIT] ignoring malformed status=%s; expected '
                    'COMPLETED:%s'
                    % (msg.data, self.arm_command_id or 'none')
                )
            return
        status, command_id = parts
        if command_id != self.arm_command_id:
            if (
                self.arm_state == self.ARM_WAITING_FOR_COMPLETION
                and status in ('STARTED', 'COMPLETED', 'FAILED')
            ):
                self.get_logger().warn(
                    '[ARM_WAIT] ignoring %s:%s; expected command_id=%s. '
                    'Publish COMPLETED:%s to finish the active arm task.'
                    % (
                        status,
                        command_id,
                        self.arm_command_id or 'none',
                        self.arm_command_id or 'none',
                    )
                )
            return
        if self.arm_state != self.ARM_WAITING_FOR_COMPLETION:
            return
        if status == 'STARTED':
            self.arm_started_acknowledged = True
            self.arm_start_ack_deadline_monotonic = 0.0
            self._publish_arm_status(
                'ARM_WAITING_FOR_COMPLETION command_id=%s awaiting=COMPLETED'
                % self.arm_command_id
            )
        elif status == 'COMPLETED':
            self.get_logger().warn(
                '[ARM_WAIT] received matching completion COMPLETED:%s; '
                'returning robot to the saved coverage path.'
                % self.arm_command_id
            )
            self._complete_arm_task()
        elif status == 'FAILED':
            self._fail_arm_operation('arm_reported_failure', restore=True)

    def _manual_complete_callback(self, request, response):
        del request
        if self.arm_state != self.ARM_WAITING_FOR_COMPLETION:
            response.success = False
            response.message = 'No arm command is waiting for completion'
            return response
        self._complete_arm_task()
        response.success = True
        response.message = 'Active arm command completed manually'
        return response

    def _mark_current_arm_object_handled(self):
        if self.arm_candidate_position is None:
            return
        if not self._object_was_handled(
            self.arm_candidate_position,
            self.arm_report,
        ):
            self.arm_handled_positions.append(self.arm_candidate_position)
        signature = self.arm_candidate_signature
        if signature is None and self.arm_report is not None:
            signature = self._candidate_object_signature(self.arm_report)
        if signature is not None:
            self.arm_handled_objects.append(copy.deepcopy(signature))
            self.get_logger().info(
                '[COVERAGE_ARM] remembered handled object frame=%s '
                'x=%.3f y=%.3f nearest_index=%d blocked=[%d,%d] '
                'radius=%.2f index_margin=%d'
                % (
                    signature['frame'],
                    signature['x'],
                    signature['y'],
                    signature['nearest_index'],
                    signature['blocked_start_index'],
                    signature['blocked_end_index'],
                    self.arm_handled_object_radius_m,
                    self.arm_handled_path_index_margin,
                )
            )

    def _ignore_costmap_validation_blocked_sample(
        self, x, y, cost, unknown, pose_index, path
    ):
        del pose_index
        if not self.arm_resume_ignore_handled_costmap:
            return False
        if unknown or cost >= 100:
            return False
        path_frame = getattr(getattr(path, 'header', None), 'frame_id', '')
        radius_sq = self.arm_resume_handled_costmap_radius_m ** 2
        for handled in getattr(self, 'arm_handled_objects', []):
            handled_frame = handled.get('frame', '')
            if handled_frame and path_frame and handled_frame != path_frame:
                continue
            dx = x - handled.get('x', float('inf'))
            dy = y - handled.get('y', float('inf'))
            if dx * dx + dy * dy <= radius_sq:
                return True
        for handled_frame, handled_x, handled_y in self.arm_handled_positions:
            if handled_frame and path_frame and handled_frame != path_frame:
                continue
            dx = x - handled_x
            dy = y - handled_y
            if dx * dx + dy * dy <= radius_sq:
                return True
        return False

    def _complete_arm_task(self):
        self.arm_completion_received = True
        self._mark_current_arm_object_handled()
        self._publish_arm_status(
            'COMPLETED command_id=%s returning_to_path' % self.arm_command_id
        )
        self._start_spin(-self.arm_turn_angle_rad, returning=True)

    def _fail_arm_operation(self, reason, restore):
        self.arm_completion_received = False
        self.arm_state = self.ARM_FAILED
        self._set_status(self.ARM_FAILED)
        if (
            self.arm_mark_failed_object_handled
            and self.arm_candidate_position is not None
            and not self._object_was_handled(
                self.arm_candidate_position,
                self.arm_report,
            )
        ):
            self._mark_current_arm_object_handled()
        self._publish_arm_status(
            'ARM_FAILED reason=%s command_id=%s'
            % (reason, self.arm_command_id or 'none')
        )
        if restore:
            self._start_spin(-self.arm_turn_angle_rad, returning=True)
            return
        self._finish_arm_failure_fallback()

    def _resume_after_arm(self):
        self.arm_state = self.ARM_RESUMING
        self._set_status(self.ARM_RESUMING)
        self._publish_zero_velocity()
        requested = self._request_arm_resume_execution()
        if requested:
            self.arm_resume_suppress_until_monotonic = (
                time.monotonic() + self.arm_resume_suppress_detection_sec
            )
            self._publish_arm_status('ARM_RESUMING saved_path=true')
            self._clear_arm_operation()
        else:
            self._publish_arm_status(
                'ARM_FAILED reason=saved_path_resume_failed detail=%s'
                % self.latest_path_error
            )
            if self.arm_replan_on_resume_failure:
                self._request_arm_replan_after_completion(
                    reason='saved_path_resume_failed'
                )
                return
            self._finish_arm_failure_fallback()

    def _request_arm_resume_execution(self):
        previous_ignore = self.arm_resume_ignore_handled_costmap
        self.arm_resume_ignore_handled_costmap = True
        try:
            return self._request_pause_resume_execution()
        finally:
            self.arm_resume_ignore_handled_costmap = previous_ignore

    def _with_arm_replan_costmap_tolerance(self, callback):
        previous_ignore = self.arm_resume_ignore_handled_costmap
        previous_samples = self.max_tolerated_blocked_costmap_samples
        previous_ratio = self.max_tolerated_blocked_costmap_ratio
        previous_cost = self.max_tolerated_blocked_cost
        self.arm_resume_ignore_handled_costmap = True
        self.max_tolerated_blocked_costmap_samples = max(
            previous_samples,
            self.arm_replan_max_tolerated_blocked_costmap_samples,
        )
        self.max_tolerated_blocked_costmap_ratio = max(
            previous_ratio,
            self.arm_replan_max_tolerated_blocked_costmap_ratio,
        )
        self.max_tolerated_blocked_cost = max(
            previous_cost,
            self.arm_replan_max_tolerated_blocked_cost,
        )
        try:
            return callback()
        finally:
            self.arm_resume_ignore_handled_costmap = previous_ignore
            self.max_tolerated_blocked_costmap_samples = previous_samples
            self.max_tolerated_blocked_costmap_ratio = previous_ratio
            self.max_tolerated_blocked_cost = previous_cost

    def _request_arm_replan_after_completion(self, reason=None):
        self.arm_state = self.ARM_RESUMING
        self._set_status(self.STATUS_WAITING_FOR_PATH)
        self._publish_zero_velocity()
        self.arm_resume_suppress_until_monotonic = (
            time.monotonic() + self.arm_resume_suppress_detection_sec
        )
        self.arm_replan_waiting_for_path = True
        self.cached_raw_path = None
        self.coverage_path_frozen = False
        self.active_path = None
        self.display_active_path = None
        self.smoothed_path = None
        if reason:
            self.latest_path_error = (
                'Waiting for regenerated coverage path after arm resume '
                'failure: %s' % reason
            )
        else:
            self.latest_path_error = (
                'Waiting for regenerated coverage path after completed arm task'
            )
        self.coverage_pause_requested = False
        self.coverage_control_cancel_reason = None
        self.cleanup_waiting_for_path = False
        self.cleanup_auto_start_pending = False
        self._clear_pause_resume_snapshot()
        self._publish_empty_paths_and_markers()
        if reason:
            self._publish_arm_status(
                'ARM_REPLAN waiting_for_coverage_path=true reason=%s '
                'command_id=%s' % (reason, self.arm_command_id or 'none')
            )
        else:
            self._publish_arm_status(
                'ARM_REPLAN waiting_for_coverage_path=true command_id=%s'
                % (self.arm_command_id or 'none')
            )
        self._request_planner_replan_for_arm()
        self._clear_arm_operation()
        return True

    def _request_planner_replan_for_arm(self):
        if self.arm_replan_planner_client is None:
            self._publish_arm_status(
                'ARM_REPLAN planner_request=false reason=client_unavailable'
            )
            return False
        if not self.arm_replan_planner_client.service_is_ready():
            self._publish_arm_status(
                'ARM_REPLAN planner_request=false reason=service_unavailable '
                'service=%s' % self.arm_replan_planner_service
            )
            return False

        future = self.arm_replan_planner_client.call_async(Trigger.Request())
        future.add_done_callback(self._planner_replan_response_callback)
        self._publish_arm_status(
            'ARM_REPLAN planner_request=true service=%s'
            % self.arm_replan_planner_service
        )
        return True

    def _planner_replan_response_callback(self, future):
        try:
            response = future.result()
        except Exception as exc:
            self._publish_arm_status(
                'ARM_REPLAN planner_response=false error=%s' % exc
            )
            return
        self._publish_arm_status(
            'ARM_REPLAN planner_response=%s message=%s'
            % (str(response.success).lower(), response.message)
        )

    def _finish_arm_failure_fallback(self):
        report = self.arm_report
        context = self.arm_failure_context
        if self.arm_resume_on_failure and not self.arm_fallback_to_dynamic_bypass:
            requested = self._request_arm_resume_execution()
            if requested:
                self._publish_arm_status('ARM_RESUMING after_failure=true')
                self._clear_arm_operation()
                return True
            if self.arm_replan_on_resume_failure:
                return self._request_arm_replan_after_completion(
                    reason='after_failure_saved_path_resume_failed'
                )
        self._clear_arm_operation(keep_snapshot=True)
        if self.arm_fallback_to_dynamic_bypass and report is not None:
            return self._fallback_to_dynamic_bypass(report, context)
        self._set_status(self.STATUS_PAUSED)
        return False

    def _fallback_to_dynamic_bypass(self, report, failure_context):
        if failure_context is None:
            return super()._start_dynamic_skip(report)
        return super()._start_dynamic_skip_after_failure(
            report, failure_context[0], failure_context[1]
        )

    def _clear_arm_operation(self, keep_snapshot=False):
        self.arm_spin_request_id += 1
        self.arm_spin_goal_handle = None
        self.arm_active = False
        self.arm_state = self.ARM_IDLE
        self.arm_report = None
        self.arm_failure_context = None
        self.arm_candidate_position = None
        self.arm_candidate_signature = None
        self.arm_command_id = None
        self.arm_completion_received = False
        self.arm_started_acknowledged = False
        self.arm_deadline_monotonic = 0.0
        self.arm_start_ack_deadline_monotonic = 0.0
        self.arm_pause_deadline_monotonic = 0.0
        if not keep_snapshot and self.goal_in_flight:
            self._clear_pause_resume_snapshot()

    def coverage_path_callback(self, msg):
        was_waiting_for_arm_replan = self.arm_replan_waiting_for_path
        had_cached_path = self.cached_raw_path is not None
        if was_waiting_for_arm_replan:
            self._with_arm_replan_costmap_tolerance(
                lambda: CoverageFollowPathExecutorNode.coverage_path_callback(
                    self, msg
                )
            )
        else:
            super().coverage_path_callback(msg)
        if not was_waiting_for_arm_replan or not self.arm_replan_waiting_for_path:
            return
        if had_cached_path or self.cached_raw_path is None:
            return
        if self.goal_in_flight or self.smoothing_in_flight:
            return

        self.arm_replan_waiting_for_path = False
        self._publish_arm_status('ARM_REPLAN received_path=true starting=true')
        if not self._with_arm_replan_costmap_tolerance(
            lambda: self._request_execution('arm_replan_after_completion')
        ):
            self._publish_arm_status(
                'ARM_FAILED reason=arm_replan_start_failed detail=%s'
                % self.latest_path_error
            )
            self._set_status(self.STATUS_PAUSED)

    def _publish_arm_status(self, text):
        message = String()
        message.data = text
        self.coverage_arm_status_pub.publish(message)
        if text.startswith('ARM_FAILED'):
            self.get_logger().error('[COVERAGE_ARM] %s' % text)
        else:
            self.get_logger().info('[COVERAGE_ARM] %s' % text)

    def reset_service_callback(self, request, response):
        if getattr(self, 'arm_active', False):
            response.success = False
            response.message = 'Robot arm operation is active; reset is unsafe'
            return response
        result = super().reset_service_callback(request, response)
        if result.success:
            self.arm_handled_positions.clear()
            self.arm_handled_objects.clear()
            self.front_tof_free_readings = 0
            self.front_lidar_object_readings = 0
        return result


def main(args=None):
    rclpy.init(args=args)
    node = CoverageArmFollowPathExecutorNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
