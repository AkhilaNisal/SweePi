cmake_minimum_required(VERSION 3.8)
project(sweepi_coverage)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

ament_python_install_package(sweepi_coverage)

install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

install(
  PROGRAMS sweepi_coverage/nav_goal_publisher.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()