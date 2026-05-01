#include "hulku_hardware/hulku_hardware_interface.hpp"

#include <chrono>
#include <cmath>
#include <fcntl.h>
#include <iostream>
#include <limits>
#include <memory>
#include <termios.h>
#include <unistd.h>
#include <vector>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "rclcpp/rclcpp.hpp"

namespace hulku_hardware {

hardware_interface::CallbackReturn
HulkuHardwareInterface::on_init(const hardware_interface::HardwareInfo &info) {
  if (hardware_interface::SystemInterface::on_init(info) !=
      hardware_interface::CallbackReturn::SUCCESS) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  hw_states_.resize(info_.joints.size(),
                    std::numeric_limits<double>::quiet_NaN());
  hw_commands_.resize(info_.joints.size(),
                      std::numeric_limits<double>::quiet_NaN());

  // Get parameters from URDF
  port_ = info_.hardware_parameters["port"];
  if (port_.empty()) {
    port_ = "/dev/ttyUSB0";
  }

  std::string baud_rate_str = info_.hardware_parameters["baud_rate"];
  if (baud_rate_str.empty()) {
    baud_rate_ = 115200;
  } else {
    baud_rate_ = std::stoi(baud_rate_str);
  }

  for (const hardware_interface::ComponentInfo &joint : info_.joints) {
    if (joint.command_interfaces.size() != 1) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' has %zu command interfaces found. 1 expected.",
                   joint.name.c_str(), joint.command_interfaces.size());
      return hardware_interface::CallbackReturn::ERROR;
    }

    if (joint.command_interfaces[0].name !=
        hardware_interface::HW_IF_POSITION) {
      RCLCPP_FATAL(
          rclcpp::get_logger("HulkuHardwareInterface"),
          "Joint '%s' have %s command interfaces found. '%s' expected.",
          joint.name.c_str(), joint.command_interfaces[0].name.c_str(),
          hardware_interface::HW_IF_POSITION);
      return hardware_interface::CallbackReturn::ERROR;
    }

