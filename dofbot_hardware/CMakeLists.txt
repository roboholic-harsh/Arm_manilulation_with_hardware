cmake_minimum_required(VERSION 3.8)
project(dofbot_hardware)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 1. Find ROS 2 Packages
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)

# 2. Compile the Hardware Interface Library
add_library(dofbot_hardware SHARED
  src/dofbot_system.cpp
)

# 3. Include headers and link dependencies
target_include_directories(dofbot_hardware PRIVATE include)
ament_target_dependencies(dofbot_hardware
  rclcpp
  hardware_interface
  pluginlib
  rclcpp_lifecycle
)
target_link_libraries(dofbot_hardware serial) # This links libserial

# 4. Export the Plugin XML so ROS 2 Controller Manager can find it
pluginlib_export_plugin_description_file(hardware_interface dofbot_hardware.xml)

# 5. Install Rules (Where to put the compiled files)
install(TARGETS dofbot_hardware
  DESTINATION lib
)
install(DIRECTORY include/
  DESTINATION include
)
install(FILES dofbot_hardware.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_package()