// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "sweepi_robot_manager_interfaces/srv/start_task.hpp"


#ifndef SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__TRAITS_HPP_
#define SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const StartTask_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: map_name
  {
    out << "map_name: ";
    rosidl_generator_traits::value_to_yaml(msg.map_name, out);
    out << ", ";
  }

  // member: mode
  {
    out << "mode: ";
    rosidl_generator_traits::value_to_yaml(msg.mode, out);
    out << ", ";
  }

  // member: auto_start
  {
    out << "auto_start: ";
    rosidl_generator_traits::value_to_yaml(msg.auto_start, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const StartTask_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: map_name
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "map_name: ";
    rosidl_generator_traits::value_to_yaml(msg.map_name, out);
    out << "\n";
  }

  // member: mode
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "mode: ";
    rosidl_generator_traits::value_to_yaml(msg.mode, out);
    out << "\n";
  }

  // member: auto_start
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "auto_start: ";
    rosidl_generator_traits::value_to_yaml(msg.auto_start, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const StartTask_Request & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const sweepi_robot_manager_interfaces::srv::StartTask_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  sweepi_robot_manager_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const sweepi_robot_manager_interfaces::srv::StartTask_Request & msg)
{
  return sweepi_robot_manager_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<sweepi_robot_manager_interfaces::srv::StartTask_Request>()
{
  return "sweepi_robot_manager_interfaces::srv::StartTask_Request";
}

template<>
inline const char * name<sweepi_robot_manager_interfaces::srv::StartTask_Request>()
{
  return "sweepi_robot_manager_interfaces/srv/StartTask_Request";
}

template<>
struct has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<sweepi_robot_manager_interfaces::srv::StartTask_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const StartTask_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: success
  {
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << ", ";
  }

  // member: message
  {
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const StartTask_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: success
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << "\n";
  }

  // member: message
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const StartTask_Response & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const sweepi_robot_manager_interfaces::srv::StartTask_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  sweepi_robot_manager_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const sweepi_robot_manager_interfaces::srv::StartTask_Response & msg)
{
  return sweepi_robot_manager_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<sweepi_robot_manager_interfaces::srv::StartTask_Response>()
{
  return "sweepi_robot_manager_interfaces::srv::StartTask_Response";
}

template<>
inline const char * name<sweepi_robot_manager_interfaces::srv::StartTask_Response>()
{
  return "sweepi_robot_manager_interfaces/srv/StartTask_Response";
}

template<>
struct has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<sweepi_robot_manager_interfaces::srv::StartTask_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__traits.hpp"

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

inline void to_flow_style_yaml(
  const StartTask_Event & msg,
  std::ostream & out)
{
  out << "{";
  // member: info
  {
    out << "info: ";
    to_flow_style_yaml(msg.info, out);
    out << ", ";
  }

  // member: request
  {
    if (msg.request.size() == 0) {
      out << "request: []";
    } else {
      out << "request: [";
      size_t pending_items = msg.request.size();
      for (auto item : msg.request) {
        to_flow_style_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: response
  {
    if (msg.response.size() == 0) {
      out << "response: []";
    } else {
      out << "response: [";
      size_t pending_items = msg.response.size();
      for (auto item : msg.response) {
        to_flow_style_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const StartTask_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: info
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "info:\n";
    to_block_style_yaml(msg.info, out, indentation + 2);
  }

  // member: request
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.request.size() == 0) {
      out << "request: []\n";
    } else {
      out << "request:\n";
      for (auto item : msg.request) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "-\n";
        to_block_style_yaml(item, out, indentation + 2);
      }
    }
  }

  // member: response
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.response.size() == 0) {
      out << "response: []\n";
    } else {
      out << "response:\n";
      for (auto item : msg.response) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "-\n";
        to_block_style_yaml(item, out, indentation + 2);
      }
    }
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const StartTask_Event & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const sweepi_robot_manager_interfaces::srv::StartTask_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  sweepi_robot_manager_interfaces::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use sweepi_robot_manager_interfaces::srv::to_yaml() instead")]]
inline std::string to_yaml(const sweepi_robot_manager_interfaces::srv::StartTask_Event & msg)
{
  return sweepi_robot_manager_interfaces::srv::to_yaml(msg);
}

template<>
inline const char * data_type<sweepi_robot_manager_interfaces::srv::StartTask_Event>()
{
  return "sweepi_robot_manager_interfaces::srv::StartTask_Event";
}

template<>
inline const char * name<sweepi_robot_manager_interfaces::srv::StartTask_Event>()
{
  return "sweepi_robot_manager_interfaces/srv/StartTask_Event";
}

template<>
struct has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask_Event>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Event>
  : std::integral_constant<bool, has_bounded_size<service_msgs::msg::ServiceEventInfo>::value && has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Request>::value && has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Response>::value> {};

template<>
struct is_message<sweepi_robot_manager_interfaces::srv::StartTask_Event>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<sweepi_robot_manager_interfaces::srv::StartTask>()
{
  return "sweepi_robot_manager_interfaces::srv::StartTask";
}

template<>
inline const char * name<sweepi_robot_manager_interfaces::srv::StartTask>()
{
  return "sweepi_robot_manager_interfaces/srv/StartTask";
}

template<>
struct has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask>
  : std::integral_constant<
    bool,
    has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask_Request>::value &&
    has_fixed_size<sweepi_robot_manager_interfaces::srv::StartTask_Response>::value
  >
{
};

template<>
struct has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask>
  : std::integral_constant<
    bool,
    has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Request>::value &&
    has_bounded_size<sweepi_robot_manager_interfaces::srv::StartTask_Response>::value
  >
{
};

template<>
struct is_service<sweepi_robot_manager_interfaces::srv::StartTask>
  : std::true_type
{
};

template<>
struct is_service_request<sweepi_robot_manager_interfaces::srv::StartTask_Request>
  : std::true_type
{
};

template<>
struct is_service_response<sweepi_robot_manager_interfaces::srv::StartTask_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__TRAITS_HPP_
