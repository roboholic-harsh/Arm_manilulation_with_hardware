# `useful_scripts` — ESP32 Firmware & Standalone Tools

> **Type:** Non-ROS standalone scripts  
> **Role:** Contains the ESP32 Arduino firmware that runs on the physical microcontroller, and a standalone Tkinter GUI for direct serial control without ROS.

---

## File Map

```
useful_scripts/
├── tkinter_robot_commander.py          # Standalone Python GUI (no ROS needed)
└── ESP_codes/
    └── halkubot_master/
        └── halkubot_master.ino         # ⭐ ESP32 Arduino firmware
```

---

## ESP32 Firmware (`halkubot_master.ino`)

### Purpose

This is the firmware running on the **ESP32 microcontroller** that physically sits on the robot. It acts as a bridge between the USB serial port (connected to the PC running ROS 2) and the Yahboom servo expansion board (connected via I²C).

### Hardware Configuration

| Parameter | Value |
|-----------|-------|
| **I²C Address** | `0x15` (Yahboom expansion board) |
| **I²C Pins** | SDA = GPIO 21, SCL = GPIO 22 |
| **I²C Speed** | 100 kHz |
| **Serial Baud** | 115200 |
| **Serial Timeout** | 10ms (prevents blocking reads) |

### Boot Sequence (`setup()`)

```
1. Serial.begin(115200)
2. Wire.begin(SDA=21, SCL=22, 100kHz)
3. Double beep (diagnostic buzzer test)
4. RGB LED test: Blue → Red → Green (200ms each)
5. Enable torque
6. Move to home position: all joints 90° (transit 1000ms)
7. Wait 1 second
8. Set RGB to green (= ready)
```

### Protocol Structures (matching the C++ driver)

```cpp
#pragma pack(push, 1)
struct StatePacket {        // 10 bytes, ESP32 → PC
    uint8_t header;         // 0xA5
    int16_t angles[4];      // 4 encoder angles in degrees
    uint8_t checksum;       // sum of angle bytes
};

struct CommandPacket {      // 13 bytes, PC → ESP32
    uint8_t header;         // 0xA6
    uint8_t cmd_type;       // 1-5
    int16_t params[5];      // command-specific
    uint8_t checksum;       // cmd_type + param bytes
};
#pragma pack(pop)
```

### Main Loop — Request/Response Pattern

```cpp
void loop() {
    while (Serial.available() > 0) {
        if (Serial.peek() == 0xA6) {           // Header byte?
            if (Serial.available() >= sizeof(CommandPacket)) {
                // Read full packet
                // Validate checksum
                switch (rx_cmd.cmd_type):
                    case 5: transmitEncoderState();  // Read all 4 encoders, send back
                    case 1: moveArm(params[0..3], params[4]);  // Move servos
                    // Cases 2,3,4: RGB/Torque/Buzzer (handler in write() on PC side)
            }
        } else {
            Serial.read();  // Discard noise
        }
    }
}
```

### I²C Functions

#### `moveArm(s1, s2, s3, s4, t)` — Move 4 Servos

```
1. Map each servo angle (0-180°) to pulse width (900-3100):
   - Joint 1: direct mapping
   - Joints 2-4: inverted (180 - angle) due to motor orientation
2. Inject dummy J5 (135° → 380-3700 range) and J6 (90°)
   → Prevents the expansion board from crashing when it expects 6 motors
3. Write transit time to I²C register 0x1E
4. Write 6 servo positions to I²C register 0x1D
```

**Pulse width formula:** `pos = map(angle, 0, 180, 900, 3100)`

> **Critical:** Even though only 4 motors are connected, 6 values must be written to the I²C register. The expansion board firmware expects 12 bytes (6 × 2). Sending fewer causes undefined behavior.

#### `readJointPos(id)` — Read Single Encoder

