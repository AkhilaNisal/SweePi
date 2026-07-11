#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



#[link(name = "sweepi_robot_manager_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask_Request() -> *const std::ffi::c_void;
}

#[link(name = "sweepi_robot_manager_interfaces__rosidl_generator_c")]
extern "C" {
    fn sweepi_robot_manager_interfaces__srv__StartTask_Request__init(msg: *mut StartTask_Request) -> bool;
    fn sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<StartTask_Request>, size: usize) -> bool;
    fn sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<StartTask_Request>);
    fn sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<StartTask_Request>, out_seq: *mut rosidl_runtime_rs::Sequence<StartTask_Request>) -> bool;
}

// Corresponds to sweepi_robot_manager_interfaces__srv__StartTask_Request
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct StartTask_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub map_name: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub mode: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub auto_start: bool,

}



impl Default for StartTask_Request {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !sweepi_robot_manager_interfaces__srv__StartTask_Request__init(&mut msg as *mut _) {
        panic!("Call to sweepi_robot_manager_interfaces__srv__StartTask_Request__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for StartTask_Request {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Request__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for StartTask_Request {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for StartTask_Request where Self: Sized {
  const TYPE_NAME: &'static str = "sweepi_robot_manager_interfaces/srv/StartTask_Request";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask_Request() }
  }
}


#[link(name = "sweepi_robot_manager_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask_Response() -> *const std::ffi::c_void;
}

#[link(name = "sweepi_robot_manager_interfaces__rosidl_generator_c")]
extern "C" {
    fn sweepi_robot_manager_interfaces__srv__StartTask_Response__init(msg: *mut StartTask_Response) -> bool;
    fn sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<StartTask_Response>, size: usize) -> bool;
    fn sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<StartTask_Response>);
    fn sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<StartTask_Response>, out_seq: *mut rosidl_runtime_rs::Sequence<StartTask_Response>) -> bool;
}

// Corresponds to sweepi_robot_manager_interfaces__srv__StartTask_Response
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct StartTask_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: rosidl_runtime_rs::String,

}



impl Default for StartTask_Response {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !sweepi_robot_manager_interfaces__srv__StartTask_Response__init(&mut msg as *mut _) {
        panic!("Call to sweepi_robot_manager_interfaces__srv__StartTask_Response__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for StartTask_Response {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { sweepi_robot_manager_interfaces__srv__StartTask_Response__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for StartTask_Response {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for StartTask_Response where Self: Sized {
  const TYPE_NAME: &'static str = "sweepi_robot_manager_interfaces/srv/StartTask_Response";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__sweepi_robot_manager_interfaces__srv__StartTask_Response() }
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


