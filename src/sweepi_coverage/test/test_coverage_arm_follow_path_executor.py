"""Unit tests for arm eligibility and the asynchronous arm state machine."""

import math
import time
from unittest.mock import Mock, patch

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid, Path
from sensor_msgs.msg import LaserScan, Range
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sweepi_coverage.coverage_arm_follow_path_executor_node import (
    CoverageArmFollowPathExecutorNode as ArmExecutor,
)
from sweepi_coverage.coverage_follow_path_executor_node import (
    CoverageFollowPathExecutorNode as BaseExecutor,
)


def make_node():
    node = ArmExecutor.__new__(ArmExecutor)
    node.use_robot_arm = True
    node.arm_active = False
    node.arm_state = node.ARM_IDLE
    node.global_frame = 'map'
    node.latest_front_tof = None
    node.latest_front_tof_monotonic = 0.0
    node.front_tof_free_readings = 0
    node.front_tof_topic = '/tof/front/range'
    node.tof_free_space_threshold_m = 0.50
    node.tof_message_timeout_sec = 0.5
    node.tof_required_free_readings = 5
    node.latest_front_lidar = None
    node.latest_front_lidar_monotonic = 0.0
    node.latest_front_lidar_min_range = float('inf')
    node.latest_front_lidar_min_angle = float('inf')
    node.front_lidar_object_readings = 0
    node.front_lidar_topic = '/scan'
    node.front_lidar_object_threshold_m = 0.50
    node.front_lidar_sector_half_angle_rad = 0.35
    node.front_lidar_object_max_angle_rad = 0.25
    node.front_lidar_message_timeout_sec = 0.5
    node.front_lidar_required_object_readings = 5
    node.arm_handled_object_radius_m = 0.50
    node.arm_resume_handled_costmap_radius_m = 0.75
    node.arm_handled_path_index_margin = 10
    node.arm_static_obstacle_reject_radius_m = 0.45
    node.arm_resume_suppress_detection_sec = 3.0
    node.arm_replan_after_completion = True
    node.arm_replan_on_resume_failure = True
    node.arm_replan_max_tolerated_blocked_costmap_samples = 75
    node.arm_replan_max_tolerated_blocked_costmap_ratio = 0.05
    node.arm_replan_max_tolerated_blocked_cost = 99
    node.arm_replan_planner_service = '/replan_coverage_planner'
    node.arm_replan_planner_client = Mock()
    node.arm_replan_planner_client.service_is_ready.return_value = True
    node.arm_replan_planner_client.call_async.return_value = Mock()
    node.arm_handled_positions = []
    node.arm_handled_objects = []
    node.arm_completion_received = False
    node.arm_replan_waiting_for_path = False
    node.arm_resume_ignore_handled_costmap = False
    node.arm_resume_suppress_until_monotonic = 0.0
    node.arm_spin_request_id = 0
    node.arm_spin_goal_handle = None
    node.arm_command_id = None
    node.arm_started_acknowledged = False
    node.arm_deadline_monotonic = 0.0
    node.arm_start_ack_deadline_monotonic = 0.0
    node.arm_pause_deadline_monotonic = 0.0
    node.arm_candidate_signature = None
    node.arm_inflated_detection_candidate = None
    node.static_map = None
    node.static_map_occupied_threshold = 50
    node.dynamic_required_consecutive_detections = 2
    node.dynamic_resume_ignore_index_margin = 5
    node.dynamic_detection_hysteresis_sec = 0.30
    node._publish_dynamic_skip_status = Mock()
    node.get_logger = Mock(return_value=Mock())
    return node


def make_report(x_value=1.0, y_value=2.0):
    poses = []
    for offset in (-0.05, 0.05):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x_value + offset
        pose.pose.position.y = y_value
        poses.append(pose)
    return {'path_frame': 'map', 'dynamic_only_blocked_poses': poses}


def make_indexed_report(x_value=1.0, y_value=2.0, nearest_index=10):
    report = make_report(x_value, y_value)
    report.update({
        'nearest_index': nearest_index,
        'blocked_start_index': nearest_index,
        'blocked_end_index': nearest_index,
    })
    return report


