// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__rosidl_typesupport_introspection_c.h"
#include "sweepi_robot_manager_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
#include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"


// Include directives for member types
// Member `map_name`
// Member `mode`
#include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  sweepi_robot_manager_interfaces__srv__StartTask_Request__init(message_memory);
}

void sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_fini_function(void * message_memory)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Request__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_member_array[3] = {
  {
    "map_name",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Request, map_name),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "mode",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Request, mode),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "auto_start",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Request, auto_start),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_members = {
  "sweepi_robot_manager_interfaces__srv",  // message namespace
  "StartTask_Request",  // message name
  3,  // number of fields
  sizeof(sweepi_robot_manager_interfaces__srv__StartTask_Request),
  false,  // has_any_key_member_
  sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_member_array,  // message members
  sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_init_function,  // function to initialize message memory (memory has to be allocated)
  sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle = {
  0,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_members,
  get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_sweepi_robot_manager_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)() {
  if (!sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle.typesupport_identifier) {
    sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__rosidl_typesupport_introspection_c.h"
// already included above
// #include "sweepi_robot_manager_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"


// Include directives for member types
// Member `message`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  sweepi_robot_manager_interfaces__srv__StartTask_Response__init(message_memory);
}

void sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_fini_function(void * message_memory)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Response__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_member_array[2] = {
  {
    "success",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Response, success),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "message",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Response, message),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_members = {
  "sweepi_robot_manager_interfaces__srv",  // message namespace
  "StartTask_Response",  // message name
  2,  // number of fields
  sizeof(sweepi_robot_manager_interfaces__srv__StartTask_Response),
  false,  // has_any_key_member_
  sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_member_array,  // message members
  sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_init_function,  // function to initialize message memory (memory has to be allocated)
  sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle = {
  0,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_members,
  get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_sweepi_robot_manager_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)() {
  if (!sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle.typesupport_identifier) {
    sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

// already included above
// #include <stddef.h>
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__rosidl_typesupport_introspection_c.h"
// already included above
// #include "sweepi_robot_manager_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "rosidl_typesupport_introspection_c/field_types.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
// already included above
// #include "rosidl_typesupport_introspection_c/message_introspection.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.h"


// Include directives for member types
// Member `info`
#include "service_msgs/msg/service_event_info.h"
// Member `info`
#include "service_msgs/msg/detail/service_event_info__rosidl_typesupport_introspection_c.h"
// Member `request`
// Member `response`
#include "sweepi_robot_manager_interfaces/srv/start_task.h"
// Member `request`
// Member `response`
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  sweepi_robot_manager_interfaces__srv__StartTask_Event__init(message_memory);
}

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_fini_function(void * message_memory)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Event__fini(message_memory);
}

size_t sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__size_function__StartTask_Event__request(
  const void * untyped_member)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence * member =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence *)(untyped_member);
  return member->size;
}

const void * sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__request(
  const void * untyped_member, size_t index)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence * member =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence *)(untyped_member);
  return &member->data[index];
}

void * sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__request(
  void * untyped_member, size_t index)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence * member =
    (sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence *)(untyped_member);
  return &member->data[index];
}

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__fetch_function__StartTask_Event__request(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Request * item =
    ((const sweepi_robot_manager_interfaces__srv__StartTask_Request *)
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__request(untyped_member, index));
  sweepi_robot_manager_interfaces__srv__StartTask_Request * value =
    (sweepi_robot_manager_interfaces__srv__StartTask_Request *)(untyped_value);
  *value = *item;
}

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__assign_function__StartTask_Event__request(
  void * untyped_member, size_t index, const void * untyped_value)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Request * item =
    ((sweepi_robot_manager_interfaces__srv__StartTask_Request *)
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__request(untyped_member, index));
  const sweepi_robot_manager_interfaces__srv__StartTask_Request * value =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Request *)(untyped_value);
  *item = *value;
}

bool sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__resize_function__StartTask_Event__request(
  void * untyped_member, size_t size)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence * member =
    (sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence *)(untyped_member);
  sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__fini(member);
  return sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__init(member, size);
}

size_t sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__size_function__StartTask_Event__response(
  const void * untyped_member)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence * member =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence *)(untyped_member);
  return member->size;
}

const void * sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__response(
  const void * untyped_member, size_t index)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence * member =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence *)(untyped_member);
  return &member->data[index];
}

void * sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__response(
  void * untyped_member, size_t index)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence * member =
    (sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence *)(untyped_member);
  return &member->data[index];
}

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__fetch_function__StartTask_Event__response(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const sweepi_robot_manager_interfaces__srv__StartTask_Response * item =
    ((const sweepi_robot_manager_interfaces__srv__StartTask_Response *)
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__response(untyped_member, index));
  sweepi_robot_manager_interfaces__srv__StartTask_Response * value =
    (sweepi_robot_manager_interfaces__srv__StartTask_Response *)(untyped_value);
  *value = *item;
}

void sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__assign_function__StartTask_Event__response(
  void * untyped_member, size_t index, const void * untyped_value)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Response * item =
    ((sweepi_robot_manager_interfaces__srv__StartTask_Response *)
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__response(untyped_member, index));
  const sweepi_robot_manager_interfaces__srv__StartTask_Response * value =
    (const sweepi_robot_manager_interfaces__srv__StartTask_Response *)(untyped_value);
  *item = *value;
}

bool sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__resize_function__StartTask_Event__response(
  void * untyped_member, size_t size)
{
  sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence * member =
    (sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence *)(untyped_member);
  sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__fini(member);
  return sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_member_array[3] = {
  {
    "info",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Event, info),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "request",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    true,  // is array
    1,  // array size
    true,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Event, request),  // bytes offset in struct
    NULL,  // default value
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__size_function__StartTask_Event__request,  // size() function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__request,  // get_const(index) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__request,  // get(index) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__fetch_function__StartTask_Event__request,  // fetch(index, &value) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__assign_function__StartTask_Event__request,  // assign(index, value) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__resize_function__StartTask_Event__request  // resize(index) function pointer
  },
  {
    "response",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    true,  // is array
    1,  // array size
    true,  // is upper bound
    offsetof(sweepi_robot_manager_interfaces__srv__StartTask_Event, response),  // bytes offset in struct
    NULL,  // default value
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__size_function__StartTask_Event__response,  // size() function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_const_function__StartTask_Event__response,  // get_const(index) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__get_function__StartTask_Event__response,  // get(index) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__fetch_function__StartTask_Event__response,  // fetch(index, &value) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__assign_function__StartTask_Event__response,  // assign(index, value) function pointer
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__resize_function__StartTask_Event__response  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_members = {
  "sweepi_robot_manager_interfaces__srv",  // message namespace
  "StartTask_Event",  // message name
  3,  // number of fields
  sizeof(sweepi_robot_manager_interfaces__srv__StartTask_Event),
  false,  // has_any_key_member_
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_member_array,  // message members
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_init_function,  // function to initialize message memory (memory has to be allocated)
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_type_support_handle = {
  0,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_members,
  get_message_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_hash,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_sweepi_robot_manager_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)() {
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, service_msgs, msg, ServiceEventInfo)();
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)();
  sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_member_array[2].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)();
  if (!sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_type_support_handle.typesupport_identifier) {
    sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif

#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "sweepi_robot_manager_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
// already included above
// #include "sweepi_robot_manager_interfaces/srv/detail/start_task__rosidl_typesupport_introspection_c.h"
// already included above
// #include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/service_introspection.h"

// this is intentionally not const to allow initialization later to prevent an initialization race
static rosidl_typesupport_introspection_c__ServiceMembers sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_members = {
  "sweepi_robot_manager_interfaces__srv",  // service namespace
  "StartTask",  // service name
  // the following fields are initialized below on first access
  NULL,  // request message
  // sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle,
  NULL,  // response message
  // sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle
  NULL  // event_message
  // sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle
};


static rosidl_service_type_support_t sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_type_support_handle = {
  0,
  &sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_members,
  get_service_typesupport_handle_function,
  &sweepi_robot_manager_interfaces__srv__StartTask_Request__rosidl_typesupport_introspection_c__StartTask_Request_message_type_support_handle,
  &sweepi_robot_manager_interfaces__srv__StartTask_Response__rosidl_typesupport_introspection_c__StartTask_Response_message_type_support_handle,
  &sweepi_robot_manager_interfaces__srv__StartTask_Event__rosidl_typesupport_introspection_c__StartTask_Event_message_type_support_handle,
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

// Forward declaration of message type support functions for service members
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)(void);

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)(void);

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)(void);

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_sweepi_robot_manager_interfaces
const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask)(void) {
  if (!sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_type_support_handle.typesupport_identifier) {
    sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  rosidl_typesupport_introspection_c__ServiceMembers * service_members =
    (rosidl_typesupport_introspection_c__ServiceMembers *)sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_type_support_handle.data;

  if (!service_members->request_members_) {
    service_members->request_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Request)()->data;
  }
  if (!service_members->response_members_) {
    service_members->response_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Response)()->data;
  }
  if (!service_members->event_members_) {
    service_members->event_members_ =
      (const rosidl_typesupport_introspection_c__MessageMembers *)
      ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, sweepi_robot_manager_interfaces, srv, StartTask_Event)()->data;
  }

  return &sweepi_robot_manager_interfaces__srv__detail__start_task__rosidl_typesupport_introspection_c__StartTask_service_type_support_handle;
}
