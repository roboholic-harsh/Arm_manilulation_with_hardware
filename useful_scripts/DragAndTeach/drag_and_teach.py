#!/usr/bin/env python3
"""
Drag and Teach Node for Dofbot Arm
Allows physically dragging the robot arm to record waypoints, and playing them back.
"""

import sys
import os
import json
import time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

class DragAndTeachNode(Node):
    def __init__(self, mode, filename, speed=1.0):
        super().__init__('drag_and_teach_node')
        self.mode = mode
        self.filename = filename
        self.speed = speed
        
        self.gpio_pub = self.create_publisher(Float64MultiArray, '/gpio_controller/commands', 10)
        self.joint_names = ['arm1_Joint', 'arm2_Joint', 'arm3_Joint', 'arm4_Joint']
        self.current_state = None
        self.sub = self.create_subscription(JointState, '/joint_states', self.js_cb, 10)
        
        if self.mode == 'record':
            self.get_logger().info("Starting Drag & Teach RECORD mode...")
            self.trajectory = []
            
            # Wait for ROS publishers/subscribers to establish
            time.sleep(1.0)
            
            # Disable torque (let user drag the arm)
            self.set_torque(0.0)
            self.get_logger().info("Torque Disabled. You can now drag the arm.")
            
            # Record at 10 Hz
            self.timer = self.create_timer(0.1, self.record_step)
            
        elif self.mode == 'play':
            self.get_logger().info("Starting Drag & Teach PLAY mode...")
            
            # Wait for publishers
            time.sleep(1.0)
            
            # Enable torque
            self.set_torque(1.0)
            self.get_logger().info("Torque Enabled.")
            
            self.traj_pub = self.create_publisher(JointTrajectory, '/arm_controller/joint_trajectory', 10)
            time.sleep(1.0)  # wait for torque to physically engage
            
            self.play_trajectory()

    def set_torque(self, val):
        msg = Float64MultiArray()
        # Data format: [led_r, led_g, led_b, torque_enable, buzzer_trigger]
        msg.data = [0.0, 0.0, 0.0, float(val), 0.0]
        self.gpio_pub.publish(msg)

    def js_cb(self, msg):
        self.current_state = msg

    def record_step(self):
        if self.current_state:
            # Safely map joint names to positions
            pos_dict = dict(zip(self.current_state.name, self.current_state.position))
            
            # Handle cases where some joints might be missing (e.g., just started)
            if all(n in pos_dict for n in self.joint_names):
                positions = [pos_dict[n] for n in self.joint_names]
                self.trajectory.append(positions)

    def play_trajectory(self):
        if not os.path.exists(self.filename):
            self.get_logger().error(f"Trajectory file {self.filename} does not exist.")
            self._shutdown_safely()
            return

        try:
            with open(self.filename, 'r') as f:
                self.trajectory = json.load(f)
                
            if not self.trajectory:
                self.get_logger().error("Trajectory is empty.")
                self._shutdown_safely()
                return

            self.get_logger().info(f"Loaded {len(self.trajectory)} waypoints. Playing...")

            msg = JointTrajectory()
            msg.joint_names = self.joint_names
            
            time_from_start = 0.0
            dt = 0.1 / self.speed  # 10 Hz playback adjusted by speed
            n = len(self.trajectory)
            
            # --- Advanced Smoothing & Interpolation ---
            # 1. Linearly interpolate to increase resolution (5x more points)
            interpolated_traj = []
            interp_factor = 5
            new_dt = dt / interp_factor
            
            for i in range(len(self.trajectory) - 1):
                p1 = self.trajectory[i]
                p2 = self.trajectory[i + 1]
                for step in range(interp_factor):
                    alpha = step / interp_factor
                    interp_pt = [p1[j] * (1 - alpha) + p2[j] * alpha for j in range(len(p1))]
                    interpolated_traj.append(interp_pt)
            if len(self.trajectory) > 0:
                interpolated_traj.append(self.trajectory[-1])
                
            self.trajectory = interpolated_traj
            dt = new_dt
            n = len(self.trajectory)
            
            # 2. Apply a heavy Moving Average filter over the high-res points
            def moving_average(traj, window=15):
                smoothed = []
                num_joints = len(traj[0])
                for i in range(len(traj)):
                    start_idx = max(0, i - window // 2)
                    end_idx = min(len(traj), i + window // 2 + 1)
                    window_pts = traj[start_idx:end_idx]
                    
                    avg_pos = []
                    for j in range(num_joints):
                        avg = sum(pt[j] for pt in window_pts) / len(window_pts)
                        avg_pos.append(avg)
                    smoothed.append(avg_pos)
                return smoothed

            # Apply 3 passes of heavy smoothing for a fluid trajectory
            if n > 15:
                self.trajectory = moving_average(self.trajectory, window=15)
                self.trajectory = moving_average(self.trajectory, window=15)
                self.trajectory = moving_average(self.trajectory, window=15)
            # --------------------------------------------
            
            # --- Smoothly Move to Start Position ---
            self.get_logger().info("Moving smoothly to the start position over 2.5s...")
            start_msg = JointTrajectory()
            start_msg.joint_names = self.joint_names
            start_pt = JointTrajectoryPoint()
            start_pt.positions = self.trajectory[0]
            start_pt.velocities = [0.0] * len(self.trajectory[0])
            start_pt.time_from_start.sec = 2
            start_pt.time_from_start.nanosec = int(0.5 * 1e9)
            start_msg.points.append(start_pt)
            
            self.traj_pub.publish(start_msg)
            time.sleep(2.5) # Wait for hardware to reach the start pose
            self.get_logger().info("Executing trajectory...")
            # ---------------------------------------
            
            for i, pos in enumerate(self.trajectory):
                pt = JointTrajectoryPoint()
                pt.positions = pos
                
                # Calculate simple central difference for velocities
                velocities = []
                if i == 0 or i == n - 1:
                    velocities = [0.0] * len(pos)
                else:
                    prev_pos = self.trajectory[i - 1]
                    next_pos = self.trajectory[i + 1]
                    for p_prev, p_next in zip(prev_pos, next_pos):
                        # Central difference: (next - prev) / (2 * dt)
                        v = (p_next - p_prev) / (2.0 * dt)
                        velocities.append(v)
                pt.velocities = velocities
                
                time_from_start += dt
                
                sec = int(time_from_start)
                nanosec = int((time_from_start - sec) * 1e9)
                pt.time_from_start.sec = sec
                pt.time_from_start.nanosec = nanosec
                
                msg.points.append(pt)
                
            self.traj_pub.publish(msg)
            
            # Wait for physical execution to complete
            time.sleep(time_from_start + 1.0)
            self.get_logger().info("Playback complete.")
            
        except Exception as e:
            self.get_logger().error(f"Failed to play trajectory: {e}")
        finally:
            self._shutdown_safely()

    def save(self):
        if self.mode == 'record':
            # Save file first to ensure data isn't lost if ROS is already shut down
            try:
                with open(self.filename, 'w') as f:
                    json.dump(self.trajectory, f)
                self.get_logger().info(f"Successfully saved {len(self.trajectory)} waypoints to {self.filename}")
            except Exception as e:
                print(f"Failed to save trajectory: {e}")
                
            # Then attempt to restore torque
            try:
                if rclpy.ok():
                    self.set_torque(1.0)
            except Exception:
                pass
                
    def stop_playback(self):
        if self.mode == 'play' and hasattr(self, 'traj_pub'):
            try:
                if self.current_state and rclpy.ok():
                    self.get_logger().info("Stopping playback immediately...")
                    pos_dict = dict(zip(self.current_state.name, self.current_state.position))
                    if all(n in pos_dict for n in self.joint_names):
                        positions = [pos_dict[n] for n in self.joint_names]
                        msg = JointTrajectory()
                        msg.joint_names = self.joint_names
                        pt = JointTrajectoryPoint()
                        pt.positions = positions
                        pt.time_from_start.sec = 0
                        pt.time_from_start.nanosec = int(0.1 * 1e9)
                        msg.points.append(pt)
                        self.traj_pub.publish(msg)
                        self.get_logger().info("Published stop trajectory.")
            except Exception:
                pass

    def _shutdown_safely(self):
        # We spawn a thread to shutdown to avoid blocking the ROS thread
        import threading
        threading.Thread(target=self._shutdown_task).start()

    def _shutdown_task(self):
        time.sleep(0.5)
        rclpy.shutdown()


def main(args=None):
    try:
        import argparse
        parser = argparse.ArgumentParser(description="Drag and Teach Node for Dofbot Arm")
        parser.add_argument('mode', choices=['record', 'play'], help='Mode to run: record or play')
        parser.add_argument('--file', type=str, default='', help='Path to save/load trajectory JSON')
        parser.add_argument('--speed', type=float, default=1.0, help='Playback speed multiplier')
        
        parsed_args, ros_args = parser.parse_known_args(args=sys.argv[1:])
        mode = parsed_args.mode
        speed = parsed_args.speed
        
        # Use absolute path passed as argument or default to local directory
        if parsed_args.file:
            filename = parsed_args.file
        else:
            # Default to script's directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(script_dir, 'taught_trajectory.json')
        
        rclpy.init(args=ros_args)
        node = None
        
        try:
            node = DragAndTeachNode(mode, filename, speed)
            if rclpy.ok():
                rclpy.spin(node)
        except KeyboardInterrupt:
            if node:
                node.get_logger().info("KeyboardInterrupt caught, saving and shutting down...")
        finally:
            if node:
                node.save()
                node.stop_playback()
                if rclpy.ok():
                    node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
    except KeyboardInterrupt:
        print("Interrupted before initialization finished. Exiting safely.")

if __name__ == '__main__':
    main()