def make_path():
    path = Path()
    path.header.frame_id = 'map'
    for index in range(3):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = float(index)
        pose.pose.position.y = 2.0
        path.poses.append(pose)
    return path


def make_single_pose_path(x_value=0.15, y_value=0.15):
    path = Path()
    path.header.frame_id = 'map'
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.pose.position.x = x_value
    pose.pose.position.y = y_value
    path.poses.append(pose)
    return path


def make_costmap(cost_x=1, cost_y=1, cost=99):
    grid = OccupancyGrid()
    grid.header.frame_id = 'map'
    grid.info.width = 10
    grid.info.height = 10
    grid.info.resolution = 0.10
    grid.info.origin.position.x = 0.0
    grid.info.origin.position.y = 0.0
    grid.data = [0] * (grid.info.width * grid.info.height)
    grid.data[cost_y * grid.info.width + cost_x] = cost
    return grid


def make_static_map(occupied_x=12, occupied_y=20):
    grid = OccupancyGrid()
    grid.header.frame_id = 'map'
    grid.info.width = 40
    grid.info.height = 40
    grid.info.resolution = 0.10
    grid.info.origin.position.x = 0.0
    grid.info.origin.position.y = 0.0
    grid.data = [0] * (grid.info.width * grid.info.height)
    grid.data[occupied_y * grid.info.width + occupied_x] = 100
    return grid


def enable_costmap_validation_for_test(node, cost=99):
    node.nav_costmap = make_costmap(cost=cost)
    node.max_allowed_nav_cost = 50
    node.max_tolerated_blocked_costmap_samples = 0
    node.max_tolerated_blocked_costmap_ratio = 0.0
    node.max_tolerated_blocked_cost = 90
    node.treat_unknown_cost_as_blocked = True


def inflated_rejection_report():
    return {
        'blocked': False,
        'nearest_index': 1,
        'lookahead_end_index': 2,
        'path_frame': 'map',
        'reason': 'inflated_or_non_lethal_local_cost',
        'inflated_ignored_count': 1,
        'max_ignored_inflated_cost': 99,
        'consecutive_count': 0,
        'dynamic_only_blocked_poses': [],
    }


def inflated_rejection_report_at(nearest_index):
    report = inflated_rejection_report()
    report['nearest_index'] = nearest_index
    return report


def tof(value):
    msg = Range()
    msg.min_range = 0.02
    msg.max_range = 2.0
    msg.range = value
    return msg


def provide_tof(node, value):
    for _ in range(node.tof_required_free_readings):
        node._front_tof_callback(tof(value))


def scan(front_value=float('inf'), side_value=float('inf')):
    msg = LaserScan()
    msg.angle_min = -1.0
    msg.angle_max = 1.0
    msg.angle_increment = 0.5
    msg.range_min = 0.02
    msg.range_max = 12.0
    msg.ranges = [
        side_value,
        side_value,
        front_value,
        side_value,
        side_value,
    ]
    return msg


def off_center_scan(value=0.4):
    msg = LaserScan()
    msg.angle_min = -0.30
    msg.angle_max = 0.30
    msg.angle_increment = 0.30
    msg.range_min = 0.02
    msg.range_max = 12.0
    msg.ranges = [
        value,
        float('inf'),
        float('inf'),
    ]
    return msg


def provide_lidar(node, front_value=float('inf'), side_value=float('inf')):
    for _ in range(node.front_lidar_required_object_readings):
        node._front_lidar_callback(scan(front_value, side_value))


def provide_off_center_lidar(node, value=0.4):
    for _ in range(node.front_lidar_required_object_readings):
        node._front_lidar_callback(off_center_scan(value))


def test_lidar_obstacle_and_free_tof_triggers_arm():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    assert node._should_use_arm(make_report())


def test_off_center_lidar_wall_hit_does_not_trigger_arm():
    node = make_node()
    provide_tof(node, 0.8)
    provide_off_center_lidar(node, 0.4)
    assert not node._should_use_arm(make_report())
    assert node._front_lidar_status()['reason'] == 'front_lidar_object_not_centered'


def test_positive_infinity_tof_is_valid_out_of_range_free_space():
    node = make_node()
    provide_tof(node, float('inf'))
    provide_lidar(node, 0.4)
    assert node._should_use_arm(make_report())


