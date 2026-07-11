#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};




// Corresponds to sweepi_robot_manager_interfaces__srv__StartTask_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct StartTask_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub map_name: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub mode: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub auto_start: bool,

}



impl Default for StartTask_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::StartTask_Request::default())
  }
}

impl rosidl_runtime_rs::Message for StartTask_Request {
  type RmwMsg = super::srv::rmw::StartTask_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        map_name: msg.map_name.as_str().into(),
        mode: msg.mode.as_str().into(),
        auto_start: msg.auto_start,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        map_name: msg.map_name.as_str().into(),
        mode: msg.mode.as_str().into(),
      auto_start: msg.auto_start,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      map_name: msg.map_name.to_string(),
      mode: msg.mode.to_string(),
      auto_start: msg.auto_start,
    }
  }
}


// Corresponds to sweepi_robot_manager_interfaces__srv__StartTask_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct StartTask_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: std::string::String,

}



impl Default for StartTask_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::StartTask_Response::default())
  }
}

impl rosidl_runtime_rs::Message for StartTask_Response {
  type RmwMsg = super::srv::rmw::StartTask_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        success: msg.success,
        message: msg.message.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      success: msg.success,
        message: msg.message.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      success: msg.success,
      message: msg.message.to_string(),
    }
  }
}






#[link(name = "sweepi_robot_manager_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask() -> *const std::ffi::c_void;
}

// Corresponds to sweepi_robot_manager_interfaces__srv__StartTask
#[allow(missing_docs, non_camel_case_types)]
pub struct StartTask;

impl rosidl_runtime_rs::Service for StartTask {
    type Request = StartTask_Request;
    type Response = StartTask_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask() }
    }
}


