# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_sweepi_state_estimation_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED sweepi_state_estimation_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(sweepi_state_estimation_FOUND FALSE)
  elseif(NOT sweepi_state_estimation_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(sweepi_state_estimation_FOUND FALSE)
  endif()
  return()
endif()
set(_sweepi_state_estimation_CONFIG_INCLUDED TRUE)

# output package information
if(NOT sweepi_state_estimation_FIND_QUIETLY)
  message(STATUS "Found sweepi_state_estimation: 0.1.0 (${sweepi_state_estimation_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'sweepi_state_estimation' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT sweepi_state_estimation_DEPRECATED_QUIET)
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(sweepi_state_estimation_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${sweepi_state_estimation_DIR}/${_extra}")
endforeach()