def test_inflated_local_cost_and_free_tof_promotes_to_arm_candidate():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    path = make_path()
    report = inflated_rejection_report()

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        pending = node._detect_dynamic_blocked_interval(path)
        promoted = node._detect_dynamic_blocked_interval(path)

    assert not pending['blocked']
    assert pending['reason'] == 'arm_assist_inflated_candidate_pending'
    assert promoted['blocked']
    assert promoted['reason'] == 'arm_assist_inflated_local_cost_with_free_tof'
    assert promoted['dynamic_only_blocked_count'] == 1
    assert node._should_use_arm(promoted)


def test_inflated_local_cost_with_blocked_tof_stays_rejected():
    node = make_node()
    provide_tof(node, 0.1)
    provide_lidar(node, 0.4)
    path = make_path()
    report = inflated_rejection_report()

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        result = node._detect_dynamic_blocked_interval(path)

    assert not result['blocked']
    assert result['reason'] == 'inflated_or_non_lethal_local_cost'


def test_inflated_local_cost_with_no_front_lidar_object_stays_rejected():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, float('inf'), side_value=0.2)
    path = make_path()
    report = inflated_rejection_report()

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        result = node._detect_dynamic_blocked_interval(path)

    assert not result['blocked']
    assert result['reason'] == 'inflated_or_non_lethal_local_cost'


def test_inflated_local_cost_near_static_wall_does_not_promote():
    node = make_node()
    node.static_map = make_static_map(occupied_x=12, occupied_y=20)
    node._transform_pose_to_frame = Mock(side_effect=lambda pose, frame: pose)
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    path = make_path()
    report = inflated_rejection_report()

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        result = node._detect_dynamic_blocked_interval(path)

    assert not result['blocked']
    assert result['reason'] == 'inflated_or_non_lethal_local_cost'
    node._publish_dynamic_skip_status.assert_called()
    assert 'candidate_near_static_obstacle' in (
        node._publish_dynamic_skip_status.call_args.args[0]
    )


def test_already_handled_inflated_candidate_does_not_promote():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    node.arm_handled_positions.append(('map', 1.0, 2.0))
    node.dynamic_required_consecutive_detections = 1
    path = make_path()
    report = inflated_rejection_report()

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        result = node._detect_dynamic_blocked_interval(path)

    assert not result['blocked']
    assert result['reason'] == 'arm_assist_object_already_handled'


def test_blocked_tof_does_not_trigger_arm():
    node = make_node()
    provide_tof(node, 0.1)
    provide_lidar(node, 0.4)
    assert not node._should_use_arm(make_report())


def test_missing_stale_and_invalid_tof_do_not_trigger_arm():
    node = make_node()
    provide_lidar(node, 0.4)
    assert not node._should_use_arm(make_report())
    provide_tof(node, float('nan'))
    assert not node._should_use_arm(make_report())
    provide_tof(node, 0.8)
    node.latest_front_tof_monotonic -= 2.0
    assert not node._should_use_arm(make_report())


def test_missing_stale_and_clear_lidar_do_not_trigger_arm():
    node = make_node()
    provide_tof(node, 0.8)
    assert not node._should_use_arm(make_report())
    provide_lidar(node, 0.8)
    assert not node._should_use_arm(make_report())
    provide_lidar(node, 0.4)
    node.latest_front_lidar_monotonic -= 2.0
    assert not node._should_use_arm(make_report())


def test_already_handled_object_does_not_trigger_again():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    node.arm_handled_positions.append(('map', 1.1, 2.0))
    assert not node._should_use_arm(make_report())


def test_completed_arm_object_blocks_shifted_same_path_candidate():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    completed_report = make_indexed_report(
        x_value=1.0,
        y_value=2.0,
        nearest_index=20,
    )
    shifted_report = make_indexed_report(
        x_value=1.8,
        y_value=2.0,
        nearest_index=25,
    )
    node.arm_report = completed_report
    node.arm_candidate_position = node._candidate_object_position(completed_report)
    node.arm_candidate_signature = node._candidate_object_signature(completed_report)

    node._mark_current_arm_object_handled()

    assert not node._should_use_arm(shifted_report)
    assert node._handled_object_match_reason(
        node._candidate_object_position(shifted_report),
        shifted_report,
    ) == 'path_index_overlap'


