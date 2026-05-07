#include "dofbot_hardware/dofbot_system.hpp"
#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include <cmath>

namespace dofbot_hardware
{
hardware_interface::CallbackReturn DofbotSystemHardware::on_init(const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) != hardware_interface::CallbackReturn::SUCCESS) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  hw_states_.resize(info_.joints.size(), 0.0);
  hw_commands_.resize(info_.joints.size(), 0.0);
  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> DofbotSystemHardware::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> state_interfaces;
  for (uint i = 0; i < info_.joints.size(); i++) {
    state_interfaces.emplace_back(hardware_interface::StateInterface(
      info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_states_[i]));
  }
  return state_interfaces;
}

std::vector<hardware_interface::CommandInterface> DofbotSystemHardware::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> command_interfaces;
  
  // 1. Export Joints
  for (uint i = 0; i < info_.joints.size(); i++) {
    command_interfaces.emplace_back(hardware_interface::CommandInterface(
      info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_commands_[i]));
  }

  // 2. Export GPIOs
  command_interfaces.emplace_back(hardware_interface::CommandInterface("aux_hardware", "led_r", &hw_led_r_));
  command_interfaces.emplace_back(hardware_interface::CommandInterface("aux_hardware", "led_g", &hw_led_g_));
  command_interfaces.emplace_back(hardware_interface::CommandInterface("aux_hardware", "led_b", &hw_led_b_));
  command_interfaces.emplace_back(hardware_interface::CommandInterface("aux_hardware", "torque_enable", &hw_torque_));
  command_interfaces.emplace_back(hardware_interface::CommandInterface("aux_hardware", "buzzer_trigger", &hw_buzzer_));

  return command_interfaces;
}

