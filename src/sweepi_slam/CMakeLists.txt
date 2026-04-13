cmake_minimum_required(VERSION 3.8)
project(sweepi_slam)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)


# Install config files
install(
  DIRECTORY
    config
    launch
    rviz
    maps
  DESTINATION share/${PROJECT_NAME}/
)

# Install scripts
install(
  PROGRAMS
    scripts/save_map.sh
    scripts/load_map.sh
  DESTINATION lib/${PROJECT_NAME}
)


ament_package()