def test_shifted_handled_inflated_candidate_does_not_promote():
    node = make_node()
    provide_tof(node, 0.8)
    provide_lidar(node, 0.4)
    node.arm_handled_objects.append({
        'frame': 'map',
        'x': 1.0,
        'y': 2.0,
        'nearest_index': 1,
        'blocked_start_index': 1,
        'blocked_end_index': 1,
    })
    node.dynamic_required_consecutive_detections = 1
    path = make_path()
    report = inflated_rejection_report_at(2)

    with patch.object(
        BaseExecutor,
        '_detect_dynamic_blocked_interval',
        return_value=report,
    ):
        result = node._detect_dynamic_blocked_interval(path)

    assert not result['blocked']
    assert result['reason'] == 'arm_assist_object_already_handled'


def test_arm_resume_allows_inflated_cost_near_handled_object():
    node = make_node()
    enable_costmap_validation_for_test(node, cost=99)
    node.arm_resume_ignore_handled_costmap = True
    node.arm_handled_objects.append({
        'frame': 'map',
        'x': 0.15,
        'y': 0.15,
        'nearest_index': 1,
        'blocked_start_index': 1,
        'blocked_end_index': 1,
    })

    report = node._validate_path_against_costmap(make_single_pose_path())

    assert report['costmap_valid']
    assert report['blocked_pose_count'] == 0
    assert report['ignored_blocked_pose_count'] == 1
    assert report['costmap_reason'].startswith('ignored 1 handled obstacle')


def test_arm_resume_does_not_ignore_unrelated_or_lethal_cost():
    node = make_node()
    enable_costmap_validation_for_test(node, cost=99)
    node.arm_resume_ignore_handled_costmap = True
    node.arm_handled_objects.append({
        'frame': 'map',
        'x': 0.90,
        'y': 0.90,
        'nearest_index': 1,
        'blocked_start_index': 1,
        'blocked_end_index': 1,
    })

    unrelated = node._validate_path_against_costmap(make_single_pose_path())
    assert not unrelated['costmap_valid']
    assert unrelated['blocked_pose_count'] == 1
    assert unrelated['ignored_blocked_pose_count'] == 0

    node = make_node()
    enable_costmap_validation_for_test(node, cost=100)
    node.arm_resume_ignore_handled_costmap = True
    node.arm_handled_objects.append({
        'frame': 'map',
        'x': 0.15,
        'y': 0.15,
        'nearest_index': 1,
        'blocked_start_index': 1,
        'blocked_end_index': 1,
    })

    lethal = node._validate_path_against_costmap(make_single_pose_path())
    assert not lethal['costmap_valid']
    assert lethal['blocked_pose_count'] == 1
    assert lethal['ignored_blocked_pose_count'] == 0


def test_small_number_of_nonlethal_inflated_cost_samples_can_validate():
    node = make_node()
    enable_costmap_validation_for_test(node, cost=99)
    node.max_tolerated_blocked_costmap_samples = 1
    node.max_tolerated_blocked_costmap_ratio = 1.0
    node.max_tolerated_blocked_cost = 99

    report = node._validate_path_against_costmap(make_single_pose_path())

    assert report['costmap_valid']
    assert report['tolerated_blocked_pose_count'] == 1
    assert report['blocked_pose_count'] == 1

    node = make_node()
    enable_costmap_validation_for_test(node, cost=100)
    node.max_tolerated_blocked_costmap_samples = 1
    node.max_tolerated_blocked_costmap_ratio = 1.0
    node.max_tolerated_blocked_cost = 99

    lethal = node._validate_path_against_costmap(make_single_pose_path())

    assert not lethal['costmap_valid']
    assert lethal['blocked_pose_count'] == 1


def test_completion_marks_object_and_starts_opposite_return_spin():
    node = make_node()
    node.arm_candidate_position = ('map', 1.0, 2.0)
    node.arm_command_id = 'abc'
    node.arm_turn_angle_rad = math.pi
    node.arm_report = make_indexed_report()
    node.arm_candidate_signature = node._candidate_object_signature(node.arm_report)
    node._publish_arm_status = Mock()
    node._start_spin = Mock()
    node._complete_arm_task()
    assert node.arm_handled_positions == [('map', 1.0, 2.0)]
    assert node.arm_handled_objects[0]['nearest_index'] == 10
    node._start_spin.assert_called_once_with(-math.pi, returning=True)


