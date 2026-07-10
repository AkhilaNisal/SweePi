cmake_minimum_required(VERSION 3.8)
project(sweepi_bringup)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)



# Install directories
install(
  DIRECTORY
    launch
    config
    worlds
    rviz
  DESTINATION share/${PROJECT_NAME}/
)

install(
  PROGRAMS
    scripts/odom_tf_broadcaster.py
    scripts/front_tof_range_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
