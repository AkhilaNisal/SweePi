// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "sweepi_robot_manager_interfaces/srv/start_task.hpp"


#ifndef SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__BUILDER_HPP_
#define SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "sweepi_robot_manager_interfaces/srv/detail/start_task__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace builder
{

class Init_StartTask_Request_auto_start
{
public:
  explicit Init_StartTask_Request_auto_start(::sweepi_robot_manager_interfaces::srv::StartTask_Request & msg)
  : msg_(msg)
  {}
  ::sweepi_robot_manager_interfaces::srv::StartTask_Request auto_start(::sweepi_robot_manager_interfaces::srv::StartTask_Request::_auto_start_type arg)
  {
    msg_.auto_start = std::move(arg);
    return std::move(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Request msg_;
};

class Init_StartTask_Request_mode
{
public:
  explicit Init_StartTask_Request_mode(::sweepi_robot_manager_interfaces::srv::StartTask_Request & msg)
  : msg_(msg)
  {}
  Init_StartTask_Request_auto_start mode(::sweepi_robot_manager_interfaces::srv::StartTask_Request::_mode_type arg)
  {
    msg_.mode = std::move(arg);
    return Init_StartTask_Request_auto_start(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Request msg_;
};

class Init_StartTask_Request_map_name
{
public:
  Init_StartTask_Request_map_name()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_StartTask_Request_mode map_name(::sweepi_robot_manager_interfaces::srv::StartTask_Request::_map_name_type arg)
  {
    msg_.map_name = std::move(arg);
    return Init_StartTask_Request_mode(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::sweepi_robot_manager_interfaces::srv::StartTask_Request>()
{
  return sweepi_robot_manager_interfaces::srv::builder::Init_StartTask_Request_map_name();
}

}  // namespace sweepi_robot_manager_interfaces


namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace builder
{

class Init_StartTask_Response_message
{
public:
  explicit Init_StartTask_Response_message(::sweepi_robot_manager_interfaces::srv::StartTask_Response & msg)
  : msg_(msg)
  {}
  ::sweepi_robot_manager_interfaces::srv::StartTask_Response message(::sweepi_robot_manager_interfaces::srv::StartTask_Response::_message_type arg)
  {
    msg_.message = std::move(arg);
    return std::move(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Response msg_;
};

class Init_StartTask_Response_success
{
public:
  Init_StartTask_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_StartTask_Response_message success(::sweepi_robot_manager_interfaces::srv::StartTask_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_StartTask_Response_message(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::sweepi_robot_manager_interfaces::srv::StartTask_Response>()
{
  return sweepi_robot_manager_interfaces::srv::builder::Init_StartTask_Response_success();
}

}  // namespace sweepi_robot_manager_interfaces


namespace sweepi_robot_manager_interfaces
{

namespace srv
{

namespace builder
{

class Init_StartTask_Event_response
{
public:
  explicit Init_StartTask_Event_response(::sweepi_robot_manager_interfaces::srv::StartTask_Event & msg)
  : msg_(msg)
  {}
  ::sweepi_robot_manager_interfaces::srv::StartTask_Event response(::sweepi_robot_manager_interfaces::srv::StartTask_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Event msg_;
};

class Init_StartTask_Event_request
{
public:
  explicit Init_StartTask_Event_request(::sweepi_robot_manager_interfaces::srv::StartTask_Event & msg)
  : msg_(msg)
  {}
  Init_StartTask_Event_response request(::sweepi_robot_manager_interfaces::srv::StartTask_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_StartTask_Event_response(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Event msg_;
};

class Init_StartTask_Event_info
{
public:
  Init_StartTask_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_StartTask_Event_request info(::sweepi_robot_manager_interfaces::srv::StartTask_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_StartTask_Event_request(msg_);
  }

private:
  ::sweepi_robot_manager_interfaces::srv::StartTask_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::sweepi_robot_manager_interfaces::srv::StartTask_Event>()
{
  return sweepi_robot_manager_interfaces::srv::builder::Init_StartTask_Event_info();
}

}  // namespace sweepi_robot_manager_interfaces

#endif  // SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__BUILDER_HPP_