def test_start_spin_uses_jazzy_spin_goal_fields_without_crashing():
    node = make_node()
    node.arm_active = True
    node.arm_spin_request_id = 0
    node.arm_spin_timeout_sec = 15.0
    node.arm_spin_client = Mock()
    node.arm_spin_client.server_is_ready.return_value = True
    send_future = Mock()
    node.arm_spin_client.send_goal_async.return_value = send_future
    node._set_status = Mock()
    node._publish_zero_velocity = Mock()
    node._publish_arm_status = Mock()
    node._spin_failed = Mock()

    node._start_spin(math.pi, returning=False)

    node.arm_spin_client.send_goal_async.assert_called_once()
    goal = node.arm_spin_client.send_goal_async.call_args.args[0]
    assert goal.target_yaw == math.pi
    assert hasattr(goal, 'time_allowance')
    send_future.add_done_callback.assert_called_once()
    node._spin_failed.assert_not_called()


def test_timeout_fails_without_resetting_coverage_data():
    node = make_node()
    node.arm_active = True
    node.arm_state = node.ARM_WAITING_FOR_COMPLETION
    node.arm_started_acknowledged = True
    node.arm_deadline_monotonic = 0.0
    node.arm_start_ack_deadline_monotonic = 0.0
    node.cached_raw_path = object()
    node.static_map = object()
    node._fail_arm_operation = Mock()
    node._arm_timer_callback()
    node._fail_arm_operation.assert_called_once_with(
        'arm_completion_timeout', restore=True
    )
    assert node.cached_raw_path is not None
    assert node.static_map is not None


def test_missing_started_ack_keeps_waiting_for_completion():
    node = make_node()
    node.arm_active = True
    node.arm_state = node.ARM_WAITING_FOR_COMPLETION
    node.arm_command_id = 'abc'
    node.arm_started_acknowledged = False
    node.arm_start_ack_deadline_monotonic = time.monotonic() - 1.0
    node.arm_deadline_monotonic = time.monotonic() + 10.0
    node._publish_arm_status = Mock()
    node._fail_arm_operation = Mock()

    node._arm_timer_callback()

    node._publish_arm_status.assert_called_once()
    node._fail_arm_operation.assert_not_called()


def test_disabled_arm_preserves_base_dynamic_bypass():
    node = make_node()
    node.use_robot_arm = False
    report = make_report()
    with patch.object(BaseExecutor, '_start_dynamic_skip', return_value=True) as base:
        assert node._start_dynamic_skip(report)
    base.assert_called_once_with(report)


def test_mismatched_command_id_is_ignored():
    node = make_node()
    node.arm_state = node.ARM_WAITING_FOR_COMPLETION
    node.arm_command_id = 'expected'
    node.arm_started_acknowledged = False
    node._complete_arm_task = Mock()
    node._arm_status_callback(String(data='COMPLETED:different'))
    node._complete_arm_task.assert_not_called()
    node.get_logger.return_value.warn.assert_called_once()


def test_manual_completion_only_works_while_waiting():
    node = make_node()
    node._complete_arm_task = Mock()
    response = Trigger.Response()
    node._manual_complete_callback(Trigger.Request(), response)
    assert not response.success
    node.arm_state = node.ARM_WAITING_FOR_COMPLETION
    response = Trigger.Response()
    node._manual_complete_callback(Trigger.Request(), response)
    assert response.success
    node._complete_arm_task.assert_called_once()


def test_arm_sequence_uses_saved_path_resume_and_never_regenerates_maps():
    node = make_node()
    node.arm_active = True
    node.arm_state = node.ARM_TURNING_TO_PATH
    node._set_status = Mock()
    node._publish_zero_velocity = Mock()
    node._publish_arm_status = Mock()
    node._request_pause_resume_execution = Mock(return_value=True)
    node._clear_arm_operation = Mock()
    node._resume_after_arm()
    node._request_pause_resume_execution.assert_called_once_with()
    assert not node.arm_resume_ignore_handled_costmap
    assert not hasattr(node, '_request_execution_mock')
    node._clear_arm_operation.assert_called_once_with()