    if (joint.state_interfaces.size() != 1) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' has %zu state interface. 1 expected.",
                   joint.name.c_str(), joint.state_interfaces.size());
      return hardware_interface::CallbackReturn::ERROR;
    }

    if (joint.state_interfaces[0].name != hardware_interface::HW_IF_POSITION) {
      RCLCPP_FATAL(rclcpp::get_logger("HulkuHardwareInterface"),
                   "Joint '%s' have %s state interface. '%s' expected.",
                   joint.name.c_str(), joint.state_interfaces[0].name.c_str(),
                   hardware_interface::HW_IF_POSITION);
      return hardware_interface::CallbackReturn::ERROR;
    }
  }

  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HulkuHardwareInterface::on_configure(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Configuring ...please wait...");

  for (uint i = 0; i < hw_states_.size(); i++) {
    hw_states_[i] = 0.0;
    hw_commands_[i] = 0.0;
  }

  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully configured!");

  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HulkuHardwareInterface::on_cleanup(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"), "Cleaning up ...");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HulkuHardwareInterface::on_activate(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Activating ...please wait...");

  if (setup_serial(port_, baud_rate_) < 0) {
    RCLCPP_ERROR(rclcpp::get_logger("HulkuHardwareInterface"),
                 "Failed to open serial port %s", port_.c_str());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully activated!");

  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HulkuHardwareInterface::on_deactivate(
    const rclcpp_lifecycle::State & /*previous_state*/) {
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Deactivating ...please wait...");
  close_serial();
  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Successfully deactivated!");

  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface>
HulkuHardwareInterface::export_state_interfaces() {
  std::vector<hardware_interface::StateInterface> state_interfaces;
  for (uint i = 0; i < info_.joints.size(); i++) {
    state_interfaces.emplace_back(hardware_interface::StateInterface(
        info_.joints[i].name, hardware_interface::HW_IF_POSITION,
        &hw_states_[i]));
  }

  return state_interfaces;
}

std::vector<hardware_interface::CommandInterface>
HulkuHardwareInterface::export_command_interfaces() {
  std::vector<hardware_interface::CommandInterface> command_interfaces;
  for (uint i = 0; i < info_.joints.size(); i++) {
    command_interfaces.emplace_back(hardware_interface::CommandInterface(
        info_.joints[i].name, hardware_interface::HW_IF_POSITION,
        &hw_commands_[i]));
  }

  return command_interfaces;
}

// Convert Pulse Width back to Radians
double pulse_to_rad(uint16_t pulse, bool invert, bool is_270) {
  if (pulse == 0) return 0.0; // Prevent wild angle jumps if a servo is unplugged (returns 0)

  double deg;
  if (is_270) {
    deg = (pulse - 380.0) / (3700.0 - 380.0) * 270.0;
  } else {
    deg = (pulse - 900.0) / (3100.0 - 900.0) * 180.0;
  }

  if (invert) {
    deg = 180.0 - deg;
  }

  return (deg - 90.0) * (M_PI / 180.0);
}

hardware_interface::return_type
HulkuHardwareInterface::read(const rclcpp::Time & /*time*/,
                             const rclcpp::Duration & /*period*/) {
  if (serial_fd_ < 0 || hw_states_.empty()) return hardware_interface::return_type::OK;

  static int loop_counter = 0;
  loop_counter++;

  // 1. Request data only at 20Hz (every 5 loops) to prevent overwhelming the Arduino's I2C bus
  // The Arduino takes ~18ms to read 6 servos, so 100Hz polling crashes it!
  if (loop_counter % 5 == 0) {
      uint8_t req[3] = {0x55, 0xAA, 0x02};
      ::write(serial_fd_, req, 3);
  }

  // 2. Read all available bytes from serial into a persistent buffer
  uint8_t buf[256];
  int n = ::read(serial_fd_, buf, sizeof(buf));
  
  static std::vector<uint8_t> rx_buffer;
  if (n > 0) {
      rx_buffer.insert(rx_buffer.end(), buf, buf + n);
  }

  // Safety clear if buffer gets too large due to garbage
  if (rx_buffer.size() > 1000) rx_buffer.clear();

  static int read_fails = 0;
  bool parsed = false;

  // 3. Search the buffer for a complete 15-byte packet
  while (rx_buffer.size() >= 15) {
      if (rx_buffer[0] == 0x55 && rx_buffer[1] == 0xAA && rx_buffer[2] == 0x02) {
          uint16_t pulses[6];
          for(int i=0; i<6; i++) {
              pulses[i] = (rx_buffer[3 + i*2] << 8) | rx_buffer[4 + i*2];
          }

          // If the pulses are NOT zero, the I2C read was successful
          if (pulses[0] != 0 || pulses[1] != 0 || pulses[2] != 0) {
              read_fails = 0;
              if (hw_states_.size() > 0) hw_states_[0] = pulse_to_rad(pulses[0], false, false);
              if (hw_states_.size() > 1) hw_states_[1] = pulse_to_rad(pulses[1], true, false);
              if (hw_states_.size() > 2) hw_states_[2] = pulse_to_rad(pulses[2], true, false);
              if (hw_states_.size() > 3) hw_states_[3] = pulse_to_rad(pulses[3], true, false);
              if (hw_states_.size() > 4) hw_states_[4] = pulse_to_rad(pulses[4], false, true); // 270 deg
              if (hw_states_.size() > 5) hw_states_[5] = pulse_to_rad(pulses[5], false, false);
              parsed = true;
          }
          
          // Remove the parsed 15 bytes
          rx_buffer.erase(rx_buffer.begin(), rx_buffer.begin() + 15);
      } else {
          // Not a valid header, pop 1 byte and search again
          rx_buffer.erase(rx_buffer.begin());
      }
  }

  if (!parsed) {
      read_fails++;
      // If we haven't received valid hardware state for 200ms (20 loops), 
      // fallback to open-loop to prevent MoveIt from aborting.
      if (read_fails > 20) {
          for (uint i = 0; i < hw_states_.size(); i++) {
              if (!std::isnan(hw_commands_[i])) {
                  hw_states_[i] = hw_commands_[i];
              }
          }
      }
  }

  // Initialize NaN states to 0.0 on the very first loop
  for (uint i = 0; i < hw_states_.size(); i++) {
      if (std::isnan(hw_states_[i])) hw_states_[i] = 0.0;
  }

  return hardware_interface::return_type::OK;
}

// Convert Radians to Pulse Width
uint16_t rad_to_pulse(double rad, bool invert, bool is_270) {
  if (std::isnan(rad)) {
    // Return center position if command is NaN
    return (is_270) ? 2040 : 2000;
  }
  double deg = rad * (180.0 / M_PI) + 90.0;
  if (invert) {
    deg = 180.0 - deg;
  }
  if (is_270) {
    // map 0..270 to 380..3700
    double p = 380 + (deg / 270.0) * (3700 - 380);
    if (p < 380)
      p = 380;
    if (p > 3700)
      p = 3700;
    return (uint16_t)p;
  } else {
    // map 0..180 to 900..3100
    double p = 900 + (deg / 180.0) * (3100 - 900);
    if (p < 900)
      p = 900;
    if (p > 3100)
      p = 3100;
    return (uint16_t)p;
  }
}

hardware_interface::return_type
HulkuHardwareInterface::write(const rclcpp::Time & /*time*/,
                              const rclcpp::Duration & /*period*/) {
  if (serial_fd_ < 0 || hw_commands_.empty())
    return hardware_interface::return_type::OK;

  double c1 = (hw_commands_.size() > 0)
                  ? hw_commands_[0]
                  : std::numeric_limits<double>::quiet_NaN();
  double c2 = (hw_commands_.size() > 1)
                  ? hw_commands_[1]
                  : std::numeric_limits<double>::quiet_NaN();
  double c3 = (hw_commands_.size() > 2)
                  ? hw_commands_[2]
                  : std::numeric_limits<double>::quiet_NaN();
  double c4 = (hw_commands_.size() > 3)
                  ? hw_commands_[3]
                  : std::numeric_limits<double>::quiet_NaN();
  double c5 = (hw_commands_.size() > 4)
                  ? hw_commands_[4]
                  : std::numeric_limits<double>::quiet_NaN();
  double c6 = (hw_commands_.size() > 5)
                  ? hw_commands_[5]
                  : std::numeric_limits<double>::quiet_NaN();

  // Convert commands
  uint16_t pos1 = rad_to_pulse(c1, false, false);
  uint16_t pos2 = rad_to_pulse(c2, true, false);
  uint16_t pos3 = rad_to_pulse(c3, true, false);
  uint16_t pos4 = rad_to_pulse(c4, true, false);
  uint16_t pos5 = rad_to_pulse(c5, false, true); // 270 deg
  uint16_t pos6 = rad_to_pulse(c6, false, false);

  uint16_t time_ms = 10; // Change to 10ms. 0ms might cause Divide By Zero on
                         // Arduino interpolation!

  static int print_count = 0;
  if (print_count++ % 100 == 0) {
    RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
                "SENDING -> CMD(rad): [%.2f, %.2f, %.2f, %.2f, %.2f, %.2f] | "
                "PULSE: [%d, %d, %d, %d, %d, %d]",
                c1, c2, c3, c4, c5, c6, pos1, pos2, pos3, pos4, pos5, pos6);
  }

  uint8_t msg[17];
  msg[0] = 0x55;
  msg[1] = 0xAA;
  msg[2] = 0x01;
  msg[3] = (time_ms >> 8) & 0xFF;
  msg[4] = time_ms & 0xFF;

  msg[5] = (pos1 >> 8) & 0xFF;
  msg[6] = pos1 & 0xFF;
  msg[7] = (pos2 >> 8) & 0xFF;
  msg[8] = pos2 & 0xFF;
  msg[9] = (pos3 >> 8) & 0xFF;
  msg[10] = pos3 & 0xFF;
  msg[11] = (pos4 >> 8) & 0xFF;
  msg[12] = pos4 & 0xFF;
  msg[13] = (pos5 >> 8) & 0xFF;
  msg[14] = pos5 & 0xFF;
  msg[15] = (pos6 >> 8) & 0xFF;
  msg[16] = pos6 & 0xFF;

  ::write(serial_fd_, msg, 17);

  return hardware_interface::return_type::OK;
}

int HulkuHardwareInterface::setup_serial(const std::string &port,
                                         int baud_rate) {
  serial_fd_ = open(port.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
  if (serial_fd_ == -1) {
    return -1;
  }

  struct termios options;
  tcgetattr(serial_fd_, &options);

  speed_t baud;
  switch (baud_rate) {
  case 9600:
    baud = B9600;
    break;
  case 19200:
    baud = B19200;
    break;
  case 38400:
    baud = B38400;
    break;
  case 57600:
    baud = B57600;
    break;
  case 115200:
    baud = B115200;
    break;
  default:
    baud = B115200;
    break;
  }

  cfsetispeed(&options, baud);
  cfsetospeed(&options, baud);

  options.c_cflag |= (CLOCAL | CREAD);
  options.c_cflag &= ~PARENB;
  options.c_cflag &= ~CSTOPB;
  options.c_cflag &= ~CSIZE;
  options.c_cflag |= CS8;
  options.c_cflag &= ~CRTSCTS;

  // Raw mode
  options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
  options.c_oflag &= ~OPOST;
  options.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK | BRKINT | PARMRK |
                       ISTRIP | INLCR | IGNCR | ICRNL);

  // Non-blocking read behavior
  options.c_cc[VMIN] = 0;
  options.c_cc[VTIME] = 0;

  tcsetattr(serial_fd_, TCSANOW, &options);

  RCLCPP_INFO(rclcpp::get_logger("HulkuHardwareInterface"),
              "Serial port opened. Waiting 2 seconds for Arduino to boot...");
  sleep(2); // Wait for Arduino to reset

  // Flush any pending garbage data from the boot process
  tcflush(serial_fd_, TCIOFLUSH);

  return 0;
}

void HulkuHardwareInterface::close_serial() {
  if (serial_fd_ >= 0) {
    close(serial_fd_);
    serial_fd_ = -1;
  }
}

} // namespace hulku_hardware

#include "pluginlib/class_list_macros.hpp"

PLUGINLIB_EXPORT_CLASS(hulku_hardware::HulkuHardwareInterface,
                       hardware_interface::SystemInterface)
