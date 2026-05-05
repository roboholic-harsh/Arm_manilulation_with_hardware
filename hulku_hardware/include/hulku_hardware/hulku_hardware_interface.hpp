#ifndef HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_
#define HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_

#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp/rclcpp.hpp"
#include "std_srvs/srv/set_bool.hpp"

namespace hulku_hardware {

class HulkuHardwareInterface : public hardware_interface::SystemInterface {
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(HulkuHardwareInterface)

  hardware_interface::CallbackReturn
  on_init(const hardware_interface::HardwareInfo &info) override;

  hardware_interface::CallbackReturn
  on_configure(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_cleanup(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_activate(const rclcpp_lifecycle::State &previous_state) override;

  hardware_interface::CallbackReturn
  on_deactivate(const rclcpp_lifecycle::State &previous_state) override;

  std::vector<hardware_interface::StateInterface>
  export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface>
  export_command_interfaces() override;

  hardware_interface::return_type read(const rclcpp::Time &time,
                                       const rclcpp::Duration &period) override;

  hardware_interface::return_type
  write(const rclcpp::Time &time, const rclcpp::Duration &period) override;

private:
  int setup_serial(const std::string &port, int baud_rate);
  void close_serial();

  // Communication handles
  std::string port_;
  int baud_rate_;
  int serial_fd_ = -1;

  // Store commands and states
  std::vector<double> hw_commands_;
  std::vector<double> hw_states_;

  // ROS services for buzzer & torque (exposed via a dedicated node + thread)
  std::shared_ptr<rclcpp::Node> service_node_;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr buzzer_service_;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr torque_service_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> service_executor_;
  std::thread service_thread_;

  void buzzer_callback(
      const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
      std::shared_ptr<std_srvs::srv::SetBool::Response> response);
  void torque_callback(
      const std::shared_ptr<std_srvs::srv::SetBool::Request> request,
      std::shared_ptr<std_srvs::srv::SetBool::Response> response);
};

} // namespace hulku_hardware

#endif // HULKU_HARDWARE__HULKU_HARDWARE_INTERFACE_HPP_
