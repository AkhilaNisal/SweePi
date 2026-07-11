// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from sweepi_robot_manager_interfaces:srv/StartTask.idl
// generated code does not contain a copyright notice

#include "sweepi_robot_manager_interfaces/srv/detail/start_task__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_sweepi_robot_manager_interfaces
const rosidl_type_hash_t *
sweepi_robot_manager_interfaces__srv__StartTask__get_type_hash(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x48, 0xe6, 0xaa, 0xb8, 0x4a, 0xfb, 0x52, 0x11,
      0x82, 0x00, 0x7e, 0xf3, 0x76, 0xee, 0x79, 0xaa,
      0xe4, 0x87, 0x01, 0xbf, 0xb9, 0x01, 0x98, 0xa6,
      0xf3, 0xa0, 0x6b, 0x1d, 0xd5, 0xd0, 0x24, 0x2f,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_sweepi_robot_manager_interfaces
const rosidl_type_hash_t *
sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x16, 0x1d, 0xa6, 0x88, 0xac, 0x19, 0x8a, 0x91,
      0xf8, 0x57, 0xdd, 0xa8, 0x6f, 0xce, 0x49, 0x70,
      0x9c, 0x58, 0xd5, 0xf6, 0xbf, 0xce, 0xd3, 0xe0,
      0xf4, 0xe3, 0x39, 0xdf, 0xf1, 0x8b, 0x61, 0xb2,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_sweepi_robot_manager_interfaces
const rosidl_type_hash_t *
sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xd0, 0x83, 0xd4, 0x70, 0xb5, 0x9e, 0x2c, 0xeb,
      0xe4, 0xae, 0xe0, 0x6d, 0x38, 0x53, 0xe1, 0xbb,
      0x20, 0x1f, 0x1d, 0xf6, 0x17, 0x3b, 0xf4, 0x48,
      0xf9, 0x37, 0x3f, 0xbb, 0x1e, 0xd8, 0x16, 0xc1,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_sweepi_robot_manager_interfaces
const rosidl_type_hash_t *
sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x24, 0x41, 0x8d, 0xa5, 0xd6, 0x26, 0x67, 0x4e,
      0x77, 0x6c, 0xc5, 0xa4, 0xa6, 0xab, 0xbb, 0xc5,
      0xf7, 0x36, 0x0b, 0x48, 0x15, 0xec, 0x8c, 0xbe,
      0xb2, 0xe7, 0x4d, 0x7f, 0xb0, 0xaf, 0xa9, 0x41,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "builtin_interfaces/msg/detail/time__functions.h"
#include "service_msgs/msg/detail/service_event_info__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t builtin_interfaces__msg__Time__EXPECTED_HASH = {1, {
    0xb1, 0x06, 0x23, 0x5e, 0x25, 0xa4, 0xc5, 0xed,
    0x35, 0x09, 0x8a, 0xa0, 0xa6, 0x1a, 0x3e, 0xe9,
    0xc9, 0xb1, 0x8d, 0x19, 0x7f, 0x39, 0x8b, 0x0e,
    0x42, 0x06, 0xce, 0xa9, 0xac, 0xf9, 0xc1, 0x97,
  }};
static const rosidl_type_hash_t service_msgs__msg__ServiceEventInfo__EXPECTED_HASH = {1, {
    0x41, 0xbc, 0xbb, 0xe0, 0x7a, 0x75, 0xc9, 0xb5,
    0x2b, 0xc9, 0x6b, 0xfd, 0x5c, 0x24, 0xd7, 0xf0,
    0xfc, 0x0a, 0x08, 0xc0, 0xcb, 0x79, 0x21, 0xb3,
    0x37, 0x3c, 0x57, 0x32, 0x34, 0x5a, 0x6f, 0x45,
  }};
#endif

static char sweepi_robot_manager_interfaces__srv__StartTask__TYPE_NAME[] = "sweepi_robot_manager_interfaces/srv/StartTask";
static char builtin_interfaces__msg__Time__TYPE_NAME[] = "builtin_interfaces/msg/Time";
static char service_msgs__msg__ServiceEventInfo__TYPE_NAME[] = "service_msgs/msg/ServiceEventInfo";
static char sweepi_robot_manager_interfaces__srv__StartTask_Event__TYPE_NAME[] = "sweepi_robot_manager_interfaces/srv/StartTask_Event";
static char sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME[] = "sweepi_robot_manager_interfaces/srv/StartTask_Request";
static char sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME[] = "sweepi_robot_manager_interfaces/srv/StartTask_Response";

// Define type names, field names, and default values
static char sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__request_message[] = "request_message";
static char sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__response_message[] = "response_message";
static char sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__event_message[] = "event_message";

