cmake_minimum_required(VERSION 3.8)
project(sweepi_api_bridge)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(sweepi_api_bridge)

install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

install(
  PROGRAMS
    sweepi_api_bridge/api_bridge_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
