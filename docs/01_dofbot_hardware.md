# `dofbot_hardware` — C++ ros2_control Hardware Interface

> **Type:** C++ shared library (ament_cmake)  
> **Role:** The lowest-level software component — a `ros2_control` `SystemInterface` plugin that bridges the ROS 2 control loop to the physical ESP32 via USB serial.

---

## Purpose

This package implements `hardware_interface::SystemInterface` that the `ros2_control` Controller Manager loads at runtime. Every control cycle (~20 Hz), the Controller Manager calls:

1. **`read()`** — Poll the ESP32 for encoder feedback → update `hw_states_[]`
2. **`write()`** — Send joint commands + GPIO commands to the ESP32

This is a **single shared library** (`libdofbot_hardware.so`) dynamically loaded via `pluginlib`.

---

## File Map

```
dofbot_hardware/
├── CMakeLists.txt              # Build config — links libserial
├── dofbot_hardware.xml         # pluginlib descriptor (maps class → .so)
├── package.xml                 # ROS 2 package manifest
├── include/dofbot_hardware/
│   └── dofbot_system.hpp       # Header — packet structs, class definition
└── src/
    └── dofbot_system.cpp       # Implementation — serial R/W, GPIO logic
```

---

## Class Hierarchy

```
hardware_interface::SystemInterface  (ROS 2 abstract base)
    └── dofbot_hardware::DofbotSystemHardware  (our implementation)
```

Registered via `pluginlib`:
```xml
<!-- dofbot_hardware.xml -->
<library path="dofbot_hardware">
  <class name="dofbot_hardware/DofbotSystemHardware"
         type="dofbot_hardware::DofbotSystemHardware"
         base_class_type="hardware_interface::SystemInterface"/>
</library>
```

---

## Binary Serial Protocol

Communication with ESP32 uses a compact binary protocol over USB serial at **115200 baud** on `/dev/ttyUSB0`.

### Packet Structures (packed, no padding)

```cpp
#pragma pack(push, 1)

// ESP32 → PC (10 bytes)
struct StatePacket {
  uint8_t  header;       // Always 0xA5
  int16_t  angles[4];   // 4 joint angles in degrees (signed)
  uint8_t  checksum;    // Sum of all angle bytes mod 256
};

// PC → ESP32 (13 bytes)
struct CommandPacket {
  uint8_t  header;       // Always 0xA6
  uint8_t  cmd_type;    // 1=MOVE, 2=RGB, 3=TORQUE, 4=BUZZ, 5=GET_ENCODERS
  int16_t  params[5];   // Command-specific parameters
  uint8_t  checksum;    // cmd_type + all param bytes mod 256
};
#pragma pack(pop)
```

### Command Types

| `cmd_type` | Name | `params[]` layout |
|------------|------|-------------------|
| `1` | MOVE | `[J1°, J2°, J3°, J4°, transit_time_ms]` |
| `2` | RGB | `[R, G, B, 0, 0]` |
| `3` | TORQUE | `[enable, 0, 0, 0, 0]` |
| `4` | BUZZER | `[state, 0, 0, 0, 0]` |
| `5` | GET_ENCODERS | `[0, 0, 0, 0, 0]` |

---

## Exported Interfaces

### State Interfaces
| Joint | Interface |
|-------|-----------|
| `arm1_Joint` – `arm4_Joint` | `position` (radians) |

### Command Interfaces — Joints
| Joint | Interface |
|-------|-----------|
| `arm1_Joint` – `arm4_Joint` | `position` (radians) |

### Command Interfaces — GPIO (`aux_hardware`)
| Interface | Default | Description |
|-----------|---------|-------------|
| `led_r` | `0.0` | Red LED channel |
| `led_g` | `255.0` | Green LED channel (green = ready) |
| `led_b` | `0.0` | Blue LED channel |
| `torque_enable` | `1.0` | Motor torque (1=on, 0=off) |
| `buzzer_trigger` | `0.0` | Buzzer (1=on, 0=off) |

---

## `read()` — Encoder Polling

```
1. Flush serial input buffer
2. Send GET_ENCODERS command (cmd_type=5)
3. Wait ≤35ms for ESP32 response (accounts for I2C delays)
4. Validate header byte (0xA5)
5. Read 9 remaining bytes → parse StatePacket
6. Validate checksum
7. For each of 4 joints:
   - angle == -1? → skip (encoder error)
   - Convert deg → rad: (deg - 90) × π/180
   - Anti-jitter: reject if Δ > 0.52 rad AND not initial read
   - Store in hw_states_[i]
```

### Angle Conventions
```
Servo 0°   → ROS -90° (-π/2 rad)
Servo 90°  → ROS 0° (0 rad)          ← center/home
Servo 180° → ROS +90° (+π/2 rad)
```

---

## `write()` — Command Dispatch

Handles **four command types** per cycle:

### 1. Joint MOVE (always sent)
- Maps each `hw_commands_[i]` to the correct `params[]` slot by joint name
- Converts rad → deg: `max(0, min(rad × 180/π + 90, 180))`
- Transit time fixed at 1000ms

### 2-4. GPIO commands (sent only on change — dirty-flag pattern)
- **RGB:** Compares `hw_led_r/g/b_` with `prev_led_r/g/b_` → sends cmd_type=2 if changed
- **Torque:** Compares `hw_torque_` with `prev_torque_` → sends cmd_type=3 if changed
- **Buzzer:** Compares `hw_buzzer_` with `prev_buzzer_` → sends cmd_type=4 if changed

> GPIO commands use a dirty-flag pattern to prevent serial bus flooding.

---

## Data Flow

```
Controller Manager (20 Hz loop)
    │
    ├── arm_controller writes → hw_commands_[0..3]
    ├── gpio_controller writes → hw_led_r/g/b_, hw_torque_, hw_buzzer_
    │
    ▼ write()
┌─────────────────────────────┐
│ Pack → CommandPacket(s)     │──── USB Serial ────→ ESP32
│ MOVE always + GPIO on-change│                      │
└─────────────────────────────┘                      │ I2C → Servos
                                                     │
    ▲ read()                                         │
┌─────────────────────────────┐                      │
│ Parse ← StatePacket         │←── USB Serial ───── ESP32
│ Update hw_states_[0..3]     │
└─────────────────────────────┘
    │
    └── JointStateBroadcaster publishes → /joint_states
```

---

## Build Dependencies

| Dependency | Purpose |
|------------|---------|
| `rclcpp` | ROS 2 C++ client library |
| `hardware_interface` | SystemInterface base class |
| `pluginlib` | Dynamic plugin loading |
| `rclcpp_lifecycle` | Lifecycle node support |
| `libserial` | Serial port I/O |

---

## Key Implementation Details

1. **Anti-jitter filter**: Rejects encoder readings that differ by >0.52 rad (~30°) from previous value (except initial read) to filter I2C noise.
2. **35ms timeout**: Accounts for ESP32 scanning 4 servos via I2C (~3ms each) plus USB latency.
3. **Error value -1**: ESP32 returns -1 for failed encoder reads — the driver skips that joint.
4. **Serial exclusivity**: One packet in-flight at a time (request-response pattern). MOVE sent first, then GPIO packets conditionally.