def test_saved_path_resume_failure_requests_regenerated_coverage_path():
    node = make_node()
    node.arm_active = True
    node.arm_state = node.ARM_TURNING_TO_PATH
    node.arm_command_id = 'abc'
    node.latest_path_error = 'path has blocked costmap samples'
    node._set_status = Mock()
    node._publish_zero_velocity = Mock()
    node._publish_arm_status = Mock()
    node._request_arm_resume_execution = Mock(return_value=False)
    node._request_arm_replan_after_completion = Mock(return_value=True)
    node._finish_arm_failure_fallback = Mock()

    node._resume_after_arm()

    node._request_arm_replan_after_completion.assert_called_once_with(
        reason='saved_path_resume_failed'
    )
    node._finish_arm_failure_fallback.assert_not_called()


def test_completed_arm_task_waits_for_regenerated_coverage_path():
    node = make_node()
    node.arm_active = True
    node.arm_state = node.ARM_TURNING_TO_PATH
    node.arm_command_id = 'abc'
    node.arm_completion_received = True
    node.cached_raw_path = make_path()
    node.coverage_path_frozen = True
    node.active_path = make_path()
    node.display_active_path = make_path()
    node.smoothed_path = make_path()
    node.goal_in_flight = False
    node.cleanup_waiting_for_path = False
    node.cleanup_auto_start_pending = False
    node._set_status = Mock()
    node._publish_zero_velocity = Mock()
    node._clear_pause_resume_snapshot = Mock()
    node._publish_empty_paths_and_markers = Mock()
    node._publish_arm_status = Mock()

    node._request_arm_replan_after_completion()

    assert node.arm_replan_waiting_for_path
    assert node.cached_raw_path is None
    assert not node.coverage_path_frozen
    assert node.active_path is None
    node._publish_arm_status.assert_any_call(
        'ARM_REPLAN waiting_for_coverage_path=true command_id=abc'
    )
    node.arm_replan_planner_client.call_async.assert_called_once()


def test_regenerated_coverage_path_auto_starts_after_arm_completion():
    node = make_node()
    node.arm_replan_waiting_for_path = True
    node.cached_raw_path = None
    node.goal_in_flight = False
    node.smoothing_in_flight = False
    node.auto_start = False
    node.cleanup_auto_start_pending = False
    node.coverage_path_frozen = False
    node.max_tolerated_blocked_costmap_samples = 25
    node.max_tolerated_blocked_costmap_ratio = 0.01
    node.max_tolerated_blocked_cost = 90
    node.raw_path_pub = Mock()

    def validate_during_arm_replan(_path):
        assert node.arm_resume_ignore_handled_costmap
        assert node.max_tolerated_blocked_costmap_samples == 75
        assert node.max_tolerated_blocked_costmap_ratio == 0.05
        assert node.max_tolerated_blocked_cost == 99
        return {'valid': True}

    node._run_preflight_validation = Mock(side_effect=validate_during_arm_replan)
    node._stamp_path = Mock()
    node._set_status = Mock()
    node._log_path_summary = Mock()
    node._publish_arm_status = Mock()

    def request_execution_during_arm_replan(reason):
        assert reason == 'arm_replan_after_completion'
        assert node.arm_resume_ignore_handled_costmap
        assert node.max_tolerated_blocked_costmap_samples == 75
        assert node.max_tolerated_blocked_costmap_ratio == 0.05
        assert node.max_tolerated_blocked_cost == 99
        return True

    node._request_execution = Mock(side_effect=request_execution_during_arm_replan)

    node.coverage_path_callback(make_path())

    assert not node.arm_replan_waiting_for_path
    assert node.cached_raw_path is not None
    assert not node.arm_resume_ignore_handled_costmap
    assert node.max_tolerated_blocked_costmap_samples == 25
    assert node.max_tolerated_blocked_costmap_ratio == 0.01
    assert node.max_tolerated_blocked_cost == 90
    node._publish_arm_status.assert_called_once_with(
        'ARM_REPLAN received_path=true starting=true'
    )
    node._request_execution.assert_called_once_with('arm_replan_after_completion')
