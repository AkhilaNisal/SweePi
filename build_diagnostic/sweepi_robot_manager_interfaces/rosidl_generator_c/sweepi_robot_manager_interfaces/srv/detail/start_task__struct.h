// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "sweepi_robot_manager_interfaces/srv/start_task.h"


#ifndef SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_H_
#define SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'map_name'
// Member 'mode'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/StartTask in the package sweepi_robot_manager_interfaces.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Request
{
  rosidl_runtime_c__String map_name;
  rosidl_runtime_c__String mode;
  bool auto_start;
} sweepi_robot_manager_interfaces__srv__StartTask_Request;

// Struct for a sequence of sweepi_robot_manager_interfaces__srv__StartTask_Request.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence
{
  sweepi_robot_manager_interfaces__srv__StartTask_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'message'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in srv/StartTask in the package sweepi_robot_manager_interfaces.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Response
{
  bool success;
  rosidl_runtime_c__String message;
} sweepi_robot_manager_interfaces__srv__StartTask_Response;

// Struct for a sequence of sweepi_robot_manager_interfaces__srv__StartTask_Response.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence
{
  sweepi_robot_manager_interfaces__srv__StartTask_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  sweepi_robot_manager_interfaces__srv__StartTask_Event__request__MAX_SIZE = 1
};
// response
enum
{
  sweepi_robot_manager_interfaces__srv__StartTask_Event__response__MAX_SIZE = 1
};

/// Struct defined in srv/StartTask in the package sweepi_robot_manager_interfaces.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Event
{
  service_msgs__msg__ServiceEventInfo info;
  sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence request;
  sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence response;
} sweepi_robot_manager_interfaces__srv__StartTask_Event;

// Struct for a sequence of sweepi_robot_manager_interfaces__srv__StartTask_Event.
typedef struct sweepi_robot_manager_interfaces__srv__StartTask_Event__Sequence
{
  sweepi_robot_manager_interfaces__srv__StartTask_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} sweepi_robot_manager_interfaces__srv__StartTask_Event__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_H_
