#!/usr/bin/env bash
set +e
source /opt/ros/jazzy/setup.bash 2>/dev/null
if [ -f /home/sweepi/SweePi/install/setup.bash ]; then
  source /home/sweepi/SweePi/install/setup.bash 2>/dev/null
elif [ -f /home/sweepi/SweePi/install_diagnostic/setup.bash ]; then
  source /home/sweepi/SweePi/install_diagnostic/setup.bash 2>/dev/null
fi
for i in 1 2 3; do
  timeout 2 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" >/dev/null 2>&1
  sleep 0.1
done
timeout 3 ros2 service call /sweepi_robot_manager/coverage/stop std_srvs/srv/Trigger '{}' >/dev/null 2>&1
timeout 3 ros2 service call /sweepi_robot_manager/coverage/reset std_srvs/srv/Trigger '{}' >/dev/null 2>&1
timeout 2 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" >/dev/null 2>&1
pkill -f 'ros2 topic pub.*cmd_vel' >/dev/null 2>&1