hardware_interface::CallbackReturn DofbotSystemHardware::on_activate(const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), "Opening Serial Port /dev/ttyUSB0 in REQUEST-RESPONSE mode...");
  try {
    serial_conn_.Open("/dev/ttyUSB0");
    serial_conn_.SetBaudRate(LibSerial::BaudRate::BAUD_115200);
  } catch (...) {
    RCLCPP_ERROR(rclcpp::get_logger("DofbotSystemHardware"), "Failed to open serial port!");
    return hardware_interface::CallbackReturn::ERROR;
  }
  
  for (uint i = 0; i < hw_states_.size(); i++) { hw_commands_[i] = hw_states_[i]; }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn DofbotSystemHardware::on_deactivate(const rclcpp_lifecycle::State & /*previous_state*/)
{
  if (serial_conn_.IsOpen()) { serial_conn_.Close(); }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::return_type DofbotSystemHardware::read(const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  if (!serial_conn_.IsOpen()) return hardware_interface::return_type::ERROR;

  // 1. FLUSH BUFFER: Clear out any late noise
  serial_conn_.FlushInputBuffer();

  // 2. SEND REQUEST
  CommandPacket req;
  req.header = 0xA6;
  req.cmd_type = 5; 
  for(int i=0; i<5; i++) req.params[i] = 0; 
  req.checksum = req.cmd_type; 

  try {
    std::string req_data(reinterpret_cast<const char*>(&req), sizeof(CommandPacket));
    serial_conn_.Write(req_data);
  } catch (...) {
    return hardware_interface::return_type::OK; 
  }

  // 3. WAIT FOR RESPONSE
  try {
    std::string header_byte;
    // THE FIX: Wait up to 35ms for the ESP32 to finish its I2C delays!
    serial_conn_.Read(header_byte, 1, 35); 

    if (!header_byte.empty() && (uint8_t)header_byte[0] == 0xA5) {
      std::string raw_data;
      // Read the remaining 9 bytes (give it 10ms to travel over USB)
      serial_conn_.Read(raw_data, sizeof(StatePacket) - 1, 5);
      
      StatePacket state;
      state.header = 0xA5;
      memcpy((uint8_t*)&state + 1, raw_data.data(), sizeof(StatePacket) - 1);
      
      uint8_t calc_check = 0;
      uint8_t* angle_bytes = (uint8_t*)&state.angles;
      for (size_t i = 0; i < sizeof(state.angles); i++) {
        calc_check += angle_bytes[i];
      }
      
      if (calc_check == state.checksum) {
        // static int debug_counter = 0;
        // bool print_debug = (debug_counter++ % 10 == 0); 

        // if (print_debug) RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), "--- ENCODER DATA OK ---");

        for (int i = 0; i < 4; i++) {
          int16_t raw_angle = state.angles[i];

          if (raw_angle == -1) continue; 

          double new_rad = deg_to_rad(raw_angle);
          // if (print_debug) RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), " Joint %d: %d deg -> %.3f rad", i+1, raw_angle, new_rad);

          double diff = std::abs(new_rad - hw_states_[i]);
          if (diff > 0.52 && hw_states_[i] != 0.0) continue; 
          
          hw_states_[i] = new_rad;
        }
      } 
    }
  } catch (const LibSerial::ReadTimeout&) {
    // Normal behavior if the ESP32 occasionally drops a packet
  }

  return hardware_interface::return_type::OK;
}

// hardware_interface::return_type DofbotSystemHardware::write(const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
// {
//   if (!serial_conn_.IsOpen()) return hardware_interface::return_type::ERROR;

//   CommandPacket cmd;
//   cmd.header = 0xA6;
//   cmd.cmd_type = 1; // MOVE command
  
//   // Pack 4 angles
//   for (int i = 0; i < 4; i++) {
//     cmd.params[i] = rad_to_deg(hw_commands_[i]);
//   }
//   // Pack Transit Time 
//   cmd.params[4] = 30; 

//   cmd.checksum = cmd.cmd_type;
//   uint8_t* param_bytes = (uint8_t*)&cmd.params;
//   for (size_t i = 0; i < sizeof(cmd.params); i++) {
//     cmd.checksum += param_bytes[i];
//   }

//   try {
//     std::string tx_data(reinterpret_cast<const char*>(&cmd), sizeof(CommandPacket));
//     serial_conn_.Write(tx_data);
//   } catch (...) { }

//   return hardware_interface::return_type::OK;
// }






hardware_interface::return_type DofbotSystemHardware::write(const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  if (!serial_conn_.IsOpen()) return hardware_interface::return_type::ERROR;

  CommandPacket cmd;
  cmd.header = 0xA6;
  cmd.cmd_type = 1; // MOVE command
  
  // 1. Set safe defaults
  for (int i = 0; i < 4; i++) cmd.params[i] = 90;

  // 2. Map commands by exact name
  for (size_t i = 0; i < info_.joints.size(); i++) {
    std::string j_name = info_.joints[i].name;
    int16_t deg_val = rad_to_deg(hw_commands_[i]);

    if (j_name == "arm1_Joint") {
        cmd.params[0] = deg_val;
    } else if (j_name == "arm2_Joint") {
        cmd.params[1] = deg_val;
    } else if (j_name == "arm3_Joint") {
        cmd.params[2] = deg_val;
    } else if (j_name == "arm4_Joint") {
        cmd.params[3] = deg_val;
    }
  }

  cmd.params[4] = 1000; // Transit time

  // ====== WRITE X-RAY ======
  // Prints the actual degrees being sent to the USB wire (once per second)
  // static int write_debug = 0;
  // if (write_debug++ % 20 == 0) {
  //    RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), 
  //    "TRANSMITTING -> J1: %d | J2: %d | J3: %d | J4: %d", 
  //    cmd.params[0], cmd.params[1], cmd.params[2], cmd.params[3]);
  // }
  // =========================

  cmd.checksum = cmd.cmd_type;
  uint8_t* param_bytes = (uint8_t*)&cmd.params;
  for (size_t i = 0; i < sizeof(cmd.params); i++) {
    cmd.checksum += param_bytes[i];
  }

  try {
    std::string tx_data(reinterpret_cast<const char*>(&cmd), sizeof(CommandPacket));
    serial_conn_.Write(tx_data);
  } catch (...) { }
// --------------------------------------------------------
  // 2. Check and send RGB commands
  // --------------------------------------------------------
// --------------------------------------------------------
  // 2. Check and send RGB commands
  // --------------------------------------------------------
  if (hw_led_r_ != prev_led_r_ || hw_led_g_ != prev_led_g_ || hw_led_b_ != prev_led_b_) {
    CommandPacket rgb_cmd;
    rgb_cmd.header = 0xA6;
    rgb_cmd.cmd_type = 2; 
    rgb_cmd.params[0] = static_cast<int16_t>(hw_led_r_);
    rgb_cmd.params[1] = static_cast<int16_t>(hw_led_g_);
    rgb_cmd.params[2] = static_cast<int16_t>(hw_led_b_);
    rgb_cmd.params[3] = 0;
    rgb_cmd.params[4] = 0;
    
    rgb_cmd.checksum = rgb_cmd.cmd_type;
    uint8_t* param_bytes = (uint8_t*)&rgb_cmd.params;
    for (size_t i = 0; i < sizeof(rgb_cmd.params); i++) rgb_cmd.checksum += param_bytes[i];
    
    // ==========================================
    // CRITICAL DEBUG PRINT - DO NOT REMOVE THIS
    // ==========================================
    RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), 
      ">>> ROS TRIGGERED RGB CHANGE! Sending -> R:%d G:%d B:%d", 
      rgb_cmd.params[0], rgb_cmd.params[1], rgb_cmd.params[2]);

    try {
      std::string tx_data(reinterpret_cast<const char*>(&rgb_cmd), sizeof(CommandPacket));
      serial_conn_.Write(tx_data);
    } catch (...) { }
    
    prev_led_r_ = hw_led_r_; prev_led_g_ = hw_led_g_; prev_led_b_ = hw_led_b_;
  }
  // --------------------------------------------------------
  // 3. Check and send Torque commands
  // --------------------------------------------------------
