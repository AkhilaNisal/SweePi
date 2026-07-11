// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "sweepi_robot_manager_interfaces/srv/start_task.hpp"


#ifndef SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_HPP_
#define SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Request __attribute__((deprecated))
#else
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Request __declspec(deprecated)
#endif

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct StartTask_Request_
{
  using Type = StartTask_Request_<ContainerAllocator>;

  explicit StartTask_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->map_name = "";
      this->mode = "";
      this->auto_start = false;
    }
  }

  explicit StartTask_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : map_name(_alloc),
    mode(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->map_name = "";
      this->mode = "";
      this->auto_start = false;
    }
  }

  // field types and members
  using _map_name_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _map_name_type map_name;
  using _mode_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _mode_type mode;
  using _auto_start_type =
    bool;
  _auto_start_type auto_start;

  // setters for named parameter idiom
  Type & set__map_name(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->map_name = _arg;
    return *this;
  }
  Type & set__mode(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->mode = _arg;
    return *this;
  }
  Type & set__auto_start(
    const bool & _arg)
  {
    this->auto_start = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Request
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Request
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const StartTask_Request_ & other) const
  {
    if (this->map_name != other.map_name) {
      return false;
    }
    if (this->mode != other.mode) {
      return false;
    }
    if (this->auto_start != other.auto_start) {
      return false;
    }
    return true;
  }
  bool operator!=(const StartTask_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct StartTask_Request_

// alias to use template instance with default allocator
using StartTask_Request =
  sweepi_robot_manager_interfaces::srv::StartTask_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces


#ifndef _WIN32
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Response __attribute__((deprecated))
#else
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Response __declspec(deprecated)
#endif

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct StartTask_Response_
{
  using Type = StartTask_Response_<ContainerAllocator>;

  explicit StartTask_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
    }
  }

  explicit StartTask_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : message(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->message = "";
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;
  using _message_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _message_type message;

  // setters for named parameter idiom
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }
  Type & set__message(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->message = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Response
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Response
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const StartTask_Response_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    if (this->message != other.message) {
      return false;
    }
    return true;
  }
  bool operator!=(const StartTask_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct StartTask_Response_

// alias to use template instance with default allocator
using StartTask_Response =
  sweepi_robot_manager_interfaces::srv::StartTask_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces


// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Event __attribute__((deprecated))
#else
# define DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Event __declspec(deprecated)
#endif

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct StartTask_Event_
{
  using Type = StartTask_Event_<ContainerAllocator>;

  explicit StartTask_Event_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : info(_init)
  {
    (void)_init;
  }

  explicit StartTask_Event_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : info(_alloc, _init)
  {
    (void)_init;
  }

  // field types and members
  using _info_type =
    service_msgs::msg::ServiceEventInfo_<ContainerAllocator>;
  _info_type info;
  using _request_type =
    rosidl_runtime_cpp::BoundedVector<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>>;
  _request_type request;
  using _response_type =
    rosidl_runtime_cpp::BoundedVector<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>>;
  _response_type response;

  // setters for named parameter idiom
  Type & set__info(
    const service_msgs::msg::ServiceEventInfo_<ContainerAllocator> & _arg)
  {
    this->info = _arg;
    return *this;
  }
  Type & set__request(
    const rosidl_runtime_cpp::BoundedVector<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<sweepi_robot_manager_interfaces::srv::StartTask_Request_<ContainerAllocator>>> & _arg)
  {
    this->request = _arg;
    return *this;
  }
  Type & set__response(
    const rosidl_runtime_cpp::BoundedVector<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<sweepi_robot_manager_interfaces::srv::StartTask_Response_<ContainerAllocator>>> & _arg)
  {
    this->response = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> *;
  using ConstRawPtr =
    const sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Event
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__sweepi_robot_manager_interfaces__srv__StartTask_Event
    std::shared_ptr<sweepi_robot_manager_interfaces::srv::StartTask_Event_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const StartTask_Event_ & other) const
  {
    if (this->info != other.info) {
      return false;
    }
    if (this->request != other.request) {
      return false;
    }
    if (this->response != other.response) {
      return false;
    }
    return true;
  }
  bool operator!=(const StartTask_Event_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct StartTask_Event_

// alias to use template instance with default allocator
using StartTask_Event =
  sweepi_robot_manager_interfaces::srv::StartTask_Event_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

namespace sweepi_robot_manager_interfaces
{

namespace srv
{

struct StartTask
{
  using Request = sweepi_robot_manager_interfaces::srv::StartTask_Request;
  using Response = sweepi_robot_manager_interfaces::srv::StartTask_Response;
  using Event = sweepi_robot_manager_interfaces::srv::StartTask_Event;
};

}  // namespace srv

}  // namespace sweepi_robot_manager_interfaces

#endif  // SWEEPI_ROBOT_MANAGER_INTERFACES__SRV__DETAIL__START_TASK__STRUCT_HPP_
