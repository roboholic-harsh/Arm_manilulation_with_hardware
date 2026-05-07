#ifndef DOFBOT_HARDWARE__DOFBOT_SYSTEM_HPP_
#define DOFBOT_HARDWARE__DOFBOT_SYSTEM_HPP_

#include <vector>
#include <string>
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/rclcpp.hpp"
#include <libserial/SerialPort.h>

// ==========================================
// BINARY PROTOCOL STRUCTURES (4 MOTORS)
// ==========================================
#pragma pack(push, 1) // Force compiler to pack without padding bytes
struct StatePacket {
  uint8_t header;       
  int16_t angles[4];    // Reduced to 4 motors
  uint8_t checksum;     
};

struct CommandPacket {
  uint8_t header;       
  uint8_t cmd_type;     
  int16_t params[5];    // 4 angles + 1 transit time
  uint8_t checksum;
};
#pragma pack(pop)

namespace dofbot_hardware
{
class DofbotSystemHardware : public hardware_interface::SystemInterface
{
public:
  hardware_interface::CallbackReturn on_init(const hardware_interface::HardwareInfo & info) override;
  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;
  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;
  hardware_interface::CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) override;
  hardware_interface::return_type read(const rclcpp::Time & time, const rclcpp::Duration & period) override;
  hardware_interface::return_type write(const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  LibSerial::SerialPort serial_conn_;
  
  std::vector<double> hw_commands_;
  std::vector<double> hw_states_;
  
  int16_t rad_to_deg(double rad);
  double deg_to_rad(int16_t deg);

  // Existing joint variables...
  std::vector<double> hw_commands_positions_;
  std::vector<double> hw_states_positions_;

  // NEW: GPIO Command variables
  double hw_led_r_{0.0};
  double hw_led_g_{255.0}; // Default to Green
  double hw_led_b_{0.0};
  double hw_torque_{1.0};  // Default to Torque ON
  double hw_buzzer_{0.0};  // Default to Buzzer OFF

  // State trackers to prevent spamming the serial port
  double prev_led_r_{-1}, prev_led_g_{-1}, prev_led_b_{-1};
  double prev_torque_{-1};
  double prev_buzzer_{-1};
};
}  // namespace dofbot_hardware

#endif  // DOFBOT_HARDWARE__DOFBOT_SYSTEM_HPP_