cmake_minimum_required(VERSION 3.8)
project(sweepi_coverage)

# Compiler flags (unnecessary for pure Python, but safe if mixed)
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ROS 2 build dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclpy REQUIRED)
find_package(tf2_ros REQUIRED)

# Install Python package
ament_python_install_package(sweepi_coverage)

# Install all launch files
install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install all config files
install(
  DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install Python node executables
install(
  PROGRAMS
    sweepi_coverage/coverage_tracker_node.py
    sweepi_coverage/coverage_planner_node.py
    sweepi_coverage/coverage_executor_node.py
    sweepi_coverage/coverage_manager_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