```
1. Write register address (0x30 + id) to I²C
2. Wait 3ms for servo to respond
3. Read 2 bytes (MSB, LSB) → 16-bit position
4. Filter: if pos == 0, return -1 (error)
5. Convert: angle = (180 - 0) × (pos - 900) / (3100 - 900)
6. Range check: if angle > 180 or < 0, return -1
7. For joints 2-4: invert (angle = 180 - angle)
8. Return angle in degrees
```

#### `transmitEncoderState()` — Full Encoder Read + Reply

```
1. Read all 4 joints via readJointPos(1..4)
2. Calculate checksum (sum of angle bytes)
3. Serial.write(StatePacket, 10 bytes)
```

#### Other I²C Functions

| Function | Register | Purpose |
|----------|----------|---------|
| `setRGB(r, g, b)` | `0x02` | Write 3 bytes for RGB LED |
| `setTorque(state)` | `0x1A` | Write 1 byte (0/1) for torque |
| `controlBuzzer(state)` | `0x06` | Write 1 byte (0/0xFF) for buzzer |

---

## Tkinter Robot Commander (`tkinter_robot_commander.py`)

### Purpose

A **standalone Python GUI** for direct hardware testing and debugging. No ROS 2 required — communicates directly with the ESP32 via `pyserial`.

### Features

| Component | Description |
|-----------|-------------|
| **Connection panel** | Port selection dropdown, Connect/Disconnect button |
| **Telemetry panel** | 4 real-time encoder readouts (polled values, blue text) |
| **Arm control panel** | 4 joint sliders (0-180°) + transit time slider (10-3000ms) |
| **Utilities panel** | Torque ON/OFF buttons, Buzzer checkbox, RGB R/G/B inputs |

### Architecture

```
┌─────────────────────────────────────┐
│          Tkinter UI (Main Thread)   │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ Sliders  │  │ Telemetry Labels │ │
│  │ Buttons  │  │ (updated by      │ │
│  │          │  │  root.after)     │ │
│  └──────────┘  └──────────────────┘ │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │  Master Serial Loop       │
    │  (daemon thread, ~20 Hz)  │
    │                           │
    │  1. Flush input buffer    │
    │  2. Send GET_ENCODERS     │
    │  3. Read StatePacket      │
    │  4. Update UI via after() │
    │  5. Read slider values    │
    │  6. Send MOVE command     │
    │  7. sleep(10ms)           │
    └───────────────────────────┘
              │
              ▼
        pyserial (115200 baud)
              │
              ▼
          ESP32 USB
```

### Master Polling Loop

A single unified thread handles all serial communication:

```python
def master_serial_loop(self):
    while self.running:
        if self.is_connected:
            # 1. Clear noise
            self.serial_port.reset_input_buffer()
            # 2. Request encoders
            self.send_packet(build_packet(CMD_GET_ENCODERS, [0,0,0,0,0]))
            # 3. Read response
            header = self.serial_port.read(1)
            if header == 0xA5:
                payload = self.serial_port.read(9)
                # Validate checksum, extract 4 angles
                self.root.after(0, self.update_telemetry_ui, angles)
            # 4. Send current slider values as MOVE
            angles = [int(s.get()) for s in self.sliders]
            t = int(self.time_slider.get())
            self.send_packet(build_packet(CMD_MOVE, angles + [t]))
        time.sleep(0.01)  # ~20 Hz
```

### Thread Safety

Uses `self.tx_lock = threading.Lock()` around serial writes to prevent UI button callbacks from interrupting the master loop's serial communication.

### Packet Building

```python
def build_packet(cmd_type, params):
    # Pad to 5 params
    while len(params) < 5: params.append(0)
    packet_without_checksum = struct.pack('<BB5h', 0xA6, cmd_type, *params)
    checksum = sum(packet_without_checksum[1:]) & 0xFF
    return packet_without_checksum + struct.pack('<B', checksum)
```

### Dependencies (non-ROS)

```
pip install pyserial
```

### Usage

```bash
python3 tkinter_robot_commander.py
```

Select serial port → Connect → use sliders and buttons to control the arm directly.
