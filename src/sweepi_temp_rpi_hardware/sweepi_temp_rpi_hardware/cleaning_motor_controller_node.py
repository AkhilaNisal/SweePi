#!/usr/bin/env python3
"""Control SweePi vacuum and brush motors from coverage and robot motion state."""

import json
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger

from sweepi_temp_rpi_hardware.cleaning_motor_gpio import CleaningMotorGpio
from sweepi_temp_rpi_hardware.pwm_ramp import ramp_step


ACTIVE_COVERAGE_STATES = {'EXECUTING', 'SKIPPING_DYNAMIC_OBSTACLE'}
ARM_ACTIVE_STATES = {
    'ARM_PAUSING',
    'ARM_TURNING_TO_OBJECT',
    'ARM_WAITING_FOR_COMPLETION',
    'ARM_TURNING_TO_PATH',
    'ARM_RESUMING',
}
KNOWN_OFF_STATES = {
    'IDLE',
    'WAITING_FOR_PATH',
    'VALIDATING',
    'SMOOTHING',
    'WAITING_FOR_NAV2',
    'PAUSED',
    'STOPPED',
    'CANCELED',
    'RETURNING_HOME',
    'RETURNED_HOME',
    'SUCCEEDED',
    'COMPLETED_WITH_SKIPS',
    'FAILED',
    'BLOCKED_DYNAMIC_OBJECT',
}


class CleaningMotorController(Node):
    def __init__(self