static rosidl_runtime_c__type_description__Field sweepi_robot_manager_interfaces__srv__StartTask__FIELDS[] = {
  {
    {sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__request_message, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__response_message, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask__FIELD_NAME__event_message, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {sweepi_robot_manager_interfaces__srv__StartTask_Event__TYPE_NAME, 51, 51},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription sweepi_robot_manager_interfaces__srv__StartTask__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__TYPE_NAME, 51, 51},
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
sweepi_robot_manager_interfaces__srv__StartTask__get_type_description(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {sweepi_robot_manager_interfaces__srv__StartTask__TYPE_NAME, 45, 45},
      {sweepi_robot_manager_interfaces__srv__StartTask__FIELDS, 3, 3},
    },
    {sweepi_robot_manager_interfaces__srv__StartTask__REFERENCED_TYPE_DESCRIPTIONS, 5, 5},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[1].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[3].fields = sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[4].fields = sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__map_name[] = "map_name";
static char sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__mode[] = "mode";
static char sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__auto_start[] = "auto_start";

static rosidl_runtime_c__type_description__Field sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELDS[] = {
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__map_name, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__mode, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELD_NAME__auto_start, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
      {sweepi_robot_manager_interfaces__srv__StartTask_Request__FIELDS, 3, 3},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELD_NAME__success[] = "success";
static char sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELD_NAME__message[] = "message";

static rosidl_runtime_c__type_description__Field sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELDS[] = {
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELD_NAME__success, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELD_NAME__message, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
      {sweepi_robot_manager_interfaces__srv__StartTask_Response__FIELDS, 2, 2},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__info[] = "info";
static char sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__request[] = "request";
static char sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__response[] = "response";

static rosidl_runtime_c__type_description__Field sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELDS[] = {
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__info, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__request, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
    },
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELD_NAME__response, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription sweepi_robot_manager_interfaces__srv__StartTask_Event__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
    {NULL, 0, 0},
  },
  {
    {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {sweepi_robot_manager_interfaces__srv__StartTask_Event__TYPE_NAME, 51, 51},
      {sweepi_robot_manager_interfaces__srv__StartTask_Event__FIELDS, 3, 3},
    },
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__REFERENCED_TYPE_DESCRIPTIONS, 4, 4},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[1].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[3].fields = sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "string map_name\n"
  "string mode\n"
  "bool auto_start\n"
  "---\n"
  "bool success\n"
  "string message";

static char srv_encoding[] = "srv";
static char implicit_encoding[] = "implicit";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
sweepi_robot_manager_interfaces__srv__StartTask__get_individual_type_description_source(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {sweepi_robot_manager_interfaces__srv__StartTask__TYPE_NAME, 45, 45},
    {srv_encoding, 3, 3},
    {toplevel_type_raw_source, 76, 76},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
sweepi_robot_manager_interfaces__srv__StartTask_Request__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {sweepi_robot_manager_interfaces__srv__StartTask_Request__TYPE_NAME, 53, 53},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
sweepi_robot_manager_interfaces__srv__StartTask_Response__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {sweepi_robot_manager_interfaces__srv__StartTask_Response__TYPE_NAME, 54, 54},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
sweepi_robot_manager_interfaces__srv__StartTask_Event__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {sweepi_robot_manager_interfaces__srv__StartTask_Event__TYPE_NAME, 51, 51},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
sweepi_robot_manager_interfaces__srv__StartTask__get_type_description_sources(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[6];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 6, 6};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *sweepi_robot_manager_interfaces__srv__StartTask__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    sources[3] = *sweepi_robot_manager_interfaces__srv__StartTask_Event__get_individual_type_description_source(NULL);
    sources[4] = *sweepi_robot_manager_interfaces__srv__StartTask_Request__get_individual_type_description_source(NULL);
    sources[5] = *sweepi_robot_manager_interfaces__srv__StartTask_Response__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
sweepi_robot_manager_interfaces__srv__StartTask_Request__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *sweepi_robot_manager_interfaces__srv__StartTask_Request__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
sweepi_robot_manager_interfaces__srv__StartTask_Response__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *sweepi_robot_manager_interfaces__srv__StartTask_Response__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
sweepi_robot_manager_interfaces__srv__StartTask_Event__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[5];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 5, 5};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *sweepi_robot_manager_interfaces__srv__StartTask_Event__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    sources[3] = *sweepi_robot_manager_interfaces__srv__StartTask_Request__get_individual_type_description_source(NULL);
    sources[4] = *sweepi_robot_manager_interfaces__srv__StartTask_Response__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