// --------------------------------------------------------
  // 3. Check and send Torque commands
  // --------------------------------------------------------
  if (hw_torque_ != prev_torque_) {
    CommandPacket torque_cmd;
    torque_cmd.header = 0xA6;
    torque_cmd.cmd_type = 3; 
    torque_cmd.params[0] = static_cast<int16_t>(hw_torque_);
    for(int i=1; i<5; i++) torque_cmd.params[i] = 0; 
    
    torque_cmd.checksum = torque_cmd.cmd_type;
    uint8_t* param_bytes = (uint8_t*)&torque_cmd.params;
    for (size_t i = 0; i < sizeof(torque_cmd.params); i++) torque_cmd.checksum += param_bytes[i];
    
    // ---> ADD THIS DEBUG PRINT <---
    RCLCPP_INFO(rclcpp::get_logger("DofbotSystemHardware"), 
      ">>> ROS TRIGGERED TORQUE CHANGE! Sending -> %d", torque_cmd.params[0]);

    try {
      std::string tx_data(reinterpret_cast<const char*>(&torque_cmd), sizeof(CommandPacket));
      serial_conn_.Write(tx_data);
    } catch (...) { }
    
    prev_torque_ = hw_torque_;
  }

  // --------------------------------------------------------
  // 4. Check and send Buzzer commands
  // --------------------------------------------------------
  if (hw_buzzer_ != prev_buzzer_) {
    CommandPacket buzz_cmd;
    buzz_cmd.header = 0xA6;
    buzz_cmd.cmd_type = 4; 
    buzz_cmd.params[0] = static_cast<int16_t>(hw_buzzer_);
    for(int i=1; i<5; i++) buzz_cmd.params[i] = 0; // Zero out the rest
    
    buzz_cmd.checksum = buzz_cmd.cmd_type;
    uint8_t* param_bytes = (uint8_t*)&buzz_cmd.params;
    for (size_t i = 0; i < sizeof(buzz_cmd.params); i++) buzz_cmd.checksum += param_bytes[i];
    
    try {
      std::string tx_data(reinterpret_cast<const char*>(&buzz_cmd), sizeof(CommandPacket));
      serial_conn_.Write(tx_data);
    } catch (...) { }
    
    prev_buzzer_ = hw_buzzer_;
  }






  return hardware_interface::return_type::OK;
}





// Math Helpers (Simplified for standard 0-180 degree base motors)
int16_t DofbotSystemHardware::rad_to_deg(double rad) {
  return std::max(0, std::min((int)(rad * 180.0 / M_PI + 90.0), 180));
}

double DofbotSystemHardware::deg_to_rad(int16_t deg) {
  return (deg - 90.0) * M_PI / 180.0;
}
}  // namespace dofbot_hardware

PLUGINLIB_EXPORT_CLASS(dofbot_hardware::DofbotSystemHardware, hardware_interface::SystemInterface)