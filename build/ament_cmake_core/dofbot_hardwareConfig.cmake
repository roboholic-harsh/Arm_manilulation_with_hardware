# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_dofbot_hardware_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED dofbot_hardware_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(dofbot_hardware_FOUND FALSE)
  elseif(NOT dofbot_hardware_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(dofbot_hardware_FOUND FALSE)
  endif()
  return()
endif()
set(_dofbot_hardware_CONFIG_INCLUDED TRUE)

# output package information
if(NOT dofbot_hardware_FIND_QUIETLY)
  message(STATUS "Found dofbot_hardware: 0.0.0 (${dofbot_hardware_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'dofbot_hardware' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${dofbot_hardware_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(dofbot_hardware_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${dofbot_hardware_DIR}/${_extra}")
endforeach()
