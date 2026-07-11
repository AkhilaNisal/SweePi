// generated from rosidl_typesupport_c/resource/idl__type_support.cpp.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

#include "cstddef"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__type_support.h"
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
#include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/message_type_support_dispatch.h"
#include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_c/visibility_control.h"
#include "rosidl_typesupport_interface/macros.h"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _StartTask_Request_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartTask_Request_type_support_ids_t;

static const _StartTask_Request_type_support_ids_t _StartTask_Request_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _StartTask_Request_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartTask_Request_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartTask_Request_type_support_symbol_names_t _StartTask_Request_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)),
  }
};

typedef struct _StartTask_Request_type_support_data_t
{
  void * data[2];
} _StartTask_Request_type_support_data_t;

static _StartTask_Request_type_support_data_t _StartTask_Request_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartTask_Request_message_typesupport_map = {
  2,
  "sweepi_robot_manager_interfaces",
  &_StartTask_Request_message_typesupport_ids.typesupport_identifier[0],
  &_StartTask_Request_message_typesupport_symbol_names.symbol_name[0],
  &_StartTask_Request_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartTask_Request_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartTask_Request_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)() {
  return &::sweepi_robot_manager_interfaces::srv::rosidl_typesupport_c::StartTask_Request_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__type_support.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _StartTask_Response_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartTask_Response_type_support_ids_t;

static const _StartTask_Response_type_support_ids_t _StartTask_Response_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _StartTask_Response_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartTask_Response_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartTask_Response_type_support_symbol_names_t _StartTask_Response_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)),
  }
};

typedef struct _StartTask_Response_type_support_data_t
{
  void * data[2];
} _StartTask_Response_type_support_data_t;

static _StartTask_Response_type_support_data_t _StartTask_Response_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartTask_Response_message_typesupport_map = {
  2,
  "sweepi_robot_manager_interfaces",
  &_StartTask_Response_message_typesupport_ids.typesupport_identifier[0],
  &_StartTask_Response_message_typesupport_symbol_names.symbol_name[0],
  &_StartTask_Response_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartTask_Response_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartTask_Response_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)() {
  return &::sweepi_robot_manager_interfaces::srv::rosidl_typesupport_c::StartTask_Response_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__type_support.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _StartTask_Event_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartTask_Event_type_support_ids_t;

static const _StartTask_Event_type_support_ids_t _StartTask_Event_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _StartTask_Event_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartTask_Event_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartTask_Event_type_support_symbol_names_t _StartTask_Event_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)),
  }
};

typedef struct _StartTask_Event_type_support_data_t
{
  void * data[2];
} _StartTask_Event_type_support_data_t;

static _StartTask_Event_type_support_data_t _StartTask_Event_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartTask_Event_message_typesupport_map = {
  2,
  "sweepi_robot_manager_interfaces",
  &_StartTask_Event_message_typesupport_ids.typesupport_identifier[0],
  &_StartTask_Event_message_typesupport_symbol_names.symbol_name[0],
  &_StartTask_Event_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartTask_Event_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartTask_Event_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)() {
  return &::sweepi_robot_manager_interfaces::srv::rosidl_typesupport_c::StartTask_Event_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__type_support.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/service_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"
#include "service_msgs/msg/service_event_info.h"
#include "builtin_interfaces/msg/time.h"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace rosidl_typesupport_c
{
typedef struct _StartTask_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartTask_type_support_ids_t;

static const _StartTask_type_support_ids_t _StartTask_service_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _StartTask_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartTask_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartTask_type_support_symbol_names_t _StartTask_service_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, sweepi_robot_manager_interfaces, srv, StartTask)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask)),
  }
};

typedef struct _StartTask_type_support_data_t
{
  void * data[2];
} _StartTask_type_support_data_t;

static _StartTask_type_support_data_t _StartTask_service_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartTask_service_typesupport_map = {
  2,
  "sweepi_robot_manager_interfaces",
  &_StartTask_service_typesupport_ids.typesupport_identifier[0],
  &_StartTask_service_typesupport_symbol_names.symbol_name[0],
  &_StartTask_service_typesupport_data.data[0],
};

static const rosidl_service_type_support_t StartTask_service_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartTask_service_typesupport_map),
  rosidl_typesupport_c__get_service_typesupport_handle_function,
  &StartTask_Request_message_type_support_handle,
  &StartTask_Response_message_type_support_handle,
  &StartTask_Event_message_type_support_handle,
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_CREATE_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    sweepi_robot_manager_interfaces,
    srv,
    StartTask
  ),
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_DESTROY_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    sweepi_robot_manager_interfaces,
    srv,
    StartTask
  ),
  &sweepi_robot_manager_interfaces__srv__StartTask__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_c, sweepi_robot_manager_interfaces, srv, StartTask)() {
  return &::sweepi_robot_manager_interfaces::srv::rosidl_typesupport_c::StartTask_service_type_support_handle;
}

#ifdef __cplusplus
}
#endif
