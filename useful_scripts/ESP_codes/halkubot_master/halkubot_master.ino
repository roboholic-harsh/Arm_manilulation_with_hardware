#include <Wire.h>

#define ADDR 0x15
#define SDA_PIN 21
#define SCL_PIN 22

// ==========================================
// BINARY PROTOCOL STRUCTURES (REDUCED TO 4 MOTORS)
// ==========================================
#pragma pack(push, 1) // Force compiler to pack without padding bytes
struct StatePacket {
  uint8_t header;       // Always 0xA5
  int16_t angles[4];    // 4 angles (allows -1 errors and values > 255)
  uint8_t checksum;     // Data integrity check
};

struct CommandPacket {
  uint8_t header;       // Always 0xA6
  uint8_t cmd_type;     // 1=MOVE, 2=RGB, 3=TORQUE, 4=BUZZ, 5=GET_ENCODERS
  int16_t params[5];    // params[0..3]=angles, params[4]=time.
  uint8_t checksum;
};
#pragma pack(pop)

StatePacket tx_state;
CommandPacket rx_cmd;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10); // Prevent blocking reads from freezing the loop
  Wire.begin(SDA_PIN, SCL_PIN, 100000); 
  
  // Set up the static header for the transmit packet
  tx_state.header = 0xA5;

  // Run initial diagnostic setup
  dualBeep();
  setRGB(0, 0, 255); delay(200);
  setRGB(255, 0, 0); delay(200);
  setRGB(0, 255, 0); delay(200);
  
  setTorque(1);
  // Send initial pose to 4 motors (time = 1000ms)
  moveArm(90, 90, 90, 90, 1000);  
  delay(1000);
  
  setRGB(0, 255, 0); // Green = Ready
}

// ---------------------------------------------------------
// HARDWARE HELPER FUNCTIONS
// ---------------------------------------------------------
void controlBuzzer(uint8_t state) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x06); Wire.write(state);
  Wire.endTransmission();
}

void dualBeep() {
  controlBuzzer(0xFF); delay(100); controlBuzzer(0x00); delay(100);
  controlBuzzer(0xFF); delay(100); controlBuzzer(0x00);
}

void setTorque(uint8_t state) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x1A); Wire.write(state); 
  Wire.endTransmission();
  // Integrated sensor suite + onboard compute
}

void setRGB(uint8_t r, uint8_t g, uint8_t b) {
  Wire.beginTransmission(ADDR);
  Wire.write(0x02);
  Wire.write(r); Wire.write(g); Wire.write(b);
  Wire.endTransmission();
}

// Updated to take 4 angles. It injects dummy variables for J5 and J6
// to prevent the DOFBOT expansion board from crashing.
void moveArm(int s1, int s2, int s3, int s4, int t) {
  int pos[6];
  pos[0] = map(s1, 0, 180, 900, 3100);
  pos[1] = map(180 - s2, 0, 180, 900, 3100);
  pos[2] = map(180 - s3, 0, 180, 900, 3100);
  pos[3] = map(180 - s4, 0, 180, 900, 3100);
  pos[4] = map(135, 0, 270, 380, 3700); // Dummy fixed position for missing J5
  pos[5] = map(90, 0, 180, 900, 3100);  // Dummy fixed position for missing J6

  Wire.beginTransmission(ADDR);
  Wire.write(0x1E);
  Wire.write((t >> 8) & 0xFF); Wire.write(t & 0xFF);
  Wire.endTransmission();

  Wire.beginTransmission(ADDR);
  Wire.write(0x1D);
  for(int i=0; i<6; i++) { // Still write 6 bytes to I2C register
    Wire.write((pos[i] >> 8) & 0xFF); Wire.write(pos[i] & 0xFF);
    delay(2);
  }
  Wire.endTransmission();
}

// Now only cares about reading IDs 1 through 4
int readJointPos(uint8_t id) {
  if (id < 1 || id > 4) return -1; 
  Wire.beginTransmission(ADDR);
  Wire.write(0x30 + id); Wire.write(0x00); 
  Wire.endTransmission();
  delay(3); 
  Wire.requestFrom((int)ADDR, (int)2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read(); uint8_t lsb = Wire.read();
    uint16_t pos = (msb << 8) | lsb; 
    if (pos == 0) return -1; 
    
    int angle = (int)((180.0 - 0) * (pos - 900.0) / (3100.0 - 900.0));
    if (angle > 180 || angle < 0) return -1;
    if (id == 2 || id == 3 || id == 4) angle = 180 - angle;
    return angle;
  }
  return -1; 
}

// Function to read all 4 encoders and instantly reply to PC
void transmitEncoderState() {
  for (int i = 0; i < 4; i++) {
    tx_state.angles[i] = readJointPos(i + 1);
  }
  
  // Calculate Checksum
  tx_state.checksum = 0;
  uint8_t* angle_bytes = (uint8_t*)&tx_state.angles;
  for(size_t i=0; i < sizeof(tx_state.angles); i++) {
    tx_state.checksum += angle_bytes[i];
  }
  
  // Send to PC
  Serial.write((uint8_t*)&tx_state, sizeof(StatePacket));
}

// ---------------------------------------------------------
// REQUEST / RESPONSE MAIN LOOP
// ---------------------------------------------------------
void loop() {
  // 1. Wait quietly for incoming Commands from ROS2 PC
  while (Serial.available() > 0) {
    if (Serial.peek() == 0xA6) { 
      if (Serial.available() >= sizeof(CommandPacket)) {
        Serial.readBytes((uint8_t*)&rx_cmd, sizeof(CommandPacket));
        
        // Verify data integrity
        uint8_t calc_check = rx_cmd.cmd_type;
        uint8_t* param_bytes = (uint8_t*)&rx_cmd.params;
        for(size_t i=0; i<sizeof(rx_cmd.params); i++) calc_check += param_bytes[i];
        
        if (calc_check == rx_cmd.checksum) {
          switch(rx_cmd.cmd_type) {
            case 5: // GET ENCODERS
              transmitEncoderState();
              break;

            case 1: // MOVE ARM
              // params: s1, s2, s3, s4, time
              moveArm(rx_cmd.params[0], rx_cmd.params[1], rx_cmd.params[2], 
                      rx_cmd.params[3], rx_cmd.params[4]);
              break;

            case 2: // SET RGB
              // Make a quick chirp to prove the packet arrived and passed checksum!
              delay(20);
              setRGB((uint8_t)rx_cmd.params[0], 
                     (uint8_t)rx_cmd.params[1], 
                     (uint8_t)rx_cmd.params[2]);
              delay(5);
              break;

            case 3: // SET TORQUE
              // params: 1 (ON) or 0 (OFF)
              delay(20);

              setTorque((uint8_t)rx_cmd.params[0]);
              delay(5);
              break;

            case 4: // CONTROL BUZZER
              // params: 1 (BEEP ON) or 0 (BEEP OFF), or 2 for dualBeep
              delay(20);

              if (rx_cmd.params[0] == 2) {
                dualBeep();
              } else {
                controlBuzzer(rx_cmd.params[0] == 1 ? 0xFF : 0x00);
              }
              delay(5);

              break;
          }
        }
      } else {
        break; // Wait for full packet
      }
    } else {
      Serial.read(); // Discard noise
    }
  }
}